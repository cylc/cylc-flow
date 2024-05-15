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
    workflow: str,  # TODO CANT CALL THIS WORKFLOW
    offset: Optional[str] = None,
    flow_num: Optional[int] = 1,
    alt_cylc_run_dir: Optional[str] = None,
) -> Tuple[bool, Dict[str, Optional[str]]]:
    """Connect to a workflow DB and check a task status or output.

    If the status or output has been achieved, return {True, result}.

    Arguments:
        workflow:
            ID of the workflow[//task] to check.
        offset:
            Interval offset from cycle point as an ISO8601 or integer duration,
            e.g. PT1H (1 hour) or P1 (1 integer cycle)
        flow_num:
            Flow number of remote task.
        alt_cylc_run_dir:
            Alternate cylc-run directory, e.g. for another user.

            .. note::

               This only needs to be supplied if the workflow is running in a
               different location to what is specified in the global
               configuration (usually ``~/cylc-run``).

    Returns:
        tuple: (satisfied, result)
        satisfied:
            True if ``satisfied`` else ``False``.
        result:
            Dictionary of the args / kwargs provided to this xtrigger.

    """
    poller = WorkflowPoller(
        workflow, offset, flow_num, alt_cylc_run_dir,
        TASK_STATUS_SUCCEEDED,
        f'"{workflow}"',
        '10',  # interval
        1,  # max polls
        args={
            "old_format": False,
            "print_outputs": False,
        }
    )
    if asyncio.run(poller.poll()):
        return (
            True,
            {
                "workflow": poller.workflow_id,
                "task": f"{poller.cycle}/{poller.task}:{poller.task_sel}",
                "flow": poller.flow_num
            }
        )
    else:
        return (
            False,
            {}
        )


def validate(args: Dict[str, Any], Err=WorkflowConfigError):
    """Validate workflow_state xtrigger function args.

    * workflow: full workflow//cycle/task[:selector]
    * flow_num: must be an integer
    * status: must be a valid status

    """
    tokens = tokenise(args["workflow"])
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
