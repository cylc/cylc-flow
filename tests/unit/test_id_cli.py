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

import os
from pathlib import Path
import pytest

from cylc.flow.exceptions import UserInputError, WorkflowFilesError
from cylc.flow.id import detokenise
from cylc.flow.id_cli import parse_ids_async, _parse_src_path


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
    workflows, _ = await parse_ids_async(*ids_in, constraint='workflows')
    assert list(workflows) == ids_out
    assert list(workflows.values()) == [[] for _ in workflows]


@pytest.mark.parametrize(
    'ids_in,ids_out',
    [
        (('./a',), ['a']),
    ]
)
async def test_parse_ids_workflows_src(ids_in, ids_out, abc_src_dir):
    workflows, _ = await parse_ids_async(
        *ids_in,
        src=True,
        constraint='workflows',
    )
    assert list(workflows) == ids_out
    assert list(workflows.values()) == [[] for _ in workflows]


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
    workflows, _ = await parse_ids_async(*ids_in, constraint='tasks')
    assert {
        workflow_id: [detokenise(tokens) for tokens in tokens_list]
        for workflow_id, tokens_list in workflows.items()
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
    workflows, _ = await parse_ids_async(*ids_in, constraint='tasks', src=True)
    assert {
        workflow_id: [detokenise(tokens) for tokens in tokens_list]
        for workflow_id, tokens_list in workflows.items()
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
    workflows, _ = await parse_ids_async(*ids_in, constraint='mixed')
    assert {
        workflow_id: [detokenise(tokens) for tokens in tokens_list]
        for workflow_id, tokens_list in workflows.items()
    } == ids_out


@pytest.mark.parametrize(
    'ids_in,ids_out',
    [
        (('./a',), {'a': []}),
        (('./a', '//i'), {'a': ['//i']}),
        (('./a', '//i', '//j', '//k'), {'a': ['//i', '//j', '//k']}),
        # (('./a', 'b//'), {'a': [], 'b': []}),  # TODO (debatable)
    ]
)
async def test_parse_ids_mixed_src(ids_in, ids_out, abc_src_dir):
    workflows, _ = await parse_ids_async(*ids_in, constraint='mixed', src=True)
    assert {
        workflow_id: [detokenise(tokens) for tokens in tokens_list]
        for workflow_id, tokens_list in workflows.items()
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


async def test_parse_ids_infer_run_name(tmp_run_dir):
    # it doesn't do anything for a named run
    tmp_run_dir('foo', named=True)
    workflows, *_ = await parse_ids_async('foo//', constraint='workflows')
    assert list(workflows) == ['foo']

    # it correctly identifies the latest run
    tmp_run_dir('bar/run1')
    workflows, *_ = await parse_ids_async('bar//', constraint='workflows')
    assert list(workflows) == ['bar/run1']
    tmp_run_dir('bar/run2')
    workflows, *_ = await parse_ids_async('bar//', constraint='workflows')
    assert list(workflows) == ['bar/run2']

    # it leaves the ID alone if infer_latest_runs = False
    workflows, *_ = await parse_ids_async(
        'bar//',
        constraint='workflows',
        infer_latest_runs=False,
    )
    assert list(workflows) == ['bar']


@pytest.fixture
def patch_expand_workflow_tokens(monkeypatch):

    def _patch_expand_workflow_tokens(_ids):

        async def _expand_workflow_tokens_impl(tokens, match_active=True):
            nonlocal _ids
            for id_ in _ids:
                yield {**tokens, 'workflow': id_}

        monkeypatch.setattr(
            'cylc.flow.id_cli._expand_workflow_tokens_impl',
            _expand_workflow_tokens_impl,
        )

    _patch_expand_workflow_tokens(['xxx'])
    return _patch_expand_workflow_tokens


@pytest.mark.parametrize(
    'ids_in,ids_out,multi_mode',
    [
        # multi mode should be True if multiple workflows are defined
        (['a//'], ['a'], False),
        (['a//', 'b//'], ['a', 'b'], True),
        # or if pattern matching is used, irrespective of the number of matches
        (['*//'], ['xxx'], True),
    ]
)
async def test_parse_ids_multi_mode(
    patch_expand_workflow_tokens,
    ids_in,
    ids_out,
    multi_mode,
):
    workflows, _multi_mode = await parse_ids_async(
        *ids_in,
        constraint='workflows',
        match_workflows=True,
    )
    assert list(workflows) == ids_out
    assert _multi_mode == multi_mode


@pytest.fixture
def src_dir(tmp_path):
    src_dir = (tmp_path / 'a')
    src_dir.mkdir()
    src_file = src_dir / 'flow.cylc'
    src_file.touch()
    os.chdir(tmp_path)
    yield src_dir


def test_parse_src_path(src_dir):
    # valid absolute path
    workflow_id, src_path, src_file_path = _parse_src_path(
        str(src_dir.resolve())
    )
    assert workflow_id == 'a'
    assert src_path == src_dir
    assert src_file_path == src_dir / 'flow.cylc'

    # broken absolute path
    with pytest.raises(UserInputError):
        workflow_id, src_path, src_file_path = _parse_src_path(
            str(src_dir.resolve()) + 'xyz'
        )

    # valid relative path
    workflow_id, src_path, src_file_path = _parse_src_path('./a')
    assert workflow_id == 'a'
    assert src_path == src_dir
    assert src_file_path == src_dir / 'flow.cylc'

    # broken relative path
    with pytest.raises(WorkflowFilesError):
        _parse_src_path('.')

    # relative '.' (invalid)
    with pytest.raises(WorkflowFilesError) as exc_ctx:
        workflow_id, src_path, src_file_path = _parse_src_path('.')
    assert 'No flow.cylc or suite.rc in .' in str(exc_ctx.value)

    # move into the src dir
    os.chdir(src_dir)

    # relative '.' (valid)
    workflow_id, src_path, src_file_path = _parse_src_path('.')
    assert workflow_id == 'a'
    assert src_path == src_dir
    assert src_file_path == src_dir / 'flow.cylc'

    # relative './<flow-file>'
    workflow_id, src_path, src_file_path = _parse_src_path('./flow.cylc')
    assert workflow_id == 'a'
    assert src_path == src_dir
    assert src_file_path == src_dir / 'flow.cylc'


async def test_parse_ids_src_path(src_dir):
    workflows, src_path = await parse_ids_async(
        './a',
        src=True,
        constraint='workflows',
    )
    assert workflows == {'a': []}


@pytest.mark.parametrize(
    'ids_in,error_msg',
    [
        (
            ['/home/me/whatever'],
            'workflow name cannot be an absolute path',
        ),
        (
            ['foo/..'],
            'cannot be a path that points to the cylc-run directory or above',
        ),
        (
            ['foo/'],
            'Invalid Cylc identifier',
        ),
    ]
)
async def test_invalid_ids(ids_in, error_msg):
    with pytest.raises(Exception) as exc_ctx:
        workflows, _multi_mode = await parse_ids_async(
            *ids_in,
            constraint='workflows',
        )
    assert error_msg in str(exc_ctx.value)
