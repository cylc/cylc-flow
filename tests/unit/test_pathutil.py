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
"""Tests for "cylc.flow.pathutil"."""

import logging
import os
from pathlib import Path
import pytest
from pytest import param
from typing import Callable, Dict, Iterable, List, Set
from unittest.mock import Mock, patch, call

from cylc.flow.exceptions import InputError, WorkflowFilesError
from cylc.flow.pathutil import (
    EXPLICIT_RELATIVE_PATH_REGEX,
    expand_path,
    get_dirs_to_symlink,
    get_next_rundir_number,
    get_remote_workflow_run_dir,
    get_remote_workflow_run_job_dir,
    get_source_conf_from_id,
    get_workflow_run_dir,
    get_workflow_run_job_dir,
    get_workflow_run_scheduler_log_dir,
    get_workflow_run_scheduler_log_path,
    get_workflow_run_pub_db_path,
    get_workflow_run_config_log_dir,
    get_workflow_run_share_dir,
    get_workflow_run_work_dir,
    get_workflow_test_log_path,
    make_localhost_symlinks,
    make_workflow_run_tree,
    parse_rm_dirs,
    remove_dir_and_target,
    remove_dir_or_file,
    remove_empty_parents,
    get_workflow_name_from_id
)

from .conftest import MonkeyMock


HOME = Path.home()


@pytest.mark.parametrize(
    'string, match_expected',
    [
        ('./foo/bar', True),
        ('../foo', True),
        ('./', True),
        ('../', True),
        ('.', True),
        ('..', True),
        ('foo/bar', False),
        ('.foo/bar', False),
        ('foo/..', False),
    ]
)
def test_explicit_relative_path_regex(string: str, match_expected: bool):
    assert bool(EXPLICIT_RELATIVE_PATH_REGEX.match(string)) is match_expected


