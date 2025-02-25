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
"""Utilities supporting dummy mode.

Dummy mode shares settings with simulation mode.
"""

from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Tuple,
)

from cylc.flow.platforms import get_platform
from cylc.flow.run_modes import RunMode
from cylc.flow.run_modes.simulation import (
    ModeSettings,
    disable_platforms,
    get_simulated_run_len,
    parse_fail_cycle_points,
)


if TYPE_CHECKING:
    # BACK COMPAT: typing_extensions.Literal
    # FROM: Python 3.7
    # TO: Python 3.8
    from typing_extensions import Literal

    from cylc.flow.task_job_mgr import TaskJobManager
    from cylc.flow.task_proxy import TaskProxy


CLEAR_THESE_SCRIPTS = [
    'init-script',
    'env-script',
    'pre-script',
    'post-script',
    'err-script',
    'exit-script',
]


def submit_task_job(
    task_job_mgr: 'TaskJobManager',
    itask: 'TaskProxy',
    rtconfig: Dict[str, Any],
    workflow: str,
    now: Tuple[float, str]
) -> 'Literal[False]':
    """Submit a task in dummy mode.

    Returns:
        False indicating that TaskJobManager needs to continue running the
        live mode path.
    """
    configure_dummy_mode(
        rtconfig, itask.tdef.rtconfig['simulation']['fail cycle points'])

    itask.summary['started_time'] = now[0]
    task_job_mgr._set_retry_timers(itask, rtconfig)

    itask.mode_settings = ModeSettings(
        itask,
        task_job_mgr.workflow_db_mgr,
        rtconfig
    )

    itask.platform = get_platform()
    itask.platform['name'] = RunMode.DUMMY.value
    itask.summary['job_runner_name'] = RunMode.DUMMY.value
    itask.summary[task_job_mgr.KEY_EXECUTE_TIME_LIMIT] = (
        itask.mode_settings.simulated_run_length)
    itask.jobs.append(
        task_job_mgr.get_simulation_job_conf(itask, workflow))
    task_job_mgr.workflow_db_mgr.put_insert_task_jobs(
        itask, {
            'time_submit': now[1],
            'try_num': itask.get_try_num(),
        }
    )

    return False


def configure_dummy_mode(rtc: Dict[str, Any], fallback: str) -> None:
    """Adjust task defs for dummy mode.
    """
    rtc['submission retry delays'] = [1]
    # Generate dummy scripting.

    for script in CLEAR_THESE_SCRIPTS:
        rtc[script] = ''

    rtc['script'] = build_dummy_script(
        rtc, get_simulated_run_len(rtc))
    disable_platforms(rtc)
    # Disable environment, in case it depends on env-script.
    rtc['environment'] = {}
    rtc["simulation"][
        "fail cycle points"
    ] = parse_fail_cycle_points(
        rtc["simulation"]["fail cycle points"], fallback
    )


def build_dummy_script(rtc: Dict[str, Any], sleep_sec: int) -> str:
    """Create fake scripting for dummy mode script.
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
