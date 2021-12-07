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
"""Utilities for performing operations on multiple workflows."""

import asyncio
import fnmatch
from functools import partial
import re

from cylc.flow.async_util import unordered_map
from cylc.flow.exceptions import (
    UserInputError,
)
from cylc.flow.id import (
    contains_multiple_workflows,
    contains_task_like,
    detokenise,
    is_null,
    parse_cli,
    strip_flow,
)
from cylc.flow.network.scan import (
    filter_name,
    is_active,
    scan,
)

FN_CHARS = re.compile(r'[\*\?\[\]\!]')


def contains_fnmatch(string):
    """Return True if a string contains filename match chars.

    Examples:
        >>> contains_fnmatch('a')
        False
        >>> contains_fnmatch('*')
        True
        >>> contains_fnmatch('abc')
        False
        >>> contains_fnmatch('a*c')
        True
    """
    return bool(FN_CHARS.search(string))


async def expand_workflow_tokens(tokens):
    """Use "cylc scan" to expand workflow patterns."""
    workflow = tokens['flow']

    if not contains_fnmatch(workflow):
        # no expansion to perform
        yield False, tokens
        return

    # use cylc-scan output to filter workflows
    workflow_sel = tokens['flow_sel']
    if workflow_sel and workflow_sel != 'running':
        raise UserInputError(
            f'The workflow selector :{workflow_sel} is not'
            'currently supported.'
        )

    # construct the pipe
    pipe = scan | filter_name(fnmatch.translate(workflow)) | is_active(True)

    # iter the results
    async for flow in pipe:
        yield True, {**tokens, 'flow': flow['name']}


def call_multi(*args, **kwargs):
    """Call a function for each workflow in a list of IDs.

    See call_multi_async for arg docs.
    """
    return asyncio.run(call_multi_async(*args, **kwargs))


async def call_multi_async(
    fcn,
    *ids,
    constraint='tasks',
    report=None
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
    tokens_list = parse_cli(*ids)

    # if only one workflow is defined in the tokens we are only performing
    # one request so don't need to adjust the output format
    multi_mode = contains_multiple_workflows(tokens_list)

    if constraint not in {'tasks', 'workflows', 'mixed'}:
        raise Exception(f'Invalid constraint: {constraint}')

    if constraint == 'workflows':
        for tokens in tokens_list:
            if contains_task_like(tokens):
                raise UserInputError()

    # expand workflow patterns
    expanded_tokens_list = []
    for tokens in tokens_list:
        async for expanded, expanded_tokens in expand_workflow_tokens(tokens):
            expanded_tokens_list.append(expanded_tokens)
            if expanded:
                # one or more of the workflows were patterns
                # change the output mode (even if we are only performing
                # one request) to make it clear what we've done
                multi_mode = True

    # batch ids by workflow
    workflows = {}
    for tokens in expanded_tokens_list:
        if tokens['user']:
            raise UserInputError('Changing user not supported')
        key = tokens['flow']
        workflows.setdefault(key, []).append(strip_flow(tokens))

    # configure reporting
    if not report:
        report = _report
    if multi_mode:
        reporter = partial(report_multi, report)
    else:
        reporter = partial(report_single, report)

    # run coros
    results = []

    async for (workflow, *_), result in unordered_map(
        fcn,
        (
            (
                workflow,
                *_get_call_ids(workflow, ids, constraint)
            )
            for workflow, ids in workflows.items()
        ),
    ):
        reporter(workflow, result)
        results.append(result)
    return results


def report_multi(report, workflow, result):
    print(workflow)
    report(result)


def report_single(report, workflow, result):
    report(result)


def _report(_):
    print('Done')


def _get_call_ids(workflow, ids, constraint):
    """Return the ids for calling the function with."""
    if constraint == 'workflows':
        # no internal IDs for working with workflows
        call_ids = []
    elif constraint == 'tasks':
        for id_ in ids:
            if not contains_task_like(id_):
                raise UserInputError(
                    # TODO: rephrase
                    f'ID must define an object within workflow: {workflow}'
                )
        call_ids = [
            detokenise(id_, relative=True)
            for id_ in ids
        ]
    elif constraint == 'mixed':
        call_ids = [
            id_
            for id_ in ids
            if not is_null(id_)
        ]
    return call_ids
