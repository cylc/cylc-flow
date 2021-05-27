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
from typing import Callable, Iterable, List
import pytest
from unittest.mock import patch, call

from cylc.flow.exceptions import WorkflowFilesError
from cylc.flow.pathutil import (
    expand_path,
    get_dirs_to_symlink,
    get_remote_workflow_run_dir,
    get_remote_workflow_run_job_dir,
    get_workflow_run_dir,
    get_workflow_run_job_dir,
    get_workflow_run_log_dir,
    get_workflow_run_log_name,
    get_workflow_run_pub_db_name,
    get_workflow_run_config_log_dir,
    get_workflow_run_share_dir,
    get_workflow_run_work_dir,
    get_workflow_test_log_name,
    make_localhost_symlinks,
    make_workflow_run_tree,
    remove_dir
)


HOME = Path.home()


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
     (get_workflow_run_log_dir, '/log/workflow'),
     (get_workflow_run_config_log_dir, '/log/flow-config'),
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
    [(get_workflow_run_log_name, '/log/workflow/log'),
     (get_workflow_run_pub_db_name, '/log/db'),
     (get_workflow_test_log_name, '/log/workflow/reftest.log')]
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
        'log/workflow',
        'log/job',
        'log/flow-config',
        'share',
        'work'
    ]:
        assert (run_dir / subdir).is_dir() is True


@pytest.mark.parametrize(
    'workflow, install_target, mocked_glbl_cfg, output',
    [
        (  # basic
            'workflow1', 'install_target_1',
            '''[symlink dirs]
            [[install_target_1]]
                run = $DEE
                work = $DAH
                log = $DUH
                share = $DOH
                share/cycle = $DAH''', {
                'run': '$DEE/cylc-run/workflow1',
                'work': '$DAH/cylc-run/workflow1/work',
                'log': '$DUH/cylc-run/workflow1/log',
                'share': '$DOH/cylc-run/workflow1/share',
                'share/cycle': '$DAH/cylc-run/workflow1/share/cycle'
            }),
        (  # remove nested run symlinks
            'workflow2', 'install_target_2',
            '''
        [symlink dirs]
            [[install_target_2]]
                run = $DEE
                work = $DAH
                log = $DEE
                share = $DOH
                share/cycle = $DAH

        ''', {
                'run': '$DEE/cylc-run/workflow2',
                'work': '$DAH/cylc-run/workflow2/work',
                'share': '$DOH/cylc-run/workflow2/share',
                'share/cycle': '$DAH/cylc-run/workflow2/share/cycle'
            }),
        (  # remove only nested run symlinks
            'workflow3', 'install_target_3', '''
        [symlink dirs]
            [[install_target_3]]
                run = $DOH
                log = $DEE
                share = $DEE
        ''', {
                'run': '$DOH/cylc-run/workflow3',
                'log': '$DEE/cylc-run/workflow3/log',
                'share': '$DEE/cylc-run/workflow3/share'})
    ], ids=["1", "2", "3"])
def test_get_dirs_to_symlink(workflow, install_target, mocked_glbl_cfg,
                             output, mock_glbl_cfg, tmp_path, monkeypatch):
    # Using env variable 'DEE' to ensure dirs returned are unexpanded
    monkeypatch.setenv('DEE', str(tmp_path))
    mock_glbl_cfg('cylc.flow.pathutil.glbl_cfg', mocked_glbl_cfg)
    dirs = get_dirs_to_symlink(install_target, workflow)
    assert dirs == output


@patch('os.path.expandvars')
@patch('cylc.flow.pathutil.get_workflow_run_dir')
@patch('cylc.flow.pathutil.make_symlink')
@patch('cylc.flow.pathutil.get_dirs_to_symlink')
def test_make_localhost_symlinks_calls_make_symlink_for_each_key_value_dir(
        mocked_dirs_to_symlink,
        mocked_make_symlink,
        mocked_get_workflow_run_dir, mocked_expandvars):

    mocked_dirs_to_symlink.return_value = {
        'run': '$DOH/workflow3',
        'log': '$DEE/workflow3/log',
        'share': '$DEE/workflow3/share'}
    mocked_get_workflow_run_dir.return_value = "rund"
    mocked_expandvars.return_value = "expanded"
    mocked_make_symlink.return_value = True
    make_localhost_symlinks('rund', 'workflow')
    mocked_make_symlink.assert_has_calls([
        call('expanded', 'rund'),
        call('expanded', 'rund/log'),
        call('expanded', 'rund/share')
    ])


@patch('os.path.expandvars')
@patch('cylc.flow.pathutil.get_workflow_run_dir')
@patch('cylc.flow.pathutil.make_symlink')
@patch('cylc.flow.pathutil.get_dirs_to_symlink')
def test_incorrect_environment_variables_raise_error(
        mocked_dirs_to_symlink,
        mocked_make_symlink,
        mocked_get_workflow_run_dir, mocked_expandvars):
    mocked_dirs_to_symlink.return_value = {
        'run': '$doh/cylc-run/test_workflow'}
    mocked_get_workflow_run_dir.return_value = "rund"
    mocked_expandvars.return_value = "$doh"

    with pytest.raises(WorkflowFilesError, match=r"Unable to create symlink"
                       r" to \$doh. '\$doh/cylc-run/test_workflow' contains an"
                       " invalid environment variable. Please check "
                       "configuration."):
        make_localhost_symlinks('rund', 'test_workflow')


@pytest.mark.parametrize(
    'filetype, expected_err',
    [('dir', None),
     ('file', NotADirectoryError),
     (None, FileNotFoundError)]
)
def test_remove_dir(filetype, expected_err, tmp_path):
    """Test that remove_dir() can delete nested dirs and handle bad paths."""
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
            remove_dir(test_path)
    else:
        remove_dir(test_path)
        assert test_path.exists() is False
        assert test_path.is_symlink() is False


@pytest.mark.parametrize(
    'target, expected_err',
    [('dir', None),
     ('file', NotADirectoryError),
     (None, None)]
)
def test_remove_dir_symlinks(target, expected_err, tmp_path):
    """Test that remove_dir() can delete symlinks, including the target."""
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
            remove_dir(symlink_path)
    else:
        remove_dir(symlink_path)
        for path in [symlink_path, target_path]:
            assert path.exists() is False
            assert path.is_symlink() is False


def test_remove_dir_relative(tmp_path):
    """Test that you cannot use remove_dir() on a relative path.

    When removing a path, we want to be absolute-ly sure where it is!
    """
    # cd to temp dir in case we accidentally succeed in deleting the path
    os.chdir(tmp_path)
    with pytest.raises(ValueError) as cm:
        remove_dir('foo/bar')
    assert 'Path must be absolute' in str(cm.value)
