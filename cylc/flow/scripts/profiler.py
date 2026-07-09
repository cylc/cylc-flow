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
from contextlib import suppress
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import signal

import psutil

from cylc.flow import LOG
from cylc.flow.exceptions import CylcProfilerError
import cylc.flow.flags
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.remote import watch_and_kill
from cylc.flow.task_message import record_messages
from cylc.flow.terminal import cli_function
from metomi.isodatetime.parsers import DurationParser

dp = DurationParser()


INTERNAL = True
PID_REGEX = re.compile(r"([^:]*\d{6,}.*)")
RE_CPU_USAGE = re.compile(r'usage_usec\s*(\d+)')


@dataclass
class Process:
    """Class for representing CPU and Memory usage of a process"""
    cgroup_memory_path: Path
    max_rss: int
    cgroup_cpu_path: Path
    memory_allocated_path: Path
    cgroup_version: int


async def report_to_scheduler(process: Process, comms_timeout: int):
    """Return the profiler's data to the scheduler."""
    # extract the stats
    profiler_data = get_profiler_data(process)

    # send a task message to the scheduler / write message to job.status file
    await record_messages(
        os.environ['CYLC_WORKFLOW_ID'],
        os.environ['CYLC_TASK_JOB'],
        [['DEBUG', f'_cylc_profiler: {json.dumps(profiler_data)}']],
        comms_timeout=comms_timeout,
    )


def get_profiler_data(process: Process):
    if (
        process.cgroup_memory_path is None
        or process.cgroup_cpu_path is None
        or process.memory_allocated_path is None
    ):
        # If a task fails instantly, or finishes very quickly (< 1 second),
        # the get config function doesn't have time to run
        max_rss = cpu_time = memory_allocated = 0
    else:
        max_rss = process.max_rss
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
        cgroup_memory_path = process.memory_allocated_path
        for _ in range(5):
            memory_max_file = cgroup_memory_path / "memory.max"
            with open(memory_max_file, 'r') as f:
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
                    if match := RE_CPU_USAGE.search(line):
                        return round(int(match.group(1)) / 1000)
            raise FileNotFoundError(process.cgroup_cpu_path)

        elif process.cgroup_version == 1:
            with open(process.cgroup_cpu_path, 'r') as f:
                for line in f:
                    # Cgroups v1 uses nanoseconds
                    return round(int(line) / 1000000)
            raise FileNotFoundError(process.cgroup_cpu_path)

    except Exception as err:
        raise CylcProfilerError(
            err, "Unable to find cpu usage data") from err
    return 0


def get_cgroup_version(cgroup_location: Path, cgroup_name: str) -> int:
    # Strip leading '/' so the name is treated as relative when joined
    cgroup_name = cgroup_name.lstrip('/')
    try:
        if (cgroup_location / cgroup_name).exists():
            return 2
        elif (cgroup_location / "memory" / cgroup_name).exists():
            return 1
        raise FileNotFoundError(cgroup_location / cgroup_name)
    except Exception as err:
        raise CylcProfilerError(
            err, f"Cgroup not found at {cgroup_location / cgroup_name}"
        ) from err


def get_cgroup_name():
    """Get the cgroup directory for the current process"""

    # fugly hack to allow functional tests to use test data
    if 'profiler_test_env_var' in os.environ:
        return os.environ['profiler_test_env_var']

    # Get the PID of the current process
    pid = os.getpid()
    cgroup_path = Path('/proc') / str(pid) / 'cgroup'
    try:
        # Get the cgroup information for the current process
        result = cgroup_path.read_text()
        return PID_REGEX.search(result).group().lstrip('/')

    except Exception as err:
        raise CylcProfilerError(
            err, f'{cgroup_path} not found') from err


def get_cgroup_paths(location: Path) -> Process:

    cgroup_name = get_cgroup_name().lstrip('/')
    cgroup_version = get_cgroup_version(location, cgroup_name)

    if cgroup_version == 2:
        return Process(
            cgroup_memory_path=location / cgroup_name / "memory.stat",
            cgroup_cpu_path=location / cgroup_name / "cpu.stat",
            memory_allocated_path=location / cgroup_name,
            cgroup_version=cgroup_version,
            max_rss=0,
        )

    elif cgroup_version == 1:
        return Process(
            cgroup_memory_path=(
                location / "memory" / cgroup_name / "memory.stat"
            ),
            cgroup_cpu_path=(
                location / "cpu" / cgroup_name / "cpuacct.usage"
            ),
            memory_allocated_path=Path(),
            cgroup_version=cgroup_version,
            max_rss=0,
        )

    raise CylcProfilerError(FileNotFoundError(),
                            "Unable to determine cgroup version")


async def profile(process: Process, delay, keep_looping=lambda: True):
    # The infinite loop that will constantly poll the cgroup
    # The lambda function is used to allow the loop to be stopped in unit tests

    while keep_looping():
        # Polling the cgroup for memory and keeping track of the max rss value
        max_rss = parse_memory_file(process)
        if max_rss is not None and max_rss > process.max_rss:
            process.max_rss = max_rss
        await asyncio.sleep(delay)


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        comms=True,
        argdoc=[
        ],
    )
    parser.add_option(
        "-i", type=str,
        help="interval between query cycles in seconds", dest="delay")
    parser.add_option(
        "-m", type=str, help="Location of cgroups directory",
        dest="cgroup_location")

    return parser


@cli_function(get_option_parser)
def main(_parser: COP, options) -> None:
    """CLI main."""
    try:
        asyncio.run(_main(options))
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        # Only log at info level as not very important (show traceback if -vv)
        LOG.info(exc, exc_info=(cylc.flow.flags.verbosity > 1))


async def _main(options) -> None:

    # list of asyncio tasks
    tasks: list[asyncio.Task] = []

    # Register the stop_profiler function with the signal library
    # The signal library doesn't work with asyncio, so we have to use the
    # loop's add_signal_handler function instead
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGHUP, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: {t.cancel() for t in tasks})

    # convert from ISO8601 duration to integer seconds
    delay = int(dp.parse(options.delay).get_seconds())

    # get cgroup information
    process = get_cgroup_paths(Path(options.cgroup_location))
    # the profiler will run until one of these coroutines calls `sys.exit`:
    tasks.extend([
        # run the profiler itself
        asyncio.create_task(
            profile(process, delay),
            name="profiler",
        ),

        # kill the profiler if its PPID changes
        # (i.e, if the job exits before the profiler does)
        asyncio.create_task(
            watch_and_kill(psutil.Process(os.getpid())),
            name="profiler_watchdog",
        ),
    ])

    with suppress(asyncio.CancelledError):
        await asyncio.gather(*tasks)

    await report_to_scheduler(process, options.comms_timeout)
