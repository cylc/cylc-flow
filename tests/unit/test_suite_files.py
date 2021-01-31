# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
import os.path
from pathlib import Path
import pytest
from unittest import mock

from cylc.flow import CYLC_LOG
from cylc.flow import suite_files
from cylc.flow.exceptions import (
    CylcError, SuiteServiceFileError, TaskRemoteMgmtError, WorkflowFilesError)
from cylc.flow.suite_files import check_nested_run_dirs


@pytest.mark.parametrize(
    'path, expected',
    [('a/b/c', '/mock_cylc_dir/a/b/c'),
     ('/a/b/c', '/a/b/c')]
)
def test_get_cylc_run_abs_path(path, expected, monkeypatch):
    monkeypatch.setattr('cylc.flow.pathutil.get_platform',
                        lambda: {'run directory': '/mock_cylc_dir'})
    assert suite_files.get_cylc_run_abs_path(path) == expected


@pytest.mark.parametrize(
    'path, expected',
    [('service/dir/exists', True),
     ('flow/file/exists', False),  # Non-run dirs can still contain flow.cylc
     ('nothing/exists', False)]
)
@pytest.mark.parametrize('is_abs_path', [False, True])
def test_is_valid_run_dir(path, expected, is_abs_path, monkeypatch):
    """Test that a directory is correctly identified as a valid run dir when
    it contains a service dir.
    """
    prefix = os.sep if is_abs_path is True else 'mock_cylc_dir'
    flow_file = os.path.join(prefix, 'flow', 'file', 'exists', 'flow.cylc')
    serv_dir = os.path.join(prefix, 'service', 'dir', 'exists', '.service')
    monkeypatch.setattr('os.path.isfile', lambda x: x == flow_file)
    monkeypatch.setattr('os.path.isdir', lambda x: x == serv_dir)
    monkeypatch.setattr('cylc.flow.pathutil.get_platform',
                        lambda: {'run directory': 'mock_cylc_dir'})
    path = os.path.normpath(path)
    if is_abs_path:
        path = os.path.join(os.sep, path)

    assert suite_files.is_valid_run_dir(path) is expected, (
        f'Is "{path}" a valid run dir?')


@pytest.mark.parametrize(
    'run_dir',
    [
        ('bright/falls/light'),
        ('bright/falls/light/dark')
    ]
)
def test_rundir_parent_that_does_not_contain_workflow_no_error(
        run_dir, monkeypatch):
    """Test that a workflow raises no error when a parent directory is not also
        a workflow directory."""

    monkeypatch.setattr('cylc.flow.suite_files.os.path.isdir',
                        lambda x: False if x.find('.service') > 0
                        else True)
    monkeypatch.setattr(
        'cylc.flow.suite_files.get_cylc_run_abs_path', lambda x: x)
    monkeypatch.setattr(
        'cylc.flow.suite_files.os.scandir', lambda x: [])

    try:
        suite_files.check_nested_run_dirs(run_dir, 'placeholder_flow')
    except Exception:
        pytest.fail("check_nested_run_dirs raised exception unexpectedly.")


@pytest.mark.parametrize(
    'run_dir, srv_dir',
    [
        ('bright/falls/light', 'bright/falls/.service'),
        ('bright/falls/light/dark', 'bright/falls/light/.service')
    ]
)
def test_rundir_parent_that_contains_workflow_raises_error(
        run_dir, srv_dir, monkeypatch):
    """Test that a workflow that contains another worfkflow raises error."""

    monkeypatch.setattr(
        'cylc.flow.suite_files.os.path.isdir', lambda x: x == srv_dir)
    monkeypatch.setattr(
        'cylc.flow.suite_files.get_cylc_run_abs_path', lambda x: x)
    monkeypatch.setattr(
        'cylc.flow.suite_files.os.scandir', lambda x: [])

    with pytest.raises(WorkflowFilesError) as exc:
        suite_files.check_nested_run_dirs(run_dir, 'placeholder_flow')
    assert 'Nested run directories not allowed' in str(exc.value)


