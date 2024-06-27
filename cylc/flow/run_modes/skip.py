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
"""Utilities supporting skip modes
"""
from logging import INFO
from typing import (
    TYPE_CHECKING, List, Set, Tuple)

from cylc.flow import LOG
from cylc.flow.exceptions import WorkflowConfigError
from cylc.flow.platforms import get_platform
from cylc.flow.task_outputs import (
    TASK_OUTPUT_SUBMITTED,
    TASK_OUTPUT_SUCCEEDED,
    TASK_OUTPUT_FAILED,
    TASK_OUTPUT_STARTED
)
from cylc.flow.task_state import RunMode

if TYPE_CHECKING:
    from cylc.flow.taskdef import TaskDef
    from cylc.flow.task_job_mgr import TaskJobManager
    from cylc.flow.task_proxy import TaskProxy
    from typing_extensions import Literal


def submit_task_job(
    task_job_mgr: 'TaskJobManager',
    itask: 'TaskProxy',
    now: Tuple[float, str]
) -> 'Literal[True]':
    """Submit a task in skip mode.

    Returns:
        True - indicating that TaskJobManager need take no further action.
    """
    itask.summary['started_time'] = now[0]
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
    for output in process_outputs(itask):
        task_job_mgr.task_events_mgr.process_message(itask, INFO, output)

    return True


def process_outputs(itask: 'TaskProxy') -> List[str]:
    """Process Skip Mode Outputs:

    * By default, all required outputs will be generated plus succeeded
      if success is optional.
    * The outputs submitted and started are always produced and do not
      need to be defined in outputs.
    * If outputs is specified and does not include either
      succeeded or failed then succeeded will be produced.

    Return:
        A list of outputs to emit.
    """
    result: List[str] = []
    conf_outputs = itask.tdef.rtconfig['skip']['outputs']

    # Remove started or submitted from our list of outputs:
    for out in get_unecessary_outputs(conf_outputs):
        conf_outputs.remove(out)

    # Always produce `submitted` output:
    result.append(TASK_OUTPUT_SUBMITTED)
    # (No need to produce `started` as this is automatically handled by
    # task event manager for jobless modes)

    # Send the rest of our outputs, unless they are succeed or failed,
    # which we hold back, to prevent warnings about pre-requisites being
    # unmet being shown because a "finished" output happens to come first.
    for message in itask.state.outputs.iter_required_messages():
        trigger = itask.state.outputs._message_to_trigger[message]
        # Send message unless it be succeeded/failed.
        if trigger in [TASK_OUTPUT_SUCCEEDED, TASK_OUTPUT_FAILED]:
            continue
        if not conf_outputs or trigger in conf_outputs:
            result.append(message)

    # Send succeeded/failed last.
    if TASK_OUTPUT_FAILED in conf_outputs:
        result.append(TASK_OUTPUT_FAILED)
    else:
        result.append(TASK_OUTPUT_SUCCEEDED)

    return result


def check_task_skip_config(tdef: 'TaskDef') -> None:
    """Ensure that skip mode configurations are sane at validation time:

    Args:
        tdef: of task

    Logs:
        * Warn that outputs need not include started and submitted as these
          are always emitted.

    Raises:
        * Error if outputs include succeeded and failed.
    """
    skip_config = tdef.rtconfig.get('skip', {})
    if not skip_config:
        return
    skip_outputs = skip_config.get('outputs', {})
    if not skip_outputs:
        return

    # Error if outputs include succeded and failed:
    if (
        TASK_OUTPUT_SUCCEEDED in skip_outputs
        and TASK_OUTPUT_FAILED in skip_outputs
    ):
        raise WorkflowConfigError(
            f'Skip mode settings for task {tdef.name} has'
            ' mutually exclusive outputs: succeeded AND failed.')
    LOG.info(f'Task {tdef.name} will be run in skip mode.')


def get_unecessary_outputs(skip_outputs: List[str]) -> Set[str]:
    """Get a list of outputs which we will always run, and don't need
    setting config.

    Examples:
        >>> this = get_unecessary_outputs
        >>> this(['foo', 'started', 'succeeded'])
        {'started'}
    """
    return {TASK_OUTPUT_SUBMITTED, TASK_OUTPUT_STARTED}.intersection(
        skip_outputs
    )
