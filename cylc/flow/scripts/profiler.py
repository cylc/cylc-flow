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
import asyncio

from pathlib import Path
from functools import partial
from dataclasses import dataclass

from cylc.flow.network.client_factory import get_client
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.terminal import cli_function


PID_REGEX = re.compile(r"([^:]*\d{6,}.*)")
RE_INT = re.compile(r'\d+')


@dataclass
class Process:
    """Class for representing CPU and Memory usage of a process"""
    cgroup_memory_path: str
    cgroup_cpu_path: str
    memory_allocated_path: str
    cgroup_version: int


def stop_profiler(process, comms_timeout, *args):
    """This function will be executed when the SIGINT signal is sent
     to this process"""

    max_rss, cpu_time, memory_allocated = get_resource_usage(process)

    graphql_mutation = """
    mutation($WORKFLOWS: [WorkflowID]!,
        $MESSAGES: [[String]], $JOB: String!, $TIME: String) {
            message(workflows: $WORKFLOWS, messages:$MESSAGES,
            taskJob:$JOB, eventTime:$TIME) {
        result
      }
    }
    """

    graphql_request_variables = {
        "WORKFLOWS": [os.environ.get('CYLC_WORKFLOW_ID')],
        "MESSAGES": [[
            "DEBUG",
            f"cpu_time {cpu_time} "
            f"max_rss {max_rss} "
            f"mem_alloc {memory_allocated}"]],
        "JOB": os.environ.get('CYLC_TASK_JOB'),
        "TIME": "now"
    }

    pclient = get_client(os.environ.get('CYLC_WORKFLOW_ID'),
                         timeout=comms_timeout)

    async def send_cylc_message():
        await pclient.async_request(
            'graphql',
            {'request_string': graphql_mutation,
             'variables': graphql_request_variables},
        )

    asyncio.run(send_cylc_message())
    sys.exit(0)


def get_resource_usage(process):
    # If a task fails instantly, or finishes very quickly (< 1 second),
    # the get config function doesn't have time to run
    if (process.cgroup_memory_path is None
            or process.cgroup_cpu_path is None
            or process.memory_allocated_path is None):
        return 0, 0, 0
    max_rss = parse_memory_file(process)
    cpu_time = parse_cpu_file(process)
    memory_allocated = parse_memory_allocated(process)
    return max_rss, cpu_time, memory_allocated


def parse_memory_file(process: Process):
    """Open the memory stat file and copy the appropriate data"""

    if process.cgroup_version == 2:
        with open(process.cgroup_memory_path, 'r') as f:
            for line in f:
                if "anon" in line:
                    return int(''.join(filter(str.isdigit, line)))
    else:
        with open(process.cgroup_memory_path, 'r') as f:
            for line in f:
                if "total_rss" in line:
                    return int(''.join(filter(str.isdigit, line)))


def parse_memory_allocated(process: Process) -> int:
    """Open the memory stat file and copy the appropriate data"""
    if process.cgroup_version == 2:
        cgroup_memory_path = Path(process.memory_allocated_path)

        for i in range(5):
            with open(cgroup_memory_path / "memory.max", 'r') as f:
                line = f.readline()
                if "max" not in line:
                    return int(line)
            cgroup_memory_path = cgroup_memory_path.parent
            if i == 5:
                break
    elif process.cgroup_version == 1:
        return 0  # Memory limit not tracked for cgroups v1

    raise FileNotFoundError("Could not find memory.max file")


def parse_cpu_file(process: Process) -> int:
    """Open the CPU stat file and return the appropriate data"""
    if process.cgroup_version == 2:
        with open(process.cgroup_cpu_path, 'r') as f:
            for line in f:
                if "usage_usec" in line:
                    return int(RE_INT.findall(line)[0]) // 1000
            raise ValueError("Unable to find cpu usage data")
    else:
        with open(process.cgroup_cpu_path, 'r') as f:
            for line in f:
                # Cgroups v1 uses nanoseconds
                return int(line) // 1000000
        raise ValueError("Unable to find cpu usage data")


def get_cgroup_version(cgroup_location: str, cgroup_name: str) -> int:
    if Path.exists(Path(cgroup_location + cgroup_name)):
        return 2
    elif Path.exists(Path(cgroup_location + "/memory" + cgroup_name)):
        return 1
    else:
        raise FileNotFoundError("Cgroup not found at " +
                                cgroup_location + cgroup_name)


def get_cgroup_name():
    """Get the cgroup directory for the current process"""

    # fugly hack to allow functional tests to use test data
    if 'profiler_test_env_var' in os.environ:
        return os.getenv('profiler_test_env_var')

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


def get_cgroup_paths(location) -> Process:
    cgroup_name = get_cgroup_name()
    cgroup_version = get_cgroup_version(location, cgroup_name)
    if cgroup_version == 2:
        return Process(
            cgroup_memory_path=location +
            cgroup_name + "/" + "memory.stat",
            cgroup_cpu_path=location +
            cgroup_name + "/" + "cpu.stat",
            memory_allocated_path=location + cgroup_name,
            cgroup_version=cgroup_version,
        )

    elif cgroup_version == 1:
        return Process(
            cgroup_memory_path=location + "memory/" +
            cgroup_name + "/memory.stat",
            cgroup_cpu_path=location + "cpu/" +
            cgroup_name + "/cpuacct.usage",
            memory_allocated_path="",
            cgroup_version=cgroup_version,
        )

    raise ValueError("Unable to determine cgroup version")


def profile(_process: Process, delay, keep_looping=lambda: True):
    # The infinite loop that will constantly poll the cgroup
    # The lambda function is used to allow the loop to be stopped in unit tests

    while keep_looping():
        # Write cpu / memory usage data to disk
        # CPU_TIME = parse_cpu_file(process.cgroup_cpu_path, version)
        time.sleep(delay)


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        comms=True,
        argdoc=[
        ],
    )
    parser.add_option(
        "-i", type=int,
        help="interval between query cycles in seconds", dest="delay")
    parser.add_option(
        "-m", type=str, help="Location of cgroups directory",
        dest="cgroup_location")

    return parser


@cli_function(get_option_parser)
def main(_parser: COP, options) -> None:
    """CLI main."""
    _main(options)


def _main(options) -> None:
    # get cgroup information
    process = get_cgroup_paths(options.cgroup_location)

    # Register the stop_profiler function with the signal library
    _stop_profiler = partial(stop_profiler, process, options.comms_timeout)
    signal.signal(signal.SIGINT, _stop_profiler)
    signal.signal(signal.SIGHUP, _stop_profiler)
    signal.signal(signal.SIGTERM, _stop_profiler)

    # run profiler run
    profile(process, options.delay)


if __name__ == "__main__":
    arg_parser = get_option_parser()
    _main(arg_parser.parse_args([]))
