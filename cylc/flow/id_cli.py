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

# TODO: move check_deprecation into the relevant scripts

# TODO changes:
# * src paths must start "./" or be absolte
#   * remove ambigious name check (no longer needed)
# * run paths cannot be absolute (use the workflow ID)
#   * no infering latest runs for paths (no longer needed)

import asyncio
import fnmatch
import os
from pathlib import Path
import re
from typing import Optional, Dict, List, Tuple, Any

from cylc.flow.exceptions import (
    UserInputError,
    WorkflowFilesError,
)
from cylc.flow.id import (
    TokensDict,
    contains_multiple_workflows,
    contains_task_like,
    detokenise,
    is_null,
    parse_cli,
    strip_workflow,
)
from cylc.flow.network.scan import (
    filter_name,
    is_active,
    scan,
)
from cylc.flow.workflow_files import (
    NO_FLOW_FILE_MSG,
    # check_deprecation,  TODO?
    check_flow_file,
    detect_both_flow_and_suite,
    get_flow_file,
    get_workflow_run_dir,
    infer_latest_run_from_id,
    validate_workflow_name,
)

FN_CHARS = re.compile(r'[\*\?\[\]\!]')


def parse_ids(*args, **kwargs):
    return asyncio.run(parse_ids_async(*args, **kwargs))


async def parse_ids_async(
    *ids: str,
    src: bool = False,
    match_workflows: bool = False,
    constraint: str = 'tasks',
    max_workflows: Optional[int] = None,
    max_tasks: Optional[int] = None,
) -> Tuple[Dict[str, List[TokensDict]], Any]:
    """Parse IDs from the command line.

    Args:
        ids:
            Collection of IDs to parse.
        src:
            If True then source workflows can be provided via an absolute
            path or a relative path starting "./".
            Infers max_workflows = 1.
        match_workflows:
            If True workflows can be globs.
        constraint:
            Constrain the types of objects the IDs should relate to.

            workflows - only allow workflows.
            tasks - require tasks to be defined.
            mixed - permit tasks not to be defined.
        max_workflows:
            Specify the maximum number of workflows permitted to be specified
            in the ids.
        max_tasks:
            Specify the maximum number of tasks permitted to be specified
            in the ids.

    """
    tokens_list = []
    src_path = None
    flow_file_path = None
    multi_mode = False

    if src:
        # can only have one workflow if permitting source workflows
        max_workflows = 1
        ret = _parse_src_path(ids[0])
        if ret:
            # yes, replace the path with an ID and continue
            workflow_id, src_path, flow_file_path = ret
            ids = (
                detokenise({
                    'user': None,
                    'workflow': workflow_id,
                }) + '//',
                *ids[1:]
            )

    tokens_list.extend(parse_cli(*ids))

    if constraint not in {'tasks', 'workflows', 'mixed'}:
        raise Exception(f'Invalid constraint: {constraint}')

    # ensure the IDS are compatible with the constraint
    _validate_constraint(*tokens_list, constraint=constraint)

    if match_workflows:
        # match workflow IDs via cylc-scan
        # if any patterns are present switch to multi_mode for clarity
        multi_mode = await _expand_workflow_tokens(tokens_list)

    # check the workflow part of the IDs are vaild
    _validate_workflow_ids(*tokens_list, src_path=src_path)

    if not multi_mode:
        # check how many workflows we are working on
        multi_mode = contains_multiple_workflows(tokens_list)

    # infer the run number if not specified the ID (and if possible)
    _infer_latest_runs(*tokens_list, src_path=src_path)

    _validate_number(
        *tokens_list,
        max_workflows=max_workflows,
        max_tasks=max_tasks,
    )

    workflows = _batch_tokens_by_workflow(*tokens_list, constraint=constraint)

    if src:
        if not flow_file_path:
            # get the workflow file path from the run dir
            flow_file_path = get_flow_file(list(workflows)[0])
        return workflows, flow_file_path
    return workflows, multi_mode


def parse_id(*args, **kwargs):
    return asyncio.run(parse_id_async(*args, **kwargs))


async def parse_id_async(
    *args,
    **kwargs,
) -> Tuple[str, Optional[TokensDict], Any]:
    """Special case of parse_ids with a more convient return format.

    Infers:
        max_workflows: 1
        max_tasks: 1

    """
    workflows, ret = await parse_ids_async(
        *args,
        **{  # type: ignore
            **kwargs,
            'max_workflows': 1,
            'max_tasks': 1,
        },
    )
    workflow_id = list(workflows)[0]
    tokens_list = workflows[workflow_id]
    tokens: Optional[TokensDict]
    if tokens_list:
        tokens = tokens_list[0]
    else:
        tokens = None
    return workflow_id, tokens, ret


