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

from typing import Dict, Optional, Tuple, Any
import asyncio

from cylc.flow.scripts.workflow_state import WorkflowPoller
from cylc.flow.id import tokenise
from cylc.flow.exceptions import WorkflowConfigError
from cylc.flow.task_state import TASK_STATUS_SUCCEEDED


def workflow_state(
    workflow_task_id: str,
    offset: Optional[str] = None,
    flow_num: Optional[int] = 1,
    is_output: Optional[bool] = False,
    is_message: Optional[bool] = False,
    alt_cylc_run_dir: Optional[str] = None,
) -> Tuple[bool, Dict[str, Optional[str]]]:
    """Connect to a workflow DB and check a task status or output.

    If the status or output has been achieved, return {True, result}.

    Arguments:
        workflow_task_id:
            ID (workflow//point/task:selector) of the target task.
        offset:
            Offset from cycle point as an ISO8601 or integer duration,
            e.g. PT1H (1 hour) or P1 (1 integer cycle)
        flow_num:
            Flow number of the target task.
        alt_cylc_run_dir:
            Alternate cylc-run directory, e.g. for another user.

            .. note::

               This is only needed if the workflow is installed to a
               non-standard location.

    Returns:
        tuple: (satisfied, result)
        satisfied:
            True if ``satisfied`` else ``False``.
        result:
            Dict {workflow_id, task_id, task_selector, flow_number}.

    """
    poller = WorkflowPoller(
        workflow_task_id, offset, flow_num, alt_cylc_run_dir,
        TASK_STATUS_SUCCEEDED,
        is_output, is_message,
        f'"{id}"',
        '10',  # interval (irrelevant, for a single poll)
        1,  # max polls (for xtriggers the scheduler does the polling)
        [], {}
    )
    if asyncio.run(poller.poll()):
        return (
            True,
            {
                "workflow_id": poller.workflow_id,
                "task_id": f"{poller.cycle}/{poller.task}",
                "task_selector": poller.task_sel,
                "flow_number": poller.flow_num
            }
        )
    else:
        return (
            False,
            {}
        )


def validate(args: Dict[str, Any]):
    """Validate workflow_state xtrigger function args.

    * workflow_task_id: full workflow//cycle/task[:selector]
    * offset: must be a valid status
    * flow_num: must be an integer
    * alt_cylc_run_dir: must be a valid path

    """
    try:
        tokens = tokenise(args["workflow_task_id"])
    except KeyError:
        raise WorkflowConfigError(
            # TODO better message
            "Full ID needed: workflow//cycle/task[:selector].")

    if any(
        tokens[token] is None
        for token in ("workflow", "cycle", "task")
    ):
        raise WorkflowConfigError(
            "Full ID needed: workflow//cycle/task[:selector].")

    try:
        int(args["flow_num"])
    except ValueError:
        raise WorkflowConfigError("flow_num must be an integer.")


def workflow_state_backcompat(
    workflow: str,
    task: str,
    point: str,
    offset: Optional[str] = None,
    status: str = 'succeeded',
    message: Optional[str] = None,
    cylc_run_dir: Optional[str] = None
) -> Tuple[bool, Optional[Dict[str, Optional[str]]]]:
    """Back-compat wrapper for the workflow_state xtrigger.

    Note Cylc 7 DBs only stored custom task outputs, not standard ones.

    Arguments:
        workflow:
            The workflow to interrogate.
        task:
            The name of the task to query.
        point:
            The cycle point.
        offset:
            The offset between the cycle this xtrigger is used in and the one
            it is querying for as an ISO8601 time duration.
            e.g. PT1H (one hour).
        status:
            The task status required for this xtrigger to be satisfied.
        message:
            The custom task output required for this xtrigger to be satisfied.

            .. note::

               This cannot be specified in conjunction with ``status``.
        cylc_run_dir:
            Alternate cylc-run directory, e.g. for another user.

            .. note::

               This only needs to be supplied if the workflow is running in a
               different location to what is specified in the global
               configuration (usually ``~/cylc-run``).

    Returns:
        tuple: (satisfied, results)

        satisfied:
            True if ``satisfied`` else ``False``.
        results:
            Dictionary containing the args / kwargs which were provided
            to this xtrigger.

    """
    is_message = False
    workflow_task_id = f"{workflow}//{point}/{task}"
    if status is not None:
        workflow_task_id += f":{status}"
    elif message is not None:
        is_message = True
        workflow_task_id += f":{message}"

    satisfied, _results = workflow_state(
        workflow_task_id,
        offset=offset,
        is_message=is_message,
        alt_cylc_run_dir=cylc_run_dir
    )

    return (
        satisfied,
        {
            'workflow': workflow,
            'task': task,
            'point': point,
            'offset': offset,
            'status': status,
            'message': message,
            'cylc_run_dir': cylc_run_dir
        }
    )


def validate_backcompat(args: Dict[str, Any]):
    """Validate old workflow_state xtrigger function args.

    """
    args['workflow_task_id'] = (
        f"{args['workflow']}//{args['point']}/{args['task']}"
    )
    args['flow_num'] = 1
    del args['workflow']
    del args['point']
    del args['task']

    validate(args)
