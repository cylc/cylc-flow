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

import logging
import os
from pathlib import Path
import pytest
from shutil import copytree, rmtree

from cylc.flow import CYLC_LOG
from cylc.flow.async_util import pipe
from cylc.flow.exceptions import InputError, WorkflowFilesError
from cylc.flow.id import detokenise, tokenise, Tokens
from cylc.flow.id_cli import (
    _expand_workflow_tokens,
    _parse_src_path,
    _validate_constraint,
    _validate_workflow_ids,
    _validate_number,
    cli_tokenise,
    parse_ids_async,
)
from cylc.flow.pathutil import get_cylc_run_dir
from cylc.flow.workflow_files import WorkflowFiles


@pytest.fixture
def mock_exists(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr('pathlib.Path.exists', lambda *a, **k: True)


@pytest.fixture(scope='module')
def abc_src_dir(tmp_path_factory):
    """Src dir containing three workflows, a, b & c."""
    cwd_before = Path.cwd()
    tmp_path = tmp_path_factory.getbasetemp()
    os.chdir(tmp_path)
    for name in ('a', 'b', 'c'):
        Path(tmp_path, name).mkdir()
        Path(tmp_path, name, WorkflowFiles.FLOW_FILE).touch()
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
async def test_parse_ids_workflows(ids_in, ids_out, mock_exists):
    """It should parse workflows & tasks."""
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
    """It should parse src workflows."""
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
async def test_parse_ids_tasks(mock_exists, ids_in, ids_out):
    """It should parse workflow tasks in two formats."""
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
async def test_parse_ids_tasks_src(mock_exists, ids_in, ids_out, abc_src_dir):
    """It should parse workflow tasks for src workflows."""
    workflows, _ = await parse_ids_async(
        *ids_in, constraint='tasks', src=True)
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
async def test_parse_ids_mixed(ids_in, ids_out, mock_exists):
    """It should parse mixed workflows & tasks."""
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
    ]
)
async def test_parse_ids_mixed_src(ids_in, ids_out, abc_src_dir, mock_exists):
    """It should parse mixed workflows & tasks from src workflows."""

    workflows, _ = await parse_ids_async(
        *ids_in, constraint='mixed', src=True
    )
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
async def test_parse_ids_max_workflows(ids_in, errors, mock_exists):
    """It should validate input against the max_workflows constraint."""
    try:
        await parse_ids_async(
            *ids_in, constraint='workflows', max_workflows=2)
    except InputError:
        if not errors:
            raise
    else:
        if errors:
            raise Exception('Should have raised InputError')


@pytest.mark.parametrize(
    'ids_in,errors',
    [
        (('a//', '//i'), False),
        (('a//', '//i', '//j'), False),
        (('a//', '//i', '//j', '//k'), True),
    ]
)
async def test_parse_ids_max_tasks(ids_in, errors, mock_exists):
    """It should validate input against the max_tasks constraint."""
    try:
        await parse_ids_async(*ids_in, constraint='tasks', max_tasks=2)
    except InputError:
        if not errors:
            raise
    else:
        if errors:
            raise Exception('Should have raised InputError')


async def test_parse_ids_infer_run_name(tmp_run_dir):
    """It should infer the run name for auto-numbered installations."""
    # it doesn't do anything for a named run
    tmp_run_dir('foo/bar', named=True, installed=True)
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

    # Now test we can see workflows in alternate cylc-run directories
    # e.g. for `cylc workflow-state` or xtriggers targetting another user.
    cylc_run_dir = get_cylc_run_dir()
    alt_cylc_run_dir = cylc_run_dir + "_alt"

    # copy the cylc-run dir to alt location and delete the original.
    copytree(cylc_run_dir, alt_cylc_run_dir, symlinks=True)
    rmtree(cylc_run_dir)

    # It can no longer parse IDs in the original cylc-run location.
    with pytest.raises(InputError):
        workflows, *_ = await parse_ids_async(
            'bar//',
            constraint='workflows',
            infer_latest_runs=True,
        )

    # But it can if we specify the alternate location.
    workflows, *_ = await parse_ids_async(
        'bar//',
        constraint='workflows',
        infer_latest_runs=True,
        alt_run_dir=alt_cylc_run_dir
    )
    assert list(workflows) == ['bar/run2']


