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
    TYPE_CHECKING,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
)

from cylc.flow import LOG
from cylc.flow.exceptions import WorkflowConfigError
from cylc.flow.run_modes import RunMode
from cylc.flow.task_outputs import (
    TASK_OUTPUT_FAILED,
    TASK_OUTPUT_STARTED,
    TASK_OUTPUT_SUBMITTED,
    TASK_OUTPUT_SUCCEEDED,
)


if TYPE_CHECKING:
    # BACK COMPAT: typing_extensions.Literal
    # FROM: Python 3.7
    # TO: Python 3.8
    from typing_extensions import Literal

    from cylc.flow.task_job_mgr import TaskJobManager
    from cylc.flow.task_proxy import TaskProxy
    from cylc.flow.taskdef import TaskDef


def submit_task_job(
    task_job_mgr: 'TaskJobManager',
    itask: 'TaskProxy',
    rtconfig: Dict,
    now: Tuple[float, str]
) -> 'Literal[True]':
    """Submit a task in skip mode.

    Returns:
        True - indicating that TaskJobManager need take no further action.
    """
    task_job_mgr._set_retry_timers(itask, rtconfig)
    itask.summary['started_time'] = now[0]
    itask.waiting_on_job_prep = False
    itask.submit_num += 1

    itask.platform = {
        'name': RunMode.SKIP.value,
        'install target': 'localhost',
        'hosts': ['localhost'],
        'disable task event handlers':
            rtconfig['skip']['disable task event handlers'],
        'execution polling intervals': [],
        'submission retry delays': [],
        'execution retry delays': []
    }
    itask.summary['job_runner_name'] = RunMode.SKIP.value
    itask.jobs.append(
        task_job_mgr.get_simulation_job_conf(itask)
    )
    itask.run_mode = RunMode.SKIP
    task_job_mgr.workflow_db_mgr.put_insert_task_jobs(
        itask, {
            'time_submit': now[1],
            'try_num': itask.get_try_num(),
            'flow_nums': str(list(itask.flow_nums)),
            'is_manual_submit': itask.is_manual_submit,
            'job_runner_name': RunMode.SKIP.value,
            'platform_name': RunMode.SKIP.value,
            'submit_status': 0   # Submission has succeeded
        }
    )
    task_job_mgr.workflow_db_mgr.put_update_task_state(itask)
    for output in sorted(
        process_outputs(itask, rtconfig),
        key=itask.state.outputs.output_sort_key,
    ):
        task_job_mgr.task_events_mgr.process_message(itask, INFO, output)

    return True


def process_outputs(
    itask: 'TaskProxy', rtconfig: Optional[dict] = None
) -> Set[str]:
    """Process Skip Mode Outputs:

    * By default, all required outputs will be generated plus succeeded
      if success is optional.
    * The outputs submitted and started are always produced and do not
      need to be defined in outputs.
    * If outputs is specified and does not include either
      succeeded or failed then succeeded will be produced.

    Return:
        A set of outputs to emit.

    """
    # Always produce `submitted` & `started` outputs first:
    result: Set[str] = {TASK_OUTPUT_SUBMITTED, TASK_OUTPUT_STARTED}

    conf_outputs = list(rtconfig['skip']['outputs']) if rtconfig else []

    # Send the rest of our outputs, unless they are succeeded or failed,
    # which we hold back, to prevent warnings about pre-requisites being
    # unmet being shown because a "finished" output happens to come first.
    for message in itask.state.outputs.iter_required_messages(
        disable=(
            TASK_OUTPUT_SUCCEEDED
            if TASK_OUTPUT_FAILED in conf_outputs
            else TASK_OUTPUT_FAILED
        )
    ):
        trigger = itask.state.outputs._message_to_trigger[message]
        # Send message unless it be succeeded/failed.
        if (
            trigger not in {TASK_OUTPUT_SUCCEEDED, TASK_OUTPUT_FAILED}
            and (not conf_outputs or trigger in conf_outputs)
        ):
            result.add(message)

    # Add optional outputs specified in skip settings:
    result.update(
        message
        for message, trigger in itask.state.outputs._message_to_trigger.items()
        if trigger in conf_outputs
    )

    if TASK_OUTPUT_FAILED in conf_outputs:
        result.add(TASK_OUTPUT_FAILED)
    else:
        result.add(TASK_OUTPUT_SUCCEEDED)

    return result


def check_task_skip_config(tdef: 'TaskDef') -> None:
    """Validate Skip Mode configuration.

    Raises:
        * Error if outputs include succeeded and failed.
    """
    skip_outputs = tdef.rtconfig.get('skip', {}).get('outputs', {})
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


def skip_mode_validate(taskdefs: 'Dict[str, TaskDef]') -> None:
    """Warn user if any tasks have "run mode" set to skip.
    """
    skip_mode_tasks: List[str] = []
    for taskdef in taskdefs.values():
        if (taskdef.rtconfig.get('run mode', None) == RunMode.SKIP.value):
            skip_mode_tasks.append(taskdef.name)

            # Run any mode specific validation checks:
            check_task_skip_config(taskdef)

    if skip_mode_tasks:
        message = 'The following tasks are set to run in skip mode:'
        for taskname in skip_mode_tasks:
            message += f'\n    * {taskname}'
        LOG.info(message)
