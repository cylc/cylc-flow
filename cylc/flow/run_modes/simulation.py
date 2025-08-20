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
"""Utilities supporting simulation mode
"""

from dataclasses import dataclass
from logging import INFO
from time import time
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Literal,
    Tuple,
    Union,
)

from metomi.isodatetime.parsers import DurationParser

from cylc.flow import LOG
from cylc.flow.cycling import PointBase
from cylc.flow.cycling.loader import get_point
from cylc.flow.exceptions import PointParsingError
from cylc.flow.platforms import FORBIDDEN_WITH_PLATFORM
from cylc.flow.run_modes import RunMode
from cylc.flow.task_outputs import TASK_OUTPUT_SUBMITTED
from cylc.flow.task_state import (
    TASK_STATUS_FAILED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUCCEEDED,
)
from cylc.flow.wallclock import get_unix_time_from_time_string


if TYPE_CHECKING:
    from cylc.flow.task_events_mgr import TaskEventsManager
    from cylc.flow.task_job_mgr import TaskJobManager
    from cylc.flow.task_proxy import TaskProxy
    from cylc.flow.workflow_db_mgr import WorkflowDatabaseManager


def submit_task_job(
    task_job_mgr: 'TaskJobManager',
    itask: 'TaskProxy',
    rtconfig: Dict[str, Any],
    now: Tuple[float, str]
) -> 'Literal[True]':
    """Submit a task in simulation mode.

    Returns:
        True - indicating that TaskJobManager need take no further action.
    """
    configure_sim_mode(
        rtconfig,
        itask.tdef.rtconfig['simulation']['fail cycle points'])
    itask.summary['started_time'] = now[0]
    task_job_mgr._set_retry_timers(itask, rtconfig)
    itask.mode_settings = ModeSettings(
        itask,
        task_job_mgr.workflow_db_mgr,
        rtconfig
    )
    itask.waiting_on_job_prep = False
    itask.submit_num += 1

    itask.platform = {
        'name': RunMode.SIMULATION.value,
        'install target': 'localhost',
        'hosts': ['localhost'],
        'submission retry delays': [],
        'execution retry delays': []
    }
    itask.summary['job_runner_name'] = RunMode.SIMULATION.value
    itask.summary[task_job_mgr.KEY_EXECUTE_TIME_LIMIT] = (
        itask.mode_settings.simulated_run_length
    )
    itask.jobs.append(
        task_job_mgr.get_simulation_job_conf(itask)
    )
    task_job_mgr.task_events_mgr.process_message(
        itask, INFO, TASK_OUTPUT_SUBMITTED,
    )
    task_job_mgr.workflow_db_mgr.put_insert_task_jobs(
        itask, {
            'time_submit': now[1],
            'time_run': now[1],
            'try_num': itask.get_try_num(),
            'flow_nums': str(list(itask.flow_nums)),
            'is_manual_submit': itask.is_manual_submit,
            'job_runner_name': RunMode.SIMULATION.value,
            'platform_name': RunMode.SIMULATION.value,
            'submit_status': 0   # Submission has succeeded
        }
    )
    itask.state.status = TASK_STATUS_RUNNING
    return True