@pytest.mark.parametrize(
    'run_dir',
    [
        ('a'),
        ('d/a'),
        ('z/d/a/a')
    ]
)
def test_rundir_children_that_do_not_contain_workflows_no_error(
        run_dir, monkeypatch):
    """Test that a run directory that contains no other workflows does not
    raise an error."""

    monkeypatch.setattr('cylc.flow.suite_files.os.path.isdir',
                        lambda x: False if x.find('.service')
                        else True)
    monkeypatch.setattr(
        'cylc.flow.suite_files.get_cylc_run_abs_path',
        lambda x: x)
    monkeypatch.setattr('cylc.flow.suite_files.os.scandir',
                        lambda x: [
                            mock.Mock(path=run_dir[0:len(x) + 2],
                                      is_symlink=lambda: False)])
    try:
        suite_files.check_nested_run_dirs(run_dir, 'placeholder_flow')
    except Exception:
        pytest.fail("check_nested_run_dirs raised exception unexpectedly.")


@pytest.mark.parametrize(
    'run_dir, srv_dir',
    [
        ('a', 'a/R/.service'),
        ('d/a', 'd/a/a/R/.service'),
        ('z/d/a/a', 'z/d/a/a/R/.service')
    ]
)
def test_rundir_children_that_contain_workflows_raise_error(
        run_dir, srv_dir, monkeypatch):
    """Test that a workflow cannot be contained in a subdir of another
    workflow."""
    monkeypatch.setattr('cylc.flow.suite_files.os.path.isdir',
                        lambda x: False if (
                            x.find('.service') > 0 and x != srv_dir)
                        else True)
    monkeypatch.setattr(
        'cylc.flow.suite_files.get_cylc_run_abs_path',
        lambda x: x)
    monkeypatch.setattr('cylc.flow.suite_files.os.scandir',
                        lambda x: [
                            mock.Mock(path=srv_dir[0:len(x) + 2],
                                      is_symlink=lambda: False)])

    with pytest.raises(WorkflowFilesError) as exc:
        check_nested_run_dirs(run_dir, 'placeholder_flow')
    assert 'Nested run directories not allowed' in str(exc.value)


@pytest.mark.parametrize(
    'reg, expected_err, expected_msg',
    [('foo/bar/', None, None),
     ('/foo/bar', SuiteServiceFileError, "cannot be an absolute path"),
     ('$HOME/alone', SuiteServiceFileError, "invalid suite name")]
)
def test_validate_reg(reg, expected_err, expected_msg):
    if expected_err:
        with pytest.raises(expected_err) as exc:
            suite_files._validate_reg(reg)
        if expected_msg:
            assert expected_msg in str(exc.value)
    else:
        suite_files._validate_reg(reg)


@pytest.mark.parametrize(
    'reg, not_stopped, err, err_msg',
    [('foo/..', False, WorkflowFilesError,
      "cannot be a path that points to the cylc-run directory or above"),
     ('foo/../..', False, WorkflowFilesError,
      "cannot be a path that points to the cylc-run directory or above"),
     ('foo', True, SuiteServiceFileError, "Cannot remove running workflow")]
)
def test_clean_check(reg, not_stopped, err, err_msg, monkeypatch):
    """Test that _clean_check() fails appropriately.

    Params:
        reg (str): Workflow name.
        err (Exception): Expected error.
        err_msg (str): Message that is expected to be in the exception.
    """
    run_dir = mock.Mock()

    def mocked_detect_old_contact_file(reg):
        if not_stopped:
            raise SuiteServiceFileError('Mocked error')

    monkeypatch.setattr('cylc.flow.suite_files.detect_old_contact_file',
                        mocked_detect_old_contact_file)

    with pytest.raises(err) as exc:
        suite_files._clean_check(reg, run_dir)
    assert err_msg in str(exc.value)