@pytest.fixture
def patch_expand_workflow_tokens(monkeypatch):
    """Define the output of scan events."""

    def _patch_expand_workflow_tokens(_ids):

        async def _expand_workflow_tokens_impl(tokens, match_active=True):
            for id_ in _ids:
                yield tokens.duplicate(workflow=id_)

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
    mock_exists
):
    """It should glob for workflows.

    Note:
        More advanced tests for this in the integration tests.

    """

    workflows, _multi_mode = await parse_ids_async(
        *ids_in,
        constraint='workflows',
        match_workflows=True,
    )
    assert list(workflows) == ids_out
    assert _multi_mode == multi_mode


@pytest.fixture
def src_dir(tmp_path):
    """A src dir containing a workflow called "a"."""
    cwd_before = Path.cwd()
    src_dir = (tmp_path / 'a')
    src_dir.mkdir()
    src_file = src_dir / 'flow.cylc'
    src_file.touch()

    other_dir = (tmp_path / 'blargh')
    other_dir.mkdir()
    other_file = other_dir / 'nugget'
    other_file.touch()

    os.chdir(tmp_path)
    yield src_dir
    os.chdir(cwd_before)


def test_parse_src_path(src_dir, monkeypatch):
    """It should locate src dirs."""
    # valid absolute path
    workflow_id, src_path, src_file_path = _parse_src_path(
        str(src_dir.resolve())
    )
    assert workflow_id == 'a'
    assert src_path == src_dir
    assert src_file_path == src_dir / 'flow.cylc'

    # broken absolute path
    with pytest.raises(InputError):
        workflow_id, src_path, src_file_path = _parse_src_path(
            str(src_dir.resolve()) + 'xyz'
        )

    # valid ./relative path
    workflow_id, src_path, src_file_path = _parse_src_path('./a')
    assert workflow_id == 'a'
    assert src_path == src_dir
    assert src_file_path == src_dir / 'flow.cylc'

    # broken relative path
    with pytest.raises(InputError):
        _parse_src_path('./xxx')

    # relative '.' dir (invalid)
    with pytest.raises(WorkflowFilesError) as exc_ctx:
        workflow_id, src_path, src_file_path = _parse_src_path('.')
    assert 'No flow.cylc or suite.rc in' in str(exc_ctx.value)

    # relative 'invalid/<flow-file>' (invalid)
    with pytest.raises(InputError) as exc_ctx:
        _parse_src_path('xxx/flow.cylc')
    assert 'Not a valid workflow ID or source directory' in str(exc_ctx.value)

    # Might be a workflow ID
    res = _parse_src_path('the/quick/brown/fox')
    assert res is None

    # Might be a workflow ID, even though there's a matching relative path
    res = _parse_src_path('a')
    assert res is None

    # Not a src directory (dir)
    with pytest.raises(WorkflowFilesError) as exc_ctx:
        _parse_src_path('./blargh')
    assert 'No flow.cylc or suite.rc in' in str(exc_ctx.value)

    # Not a src directory (file)
    with pytest.raises(InputError) as exc_ctx:
        _parse_src_path('./blargh/nugget')
    assert 'Path is not a source directory' in str(exc_ctx.value)

    # move into the src dir
    monkeypatch.chdir(src_dir)

    # relative '.' dir (valid)
    workflow_id, src_path, src_file_path = _parse_src_path('.')
    assert workflow_id == 'a'
    assert src_path == src_dir
    assert src_file_path == src_dir / 'flow.cylc'

    # relative './<flow-file>' (invalid)
    with pytest.raises(InputError) as exc_ctx:
        _parse_src_path('./flow.cylc')
    assert 'Not a valid workflow ID or source directory' in str(exc_ctx.value)

    # suite.rc & flow.cylc both present:
    (src_dir / 'suite.rc').touch()
    with pytest.raises(WorkflowFilesError) as exc_ctx:
        _parse_src_path(str(src_dir))
    assert 'Both flow.cylc and suite.rc files' in str(exc_ctx.value)


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
            'Invalid ID: /home/me/whatever',
        ),
        (
            ['foo/..'],
            'cannot be a path that points to the cylc-run directory or above',
        ),
        (
            ['~alice/foo'],
            "Operating on other users' workflows is not supported",
        ),
    ]
)
async def test_parse_ids_invalid_ids(
    ids_in, error_msg, monkeypatch: pytest.MonkeyPatch
):
    """It should error for invalid IDs."""
    monkeypatch.setattr('cylc.flow.id_cli.get_user', lambda: 'rincewind')
    with pytest.raises(Exception) as exc_ctx:
        await parse_ids_async(
            *ids_in,
            constraint='workflows',
        )
    assert error_msg in str(exc_ctx.value)