@pytest.mark.parametrize(
    'path, expected',
    [('~/moo', os.path.join(HOME, 'moo')),
     ('$HOME/moo', os.path.join(HOME, 'moo')),
     ('~/$FOO/moo', os.path.join(HOME, 'foo', 'bar', 'moo')),
     ('$NON_EXIST/moo', '$NON_EXIST/moo')]
)
def test_expand_path(
    path: str, expected: str,
    monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv('FOO', 'foo/bar')
    monkeypatch.delenv('NON_EXIST', raising=False)
    assert expand_path(path) == expected


@pytest.mark.parametrize(
    'func, extra_args, expected',
    [
        (get_remote_workflow_run_dir, (), "$HOME/cylc-run/foo"),
        (
            get_remote_workflow_run_dir,
            ("comes", "true"),
            "$HOME/cylc-run/foo/comes/true",
        ),
        (
            get_remote_workflow_run_job_dir,
            (),
            "$HOME/cylc-run/foo/log/job"),
        (
            get_remote_workflow_run_job_dir,
            ("comes", "true"),
            "$HOME/cylc-run/foo/log/job/comes/true",
        )
    ]
)
def test_get_remote_workflow_run_dirs(
    func: Callable, extra_args: Iterable[str], expected: str,
) -> None:
    """Tests for get_remote_workflow_run_[|job|work]_dir"""
    if extra_args:
        result = func('foo', *extra_args)
    else:
        result = func('foo')
    assert result == expected


@pytest.mark.parametrize(
    'func, tail1',
    [(get_workflow_run_dir, ''),
     (get_workflow_run_job_dir, '/log/job'),
     (get_workflow_run_scheduler_log_dir, '/log/scheduler'),
     (get_workflow_run_config_log_dir, '/log/config'),
     (get_workflow_run_share_dir, '/share'),
     (get_workflow_run_work_dir, '/work')]
)
@pytest.mark.parametrize(
    'args, tail2',
    [([], ''),
     (['comes', 'true'], '/comes/true')]
)
def test_get_workflow_run_dirs(
    func: Callable, tail1: str, args: List[str], tail2: str
) -> None:
    """Usage of get_workflow_run_*dir.

    Params:
        func: get_remote_* function to test
        tail1: expected tail of return value from configuration
        args: extra *args
        tail2: expected tail of return value from extra args
    """
    homedir = os.getenv("HOME")

    expected_result = f'{homedir}/cylc-run/my-workflow/dream{tail1}{tail2}'
    assert func('my-workflow/dream', *args) == expected_result


@pytest.mark.parametrize(
    'func, tail',
    [(get_workflow_run_scheduler_log_path, '/log/scheduler/log'),
     (get_workflow_run_pub_db_path, '/log/db'),
     (get_workflow_test_log_path, '/log/scheduler/reftest.log')]
)
def test_get_workflow_run_names(func: Callable, tail: str) -> None:
    """Usage of get_workflow_run_*name.

    Params:
        func: get_remote_* function to test
        cfg: configuration used in mocked global configuration
        tail: expected tail of return value from configuration
    """
    homedir = os.getenv("HOME")

    assert (
        func('my-workflow/dream') ==
        f'{homedir}/cylc-run/my-workflow/dream{tail}'
    )


def test_make_workflow_run_tree(
    tmp_run_dir: Callable, caplog: pytest.LogCaptureFixture
) -> None:
    run_dir: Path = tmp_run_dir('my-workflow')
    caplog.set_level(logging.DEBUG)  # Only used for debugging test

    make_workflow_run_tree('my-workflow')
    # Check that directories have been created
    for subdir in [
        '',
        'log/scheduler',
        'log/job',
        'log/config',
        'share',
        'work'
    ]:
        assert (run_dir / subdir).is_dir() is True


@pytest.mark.parametrize(
    'mocked_glbl_cfg, output',
    [
        pytest.param(  # basic
            '''
            [install]
            [[symlink dirs]]
                [[[the_matrix]]]
                    run = $DEE
                    work = $DAH
                    log = $DUH
                    share = $DOH
                    share/cycle = $DAH
            ''',
            {
                'run': '$DEE/cylc-run/morpheus',
                'work': '$DAH/cylc-run/morpheus/work',
                'log': '$DUH/cylc-run/morpheus/log',
                'share': '$DOH/cylc-run/morpheus/share',
                'share/cycle': '$DAH/cylc-run/morpheus/share/cycle'
            },
            id="basic"
        ),
        pytest.param(  # remove nested run symlinks
            '''
            [install]
            [[symlink dirs]]
                [[[the_matrix]]]
                    run = $DEE
                    work = $DAH
                    log = $DEE
                    share = $DOH
                    share/cycle = $DAH
            ''',
            {
                'run': '$DEE/cylc-run/morpheus',
                'work': '$DAH/cylc-run/morpheus/work',
                'share': '$DOH/cylc-run/morpheus/share',
                'share/cycle': '$DAH/cylc-run/morpheus/share/cycle'
            },
            id="remove nested run symlinks"
        ),
        pytest.param(  # remove only nested run symlinks
            '''
            [install]
            [[symlink dirs]]
                [[[the_matrix]]]
                    run = $DOH
                    log = $DEE
                    share = $DEE
            ''',
            {
                'run': '$DOH/cylc-run/morpheus',
                'log': '$DEE/cylc-run/morpheus/log',
                'share': '$DEE/cylc-run/morpheus/share'
            },
            id="remove only nested run symlinks"
        ),
        pytest.param(  # blank entries
            '''
            [install]
            [[symlink dirs]]
                [[[the_matrix]]]
                    run =
                    log = ""
                    share =
                    work = " "
            ''',
            {},
            id="blank entries"
        )
    ]
)
def test_get_dirs_to_symlink(
    mocked_glbl_cfg: str,
    output: Dict[str, str],
    mock_glbl_cfg: Callable,
    monkeypatch: pytest.MonkeyPatch
) -> None:
    # Set env var 'DEE', but we expect it to be unexpanded
    monkeypatch.setenv('DEE', 'poiuytrewq')
    mock_glbl_cfg('cylc.flow.pathutil.glbl_cfg', mocked_glbl_cfg)
    dirs = get_dirs_to_symlink('the_matrix', 'morpheus')
    assert dirs == output


@patch('cylc.flow.pathutil.get_workflow_run_dir')
@patch('cylc.flow.pathutil.get_dirs_to_symlink')
def test_make_localhost_symlinks_calls_make_symlink_for_each_key_value_dir(
    mocked_dirs_to_symlink: Mock,
    mocked_get_workflow_run_dir: Mock,
    monkeypatch: pytest.MonkeyPatch, monkeymock: MonkeyMock
) -> None:
    mocked_dirs_to_symlink.return_value = {
        'run': '$DOH/trinity',
        'log': '$DEE/trinity/log',
        'share': '$DEE/trinity/share'
    }
    mocked_get_workflow_run_dir.return_value = "rund"
    for v in ('DOH', 'DEE'):
        monkeypatch.setenv(v, 'expanded')
    mocked_make_symlink = monkeymock('cylc.flow.pathutil.make_symlink_dir')

    make_localhost_symlinks('rund', 'workflow')
    mocked_make_symlink.assert_has_calls([
        call('rund', 'expanded/trinity'),
        call('rund/log', 'expanded/trinity/log'),
        call('rund/share', 'expanded/trinity/share')
    ])


@patch('cylc.flow.pathutil.get_workflow_run_dir')
@patch('cylc.flow.pathutil.make_symlink_dir')
@patch('cylc.flow.pathutil.get_dirs_to_symlink')
def test_incorrect_environment_variables_raise_error(
    mocked_dirs_to_symlink,
    mocked_make_symlink,
    mocked_get_workflow_run_dir,
    monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv('doh', raising=False)
    mocked_dirs_to_symlink.return_value = {
        'run': '$doh/cylc-run/test_workflow'}
    mocked_get_workflow_run_dir.return_value = "rund"

    with pytest.raises(WorkflowFilesError) as excinfo:
        make_localhost_symlinks('rund', 'test_workflow')
    assert (
        "Can't symlink to $doh/cylc-run/test_workflow\n"
        "Undefined variables, check global config: $doh"
    ) in str(excinfo.value)


@pytest.mark.parametrize(
    'filetype, expected_err',
    [('dir', None),
     ('file', NotADirectoryError),
     (None, FileNotFoundError)]
)
def test_remove_dir_and_target(filetype, expected_err, tmp_path):
    """Test that remove_dir_and_target() can delete nested dirs and handle
    bad paths."""
    test_path = tmp_path.joinpath('foo/bar')
    if filetype == 'dir':
        # Test removal of sub directories too
        sub_dir = test_path.joinpath('baz')
        sub_dir.mkdir(parents=True)
        sub_dir_file = sub_dir.joinpath('meow')
        sub_dir_file.touch()
    elif filetype == 'file':
        test_path = tmp_path.joinpath('meow')
        test_path.touch()

    if expected_err:
        with pytest.raises(expected_err):
            remove_dir_and_target(test_path)
    else:
        remove_dir_and_target(test_path)
        assert test_path.exists() is False
        assert test_path.is_symlink() is False


@pytest.mark.parametrize(
    'target, expected_err',
    [('dir', None),
     ('file', NotADirectoryError),
     (None, None)]
)
def test_remove_dir_and_target_symlinks(target, expected_err, tmp_path):
    """Test that remove_dir_and_target() can delete symlinks, including
    the target."""
    target_path = tmp_path.joinpath('x/y')
    target_path.mkdir(parents=True)

    tmp_path.joinpath('a').mkdir()
    symlink_path = tmp_path.joinpath('a/b')

    if target == 'dir':
        # Add a file into the the target dir to check it removes that ok
        target_path.joinpath('meow').touch()
        symlink_path.symlink_to(target_path)
    elif target == 'file':
        target_path = target_path.joinpath('meow')
        target_path.touch()
        symlink_path.symlink_to(target_path)
    elif target is None:
        symlink_path.symlink_to(target_path)
        # Break symlink
        target_path.rmdir()

    if expected_err:
        with pytest.raises(expected_err):
            remove_dir_and_target(symlink_path)
    else:
        remove_dir_and_target(symlink_path)
        for path in [symlink_path, target_path]:
            assert path.exists() is False
            assert path.is_symlink() is False


@pytest.mark.parametrize(
    'func', [remove_dir_and_target, remove_dir_or_file]
)
def test_remove_relative(func: Callable, tmp_path: Path):
    """Test that you cannot use remove_dir_and_target() or remove_dir_or_file()
    on relative paths.

    When removing a path, we want to be absolute-ly sure where it is!
    """
    # cd to temp dir in case we accidentally succeed in deleting the path
    os.chdir(tmp_path)
    with pytest.raises(ValueError) as cm:
        func('foo/bar')
    assert 'Path must be absolute' in str(cm.value)


def test_remove_dir_or_file(tmp_path: Path):
    """Test remove_dir_or_file()"""
    a_file = tmp_path.joinpath('fyle')
    a_file.touch()
    assert a_file.exists()
    remove_dir_or_file(a_file)
    assert a_file.exists() is False

    a_symlink = tmp_path.joinpath('simlynk')
    a_file.touch()
    a_symlink.symlink_to(a_file)
    assert a_symlink.is_symlink()
    remove_dir_or_file(a_symlink)
    assert a_symlink.is_symlink() is False
    assert a_file.exists()

    a_dir = tmp_path.joinpath('der')
    # Add contents to check whole tree is removed
    sub_dir = a_dir.joinpath('sub_der')
    sub_dir.mkdir(parents=True)
    sub_dir.joinpath('fyle').touch()
    assert a_dir.exists()
    remove_dir_or_file(a_dir)
    assert a_dir.exists() is False


def test_remove_empty_parents(tmp_path: Path):
    """Test that _remove_empty_parents() doesn't remove parents containing a
    sibling."""
    # -- Setup --
    reg = 'foo/bar/baz/qux'
    path = tmp_path.joinpath(reg)
    tmp_path.joinpath('foo/bar/baz').mkdir(parents=True)
    # Note qux does not exist, but that shouldn't matter
    sibling_reg = 'foo/darmok'
    sibling_path = tmp_path.joinpath(sibling_reg)
    sibling_path.mkdir()
    # -- Test --
    remove_empty_parents(path, reg)
    assert tmp_path.joinpath('foo/bar').exists() is False
    assert tmp_path.joinpath('foo').exists() is True
    # Check it skips non-existent dirs, and stops at the right place too
    tmp_path.joinpath('foo/bar').mkdir()
    sibling_path.rmdir()
    remove_empty_parents(path, reg)
    assert tmp_path.joinpath('foo').exists() is False
    assert tmp_path.exists() is True


@pytest.mark.parametrize(
    'path, tail, exc_msg',
    [
        pytest.param(
            'meow/foo/darmok', 'foo/darmok', "path must be absolute",
            id="relative path"
        ),
        pytest.param(
            '/meow/foo/darmok', '/foo/darmok',
            "tail must not be an absolute path",
            id="absolute tail"
        ),
        pytest.param(
            '/meow/foo/darmok', 'foo/jalad',
            "path '/meow/foo/darmok' does not end with 'foo/jalad'",
            id="tail not in path"
        )
    ]
)
def test_remove_empty_parents_bad(path: str, tail: str, exc_msg: str):
    """Test that _remove_empty_parents() fails appropriately with bad args."""
    with pytest.raises(ValueError) as exc:
        remove_empty_parents(path, tail)
    assert exc_msg in str(exc.value)


@pytest.mark.parametrize(
    'dirs, expected',
    [
        ([" "], set()),
        (["foo", "bar"], {"foo", "bar"}),
        (["foo:bar", "baz/*"], {"foo", "bar", "baz/*"}),
        ([" :foo :bar:"], {"foo", "bar"}),
        (["foo/:bar//baz "], {"foo/", "bar/baz"}),
        ([".foo", "..bar", " ./gah"], {".foo", "..bar", "gah"})
        # Note '..bar' is a valid filename (doesn't point to parent dir)
    ]
)
def test_parse_rm_dirs(dirs: List[str], expected: Set[str]):
    """Test parse_dirs()"""
    assert parse_rm_dirs(dirs) == expected


@pytest.mark.parametrize(
    'dirs, err_msg',
    [
        (["foo:/bar"],
         "--rm option cannot take absolute paths"),
        ([".."],
         "cannot take paths that point to the run directory or above"),
        (["foo:../bar"],
         "cannot take paths that point to the run directory or above"),
        (["foo:bar/../../gah"],
         "cannot take paths that point to the run directory or above"),
    ]
)
def test_parse_rm_dirs__bad(dirs: List[str], err_msg: str):
    """Test parse_dirs() with bad inputs"""
    with pytest.raises(InputError) as exc:
        parse_rm_dirs(dirs)
    assert err_msg in str(exc.value)


@pytest.mark.parametrize(
    'expect, files, runN',
    [
        param(1, [], False, id='1st run (from filenames)'),
        param(2, ['run1'], False, id='2nd run (from filenames)'),
        param(
            1000, ['run20', 'run400', 'run999'], False,
            id='1000th run (from filenames)'
        ),
        param(
            6, ['run1', 'run5'], False,
            id='Non-sequential (from filenames)'),
        param(2, ['run1'], True, id='2nd run (from symlink)'),
        param(100, ['run1', 'run99'], True, id='100th run (from symlink)'),
        param(42, ['foo', 'foo12', 'run41'], False, id='with dirs not runX')
    ]
)
def test_get_next_rundir_number(tmp_path, expect, files, runN):
    for file_ in files:
        (tmp_path / file_).mkdir()
    if runN:
        (tmp_path / 'runN').symlink_to(tmp_path / files[-1])
    assert get_next_rundir_number(tmp_path) == expect


@pytest.mark.parametrize(
    'name, id_, src',
    (
        param('my_workflow1', 'my_workflow1', False, id='--no-run-name'),
        param('my_workflow2', 'my_workflow2/run22', False, id='installed'),
        param(
            'my_workflow3', 'my_workflow3/foo', False, id='--run-name="foo"'),
        param('my_workflow4', 'my_workflow4', True, id='not installed'),
    )
)
def test_get_workflow_name_from_id(
    tmp_path, monkeypatch,
    name: str, id_: str, src: bool
) -> None:
    """It gets the correct name.

    args:
        name: Workflow name
        id: Workflow id
        src: Is this workflow a source or installed workflow.
    """
    monkeypatch.setattr(
        'cylc.flow.pathutil.get_cylc_run_dir', lambda: tmp_path)

    (tmp_path / name).mkdir(exist_ok=True)
    if not src:
        (tmp_path / name / '_cylc-install').mkdir(exist_ok=True)
    (tmp_path / id_).mkdir(exist_ok=True)

    result = get_workflow_name_from_id(id_)
    assert result == name


@pytest.fixture
def _setup_get_source_conf_from_id(tmp_path, monkeypatch):
    run = tmp_path / 'cylc-run/run'
    src = tmp_path / 'cylc-src/src'
    src.mkdir(parents=True)
    (run / '_cylc-install').mkdir(parents=True)
    (run / '_cylc-install/source').symlink_to(src)
    monkeypatch.setattr(
        'cylc.flow.pathutil.get_workflow_run_dir',
        lambda workflow_id: tmp_path / 'cylc-run/run'
    )
    monkeypatch.setattr(
        'cylc.flow.pathutil.get_cylc_run_dir',
        lambda: tmp_path / 'cylc-run'
    )
    yield tmp_path


@pytest.mark.parametrize(
    'conf_file',
    (
        param('flow.cylc', id='flow.cylc'),
        param('suite.rc', id='flow.cylc'),
        param(None, id='no file'),
    )
)
def test_get_source_conf_from_id(
    _setup_get_source_conf_from_id, conf_file
):
    """It locates a flow.cylc, suite.rc from a run dir, or fails nicely.
    """
    if conf_file:
        expect = _setup_get_source_conf_from_id / f'cylc-src/src/{conf_file}'
        expect.touch()
        assert get_source_conf_from_id('run') == expect
    else:
        with pytest.raises(WorkflowFilesError):
            get_source_conf_from_id('run')
