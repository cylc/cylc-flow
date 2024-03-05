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

from cylc.flow import LOG
from cylc.flow.cycling.loader import get_point
from cylc.flow.exceptions import PointParsingError
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
from cylc.flow.wallclock import get_unix_time_from_time_string

from metomi.isodatetime.parsers import DurationParser

if TYPE_CHECKING:
    from cylc.flow.broadcast_mgr import BroadcastMgr
    from cylc.flow.task_events_mgr import TaskEventsManager
    from cylc.flow.task_proxy import TaskProxy
    from cylc.flow.workflow_db_mgr import WorkflowDatabaseManager
    from cylc.flow.cycling import PointBase


@dataclass
class ModeSettings:
    """A store of state for simulation modes.

    Used instead of modifying the runtime config.

    Args:
        itask:
            The task proxy this submission relates to.
        broadcast_mgr:
            The broadcast manager is used to apply any runtime alterations
            pre simulated submission.
        db_mgr:
            The database manager must be provided for simulated jobs
            that are being resumed after workflow restart. It is used to
            extract the original scheduled finish time for the job.

    Attrs:
        simulated_run_length:
            The length of time this simulated job will take to run in seconds.
        timeout:
            The wall-clock time at which this simulated job will finish as
            a Unix epoch time.
        sim_task_fails:
            True, if this job is intended to fail when it finishes, else False.

    """
    simulated_run_length: float = 0.0
    sim_task_fails: bool = False
    timeout: float = 0.0

    def __init__(
        self,
        itask: 'TaskProxy',
        broadcast_mgr: 'BroadcastMgr',
        db_mgr: 'WorkflowDatabaseManager',
    ):

        # itask.summary['started_time'] and mode_settings.timeout need
        # repopulating from the DB on workflow restart:
        started_time = itask.summary['started_time']
        try_num = None
        if started_time is None:
            # Get DB info
            db_info = db_mgr.pri_dao.select_task_job(
                itask.tokens['cycle'],
                itask.tokens['task'],
                itask.tokens['job'],
            )

            # Get the started time:
            if db_info['time_submit']:
                started_time = get_unix_time_from_time_string(
                    db_info["time_submit"])
                itask.summary['started_time'] = started_time
            else:
                started_time = time()

            # Get the try number:
            try_num = db_info["try_num"]

        # Update anything changed by broadcast:
        overrides = broadcast_mgr.get_broadcast(itask.tokens)
        if overrides:
            rtconfig = pdeepcopy(itask.tdef.rtconfig)
            poverride(rtconfig, overrides, prepend=True)

            try:
                rtconfig["simulation"][
                    "fail cycle points"
                ] = parse_fail_cycle_points(
                    rtconfig["simulation"]["fail cycle points"]
                )
            except PointParsingError as exc:
                # Broadcast Fail CP didn't parse
                LOG.error(
                    'Broadcast fail cycle point was invalid:\n'
                    f'    {exc.args[0]}'
                )
                rtconfig['simulation'][
                    'fail cycle points'
                ] = itask.tdef.rtconfig['simulation']['fail cycle points']
        else:
            rtconfig = itask.tdef.rtconfig

        # Calculate simulation info:
        self.simulated_run_length = (
            get_simulated_run_len(rtconfig))
        self.sim_task_fails = sim_task_failed(
            rtconfig['simulation'],
            itask.point,
            try_num or itask.get_try_num()
        )
        self.timeout = started_time + self.simulated_run_length


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
    task_events_manager: 'TaskEventsManager',
    itasks: 'List[TaskProxy]',
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
        if itask.state.status != TASK_STATUS_RUNNING:
            continue

        # This occurs if the workflow has been restarted.
        if itask.mode_settings is None:
            itask.mode_settings = ModeSettings(
                itask,
                task_events_manager.broadcast_mgr,
                db_mgr,
            )

        if now > itask.mode_settings.timeout:
            if itask.mode_settings.sim_task_fails:
                task_events_manager.process_message(
                    itask, 'CRITICAL', TASK_STATUS_FAILED,
                    flag=task_events_manager.FLAG_RECEIVED
                )
            else:
                task_events_manager.process_message(
                    itask, 'DEBUG', TASK_STATUS_SUCCEEDED,
                    flag=task_events_manager.FLAG_RECEIVED
                )
            # Simulate message outputs.
            for msg in itask.tdef.rtconfig['outputs'].values():
                task_events_manager.process_message(
                    itask, 'DEBUG', msg,
                    flag=task_events_manager.FLAG_RECEIVED
                )

            # We've finished this psuedojob, so delete all the mode settings.
            itask.mode_settings = None
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
    x = (
        sim_conf['fail cycle points'] is None  # i.e. "all"
        or point in sim_conf['fail cycle points']
    ) and (
        try_num == 1 or not sim_conf['fail try 1 only']
    )
    # breakpoint(header=f'{x},{sim_conf}, {point}, {try_num}')
    return x
