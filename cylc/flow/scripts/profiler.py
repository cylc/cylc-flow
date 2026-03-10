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

import asyncio
import json
import os
import re
import sys
import signal
import psutil

from pathlib import Path
from dataclasses import dataclass

from cylc.flow.exceptions import CylcProfilerError
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.remote import watch_and_kill
from cylc.flow.task_message import record_messages
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


def stop_profiler(process, comms_timeout, *_args):
    """Stop the profiler and return its data to the scheduler.

    This function will be executed when the profiler receives a stop signal.
    """
    profiler_data = get_profiler_data(process)

    record_messages(
        os.environ['CYLC_WORKFLOW_ID'],
        os.environ['CYLC_TASK_JOB'],
        [['DEBUG', f'_cylc_profiler: {json.dumps(profiler_data)}']],
        comms_timeout=comms_timeout,
    )
    sys.exit(0)


def get_profiler_data(process):
    if (
        process.cgroup_memory_path is None
        or process.cgroup_cpu_path is None
        or process.memory_allocated_path is None
    ):
        # If a task fails instantly, or finishes very quickly (< 1 second),
        # the get config function doesn't have time to run
        max_rss = cpu_time = memory_allocated = 0
    else:
        max_rss = parse_memory_file(process)
        cpu_time = parse_cpu_file(process)
        memory_allocated = parse_memory_allocated(process)
    return {
        'max_rss': max_rss,
        'cpu_time': cpu_time,
        'memory_allocated': memory_allocated,
    }


def parse_memory_file(process: Process):
    """Open the memory stat file and copy the appropriate data"""

    try:
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
    except Exception as err:
        raise CylcProfilerError(
            err, "Unable to find memory usage data") from err


def parse_memory_allocated(process: Process) -> int:
    """Open the memory stat file and copy the appropriate data"""
    if process.cgroup_version == 2:
        cgroup_memory_path = Path(process.memory_allocated_path)
        for _ in range(5):
            with open(cgroup_memory_path / "memory.max", 'r') as f:
                line = f.readline()
                if "max" not in line:
                    return int(line)
            cgroup_memory_path = cgroup_memory_path.parent
        return 0
    else:  # Memory limit not tracked for cgroups v1
        return 0


def parse_cpu_file(process: Process) -> int:
    """Open the CPU stat file and return the appropriate data"""
    try:
        if process.cgroup_version == 2:
            with open(process.cgroup_cpu_path, 'r') as f:
                for line in f:
                    if "usage_usec" in line:
                        return int(RE_INT.findall(line)[0]) // 1000
            raise FileNotFoundError(process.cgroup_cpu_path)

        elif process.cgroup_version == 1:
            with open(process.cgroup_cpu_path, 'r') as f:
                for line in f:
                    # Cgroups v1 uses nanoseconds
                    return int(line) // 1000000
            raise FileNotFoundError(process.cgroup_cpu_path)

    except Exception as err:
        raise CylcProfilerError(
            err, "Unable to find cpu usage data") from err
    return 0


def get_cgroup_version(cgroup_location: str, cgroup_name: str) -> int:
    try:
        if Path.exists(Path(cgroup_location + cgroup_name)):
            return 2
        elif Path.exists(Path(cgroup_location + "/memory" + cgroup_name)):
            return 1
        raise FileNotFoundError(cgroup_location + cgroup_name)
    except Exception as err:
        raise CylcProfilerError(
            err, "Cgroup not found at " + cgroup_location +
                 cgroup_name) from err


def get_cgroup_name():
    """Get the cgroup directory for the current process"""

    # fugly hack to allow functional tests to use test data
    if 'profiler_test_env_var' in os.environ:
        return os.environ['profiler_test_env_var']

    # Get the PID of the current process
    pid = os.getpid()
    try:
        # Get the cgroup information for the current process
        with open('/proc/' + str(pid) + '/cgroup', 'r') as f:
            result = f.read()
        result = PID_REGEX.search(result).group()
        return result

    except Exception as err:
        raise CylcProfilerError(
            err, '/proc/' + str(pid) + '/cgroup not found') from err


def get_cgroup_paths(location) -> Process:

    try:
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
        raise Exception
    except Exception as err:
        raise CylcProfilerError(
            err, "Unable to determine cgroup version") from err


async def profile(_process: Process, delay, keep_looping=lambda: True):
    # The infinite loop that will constantly poll the cgroup
    # The lambda function is used to allow the loop to be stopped in unit tests

    while keep_looping():
        # Write cpu / memory usage data to disk
        # CPU_TIME = parse_cpu_file(process.cgroup_cpu_path, version)
        await asyncio.sleep(delay)


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
    asyncio.run(_main(options))


async def _main(options) -> None:
    # get cgroup information
    process = get_cgroup_paths(options.cgroup_location)

    # Register the stop_profiler function with the signal library
    # The signal library doesn't work with asyncio, so we have to use the
    # loop's add_signal_handler function instead
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGHUP, signal.SIGTERM):
        loop.add_signal_handler(
            sig,
            lambda: asyncio.create_task(
                stop_profiler(process, options.comms_timeout)
            ),
        )

    # the profiler will run until one of these coroutines calls `sys.exit`:
    await asyncio.gather(
        # run the profiler itself
        profile(process, options.delay),

        # kill the profiler if its PPID changes
        # (i.e, if the job exits before the profiler does)
        watch_and_kill(psutil.Process(os.getpid())),
    )
