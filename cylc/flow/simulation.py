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
"""Utilities supporting simulation and skip modes
"""

from queue import Queue
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union
from time import time

from cylc.flow.cycling.loader import get_point
from cylc.flow.network.resolvers import TaskMsg
from cylc.flow.platforms import FORBIDDEN_WITH_PLATFORM
from cylc.flow.task_state import (
    TASK_STATUS_RUNNING,
    TASK_STATUS_FAILED,
    TASK_STATUS_SUCCEEDED,
)
from cylc.flow.wallclock import get_current_time_string

from metomi.isodatetime.parsers import DurationParser

if TYPE_CHECKING:
    from cylc.flow.cycling import PointBase
    from cylc.flow.task_proxy import TaskProxy


def configure_sim_modes(taskdefs, sim_mode):
    """Adjust task defs for simulation and dummy mode.

    """
    dummy_mode = bool(sim_mode == 'dummy')

    for tdef in taskdefs:
        # Compute simulated run time by scaling the execution limit.
        rtc = tdef.rtconfig
        sleep_sec = get_simulated_run_len(rtc)

        rtc['execution time limit'] = (
            sleep_sec + DurationParser().parse(str(
                rtc['simulation']['time limit buffer'])).get_seconds()
        )

        rtc['simulation']['simulated run length'] = sleep_sec
        rtc['submission retry delays'] = [1]

        # Generate dummy scripting.
        rtc['init-script'] = ""
        rtc['env-script'] = ""
        rtc['pre-script'] = ""
        rtc['post-script'] = ""
        rtc['script'] = build_dummy_script(
            rtc, sleep_sec) if dummy_mode else ""

        disable_platforms(rtc)

        # Disable environment, in case it depends on env-script.
        rtc['environment'] = {}

        rtc["simulation"][
            "fail cycle points"
        ] = parse_fail_cycle_points(
            rtc["simulation"]["fail cycle points"]
        )


def get_simulated_run_len(rtc: Dict[str, Any]) -> int:
    """Get simulated run time.

    rtc = run time config
    """
    limit = rtc['execution time limit']
    speedup = rtc['simulation']['speedup factor']
    if limit and speedup:
        sleep_sec = (DurationParser().parse(
            str(limit)).get_seconds() / speedup)
    else:
        sleep_sec = DurationParser().parse(
            str(rtc['simulation']['default run length'])
        ).get_seconds()

    return sleep_sec


def build_dummy_script(rtc: Dict[str, Any], sleep_sec: int) -> str:
    """Create fake scripting for dummy mode.

    This is for Dummy mode only.
    """
    script = "sleep %d" % sleep_sec
    # Dummy message outputs.
    for msg in rtc['outputs'].values():
        script += "\ncylc message '%s'" % msg
    if rtc['simulation']['fail try 1 only']:
        arg1 = "true"
    else:
        arg1 = "false"
    arg2 = " ".join(rtc['simulation']['fail cycle points'])
    script += "\ncylc__job__dummy_result %s %s || exit 1" % (arg1, arg2)
    return script


def disable_platforms(
    rtc: Dict[str, Any]
) -> None:
    """Force platform = localhost

    Remove legacy sections [job] and [remote], which would conflict
    with setting platforms.

    This can be simplified when support for the FORBIDDEN_WITH_PLATFORM
    configurations is dropped.
    """
    for section, keys in FORBIDDEN_WITH_PLATFORM.items():
        if section in rtc:
            for key in keys:
                if key in rtc[section]:
                    rtc[section][key] = None
    rtc['platform'] = 'localhost'


def parse_fail_cycle_points(
    f_pts_orig: list
) -> 'Union[None, List[PointBase]]':
    """Parse `[simulation][fail cycle points]`.

    - None for "fail all points".
    - Else a list of cycle point objects.

    Examples:
        >>> this = parse_fail_cycle_points
        >>> this(['all']) is None
        True
        >>> this([])
        []
    """
    f_pts: 'Optional[List[PointBase]]'
    if 'all' in f_pts_orig:
        f_pts = None
    else:
        f_pts = []
        for point_str in f_pts_orig:
            f_pts.append(get_point(point_str).standardise())
    return f_pts


def sim_time_check(
    message_queue: 'Queue[TaskMsg]', itasks: 'List[TaskProxy]'
) -> bool:
    """Check if sim tasks have been "running" for as long as required.

    If they have change the task state.

    Returns:
        True if _any_ simulated task state has changed.
    """
    sim_task_state_changed = False
    now = time()
    for itask in itasks:
        if itask.state.status != TASK_STATUS_RUNNING:
            continue
        # Started time is not set on restart
        if itask.summary['started_time'] is None:
            itask.summary['started_time'] = now
        timeout = (
            itask.summary['started_time'] +
            itask.tdef.rtconfig['simulation']['simulated run length']
        )
        if now > timeout:
            job_d = itask.tokens.duplicate(job=str(itask.submit_num))
            now_str = get_current_time_string()
            if sim_task_failed(
                itask.tdef.rtconfig['simulation'],
                itask.point,
                itask.get_try_num()
            ):
                message_queue.put(
                    TaskMsg(job_d, now_str, 'CRITICAL', TASK_STATUS_FAILED)
                )
            else:
                # Simulate message outputs.
                for msg in itask.tdef.rtconfig['outputs'].values():
                    message_queue.put(
                        TaskMsg(job_d, now_str, 'DEBUG', msg)
                    )
                message_queue.put(
                    TaskMsg(job_d, now_str, 'DEBUG', TASK_STATUS_SUCCEEDED)
                )
            sim_task_state_changed = True
    return sim_task_state_changed


def sim_task_failed(
        sim_conf: Dict[str, Any],
        point: 'PointBase',
        try_num: int,
) -> bool:
    """Encapsulate logic for deciding whether a sim task has failed.

    Allows Unit testing.
    """
    return (
        sim_conf['fail cycle points'] is None  # i.e. "all"
        or point in sim_conf['fail cycle points']
    ) and (
        try_num == 1 or not sim_conf['fail try 1 only']
    )