async def test_parse_ids_current_user(
    monkeypatch: pytest.MonkeyPatch, mock_exists
):
    """It should work if the user in the ID is the current user."""
    monkeypatch.setattr('cylc.flow.id_cli.get_user', lambda: 'rincewind')
    await parse_ids_async('~rincewind/luggage', constraint='workflows')


async def test_parse_ids_file(tmp_run_dir):
    """It should reject IDs that are paths to files."""
    tmp_path = tmp_run_dir('x')
    tmp_file = tmp_path / 'tmpfile'
    tmp_file.touch()
    (tmp_path / WorkflowFiles.FLOW_FILE).touch()
    # using a directory should work
    await parse_ids_async(
        str(tmp_path.relative_to(get_cylc_run_dir())),
        constraint='workflows',
    )
    with pytest.raises(Exception) as exc_ctx:
        # using a file should not
        await parse_ids_async(
            str(tmp_file.relative_to(get_cylc_run_dir())),
            constraint='workflows',
        )
    assert 'Workflow ID cannot be a file' in str(exc_ctx.value)


async def test_parse_ids_constraint(mock_exists):
    """It should validate input against the constraint."""
    # constraint: workflows
    await parse_ids_async('a//', constraint='workflows')
    with pytest.raises(InputError):
        await parse_ids_async('a//b', constraint='workflows')
    # constraint: tasks
    await parse_ids_async('a//b', constraint='tasks')
    with pytest.raises(InputError):
        await parse_ids_async('a//', constraint='tasks')
    # constraint: mixed
    await parse_ids_async('a//', constraint='mixed')
    await parse_ids_async('a//b', constraint='mixed')
    # constraint: invalid
    with pytest.raises(ValueError):
        await parse_ids_async('foo', constraint='bar')


async def test_parse_ids_src_run(abc_src_dir, tmp_run_dir):
    """It should locate the flow file when src=True."""
    # locate flow file for a src workflow
    workflows, flow_file_path = await parse_ids_async(
        './a',
        src=True,
        constraint='workflows',
    )
    assert list(workflows) == ['a']
    assert flow_file_path == abc_src_dir / 'a' / WorkflowFiles.FLOW_FILE

    # locate flow file for a run workflow
    run_dir = tmp_run_dir('b')
    workflows, flow_file_path = await parse_ids_async(
        'b',
        src=True,
        constraint='workflows',
    )
    assert list(workflows) == ['b']
    assert flow_file_path == run_dir / WorkflowFiles.FLOW_FILE


def test_validate_constraint():
    """It should validate tokens against the constraint."""
    # constraint=workflows
    _validate_constraint(Tokens(workflow='a'), constraint='workflows')
    with pytest.raises(InputError):
        _validate_constraint(Tokens(cycle='a'), constraint='workflows')
    with pytest.raises(InputError):
        _validate_constraint(Tokens(), constraint='workflows')
    # constraint=tasks
    _validate_constraint(Tokens(cycle='a'), constraint='tasks')
    with pytest.raises(InputError):
        _validate_constraint(Tokens(workflow='a'), constraint='tasks')
    with pytest.raises(InputError):
        _validate_constraint(Tokens(), constraint='tasks')
    # constraint=mixed
    _validate_constraint(Tokens(workflow='a'), constraint='mixed')
    _validate_constraint(Tokens(cycle='a'), constraint='mixed')
    with pytest.raises(InputError):
        _validate_constraint(Tokens(), constraint='mixed')