@pytest.mark.parametrize(
    'reg, props, clean_called, remote_clean_called',
    [
        ('foo/bar', {
            'no dir': True,
            'log': (logging.INFO, "No directory to clean")
        }, False, False),
        ('foo/bar', {
            'no db': True,
            'log': (logging.INFO,
                    "No workflow database - will only clean locally")
        }, True, False),
        ('foo/bar', {
            'db platforms': ['localhost', 'localhost']
        }, True, False),
        ('foo/bar', {
            'db platforms': ['horse']
        }, True, True)
    ]
)
def test_init_clean_ok(
        reg, props, clean_called, remote_clean_called,
        monkeypatch, tmp_path, caplog):
    """Test the init_clean() function logic.

    Params:
        reg (str): Workflow name.
        props (dict): Possible values are (all optional):
            'no dir' (bool): If True, do not create run dir for this test case.
            'log' (tuple): Of form (severity, msg):
                severity (logging level): Expected level e.g. logging.INFO.
                msg (str): Message that is expected to be logged.
            'db platforms' (list): Platform names that would be loaded from
                the database.
            'no db' (bool): If True, workflow database doesn't exist.
        clean_called (bool): If a local clean is expected to go ahead.
        remote_clean_called (bool): If a remote clean is expected to go ahead.
    """
    # --- Setup ---
    expected_log = props.get('log')
    if expected_log:
        level, msg = expected_log
        caplog.set_level(level, CYLC_LOG)

    tmp_path.joinpath('cylc-run').mkdir()
    run_dir = tmp_path.joinpath('cylc-run', reg)
    if not props.get('no dir'):
        run_dir.mkdir(parents=True)

    mocked_clean = mock.Mock()
    monkeypatch.setattr('cylc.flow.suite_files.clean', mocked_clean)
    mocked_remote_clean = mock.Mock()
    monkeypatch.setattr('cylc.flow.suite_files.remote_clean',
                        mocked_remote_clean)
    monkeypatch.setattr('cylc.flow.suite_files.get_workflow_run_dir',
                        lambda x: tmp_path.joinpath('cylc-run', x))

    _get_platforms_from_db = suite_files.get_platforms_from_db

    def mocked_get_platforms_from_db(run_dir):
        if props.get('no dir') or props.get('no db'):
            return _get_platforms_from_db(run_dir)  # Handle as normal
        return set(props.get('db platforms'))

    monkeypatch.setattr('cylc.flow.suite_files.get_platforms_from_db',
                        mocked_get_platforms_from_db)

    # --- The actual test ---
    suite_files.init_clean(reg, opts=mock.Mock())
    if expected_log:
        assert msg in caplog.text
    if clean_called:
        assert mocked_clean.called is True
    else:
        assert mocked_clean.called is False
    if remote_clean_called:
        assert mocked_remote_clean.called is True
    else:
        assert mocked_remote_clean.called is False


@pytest.mark.parametrize(
    'reg, props',
    [
        ('foo/bar/', {}),  # Works ok
        ('foo', {'no dir': True}),  # Nothing to clean
        ('foo', {
            'not stopped': True,
            'err': SuiteServiceFileError,
            'err msg': 'Cannot remove running workflow'
        }),
        ('foo/bar', {
            'symlink dirs': {
                'log': 'sym-log',
                'share': 'sym-share',
                'share/cycle': 'sym-cycle',
                'work': 'sym-work'
            }
        }),
        ('foo', {
            'symlink dirs': {
                'run': 'sym-run',
                'log': 'sym-log',
                'share': 'sym-share',
                'share/cycle': 'sym-cycle',
                'work': 'sym-work'
            }
        }),
        ('foo', {
            'bad symlink': {
                'type': 'file',
                'path': 'sym-log/cylc-run/foo/meow.txt'
            },
            'err': WorkflowFilesError,
            'err msg': 'Target is not a directory'
        }),
        ('foo', {
            'bad symlink': {
                'type': 'dir',
                'path': 'sym-log/bad/path'
            },
            'err': WorkflowFilesError,
            'err msg': 'Expected target to end with "cylc-run/foo/log"'
        })
    ]
)
def test_clean(reg, props, monkeypatch, tmp_path):
    """Test the clean() function.

    Params:
        reg (str): Workflow name.
        props (dict): Possible values are (all optional):
            'err' (Exception): Expected error.
            'err msg' (str): Message that is expected to be in the exception.
            'no dir' (bool): If True, do not create run dir for this test case.
            'not stopped' (bool): If True, simulate that the workflow is
                still running.
            'symlink dirs' (dict): As you would find in the global config
                under [symlink dirs][platform].
            'bad symlink' (dict): Simulate an invalid log symlink dir:
                'type' (str): 'file' or 'dir'.
                'path' (str): Path of the symlink target relative to tmp_path.
    """
    # --- Setup ---
    tmp_path.joinpath('cylc-run').mkdir()
    run_dir = tmp_path.joinpath('cylc-run', reg)
    run_dir_top_parent = tmp_path.joinpath('cylc-run', Path(reg).parts[0])
    symlink_dirs = props.get('symlink dirs')
    bad_symlink = props.get('bad symlink')
    if not props.get('no dir') and (
            not symlink_dirs or 'run' not in symlink_dirs):
        run_dir.mkdir(parents=True)

    dirs_to_check = [run_dir_top_parent]
    if symlink_dirs:
        if 'run' in symlink_dirs:
            dst = tmp_path.joinpath(symlink_dirs['run'], 'cylc-run', reg)
            dst.mkdir(parents=True)
            run_dir.symlink_to(dst)
            dirs_to_check.append(dst)
            symlink_dirs.pop('run')
        for s, d in symlink_dirs.items():
            dst = tmp_path.joinpath(d, 'cylc-run', reg, s)
            dst.mkdir(parents=True)
            src = run_dir.joinpath(s)
            src.symlink_to(dst)
            dirs_to_check.append(dst.parent)
    if bad_symlink:
        dst = tmp_path.joinpath(bad_symlink['path'])
        if bad_symlink['type'] == 'file':
            dst.parent.mkdir(parents=True)
            dst.touch()
        else:
            dst.mkdir(parents=True)
        src = run_dir.joinpath('log')
        src.symlink_to(dst)

    def mocked_detect_old_contact_file(reg):
        if props.get('not stopped'):
            raise SuiteServiceFileError('Mocked error')

    monkeypatch.setattr('cylc.flow.suite_files.detect_old_contact_file',
                        mocked_detect_old_contact_file)
    monkeypatch.setattr('cylc.flow.suite_files.get_workflow_run_dir',
                        lambda x: tmp_path.joinpath('cylc-run', x))

    # --- The actual test ---
    expected_err = props.get('err')
    if expected_err:
        with pytest.raises(expected_err) as exc:
            suite_files.clean(reg)
        expected_msg = props.get('err msg')
        if expected_msg:
            assert expected_msg in str(exc.value)
    else:
        suite_files.clean(reg)
        for d in dirs_to_check:
            assert d.exists() is False
            assert d.is_symlink() is False


