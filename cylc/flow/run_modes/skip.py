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

from logging import INFO
from typing import (
    TYPE_CHECKING, Any, Dict, Tuple)

from cylc.flow.platforms import get_platform
from cylc.flow.task_outputs import TASK_OUTPUT_SUBMITTED, TASK_OUTPUT_SUCCEEDED
from cylc.flow.task_state import RunMode

if TYPE_CHECKING:
    from cylc.flow.task_job_mgr import TaskJobManager
    from cylc.flow.task_proxy import TaskProxy
    from typing_extensions import Literal


def submit_task_job(
    task_job_mgr: 'TaskJobManager',
    itask: 'TaskProxy',
    rtconfig: Dict[str, Any],
    workflow: str,
    now: Tuple[float, str]
) -> 'Literal[True]':
    """Submit a task in skip mode.

    Returns:
        True - indicating that TaskJobManager need take no further action.
    """
    itask.summary['started_time'] = now[0]
    # TODO - do we need this? I don't thing so?
    task_job_mgr._set_retry_timers(itask, rtconfig)
    itask.waiting_on_job_prep = False
    itask.submit_num += 1

    itask.platform = get_platform()
    itask.platform['name'] = RunMode.SKIP
    itask.summary['job_runner_name'] = RunMode.SKIP
    itask.tdef.run_mode = RunMode.SKIP
    task_job_mgr.task_events_mgr.process_message(
        itask, INFO, TASK_OUTPUT_SUBMITTED,
    )
    task_job_mgr.workflow_db_mgr.put_insert_task_jobs(
        itask, {
            'time_submit': now[1],
            'try_num': itask.get_try_num(),
        }
    )
    task_job_mgr.task_events_mgr.process_message(
        itask, INFO, TASK_OUTPUT_SUCCEEDED,
    )
    return True
