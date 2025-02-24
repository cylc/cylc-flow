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
        "-o", type=str, help="output directory for json file",
        default=os.environ['DATADIR'], dest="output_dir")
    parser.add_option(
        "-m", type=str, help="Location of memory process files",
        default="/sys/fs/cgroup",
        dest="memory")

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
    job_id: str


def stop_profiler(*args):
    """This function will be executed when the SIGINT signal is sent
     to this process"""
    print('profiler exited')
    sys.exit(0)


def parse_memory_file(process):
    """Open the memory stat file and copy the appropriate data"""
    memory_stats = {}

    for line in open(process.cgroup_memory_path):
        return int(line)


def parse_cpu_file(process):
    """Open the memory stat file and copy the appropriate data"""
    memory_stats = {}

    for line in open(process.cgroup_cpu_path):
        if "usage_usec" in line:
            return int(re.findall(r'\d+', line)[0])


def write_data(process, data, output_dir, data_type, filename):

    # Build the output file path
    path = os.path.join(output_dir, process.job_id + data_type)
    try:
        with open(filename, 'w') as f:
            f.write(data + "\n")
    except IOError:
        raise IOError("Unable to write memory data to file")


def get_cgroup_dir():
    """Get the cgroup directory for the current process"""
    # Get the PID of the current process
    pid = os.getpid()
    # Get the cgroup information for the current process
    result = subprocess.run(['cat', '/proc/' + str(pid) + '/cgroup'], capture_output=True, text=True)
    result = PID_REGEX.search(result.stdout).group()
    return result


def profile(args):

    cgroup_name = get_cgroup_dir()

    # AZURE SPICE CGROUP LOCATION
    cgroup_location = "/sys/fs/cgroup/" + cgroup_name
    peak_memory = 0
    processes = []
    # last_system_usage = None
    # last_cpu_usage = None
    # Find the correct memory_stat file for the process
    if not Path.exists(Path(cgroup_location)):
        raise FileNotFoundError("cgroups not found:" + cgroup_location)
    try:
        # Find memory.stat files
        for job_id in os.listdir(cgroup_location):
            if "memory.peak" in job_id:
                processes.append(Process(
                    cgroup_memory_path=cgroup_location + "/" + job_id,
                    cgroup_cpu_path=cgroup_location + "/" + "cpu.stat",
                    job_id=job_id))
    except FileNotFoundError as e:
        print(e)
        raise FileNotFoundError("cgroups not found:" + cgroup_location)

    # cpu_count = get_host_num_cpus(args.cpuset_path, processes)
    while True:
        # Write memory usage data
        for process in processes:
            # Only save Max RSS to disk if it is above the previous value
            try:
                memory = parse_memory_file(process)
                if memory > peak_memory:
                    peak_memory = memory
                    write_data(process, str(peak_memory), args.output_dir, ".memory", "max_rss")
                cpu_time = parse_cpu_file(process)
                write_data(process, str(cpu_time), args.output_dir, ".cpu", "cpu_time")

            except (OSError, IOError, ValueError) as error:
                print(error)

            # process, usage_percent = get_cpu_percent(
            #     cpu_count, args.proc_path,
            #     process, last_system_usage, last_cpu_usage)
            #
            # write_data(process, usage_percent,
            #            args.output_dir, ".cpu")

            time.sleep(args.delay)


if __name__ == "__main__":

    arg_parser = get_option_parser()
    profile(arg_parser.parse_args())
