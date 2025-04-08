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

Profiler which periodically polls cgroups to track
the resource usage of jobs running on the node.
"""

import os
import re
import sys
import time
import signal
from pathlib import Path
from dataclasses import dataclass
from cylc.flow.terminal import cli_function
from cylc.flow.option_parsers import CylcOptionParser as COP

INTERNAL = True
PID_REGEX = re.compile(r"([^:]*\d{6,}.*)")
RE_INT = re.compile(r'\d+')


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
        dest="cgroup_location")

    return parser


@cli_function(get_option_parser)
def main(parser: COP, options) -> None:
    """CLI main."""
    # Register the stop_profiler function with the signal library
    signal.signal(signal.SIGINT, stop_profiler)
    signal.signal(signal.SIGHUP, stop_profiler)
    signal.signal(signal.SIGTERM, stop_profiler)

    get_config(options)


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


def parse_memory_file(cgroup_memory_path):
    """Open the memory stat file and copy the appropriate data"""

    with open(cgroup_memory_path, 'r') as f:
        for line in f:
            return int(line) // 1024


def parse_cpu_file(cgroup_cpu_path, cgroup_version):
    """Open the memory stat file and return the appropriate data"""

    if cgroup_version == 1:
        with open(cgroup_cpu_path, 'r') as f:
            for line in f:
                if "usage_usec" in line:
                    return int(RE_INT.findall(line)[0]) // 1000
    elif cgroup_version == 2:
        with open(cgroup_cpu_path, 'r') as f:
            for line in f:
                # Cgroups v2 uses nanoseconds
                return int(line) / 1000000


def write_data(data, filename):
    with open(filename, 'w') as f:
        f.write(data + "\n")


def get_cgroup_version(cgroup_location: str, cgroup_name: str) -> int:
    # HPC uses cgroups v2 and SPICE uses cgroups v1
    if Path.exists(Path(cgroup_location + cgroup_name)):
        return 1
    elif Path.exists(Path(cgroup_location + "/memory" + cgroup_name)):
        return 2
    else:
        raise FileNotFoundError("Cgroup not found")


def get_cgroup_name():
    """Get the cgroup directory for the current process"""
    # Get the PID of the current process
    pid = os.getpid()
    try:
        # Get the cgroup information for the current process
        with open('/proc/' + str(pid) + '/cgroup', 'r') as f:
            result = f.read()
        result = PID_REGEX.search(result).group()
        return result
    except FileNotFoundError as err:
        raise FileNotFoundError(
            '/proc/' + str(pid) + '/cgroup not found') from err

    except AttributeError as err:
        raise AttributeError("No cgroup found for process:", pid) from err


def get_cgroup_paths(version, location, name):

    if version == 1:
        return Process(
            cgroup_memory_path=location +
            name + "/" + "memory.peak",
            cgroup_cpu_path=location +
            name + "/" + "cpu.stat")

    elif version == 2:
        return Process(
            cgroup_memory_path=location + "/memory" +
            name + "/memory.max_usage_in_bytes",
            cgroup_cpu_path=location + "/cpu" +
            name + "/cpuacct.usage")


def profile(process, version, delay, keep_looping=lambda: True):
    # The infinite loop that will constantly poll the cgroup
    # The lambda function is used to allow the loop to be stopped in unit tests
    peak_memory = 0
    while keep_looping():
        # Write cpu / memory usage data to disk
        cpu_time = parse_cpu_file(process.cgroup_cpu_path, version)
        write_data(str(cpu_time), "cpu_time")

        memory = parse_memory_file(process.cgroup_memory_path)
        # Only save Max RSS to disk if it is above the previous value
        if memory > peak_memory:
            peak_memory = memory
            write_data(str(peak_memory), "max_rss")

        time.sleep(delay)


def get_config(args):
    # Find the cgroup that this process is running in.
    # Cylc will put this profiler in the same cgroup
    # as the job it is profiling
    cgroup_name = get_cgroup_name()
    cgroup_version = get_cgroup_version(args.cgroup_location, cgroup_name)
    process = get_cgroup_paths(cgroup_version,
                               args.cgroup_location,
                               cgroup_name)

    profile(process, cgroup_version, args.delay)


if __name__ == "__main__":

    arg_parser = get_option_parser()
    get_config(arg_parser.parse_args([]))