def contains_fnmatch(string: str) -> bool:
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


def _validate_constraint(*tokens_list, constraint=None):
    if constraint == 'workflows':
        for tokens in tokens_list:
            if contains_task_like(tokens):
                raise UserInputError()  # TODO
        return
    if constraint == 'tasks':
        for tokens in tokens_list:
            if not contains_task_like(tokens):
                raise UserInputError()  # TODO
        return
    if constraint == 'mixed':
        for tokens in tokens_list:
            if is_null(tokens):
                raise UserInputError()  # TODO
        return
    raise Exception(f'Invalid constraint: {constraint}')


def _validate_workflow_ids(*tokens_list, src_path):
    for ind, tokens in enumerate(tokens_list):
        if tokens['user']:
            raise UserInputError(
                'Operating on others workflows is not supported'
            )
        validate_workflow_name(tokens['workflow'])
        if ind == 0 and src_path:
            # source workflow passed in as a path
            pass
        else:
            src_path = Path(get_workflow_run_dir(tokens['workflow']))
        # if not src_path.exists():
        #     raise UserInputError()  # TODO ???
        if src_path.is_file():
            raise UserInputError(
                f'Workflow ID cannot be a file: {tokens["workflow"]}'
            )
        detect_both_flow_and_suite(src_path)


def _infer_latest_runs(*tokens_list, src_path):
    for ind, tokens in enumerate(tokens_list):
        if ind == 0 and src_path:
            # source workflow passed in as a path
            continue
        tokens['workflow'] = infer_latest_run_from_id(tokens['workflow'])
        pass


def _validate_number(*tokens_list, max_workflows=None, max_tasks=None):
    if not max_workflows and not max_tasks:
        return
    workflows_count = 0
    tasks_count = 0
    for tokens in tokens_list:
        if contains_task_like(tokens):
            tasks_count += 1
        else:
            workflows_count += 1
    if max_workflows and workflows_count > max_workflows:
        raise UserInputError()  # TODO
    if max_tasks and tasks_count > max_tasks:
        raise UserInputError()  # TODO


def _batch_tokens_by_workflow(*tokens_list, constraint=None):
    """Sorts tokens into lists by workflow ID.

    Example:
        >>> _batch_tokens_by_workflow(
        ...     {'workflow': 'x', 'cycle': '1'},
        ...     {'workflow': 'x', 'cycle': '2'},
        ... )
        {'x': [{'cycle': '1'}, {'cycle': '2'}]}

    """
    workflow_tokens = {}
    for tokens in tokens_list:
        w_tokens = workflow_tokens.setdefault(tokens['workflow'], [])
        relative_tokens = strip_workflow(tokens)
        if constraint == 'mixed' and is_null(relative_tokens):
            continue
        w_tokens.append(relative_tokens)
    return workflow_tokens


async def _expand_workflow_tokens(tokens_list):
    multi_mode = False
    for tokens in list(tokens_list):
        workflow = tokens['workflow']
        if not contains_fnmatch(workflow):
            # no expansion to perform
            continue
        else:
            # remove the original entry
            multi_mode = True
            tokens_list.remove(tokens)
            async for tokens in _expand_workflow_tokens_impl(tokens):
                # add the expanded tokens back onto the list
                # TODO: insert into the same location to preserve order?
                tokens_list.append(tokens)
    return multi_mode


async def _expand_workflow_tokens_impl(tokens):
    """Use "cylc scan" to expand workflow patterns."""
    workflow_sel = tokens['workflow_sel']
    if workflow_sel and workflow_sel != 'running':
        raise UserInputError(
            f'The workflow selector :{workflow_sel} is not'
            'currently supported.'
        )

    # construct the pipe
    pipe = (
        scan
        | filter_name(fnmatch.translate(tokens['workflow']))
        | is_active(True)
    )

    # iter the results
    async for workflow in pipe:
        yield {**tokens, 'workflow': workflow['name']}


def _parse_src_path(id_):
    src_path = Path(id_)
    if (
        id_.startswith(f'{os.curdir}{os.sep}')
        or Path(id_).is_absolute()
    ):
        src_path.resolve()
        if not src_path.exists():
            raise UserInputError(src_path)
        if src_path.name == 'flow.cylc':  # TODO constantize
            src_path = src_path.parent
        try:
            src_file_path = check_flow_file(src_path)
        except WorkflowFilesError:
            raise WorkflowFilesError(NO_FLOW_FILE_MSG.format(id_))
        workflow_id = src_path.name
        return workflow_id, src_path, src_file_path
    return None
