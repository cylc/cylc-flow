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
    NO_FLOW_FILE_MSG,
    check_deprecation,
    check_flow_file,
    detect_both_flow_and_suite,
    get_workflow_run_dir,
    infer_latest_run,
    validate_workflow_name,
)

FN_CHARS = re.compile(r'[\*\?\[\]\!]')


def parse_ids(*args, **kwargs):
    return asyncio.run(parse_ids_async(*args, **kwargs))


async def parse_ids_async(
    *ids,
    src=False,
    match_workflows=False,
    constraint='tasks',
    max_workflows=None,
    max_tasks=None,
):
    tokens_list = []
    src_path = None
    src_file_path = None
    multi_mode = False

    if src:
        max_workflows = 1
        ret = _parse_src_path(ids[0])
        if ret:
            # yes, replace the path with an ID and continue
            workflow_id, src_path, src_file_path = ret
            ids = (
                detokenise({
                    'user': None,
                    'flow': workflow_id
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

    _validate_number(*tokens_list, max_workflows=max_workflows, max_tasks=max_tasks)

    if constraint == 'workflows':
        ret = []
        for tokens in tokens_list:
            # detokenise, but remove duplicates
            id_ = detokenise(tokens)
            if id_ not in ret:
                ret.append(id_)
    elif constraint in ('tasks', 'mixed'):
        ret = _batch_tokens_by_workflow(*tokens_list, constraint=constraint)

    if src:
        return ret[0], src_file_path
    return ret, multi_mode


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
            raise UserInputError('Operating on others workflows is not supported')  # TODO
        validate_workflow_name(tokens['flow'])
        if ind == 0 and src_path:
            # source workflow passed in as a path
            pass
        else:
            src_path = Path(get_workflow_run_dir(tokens['flow']))
        if not src_path.exists():
            raise UserInputError()  # TODO ???
        if src_path.is_file():
            raise UserInputError(f'Workflow ID cannot be a file: {tokens["flow"]}')
        detect_both_flow_and_suite(src_path)


def _infer_latest_runs(*tokens_list, src_path):
    for ind, tokens in enumerate(tokens_list):
        if ind == 0 and src_path:
            # source workflow passed in as a path
            continue
        # TODO: infer_latest_run is expecting a path not an ID
        # infer_latest_run(tokens['flow'])
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
        ...     {'flow': 'x', 'cycle': '1'},
        ...     {'flow': 'x', 'cycle': '2'},
        ... )
        {'x': [{'cycle': '1'}, {'cycle': '2'}]}

    """
    workflow_tokens = {}
    for tokens in tokens_list:
        w_tokens = workflow_tokens.setdefault(tokens['flow'], [])
        relative_tokens = strip_flow(tokens)
        if constraint == 'mixed' and is_null(relative_tokens):
            continue
        w_tokens.append(relative_tokens)
    return workflow_tokens


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


async def _expand_workflow_tokens(tokens_list):
    multi_mode = False
    for tokens in list(tokens_list):
        workflow = tokens['flow']
        if not _contains_fnmatch(workflow):
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
    workflow_sel = tokens['flow_sel']
    if workflow_sel and workflow_sel != 'running':
        raise UserInputError(
            f'The workflow selector :{workflow_sel} is not'
            'currently supported.'
        )

    # construct the pipe
    pipe = scan | filter_name(fnmatch.translate(tokens['flow'])) | is_active(True)

    # iter the results
    async for flow in pipe:
        yield {**tokens, 'flow': flow['name']}


# changes:
# * src paths must start "./" or be absolte
#   * remove ambigious name check (no longer needed)
# * run paths cannot be absolute (use the workflow ID)
#   * no infering latest runs for paths (no longer needed)


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


import os
import pytest


@pytest.fixture(scope='module')
def abc_src_dir(tmp_path_factory):
    cwd_before = Path.cwd()
    tmp_path = tmp_path_factory.getbasetemp()
    os.chdir(tmp_path)
    for name in ('a', 'b', 'c'):
        Path(tmp_path, name).mkdir()
        Path(tmp_path, name, 'flow.cylc').touch()  # TODO: const
    yield tmp_path
    os.chdir(cwd_before)


@pytest.mark.parametrize(
    'ids_in,ids_out',
    [
        (('a//',), ['a']),
        (('a//', 'a//'), ['a']),
        (('a//', 'b//'), ['a', 'b']),
    ]
)
async def test_parse_ids_workflows(ids_in, ids_out):
    ret = await parse_ids_async(*ids_in, constraint='workflows')
    assert ret[0] == ids_out


@pytest.mark.parametrize(
    'ids_in,ids_out',
    [
        (('./a',), ['a']),
    ]
)
async def test_parse_ids_workflows_src(ids_in, ids_out, abc_src_dir):
    ret = await parse_ids_async(*ids_in, constraint='workflows', src=True)
    assert ret[0] == ids_out


@pytest.mark.parametrize(
    'ids_in,ids_out',
    [
        (
            ('a//i',),
            {'a': ['//i']},
        ),
        (
            ('a//i', 'a//j'),
            {'a': ['//i', '//j']},
        ),
        (
            ('a//i', 'b//i'),
            {'a': ['//i'], 'b': ['//i']},
        ),
        (
            ('a//', '//i', 'b//', '//i'),
            {'a': ['//i'], 'b': ['//i']},
        ),
    ]
)
async def test_parse_ids_tasks(ids_in, ids_out):
    ret = await parse_ids_async(*ids_in, constraint='tasks')
    assert {
        workflow_id: [detokenise(tokens) for tokens in tokens_list]
        for workflow_id, tokens_list in ret[0].items()
    } == ids_out


@pytest.mark.parametrize(
    'ids_in,ids_out',
    [
        (
            ('./a', '//i'),
            {'a': ['//i']}
        ),
        (
            ('./a', '//i', '//j', '//k'),
            {'a': ['//i', '//j', '//k']}
        ),
    ]
)
async def test_parse_ids_tasks_src(ids_in, ids_out, abc_src_dir):
    ret = await parse_ids_async(*ids_in, constraint='tasks', src=True)
    assert {
        workflow_id: [detokenise(tokens) for tokens in tokens_list]
        for workflow_id, tokens_list in ret[0].items()
    } == ids_out


@pytest.mark.parametrize(
    'ids_in,ids_out',
    [
        (('a//',), {'a': []}),
        (
            ('a//', 'b//', 'c//'),
            {'a': [], 'b': [], 'c': []}
        ),
        (('a//i',), {'a': ['//i']}),
        (('a//', '//i'), {'a': ['//i']}),
        (
            ('a//', '//i', '//j', '//k'),
            {'a': ['//i', '//j', '//k']},
        ),
        (('a//', '//i', 'b//'), {'a': ['//i'], 'b': []}),
    ]
)
async def test_parse_ids_mixed(ids_in, ids_out):
    ret = await parse_ids_async(*ids_in, constraint='mixed')
    assert {
        workflow_id: [detokenise(tokens) for tokens in tokens_list]
        for workflow_id, tokens_list in ret[0].items()
    } == ids_out


@pytest.mark.parametrize(
    'ids_in,ids_out',
    [
        (('./a',), {'a': []}),
        (('./a', '//i'), {'a': ['//i']}),
        (('./a', '//i', '//j', '//k'), {'a': ['//i', '//j', '//k']}),
        (('./a', 'b//'), {'a': [], 'b': []}),  # TODO (debatable)
    ]
)
async def test_parse_ids_mixed_src(ids_in, ids_out, abc_src_dir):
    ret = await parse_ids_async(*ids_in, constraint='mixed', src=True)
    assert {
        workflow_id: [detokenise(tokens) for tokens in tokens_list]
        for workflow_id, tokens_list in ret[0].items()
    } == ids_out


@pytest.mark.parametrize(
    'ids_in,errors',
    [
        (('a//',), False),
        (('a//', 'b//'), False),
        (('a//', 'b//', 'c//'), True),
    ]
)
async def test_parse_ids_max_workflows(ids_in, errors):
    try:
        await parse_ids_async(*ids_in, constraint='workflows', max_workflows=2)
    except UserInputError:
        if not errors:
            raise
    else:
        if errors:
            raise Exception('Should have raised UserInputError')


@pytest.mark.parametrize(
    'ids_in,errors',
    [
        (('a//', '//i'), False),
        (('a//', '//i', '//j'), False),
        (('a//', '//i', '//j', '//k'), True),
    ]
)
async def test_parse_ids_max_tasks(ids_in, errors):
    try:
        await parse_ids_async(*ids_in, constraint='tasks', max_tasks=2)
    except UserInputError:
        if not errors:
            raise
    else:
        if errors:
            raise Exception('Should have raised UserInputError')