def test_clean_broken_symlink_run_dir(monkeypatch, tmp_path):
    """Test clean() for removing a run dir that is a broken symlink."""
    reg = 'foo/bar'
    run_dir = tmp_path.joinpath('cylc-run', reg)
    run_dir.parent.mkdir(parents=True)
    target = tmp_path.joinpath('rabbow/cylc-run', reg)
    target.mkdir(parents=True)
    run_dir.symlink_to(target)
    target.rmdir()

    monkeypatch.setattr('cylc.flow.suite_files.get_workflow_run_dir',
                        lambda x: tmp_path.joinpath('cylc-run', x))

    suite_files.clean(reg)
    assert run_dir.parent.is_dir() is False


PLATFORMS = {
    'enterprise': {
        'hosts': ['kirk', 'picard'],
        'install target': 'picard',
        'name': 'enterprise'
    },
    'voyager': {
        'hosts': ['janeway'],
        'install target': 'janeway',
        'name': 'voyager'
    },
    'stargazer': {
        'hosts': ['picard'],
        'install target': 'picard',
        'name': 'stargazer'
    },
    'exeter': {
        'hosts': ['localhost'],
        'install target': 'localhost',
        'name': 'exeter'
    }
}


@pytest.mark.parametrize(
    'install_targets_map, failed_platforms, expected_platforms, expected_err',
    [
        (
            {'localhost': [PLATFORMS['exeter']]}, None, None, None
        ),
        (
            {
                'localhost': [PLATFORMS['exeter']],
                'picard': [PLATFORMS['enterprise']]
            },
            None,
            ['enterprise'],
            None
        ),
        (
            {
                'picard': [PLATFORMS['enterprise'], PLATFORMS['stargazer']],
                'janeway': [PLATFORMS['voyager']]
            },
            None,
            ['enterprise', 'voyager'],
            None
        ),
        (
            {
                'picard': [PLATFORMS['enterprise'], PLATFORMS['stargazer']],
                'janeway': [PLATFORMS['voyager']]
            },
            ['enterprise'],
            ['enterprise', 'stargazer', 'voyager'],
            None
        ),
        (
            {
                'picard': [PLATFORMS['enterprise'], PLATFORMS['stargazer']],
                'janeway': [PLATFORMS['voyager']]
            },
            ['enterprise', 'stargazer'],
            ['enterprise', 'stargazer', 'voyager'],
            (CylcError, "Could not clean on install targets: picard")
        ),
        (
            {
                'picard': [PLATFORMS['enterprise']],
                'janeway': [PLATFORMS['voyager']]
            },
            ['enterprise', 'voyager'],
            ['enterprise', 'voyager'],
            (CylcError, "Could not clean on install targets: picard, janeway")
        )
    ]
)
def test_remote_clean(install_targets_map, failed_platforms,
                      expected_platforms, expected_err, monkeypatch, caplog):
    """Test remote_clean() logic.

    Params:
        install_targets_map (dict): The map that would be returned by
            platforms.get_install_target_to_platforms_map()
        failed_platforms (list): If specified, any platforms that clean will
            artificially fail on in this test case.
        expected_platforms (list): If specified, all the platforms that the
            remote clean cmd is expected to run on.
        expected_err (tuple):  If specified, a tuple of the form
            (Exception, str) giving an exception that is expected to be raised.
    """
    # ----- Setup -----
    caplog.set_level(logging.DEBUG, CYLC_LOG)
    monkeypatch.setattr(
        'cylc.flow.suite_files.get_install_target_to_platforms_map',
        lambda x: install_targets_map)
    # Remove randomness:
    mocked_shuffle = mock.Mock()
    monkeypatch.setattr('cylc.flow.suite_files.shuffle', mocked_shuffle)

    def mocked_remote_clean_cmd_side_effect(reg, platform, timeout):
        proc_ret_code = 0
        if failed_platforms and platform['name'] in failed_platforms:
            proc_ret_code = 1
        return mock.Mock(
            poll=lambda: proc_ret_code,
            communicate=lambda: (b"", b""),
            args=[])

    mocked_remote_clean_cmd = mock.Mock(
        side_effect=mocked_remote_clean_cmd_side_effect)
    monkeypatch.setattr(
        'cylc.flow.suite_files._remote_clean_cmd', mocked_remote_clean_cmd)
    # ----- Test -----
    reg = 'foo'
    platform_names = (
        "This arg bypassed as we provide the install targets map in the test")
    if expected_err:
        err, msg = expected_err
        with pytest.raises(err) as exc:
            suite_files.remote_clean(reg, platform_names, timeout='irrelevant')
        assert msg in str(exc.value)
    else:
        suite_files.remote_clean(reg, platform_names, timeout='irrelevant')
    if expected_platforms:
        for p_name in expected_platforms:
            mocked_remote_clean_cmd.assert_any_call(
                reg, PLATFORMS[p_name], 'irrelevant')
    else:
        mocked_remote_clean_cmd.assert_not_called()
    if failed_platforms:
        for p_name in failed_platforms:
            assert f"{p_name}: {TaskRemoteMgmtError.MSG_TIDY}" in caplog.text


