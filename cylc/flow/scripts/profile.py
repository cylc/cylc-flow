#!/usr/bin/env python3
# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""cylc profiler [OPTIONS]

Profiler which periodically polls PBS cgroups to track
the resource usage of jobs running on the node.
"""

import os
import re
import sys
import time
import signal
import subprocess
from pathlib import Path
from dataclasses import dataclass
from cylc.flow.terminal import cli_function
from cylc.flow.option_parsers import CylcOptionParser as COP

INTERNAL = True
PID_REGEX = re.compile(r"([^:]*\d{6,}.*)")


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        argdoc=[
        ],
    )
    parser.add_option(
        "-i", type=int, help="interval between query cycles in seconds",
        default=10, dest="delay")
    parser.add_option(
        "-m", type=str, help="Location of cgroups directory",
        default="/sys/fs/cgroup",
        dest="cgroup_location")

    return parser


@cli_function(get_option_parser)
def main(parser, options):
    """CLI main."""
    # Register the stop_profiler function with the signal library
    signal.signal(signal.SIGINT, stop_profiler)

    profile(options)


@dataclass
class Process:
    """Class for representing CPU and Memory usage of a process"""
    cgroup_memory_path: str
    cgroup_cpu_path: str


def stop_profiler(*args):
    """This function will be executed when the SIGINT signal is sent
     to this process"""
    print('profiler exited')
    sys.exit(0)


def parse_memory_file(process):
    """Open the memory stat file and copy the appropriate data"""
    memory_stats = {}

    for line in open(process.cgroup_memory_path):
        return int(line) // 1024


def parse_cpu_file(process, cgroup_version):
    """Open the memory stat file and return the appropriate data"""
    memory_stats = {}

    if cgroup_version == 1:
        for line in open(process.cgroup_cpu_path):
            if "usage_usec" in line:
                return int(re.findall(r'\d+', line)[0]) / 1000
    elif cgroup_version == 2:
        for line in open(process.cgroup_cpu_path):
            # Cgroups v2 uses nanoseconds
            return int(line) / 1000000
    else:
        raise FileNotFoundError("cpu usage files not found")


def write_data(data, filename):
    try:
        with open(filename, 'w') as f:
            f.write(data + "\n")
    except IOError:
        raise IOError("Unable to write data to file:" + filename)


def get_cgroup_dir():
    """Get the cgroup directory for the current process"""
    # Get the PID of the current process
    pid = os.getpid()
    # Get the cgroup information for the current process
    result = subprocess.run(['cat', '/proc/' + str(pid) + '/cgroup'], capture_output=True, text=True)
    result = PID_REGEX.search(result.stdout).group()
    return result


def profile(args):
    # Find the cgroup that this process is running in.
    # Cylc will put this profiler in the same cgroup as the job it is profiling
    cgroup_name = get_cgroup_dir()

    # HPC uses cgroups v2 and SPICE uses cgroups v1
    cgroup_version = None

    if Path.exists(Path(args.cgroup_location + cgroup_name)):
        cgroup_version = 1
    elif Path.exists(Path(args.cgroup_location + "/memory" + cgroup_name)):
        cgroup_version = 2
    else:
        raise FileNotFoundError("cgroups not found:" + cgroup_name)

    peak_memory = 0
    processes = []

    if cgroup_version == 1:
        try:
            processes.append(Process(
                cgroup_memory_path=args.cgroup_location + cgroup_name + "/" + "memory.peak",
                cgroup_cpu_path=args.cgroup_location + cgroup_name + "/" + "cpu.stat"))
        except FileNotFoundError as e:
            print(e)
            raise FileNotFoundError("cgroups not found:" + args.cgroup_location)

    elif cgroup_version == 2:
        try:
            processes.append(Process(
                cgroup_memory_path=args.cgroup_location + "/memory" + cgroup_name + "/memory.max_usage_in_bytes",
                cgroup_cpu_path=args.cgroup_location + "/cpu" + cgroup_name + "/cpuacct.usage"))
        except FileNotFoundError as e:
            print(e)
            raise FileNotFoundError("cgroups not found:" + args.cgroup_location)

    while True:
        # Write memory usage data
        for process in processes:
            # Only save Max RSS to disk if it is above the previous value
            try:
                memory = parse_memory_file(process)
                if memory > peak_memory:
                    peak_memory = memory
                    write_data(str(peak_memory), "max_rss")
                cpu_time = parse_cpu_file(process, cgroup_version)
                write_data(str(cpu_time), "cpu_time")

            except (OSError, IOError, ValueError) as error:
                print(error)

            time.sleep(args.delay)


if __name__ == "__main__":

    arg_parser = get_option_parser()
    profile(arg_parser.parse_args())