def test_validate_workflow_ids_basic(tmp_run_dir):
    _validate_workflow_ids(Tokens('workflow'), src_path='')
    with pytest.raises(InputError):
        _validate_workflow_ids(Tokens('~alice/workflow'), src_path='')
    run_dir = tmp_run_dir('b')
    with pytest.raises(InputError):
        _validate_workflow_ids(
            Tokens('workflow'),
            src_path=run_dir / 'flow.cylc',
        )


def test_validate_workflow_ids_warning(caplog):
    """It should warn when the run number is provided as a cycle point."""
    caplog.set_level(logging.WARN, CYLC_LOG)
    _validate_workflow_ids(Tokens('workflow/run1//cycle/task'), src_path='')
    assert caplog.messages == []

    _validate_workflow_ids(Tokens('workflow//run1'), src_path='')
    assert caplog.messages == ['Did you mean: workflow/run1']

    caplog.clear()
    _validate_workflow_ids(Tokens('workflow//run1/cycle/task'), src_path='')
    assert caplog.messages == ['Did you mean: workflow/run1//cycle/task']


def test_validate_number():
    _validate_number(Tokens('a'), max_workflows=1)
    with pytest.raises(InputError):
        _validate_number(Tokens('a'), Tokens('b'), max_workflows=1)
    t1 = Tokens(cycle='1')
    t2 = Tokens(cycle='2')
    _validate_number(t1, max_tasks=1)
    with pytest.raises(InputError):
        _validate_number(t1, t2, max_tasks=1)
    _validate_number(t1, max_tasks=1)
    _validate_number(Tokens('a//1'), Tokens('a//2'), max_workflows=1)
    _validate_number(
        Tokens('a'), Tokens('//2'), Tokens('//3'), max_workflows=1
    )
    with pytest.raises(InputError):
        _validate_number(Tokens('a//1'), Tokens('b//1'), max_workflows=1)
    _validate_number(Tokens('a//1'), Tokens('b//1'), max_workflows=2)


@pytest.fixture
def no_scan(monkeypatch):
    """Disable the filesystem part of scan."""

    @pipe
    async def _scan():
        # something that looks like scan but doesn't do anything
        yield

    monkeypatch.setattr('cylc.flow.network.scan.scan', _scan)


async def test_expand_workflow_tokens_impl_selector(no_scan):
    """It should reject filters it can't handle."""
    tokens = tokenise('~user/*')
    await _expand_workflow_tokens([tokens])
    tokens = tokens.duplicate(workflow_sel='stopped')
    with pytest.raises(InputError):
        await _expand_workflow_tokens([tokens])


@pytest.mark.parametrize('identifier, expected', [
    (
        '//2024-01-01T00:fail/a',
        {'cycle': '2024-01-01T00', 'cycle_sel': 'fail', 'task': 'a'}
    ),
    (
        '//2024-01-01T00:00Z/a',
        {'cycle': '2024-01-01T00:00Z', 'task': 'a'}
    ),
    (
        '//2024-01-01T00:00Z:fail/a',
        {'cycle': '2024-01-01T00:00Z', 'cycle_sel': 'fail', 'task': 'a'}
    ),
    (
        '//2024-01-01T00:00:00+05:30/a',
        {'cycle': '2024-01-01T00:00:00+05:30', 'task': 'a'}
    ),
    (
        '//2024-01-01T00:00:00+05:30:f/a',
        {'cycle': '2024-01-01T00:00:00+05:30', 'cycle_sel': 'f', 'task': 'a'}
    ),
    (
        # Nonsensical example, but whatever...
        '//2024-01-01T00:00Z:00Z/a',
        {'cycle': '2024-01-01T00:00Z', 'cycle_sel': '00Z', 'task': 'a'}
    )
])
def test_iso_long_fmt(identifier, expected):
    assert {
        k: v for k, v in cli_tokenise(identifier).items()
        if v is not None
    } == expected
