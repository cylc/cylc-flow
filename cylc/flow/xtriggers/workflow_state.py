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
from inspect import signature

from cylc.flow.scripts.workflow_state import WorkflowPoller
from cylc.flow.id import tokenise
from cylc.flow.exceptions import WorkflowConfigError
from cylc.flow.task_state import TASK_STATUS_SUCCEEDED


def workflow_state(
    workflow_task_id: str,
    offset: Optional[str] = None,
    flow_num: Optional[int] = None,
    is_trigger: bool = False,
    is_message: bool = False,
    alt_cylc_run_dir: Optional[str] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """Connect to a workflow DB and check a task status or output.

    If the status or output has been achieved, return {True, result}.

    Args:
        workflow_task_id:
            ID (workflow//point/task:selector) of the target task.
        offset:
            Offset from cycle point as an ISO8601 or integer duration,
            e.g. PT1H (1 hour) or P1 (1 integer cycle)
        flow_num:
            Flow number of the target task.
        is_message:
            Interpret the task:selector as a task output message
            (the default is a task status or trigger)
        is_trigger:
            Interpret the task:selector as a task trigger name
            (only needed if it is also a valid status name)
        alt_cylc_run_dir:
            Alternate cylc-run directory, e.g. for another user.

    Returns:
        tuple: (satisfied, result)

        satisfied:
            True if ``satisfied`` else ``False``.
        result:
            Dict containing the keys:

            * ``workflow``
            * ``task``
            * ``point``
            * ``offset``
            * ``status``
            * ``message``
            * ``trigger``
            * ``flow_num``
            * ``run_dir``

    .. versionchanged:: 8.3.0

       The ``workflow_task_id`` argument was introduced to replace the
       separate ``workflow``, ``point``, ``task``, ``status``, and ``message``
       arguments (which are still supported for backwards compatibility).
       The ``flow_num`` argument was added. The ``cylc_run_dir`` argument
       was renamed to ``alt_cylc_run_dir``.
    """
    poller = WorkflowPoller(
        workflow_task_id,
        offset,
        flow_num,
        alt_cylc_run_dir,
        TASK_STATUS_SUCCEEDED,
        is_trigger, is_message,
        old_format=False,
        condition=workflow_task_id,
        max_polls=1,  # (for xtriggers the scheduler does the polling)
        interval=0,  # irrelevant for 1 poll
        args=[]
    )

    # NOTE the results dict item names remain compatible with older usage.

    if asyncio.run(poller.poll()):
        results = {
            'workflow': poller.workflow_id,
            'task': poller.task,
            'point': poller.cycle,
        }
        if poller.alt_cylc_run_dir is not None:
            results['cylc_run_dir'] = poller.alt_cylc_run_dir

        if offset is not None:
            results['offset'] = poller.offset

        if flow_num is not None:
            results["flow_num"] = poller.flow_num

        if poller.is_message:
            results['message'] = poller.selector
        elif poller.is_trigger:
            results['trigger'] = poller.selector
        else:
            results['status'] = poller.selector

        return (True, results)
    else:
        return (False, {})


def validate(args: Dict[str, Any]):
    """Validate workflow_state xtrigger function args.

    Arguments:
        workflow_task_id:
            full workflow//cycle/task[:selector]
        offset:
            must be a valid status
        flow_num:
            must be an integer
        alt_cylc_run_dir:
            must be a valid path

    """
    tokens = tokenise(args["workflow_task_id"])

    if any(
        tokens[token] is None
        for token in ("workflow", "cycle", "task")
    ):
        raise WorkflowConfigError(
            "Full ID needed: workflow//cycle/task[:selector].")

    if (
        args["flow_num"] is not None and
        not isinstance(args["flow_num"], int)
    ):
        raise WorkflowConfigError("flow_num must be an integer if given.")


# BACK COMPAT: workflow_state_backcompat
# from: 8.0.0
# to: 8.3.0
# remove at: 8.x
def _workflow_state_backcompat(
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

    Returns:
        tuple: (satisfied, results)

        satisfied:
            True if ``satisfied`` else ``False``.
        results:
            Dictionary containing the args / kwargs which were provided
            to this xtrigger.

    """
    args = {
        'workflow': workflow,
        'task': task,
        'point': point,
        'offset': offset,
        'status': status,
        'message': message,
        'cylc_run_dir': cylc_run_dir
    }
    upg_args = _upgrade_workflow_state_sig(args)
    satisfied, _results = workflow_state(**upg_args)

    return (satisfied, args)


# BACK COMPAT: workflow_state_backcompat
# from: 8.0.0
# to: 8.3.0
# remove at: 8.x
def _upgrade_workflow_state_sig(args: Dict[str, Any]) -> Dict[str, Any]:
    """Return upgraded args for workflow_state, given the deprecated args."""
    is_message = False
    workflow_task_id = f"{args['workflow']}//{args['point']}/{args['task']}"
    status = args.get('status')
    message = args.get('message')
    if status is not None:
        workflow_task_id += f":{status}"
    elif message is not None:
        is_message = True
        workflow_task_id += f":{message}"
    return {
        'workflow_task_id': workflow_task_id,
        'offset': args.get('offset'),
        'alt_cylc_run_dir': args.get('cylc_run_dir'),
        'is_message': is_message,
    }


# BACK COMPAT: workflow_state_backcompat
# from: 8.0.0
# to: 8.3.0
# remove at: 8.x
def _validate_backcompat(args: Dict[str, Any]):
    """Validate old workflow_state xtrigger function args.
    """
    bound_args = signature(workflow_state).bind(
        **_upgrade_workflow_state_sig(args)
    )
    bound_args.apply_defaults()
    validate(bound_args.arguments)