def test_remove_empty_reg_parents(tmp_path):
    """Test that _remove_empty_parents() doesn't remove parents containing a
    sibling."""
    reg = 'foo/bar/baz/qux'
    path = tmp_path.joinpath(reg)
    tmp_path.joinpath('foo/bar/baz').mkdir(parents=True)
    sibling_reg = 'foo/darmok'
    sibling_path = tmp_path.joinpath(sibling_reg)
    sibling_path.mkdir()
    suite_files._remove_empty_reg_parents(reg, path)
    assert tmp_path.joinpath('foo/bar').exists() is False
    assert tmp_path.joinpath('foo').exists() is True
    # Also path must be absolute
    with pytest.raises(ValueError) as exc:
        suite_files._remove_empty_reg_parents('foo/darmok', 'meow/foo/darmok')
    assert 'Path must be absolute' in str(exc.value)
    # Check it skips non-existent dirs, and stops at the right place too
    tmp_path.joinpath('foo/bar').mkdir()
    sibling_path.rmdir()
    suite_files._remove_empty_reg_parents(reg, path)
    assert tmp_path.joinpath('foo').exists() is False
    assert tmp_path.exists() is True


@pytest.mark.parametrize(
    'run_dir, srv_dir',
    [
        ('a', 'a/R/.service'),
        ('d/a', 'd/a/a/R/.service'),
        ('z/d/a/a', 'z/d/a/a/R/.service')
    ]
)
def test_symlinkrundir_children_that_contain_workflows_raise_error(
        run_dir, srv_dir, monkeypatch):
    """Test that a workflow cannot be contained in a subdir of another
    workflow."""
    monkeypatch.setattr('cylc.flow.suite_files.os.path.isdir',
                        lambda x: False if (
                            x.find('.service') > 0 and x != srv_dir)
                        else True)
    monkeypatch.setattr(
        'cylc.flow.suite_files.get_cylc_run_abs_path',
        lambda x: x)
    monkeypatch.setattr('cylc.flow.suite_files.os.scandir',
                        lambda x: [
                            mock.Mock(path=srv_dir[0:len(x) + 2],
                                      is_symlink=lambda: True)])

    try:
        check_nested_run_dirs(run_dir, 'placeholder_flow')
    except SuiteServiceFileError:
        pytest.fail("Unexpected SuiteServiceFileError, Check symlink logic.")
