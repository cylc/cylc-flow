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

"""Cylc univeral identifier system for referencing Cylc "objets".

This module contains the implementations for parsing IDs parsed in
by users on the CLI.
"""

import asyncio
import fnmatch
from functools import partial
import os
from pathlib import Path
import re
from typing import Tuple

from cylc.flow.async_util import unordered_map
from cylc.flow.exceptions import (
    UserInputError,
    WorkflowFilesError,
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
from cylc.flow.workflow_files import (
    _parse_src_reg,
    check_deprecation,
    detect_both_flow_and_suite,
    get_workflow_run_dir,
    infer_latest_run,
    validate_workflow_name,
)

FN_CHARS = re.compile(r'[\*\?\[\]\!]')


def parse_id(id_, constraint='workflows', src=False, warn_depr=True):
    tokens = parse_cli(id_)[0]
    if tokens['user']:
        raise UserInputError()
    if tokens['flow_sel']:
        raise UserInputError()

    return _parse_id(tokens['flow'], src=src, warn_depr=warn_depr)


async def parse_ids(
    *ids,
    constraint='tasks',
):
    """Call a function for each workflow in a list of IDs.

    Args:
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
        async for expanded, expanded_tokens in _expand_workflow_tokens(tokens):
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
        key, _ = _parse_id(tokens['flow'], src=False, warn_depr=False)
        workflows.setdefault(key, []).append(strip_flow(tokens))

    return (
        {
            workflow_id: _get_call_ids(workflow_id, ids, constraint)
            for workflow_id, ids in workflows.items()
        },
        multi_mode,
    )


async def call_multi_async(
    fcn,
    *ids,
    constraint='tasks',
    report=None,
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
    workflow_args, multi_mode = await parse_ids(*ids, constraint=constraint)

    # configure reporting
    if not report:
        report = _report
    if multi_mode:
        reporter = partial(_report_multi, report)
    else:
        reporter = partial(_report_single, report)

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


def call_multi(*args, **kwargs):
    """Call a function for each workflow in a list of IDs.

    See call_multi_async for arg docs.
    """
    return asyncio.run(call_multi_async(*args, **kwargs))


def _parse_id(reg: str, src: bool = False, warn_depr=True) -> Tuple[str, Path]:
    """Centralised parsing of the workflow argument, to be used by most
    cylc commands (script modules).

    Infers the latest numbered run if a specific one is not given (e.g.
    foo -> foo/run3, foo/runN -> foo/run3).

    "Offline" commands (e.g. cylc validate) can usually be used on
    workflow sources so will need src = True.

    "Online" commands (e.g. cylc stop) are usually only used on workflows in
    the cylc-run dir so will need src = False.

    Args:
        reg: The workflow arg. Can be one of:
            - relative path to the run dir from ~/cylc-run, i.e. the "name"
                of the workflow;
            - absolute path to a run dir, source dir or workflow file (only
                if src is True);
            - '.' for the current directory (only if src is True).
        src: Whether the workflow arg can be a workflow source (i.e. an
            absolute path (which might not be in ~/cylc-run) and/or a
            flow.cylc file (or any file really), or '.' for cwd).

    Returns:
        reg: The normalised workflow arg.
        path: If src is True, the absolute path to the workflow file
            (flow.cylc or suite.rc). Otherwise, the absolute path to the
            workflow run dir.
    """
    if src:
        # starts with './'
        cur_dir_only = reg.startswith(f'{os.curdir}{os.sep}')
        reg, abs_path = _parse_src_reg(reg, cur_dir_only)
    else:
        validate_workflow_name(reg)
        abs_path = Path(get_workflow_run_dir(reg))
        if abs_path.is_file():
            raise WorkflowFilesError(
                "Workflow name must refer to a directory, "
                f"but '{reg}' is a file."
            )
        abs_path, reg = infer_latest_run(abs_path)
    detect_both_flow_and_suite(abs_path)
    # TODO check_deprecation?
    check_deprecation(abs_path, warn=warn_depr)
    return (str(reg), abs_path)


def _contains_fnmatch(string):
    """Return True if a string contains filename match chars.

    Examples:
        >>> _contains_fnmatch('a')
        False
        >>> _contains_fnmatch('*')
        True
        >>> _contains_fnmatch('abc')
        False
        >>> _contains_fnmatch('a*c')
        True
    """
    return bool(FN_CHARS.search(string))


async def _expand_workflow_tokens(tokens):
    """Use "cylc scan" to expand workflow patterns."""
    workflow = tokens['flow']

    if not _contains_fnmatch(workflow):
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


def _report_multi(report, workflow, result):
    print(workflow)
    report(result)


def _report_single(report, workflow, result):
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
