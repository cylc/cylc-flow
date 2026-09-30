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
# Any cgroups v1 memory limit at or above this is the kernel's "no limit"
# value (PAGE_COUNTER_MAX * PAGE_SIZE, which depends on the page size).
CGROUP_V1_UNLIMITED = 2 ** 62
# cgroups v1 mounts each controller separately, and the mount point is not
# always named after the controller (cpu and cpuacct are usually co-mounted)
V1_MOUNTS = {
    'memory': ('memory',),
    'cpu': ('cpu', 'cpu,cpuacct', 'cpuacct'),
}


@dataclass
class Process:
    """Class for representing CPU and Memory usage of a process"""
    cgroup_memory_path: Path
    max_rss: int
    cgroup_cpu_path: Path
    memory_allocated_path: Path
    # the cgroup version is tracked separately for each controller, a node
    # running cgroups in "hybrid" mode can provide v2 data for one and only
    # v1 data for the other
    memory_version: int
    cpu_version: int


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
        max_rss = cpu_time = memory_allocated = None
    else:
        max_rss = process.max_rss
        cpu_time = parse_cpu_file(process)
        memory_allocated = parse_memory_allocated(process)
        print({
            'max_rss': max_rss,
            'cpu_time': cpu_time,
            'memory_allocated': memory_allocated,
        })
    return {
        'max_rss': max_rss,
        'cpu_time': cpu_time,
        'memory_allocated': memory_allocated,
    }


def parse_memory_file(process: Process):
    """Open the memory stat file and copy the appropriate data"""

    try:
        if process.memory_version == 2:
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


def parse_memory_allocated(process: Process) -> int | None:
    """Open the memory stat file and copy the appropriate data"""
    if process.memory_version == 2:
        try:
            cgroup_memory_path = process.memory_allocated_path
            for _ in range(10):
                memory_max_file = cgroup_memory_path / "memory.max"
                if not os.path.isfile(memory_max_file):
                    # we have walked off the top of the cgroup filesystem
                    break
                with open(memory_max_file, 'r') as f:
                    line = f.readline()
                    if "max" not in line:
                        return int(line)
                    cgroup_memory_path = cgroup_memory_path.parent
        except Exception as err:
            raise CylcProfilerError(
                err, "Unable to find memory allocation") from err
    if process.memory_version == 1:
        try:
            cgroup_memory_path = process.memory_allocated_path
            for _ in range(10):
                memory_limit_file = (cgroup_memory_path /
                                     "memory.limit_in_bytes")
                if not os.path.isfile(memory_limit_file):
                    # we have walked off the top of the cgroup filesystem
                    break
                with open(memory_limit_file, 'r') as f:
                    line = f.readline()
                    # cgroups v1 uses a huge number, rather than "max", to
                    # mean "no limit". The exact value is
                    # PAGE_COUNTER_MAX * PAGE_SIZE, so it varies with the
                    # page size of the node (9223372036854771712 with the
                    # usual 4K pages) - test a threshold, not equality.
                    if int(line) < CGROUP_V1_UNLIMITED:
                        return int(line)
                    cgroup_memory_path = cgroup_memory_path.parent
        except Exception as err:
            raise CylcProfilerError(
                err, "Unable to find memory allocation") from err
    # no limit is set anywhere in this cgroup's ancestry
    return 0


def parse_cpu_file(process: Process) -> int:
    """Open the CPU stat file and return the appropriate data"""
    try:
        if process.cpu_version == 2:
            with open(process.cgroup_cpu_path, 'r') as f:
                for line in f:
                    if match := RE_CPU_USAGE.search(line):
                        return round(int(match.group(1)) / 1000)
            raise FileNotFoundError(process.cgroup_cpu_path)

        elif process.cpu_version == 1:
            with open(process.cgroup_cpu_path, 'r') as f:
                for line in f:
                    # Cgroups v1 uses nanoseconds
                    return round(int(line) / 1000000)
            raise FileNotFoundError(process.cgroup_cpu_path)

    except Exception as err:
        raise CylcProfilerError(
            err, "Unable to find cpu usage data") from err
    return 0


