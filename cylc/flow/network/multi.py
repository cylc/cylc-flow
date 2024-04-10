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

import asyncio
from functools import partial

from cylc.flow.async_util import unordered_map
from cylc.flow.id_cli import parse_ids_async
from cylc.flow.exceptions import InputError


def print_response(multi_results):
    """Print server mutation response to stdout.

    The response will be either:
        - (False, argument-validation-error)
        - (True, ID-of-queued-command)

    Raise InputError if validation failed.

    """
    for multi_result in multi_results:
        for _cmd, results in multi_result.items():
            for result in results.values():
                for wf_res in result:
                    wf_id = wf_res["id"]
                    response = wf_res["response"]
                    if not response[0]:
                        # Validation failure
                        raise InputError(response[1])
                    else:
                        print(f"{wf_id}: command {response[1]} queued")


def call_multi(*args, **kwargs):
    """Call a function for each workflow in a list of IDs.

    See call_multi_async for arg docs.
    """
    return asyncio.run(call_multi_async(*args, **kwargs))


async def call_multi_async(
    fcn,
    *ids,
    constraint='tasks',
    report=None,
    max_workflows=None,
    max_tasks=None,
):
    """Call a function for each workflow in a list of IDs.

    Args:
        fcn:
            The function to call for each workflow.
        ids:
            The list of universal identifiers to parse.
        constraint:
            The type of objects IDs must identify.

            tasks:
                For task-like objects i.e. cycles/tasks/jobs.
            workflow:
                For workflow-like objects i.e. [user/]workflows.
            mixed:
                No constraint.
        report:
            Override the default stdout output.
            This function is provided with the return value of fcn.

    """
    # parse ids
    workflow_args, multi_mode = await parse_ids_async(
        *ids,
        src=False,
        constraint=constraint,
        max_workflows=max_workflows,
        max_tasks=max_tasks,
        match_workflows=True,
    )

    # configure reporting
    if not report:
        report = _report
    if multi_mode:
        reporter = partial(_report_multi, report)
    else:
        reporter = partial(_report_single, report)

    if constraint == 'workflows':
        # TODO: this is silly, just standardise the responses
        workflow_args = {
            workflow_id: []
            for workflow_id in workflow_args
        }

    # run coros
    results = []
    async for (workflow_id, *args), result in unordered_map(
        fcn,
        (
            (workflow_id, *args)
            for workflow_id, args in workflow_args.items()
        ),
    ):
        reporter(workflow_id, result)
        results.append(result)
    return results


def _report_multi(report, workflow, result):
    print(workflow)
    report(result)


def _report_single(report, workflow, result):
    report(result)


def _report(_):
    pass
