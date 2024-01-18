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

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union
from time import time

from cylc.flow.cycling.loader import get_point
from cylc.flow.network.resolvers import TaskMsg
from cylc.flow.parsec.util import (
    pdeepcopy,
    poverride
)
from cylc.flow.platforms import FORBIDDEN_WITH_PLATFORM
from cylc.flow.task_state import (
    TASK_STATUS_RUNNING,
    TASK_STATUS_FAILED,
    TASK_STATUS_SUCCEEDED,
)
from cylc.flow.wallclock import get_current_time_string

from metomi.isodatetime.parsers import DurationParser, TimePointParser

if TYPE_CHECKING:
    from queue import Queue
    from cylc.flow.broadcast_mgr import BroadcastMgr
    from cylc.flow.cycling import PointBase
    from cylc.flow.task_proxy import TaskProxy
    from cylc.flow.workflow_db_mgr import WorkflowDatabaseManager


@dataclass
class ModeSettings:
    """A store of state for simulation modes.

    Used instead of modifying the runtime config.
    """
    simulated_run_length: float = 0.0
    sim_task_fails: bool = False

    def __init__(self, itask: 'TaskProxy', broadcast_mgr: 'BroadcastMgr'):
        overrides = broadcast_mgr.get_broadcast(itask.tokens)
        if overrides:
            rtconfig = pdeepcopy(itask.tdef.rtconfig)
            poverride(rtconfig, overrides, prepend=True)
        else:
            rtconfig = itask.tdef.rtconfig
        self.simulated_run_length = (
            get_simulated_run_len(rtconfig))
        self.sim_task_fails = sim_task_failed(
            rtconfig['simulation'],
            itask.point,
            itask.submit_num
        )


def configure_sim_modes(taskdefs, sim_mode):
    """Adjust task defs for simulation and dummy mode.

    """
    dummy_mode = bool(sim_mode == 'dummy')

    for tdef in taskdefs:
        # Compute simulated run time by scaling the execution limit.
        rtc = tdef.rtconfig

        rtc['submission retry delays'] = [1]

        if dummy_mode:
            # Generate dummy scripting.
            rtc['init-script'] = ""
            rtc['env-script'] = ""
            rtc['pre-script'] = ""
            rtc['post-script'] = ""
            rtc['script'] = build_dummy_script(
                rtc, get_simulated_run_len(rtc))

        disable_platforms(rtc)

        # Disable environment, in case it depends on env-script.
        rtc['environment'] = {}

        rtc["simulation"][
            "fail cycle points"
        ] = parse_fail_cycle_points(
            rtc["simulation"]["fail cycle points"]
        )


def get_simulated_run_len(rtc: Dict[str, Any]) -> int:
    """Calculate simulation run time from a task's config.

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
    f_pts_orig: List[str]
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
    message_queue: 'Queue[TaskMsg]',
    itasks: 'List[TaskProxy]',
    broadcast_mgr: 'BroadcastMgr',
    db_mgr: 'WorkflowDatabaseManager',
) -> bool:
    """Check if sim tasks have been "running" for as long as required.

    If they have change the task state.

    Returns:
        True if _any_ simulated task state has changed.
    """
    now = time()
    sim_task_state_changed: bool = False
    for itask in itasks:
        if (
            itask.state.status != TASK_STATUS_RUNNING
            or itask.state.is_queued
            or itask.state.is_held
            or itask.state.is_runahead
        ):
            continue

        # Started time and mode_settings are not set on restart:
        started_time = itask.summary['started_time']
        if started_time is None:
            started_time = int(
                TimePointParser()
                .parse(
                    db_mgr.pub_dao.select_task_job(
                        *itask.tokens.relative_id.split("/")
                    )["time_submit"]
                )
                .seconds_since_unix_epoch
            )
            itask.summary['started_time'] = started_time
        if itask.mode_settings is None:
            itask.mode_settings = ModeSettings(itask, broadcast_mgr)

        timeout = started_time + itask.mode_settings.simulated_run_length
        if now > timeout:
            job_d = itask.tokens.duplicate(job=str(itask.submit_num))
            now_str = get_current_time_string()

            if itask.mode_settings.sim_task_fails:
                message_queue.put(
                    TaskMsg(job_d, now_str, 'CRITICAL', TASK_STATUS_FAILED)
                )
            else:
                message_queue.put(
                    TaskMsg(job_d, now_str, 'DEBUG', TASK_STATUS_SUCCEEDED)
                )

            # Simulate message outputs.
            for msg in itask.tdef.rtconfig['outputs'].values():
                message_queue.put(
                    TaskMsg(job_d, now_str, 'DEBUG', msg)
                )
            sim_task_state_changed = True
    return sim_task_state_changed


def sim_task_failed(
        sim_conf: Dict[str, Any],
        point: 'PointBase',
        submit_num: int,
) -> bool:
    """Encapsulate logic for deciding whether a sim task has failed.

    Allows Unit testing.
    """
    return (
        sim_conf['fail cycle points'] is None  # i.e. "all"
        or point in sim_conf['fail cycle points']
    ) and (
        submit_num == 0 or not sim_conf['fail try 1 only']
    )