@dataclass
class ModeSettings:
    """A store of state for simulation modes.

    Used instead of modifying the runtime config. We want to leave the
    config unchanged so that clearing a broadcast change of run mode
    clears the run mode settings.

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
        db_mgr: 'WorkflowDatabaseManager',
        rtconfig: Dict[str, Any]
    ):
        # itask.summary['started_time'] and mode_settings.timeout need
        # repopulating from the DB on workflow restart:
        started_time = itask.summary['started_time']
        try_num = None
        if started_time is None:
            # This is a restart - Get DB info
            db_info = db_mgr.pri_dao.select_task_job(
                itask.tokens['cycle'],
                itask.tokens['task'],
                itask.tokens['job'],
            )

            if db_info['time_submit']:
                started_time = get_unix_time_from_time_string(
                    db_info["time_submit"])
                itask.summary['started_time'] = started_time
            else:
                started_time = time()

            try_num = db_info["try_num"]

        # Parse fail cycle points:
        if not rtconfig:
            rtconfig = itask.tdef.rtconfig
        if rtconfig and rtconfig != itask.tdef.rtconfig:
            rtconfig["simulation"][
                "fail cycle points"
            ] = parse_fail_cycle_points(
                rtconfig["simulation"]["fail cycle points"],
                itask.tdef.rtconfig['simulation']['fail cycle points']
            )

        # Calculate simulation outcome and run-time:
        self.simulated_run_length = (
            get_simulated_run_len(rtconfig))
        self.sim_task_fails = sim_task_failed(
            rtconfig['simulation'],
            itask.point,
            try_num or itask.get_try_num()
        )
        self.timeout = started_time + self.simulated_run_length


def configure_sim_mode(rtc, fallback, warnonly: bool = True):
    """Adjust task defs for simulation mode.

    Example:
        >>> this = configure_sim_mode
        >>> rtc = {
        ...     'submission retry delays': [42, 24, 23],
        ...     'environment': {'DoNot': '"WantThis"'},
        ...     'simulation': {'fail cycle points': ['all']}
        ... }
        >>> this(rtc, [53])
        >>> rtc['submission retry delays']
        [1]
        >>> rtc['environment']
        {}
        >>> rtc['simulation']
        {'fail cycle points': None}
        >>> rtc['platform']
        'localhost'
    """
    if not warnonly:
        parse_fail_cycle_points(
            rtc["simulation"]["fail cycle points"],
            fallback,
            warnonly
        )
        return
    rtc['submission retry delays'] = [1]

    disable_platforms(rtc)

    # Disable environment, in case it depends on env-script.
    rtc['environment'] = {}

    rtc["simulation"][
        "fail cycle points"
    ] = parse_fail_cycle_points(
        rtc["simulation"]["fail cycle points"],
        fallback,
        warnonly
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
    fail_at_points_updated: List[str],
    fail_at_points_config,
    warnonly: bool = True
) -> 'Union[None, List[PointBase]]':
    """Parse `[simulation][fail cycle points]`.

    - None for "fail all points".
    - Else a list of cycle point objects.

    Args:
        fail_at_points_updated: Fail cycle points from a broadcast.
        fail_at_points_config:
            Fail cycle points from original workflow config, which would
            have caused the scheduler to fail on config parsing. This check is
            designed to prevent broadcasts from taking the scheduler down.

    Examples:
        >>> this = parse_fail_cycle_points
        >>> this(['all'], ['42']) is None
        True
        >>> this([], ['42'])
        []
        >>> this(None, ['42']) is None
        True
    """
    fail_at_points: 'List[PointBase]' = []
    if (
        fail_at_points_updated is None
        or fail_at_points_updated
        and 'all' in fail_at_points_updated
    ):
        return None
    elif fail_at_points_updated:
        for point_str in fail_at_points_updated:
            if isinstance(point_str, PointBase):
                fail_at_points.append(point_str)
            else:
                try:
                    fail_at_points.append(get_point(point_str).standardise())
                except PointParsingError as exc:
                    if warnonly:
                        LOG.warning(exc.args[0])
                        return fail_at_points_config
                    else:
                        raise exc
    return fail_at_points


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
        if (
            itask.state.status != TASK_STATUS_RUNNING
            or (
                itask.run_mode
                and itask.run_mode != RunMode.SIMULATION
            )
        ):
            continue

        # This occurs if the workflow has been restarted.
        if itask.mode_settings is None:
            rtconfig = task_events_manager.broadcast_mgr.get_updated_rtconfig(
                itask)
            rtconfig = configure_sim_mode(
                rtconfig,
                itask.tdef.rtconfig['simulation']['fail cycle points'])
            itask.mode_settings = ModeSettings(
                itask,
                db_mgr,
                rtconfig
            )

        if now > itask.mode_settings.timeout:
            # simulate custom outputs
            for msg in itask.tdef.rtconfig['outputs'].values():
                task_events_manager.process_message(
                    itask, 'DEBUG', msg,
                    flag=task_events_manager.FLAG_RECEIVED
                )

            # simulate job outcome
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

            # We've finished this pseudo job, so delete all the mode settings.
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
    return (
        sim_conf['fail cycle points'] is None  # i.e. "all"
        or point in sim_conf['fail cycle points']
    ) and (
        try_num == 1 or not sim_conf['fail try 1 only']
    )
