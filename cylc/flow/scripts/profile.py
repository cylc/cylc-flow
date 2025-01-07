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
import sys
import time
import signal
from pathlib import Path
from dataclasses import dataclass
from argparse import ArgumentParser
from cylc.flow.terminal import cli_function
from cylc.flow.option_parsers import CylcOptionParser as COP

INTERNAL = True

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
        default="/sys/fs/cgroup/memory/pbspro.service/jobid", dest="memory")

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
    # cgroup_cpu_path: str
    job_id: str
    # system_usage: int
    # cpu_usage: int


def stop_profiler(*args):
    """This function will be executed when the SIGINT signal is sent
     to this process"""
    print('profiler exited')
    sys.exit(0)


def parse_memory_file(process):
    """Open the memory stat file and copy the appropriate data"""
    path = os.path.join(process.cgroup_memory_path + "/" +
                        process.job_id, "memory.stat")

    for line in open(path):
        key, value = line.strip().split()
        # Grab the data we want
        if key == 'rss':
            return value


def write_data(process, data, output_dir, data_type):

    # Build the output file path
    path = os.path.join(output_dir, process.job_id + data_type)
    try:
        with open("/home/h01/cbennett/repos/cylc_ui_gantt/cylc-flow/max_rss", 'w') as f:
            f.write(data)
    except IOError:
        raise IOError("Unable to write memory data to file")


# def get_host_num_cpus(cpuset_path, processes):
#     """Number of physical CPUs available to the process"""
#     cpuset = open(cpuset_path + '/' +
#                        processes[0].job_id + '/cpuset.cpus').read()
#     print("raw_data:", cpuset)
#     cpu_number = cpuset.split('-')
#     print('split:', cpu_number)
#     number_of_cpus = ((int(cpu_number[1]) - int(cpu_number[0])) + 1) // 2
    # split_proc_stat_lines = [cpuset.split(') for line in proc_stat_lines]
    # cpu_lines = [
    #     split_line
    #     for split_line in split_proc_stat_lines
    #     if len(split_line) > 0 and "cpu" in split_line[0]
    # ]
    # # Number of lines starting with a word including 'cpu', subtracting
    # # 1 for the first summary line.
    # host_num_cpus = len(cpu_lines) - 1
    # print(number_of_cpus)
    # return number_of_cpus


# def get_system_usage():
#     """
#     Computes total CPU usage of the host in nanoseconds.
#     See also the / proc / stat entry here:
#     https://man7.org/linux/man-pages/man5/proc.5.html
#     """
#     # Grab usage data from proc/stat
#     usage_data = open('/proc/stat').read().split("\n")[0].split()[1:8]
#
#     total_clock_ticks = sum(int(entry) for entry in usage_data)
#     # 100 clock ticks per second, 10^9 ns per second
#     usage_ns = total_clock_ticks * 10 ** 7
#     return usage_ns
#
#
# def get_cpu_percent(num_of_cpus, proc_path, process,
#                     last_system_usage, last_cpu_usage):
#
#     time.sleep(5)
#     # Find cpuacct.usage files
#     cpu_usage = int(open(process.cgroup_cpu_path + "/" +
#                          process.job_id + "/cpuacct.usage").read())
#     system_usage = get_system_usage()
#
#     # Since deltas are not initially available, return 0.0 on first call.
#     if last_system_usage is None:
#         cpu_percent = 0.0
#     else:
#         cpu_delta = cpu_usage - last_cpu_usage
#         # "System time passed." (Typically close to clock time.)
#         system_delta = (system_usage - last_system_usage) / num_of_cpus
#
#         quotient = cpu_delta / system_delta
#         cpu_percent = round(quotient * 100 / 8, 1)
#     process.system_usage = system_usage
#     process.cpu_usage = cpu_usage
#     # Computed percentage might be slightly above 100%.
#     return process, min(cpu_percent, 100.0)


def profile(args):

    # print("cylc_profile:", os.environ['CYLC_PROFILE'])
    max_rss = 0
    processes = []
    # last_system_usage = None
    # last_cpu_usage = None

    # Find the correct memory_stat file for the process
    if not Path.exists(Path(args.memory)):
        FileNotFoundError("cgroups not found")

    try:
        # Find memory.stat files
        for job_id in os.listdir(args.memory):
            if "ex" in job_id:
                print("found process:", job_id)
                processes.append(Process(
                    cgroup_memory_path=args.memory,
                    # cgroup_cpu_path=args.cpu,
                    # system_usage=0,
                    # cpu_usage=0,
                    job_id=job_id))
    except FileNotFoundError as e:
        print(e)
        exit("Is this being ran on Azure HPC?")

    # cpu_count = get_host_num_cpus(args.cpuset_path, processes)
    for i in range(30):
        # Write memory usage data
        for process in processes:
            # Only save Max RSS to disk if it is above the previous value
            try:
                rss = int(parse_memory_file(process))
                if rss > max_rss:
                    max_rss = rss
                    write_data(process, rss,
                               args.output_dir, ".memory")

            except (OSError, IOError) as error:
                print(error)

            # process, usage_percent = get_cpu_percent(
            #     cpu_count, args.proc_path,
            #     process, last_system_usage, last_cpu_usage)
            #
            # write_data(process, usage_percent,
            #            args.output_dir, ".cpu")

            time.sleep(args.delay)


def parse_arguments():

    p = ArgumentParser(
        usage="%(prog)s [options]",
        description="Profiler which periodically polls PBS cgroups to track "
                    "the resource usage of jobs running on the node.")

    p.add_argument("-i", dest="delay", type=int, metavar="S",
                   default=10, help="interval between query cycles in seconds")
    p.add_argument("-o", dest="output_dir", type=str,
                   default=os.environ['DATADIR'],
                   help="output directory for json file")
    p.add_argument("-m", dest="memory", type=str,
                   default="/sys/fs/cgroup/memory/pbspro.service/jobid",
                   # default="/sys/fs/cgroup",
                   help="Location of memory process files")
    # p.add_argument("-c", dest="cpu", type=str,
    #                default="/sys/fs/cgroup/cpu,cpuacct/pbspro.service/jobid",
    #                # default="/sys/fs/cgroup",
    #                help="Location of cpu cgroup files")
    # p.add_argument("-u", dest="cpuset_path", type=str,
    #                default="/sys/fs/cgroup/cpuset/pbspro.service/jobid",
    #                help="Location of processor details")
    # p.add_argument("-p", dest="proc_path", type=str,
    #                default="/sys/fs/cgroup/cpuset/pbspro.service/jobid",
    #                help="Location of processor details")

    args = p.parse_args()

    return args