def get_cgroup_names() -> dict:
    """Return the cgroup path of this process for each controller.

    On a node running cgroups in "hybrid" mode each controller can be in a
    different place, e.g:

        5:cpu,cpuacct:/pbspro.service/jobid/2397344.ehz100
        4:memory:/pbspro.service/jobid/2397344.ehz100
        0::/system.slice/pbs.service

    gives {'cpu': 'pbspro.service/...', 'cpuacct': 'pbspro.service/...',
           'memory': 'pbspro.service/...', 'v2': 'system.slice/pbs.service'}

    The v2 (unified) hierarchy is stored under the key "v2".
    """
    # fugly hack to allow functional tests to use test data
    if 'profiler_test_env_var' in os.environ:
        name = os.environ['profiler_test_env_var'].lstrip('/')
        return {'v2': name, 'memory': name, 'cpu': name, 'cpuacct': name}

    pid = os.getpid()
    cgroup_path = Path('/proc') / str(pid) / 'cgroup'
    try:
        result = cgroup_path.read_text()
    except Exception as err:
        raise CylcProfilerError(
            err, f'{cgroup_path} not found') from err

    names = {}
    for line in result.splitlines():
        fields = line.split(':', 2)
        if len(fields) != 3:
            continue
        hierarchy_id, controllers, path = fields
        path = path.lstrip('/')
        if hierarchy_id == '0' and not controllers:
            # the unified (v2) hierarchy
            names['v2'] = path
        else:
            for controller in controllers.split(','):
                # "name=systemd" is a named v1 hierarchy, not a controller
                if not controller.startswith('name='):
                    names[controller] = path
    return names


def v2_controllers_enabled(directory: Path) -> bool:
    """Is this cgroup v2 directory backed by real resource controllers?

    In systemd's "hybrid" mode a cgroup2 hierarchy is mounted purely to
    track processes, with no controllers enabled - its cgroup.controllers
    files are empty and the resource controllers stay on v1.

    This matters because the kernel exposes cpu.stat in every v2 cgroup
    whether or not the cpu controller is enabled. In hybrid mode that file
    is readable but describes the wrong cgroup (e.g. the batch system's
    service cgroup, shared by every job on the node), so its presence alone
    is not enough to tell us v2 is usable.
    """
    controllers = Path(directory) / 'cgroup.controllers'
    try:
        return bool(controllers.read_text().split())
    except OSError:
        return False


def get_controller_paths(
    location: Path, names: dict, controller: str, v2_file: str, v1_file: str
):
    """Locate the cgroup directory holding a controller's data.

    Prefers cgroups v2, falling back to v1 if the v2 hierarchy does not
    provide this controller (as happens in "hybrid" mode).

    Returns (version, directory).
    """
    # cgroups v2: everything lives in the one unified hierarchy
    if 'v2' in names:
        directory = location / names['v2']
        if (
            os.path.isfile(directory / v2_file)
            and v2_controllers_enabled(directory)
        ):
            return 2, directory

    # cgroups v1: each controller is mounted separately, and the mount
    # point does not always match the controller name (e.g. the cpu and
    # cpuacct controllers are usually co-mounted as "cpu,cpuacct")
    for mount in V1_MOUNTS[controller]:
        for name in (names.get(mount), names.get(controller)):
            if name is None:
                continue
            directory = location / mount / name
            if os.path.isfile(directory / v1_file):
                return 1, directory

    raise CylcProfilerError(
        FileNotFoundError(location),
        f"Cgroup not found for the {controller} controller under {location}"
    )


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
    """Work out where this process's cgroup data lives.

    The memory and cpu controllers are resolved independently: in "hybrid"
    mode a node can serve v2 data for one and only v1 data for the other.
    """
    names = get_cgroup_names()

    # RSS and the memory limit both come from the memory controller
    memory_version, memory_dir = get_controller_paths(
        location, names, 'memory', 'memory.stat', 'memory.stat'
    )
    cpu_version, cpu_dir = get_controller_paths(
        location, names, 'cpu', 'cpu.stat', 'cpuacct.usage'
    )
    LOG.debug(
        f'profiler: memory=cgroups v{memory_version} ({memory_dir}), '
        f'cpu=cgroups v{cpu_version} ({cpu_dir})'
    )

    return Process(
        cgroup_memory_path=memory_dir / "memory.stat",
        cgroup_cpu_path=(
            cpu_dir / ("cpu.stat" if cpu_version == 2 else "cpuacct.usage")
        ),
        memory_allocated_path=memory_dir,
        memory_version=memory_version,
        cpu_version=cpu_version,
        max_rss=0,
    )


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

    # convert from ISO8601 duration to integer seconds
    delay = int(dp.parse(options.delay).get_seconds())

    # get cgroup information
    process = get_cgroup_paths(Path(options.cgroup_location))
    # the profiler will run until one of these coroutines calls `sys.exit`:
    tasks = [
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
    ]

    # The signal library doesn't work with asyncio, so we have to use the
    # loop's add_signal_handler function instead
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGHUP, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: {t.cancel() for t in tasks})

    with suppress(asyncio.CancelledError):
        await asyncio.gather(*tasks)

    await report_to_scheduler(process, options.comms_timeout)
