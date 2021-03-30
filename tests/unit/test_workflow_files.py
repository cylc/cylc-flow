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

from cylc.flow.option_parsers import Options
import logging
from pathlib import Path
import pytest
import shutil
from typing import Callable, Optional, Tuple, Type
from unittest import mock

from cylc.flow import CYLC_LOG
from cylc.flow import workflow_files
from cylc.flow.exceptions import (
    CylcError,
    ServiceFileError,
    TaskRemoteMgmtError,
    WorkflowFilesError
)
from cylc.flow.scripts.clean import get_option_parser as _clean_GOP
from cylc.flow.workflow_files import (
    WorkflowFiles,
    check_flow_file,
    check_nested_run_dirs,
    get_workflow_source_dir,
    reinstall_workflow, search_install_source_dirs)


CleanOpts = Options(_clean_GOP())


@pytest.mark.parametrize(
    'path, expected',
    [('a/b/c', '/mock_cylc_dir/a/b/c'),
     ('/a/b/c', '/a/b/c')]
)
def test_get_cylc_run_abs_path(
    path: str, expected: str,
    monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr('cylc.flow.pathutil._CYLC_RUN_DIR', '/mock_cylc_dir')
    assert workflow_files.get_cylc_run_abs_path(path) == expected


@pytest.mark.parametrize('is_abs_path', [False, True])
def test_is_valid_run_dir(is_abs_path: bool, tmp_run_dir: Callable):
    """Test that a directory is correctly identified as a valid run dir when
    it contains a service dir.
    """
    cylc_run_dir: Path = tmp_run_dir()
    prefix = str(cylc_run_dir) if is_abs_path else ''
    # What if no dir there?
    assert workflow_files.is_valid_run_dir(
        Path(prefix, 'nothing/here')) is False
    # What if only flow.cylc exists but no service dir?
    # (Non-run dirs can still contain flow.cylc)
    run_dir = cylc_run_dir.joinpath('foo/bar')
    run_dir.mkdir(parents=True)
    run_dir.joinpath(WorkflowFiles.FLOW_FILE).touch()
    assert workflow_files.is_valid_run_dir(Path(prefix, 'foo/bar')) is False
    # What if service dir exists?
    run_dir.joinpath(WorkflowFiles.Service.DIRNAME).mkdir()
    assert workflow_files.is_valid_run_dir(Path(prefix, 'foo/bar')) is True


def test_check_nested_run_dirs_parents(tmp_run_dir: Callable):
    """Test that check_nested_run_dirs() raises when a parent dir is a
    workflow directory."""
    cylc_run_dir: Path = tmp_run_dir()
    test_dir = cylc_run_dir.joinpath('a/b/c/d/e')
    test_dir.mkdir(parents=True)
    # Parents are not run dirs - ok:
    workflow_files.check_nested_run_dirs(test_dir, 'e')
    # Parent contains a run dir but that run dir is not direct ancestor
    # of our test dir - ok:
    tmp_run_dir('a/Z')
    workflow_files.check_nested_run_dirs(test_dir, 'e')
    # Now make run dir out of parent - not ok:
    tmp_run_dir('a')
    with pytest.raises(WorkflowFilesError) as exc:
        workflow_files.check_nested_run_dirs(test_dir, 'e')
    assert "Nested run directories not allowed" in str(exc.value)


def test_check_nested_run_dirs_children(tmp_run_dir: Callable):
    """Test that check_nested_run_dirs() raises when a child dir is a
    workflow directory."""
    cylc_run_dir: Path = tmp_run_dir()
    cylc_run_dir.joinpath('a/b/c/d/e').mkdir(parents=True)
    test_dir = cylc_run_dir.joinpath('a')
    # No run dir in children - ok:
    workflow_files.check_nested_run_dirs(test_dir, 'a')
    # Run dir in child - not ok:
    d: Path = tmp_run_dir('a/b/c/d/e')
    with pytest.raises(WorkflowFilesError) as exc:
        workflow_files.check_nested_run_dirs(test_dir, 'a')
    assert "Nested run directories not allowed" in str(exc.value)
    shutil.rmtree(d)
    # Run dir in child but below max scan depth - not ideal but passes:
    tmp_run_dir('a/b/c/d/e/f')
    workflow_files.check_nested_run_dirs(test_dir, 'a')


@pytest.mark.parametrize(
    'reg, expected_err, expected_msg',
    [('foo/bar/', None, None),
     ('/foo/bar', WorkflowFilesError, "cannot be an absolute path"),
     ('$HOME/alone', WorkflowFilesError, "invalid workflow name"),
     ('./foo', WorkflowFilesError, "invalid workflow name")]
)
def test_validate_flow_name(reg, expected_err, expected_msg):
    if expected_err:
        with pytest.raises(expected_err) as exc:
            workflow_files.validate_flow_name(reg)
        if expected_msg:
            assert expected_msg in str(exc.value)
    else:
        workflow_files.validate_flow_name(reg)


@pytest.mark.parametrize(
    'reg, not_stopped, err, err_msg',
    [('foo/..', False, WorkflowFilesError,
      "cannot be a path that points to the cylc-run directory or above"),
     ('foo/../..', False, WorkflowFilesError,
      "cannot be a path that points to the cylc-run directory or above"),
     ('foo', True, ServiceFileError, "Cannot remove running workflow")]
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
            raise ServiceFileError('Mocked error')

    monkeypatch.setattr('cylc.flow.workflow_files.detect_old_contact_file',
                        mocked_detect_old_contact_file)

    with pytest.raises(err) as exc:
        workflow_files._clean_check(reg, run_dir)
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
    monkeypatch.setattr('cylc.flow.workflow_files.clean', mocked_clean)
    mocked_remote_clean = mock.Mock()
    monkeypatch.setattr('cylc.flow.workflow_files.remote_clean',
                        mocked_remote_clean)
    monkeypatch.setattr('cylc.flow.workflow_files.get_workflow_run_dir',
                        lambda x: tmp_path.joinpath('cylc-run', x))

    _get_platforms_from_db = workflow_files.get_platforms_from_db

    def mocked_get_platforms_from_db(run_dir):
        if props.get('no dir') or props.get('no db'):
            return _get_platforms_from_db(run_dir)  # Handle as normal
        return set(props.get('db platforms'))

    monkeypatch.setattr('cylc.flow.workflow_files.get_platforms_from_db',
                        mocked_get_platforms_from_db)

    # --- The actual test ---
    workflow_files.init_clean(reg, opts=mock.Mock())
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
            'err': ServiceFileError,
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
            raise ServiceFileError('Mocked error')

    monkeypatch.setattr('cylc.flow.workflow_files.detect_old_contact_file',
                        mocked_detect_old_contact_file)
    monkeypatch.setattr('cylc.flow.workflow_files.get_workflow_run_dir',
                        lambda x: tmp_path.joinpath('cylc-run', x))

    # --- The actual test ---
    expected_err = props.get('err')
    if expected_err:
        with pytest.raises(expected_err) as exc:
            workflow_files.clean(reg)
        expected_msg = props.get('err msg')
        if expected_msg:
            assert expected_msg in str(exc.value)
    else:
        workflow_files.clean(reg)
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

    monkeypatch.setattr('cylc.flow.workflow_files.get_workflow_run_dir',
                        lambda x: tmp_path.joinpath('cylc-run', x))

    workflow_files.clean(reg)
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
        'cylc.flow.workflow_files.get_install_target_to_platforms_map',
        lambda x: install_targets_map)
    # Remove randomness:
    mocked_shuffle = mock.Mock()
    monkeypatch.setattr('cylc.flow.workflow_files.shuffle', mocked_shuffle)

    def mocked_remote_clean_cmd_side_effect(reg, platform, timeout):
        proc_ret_code = 0
        if failed_platforms and platform['name'] in failed_platforms:
            proc_ret_code = 1
        return mock.Mock(
            poll=lambda: proc_ret_code,
            communicate=lambda: ("", ""),
            args=[])

    mocked_remote_clean_cmd = mock.Mock(
        side_effect=mocked_remote_clean_cmd_side_effect)
    monkeypatch.setattr(
        'cylc.flow.workflow_files._remote_clean_cmd', mocked_remote_clean_cmd)
    # ----- Test -----
    reg = 'foo'
    platform_names = (
        "This arg bypassed as we provide the install targets map in the test")
    if expected_err:
        err, msg = expected_err
        with pytest.raises(err) as exc:
            workflow_files.remote_clean(
                reg, platform_names, timeout='irrelevant')
        assert msg in str(exc.value)
    else:
        workflow_files.remote_clean(reg, platform_names, timeout='irrelevant')
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
    workflow_files._remove_empty_reg_parents(reg, path)
    assert tmp_path.joinpath('foo/bar').exists() is False
    assert tmp_path.joinpath('foo').exists() is True
    # Also path must be absolute
    with pytest.raises(ValueError) as exc:
        workflow_files._remove_empty_reg_parents(
            'foo/darmok', 'meow/foo/darmok')
    assert 'Path must be absolute' in str(exc.value)
    # Check it skips non-existent dirs, and stops at the right place too
    tmp_path.joinpath('foo/bar').mkdir()
    sibling_path.rmdir()
    workflow_files._remove_empty_reg_parents(reg, path)
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
    monkeypatch.setattr('cylc.flow.workflow_files.os.path.isdir',
                        lambda x: False if (
                            x.find('.service') > 0 and x != srv_dir)
                        else True)
    monkeypatch.setattr(
        'cylc.flow.workflow_files.get_cylc_run_abs_path',
        lambda x: x)
    monkeypatch.setattr('cylc.flow.workflow_files.os.scandir',
                        lambda x: [
                            mock.Mock(path=srv_dir[0:len(x) + 2],
                                      is_symlink=lambda: True)])

    try:
        check_nested_run_dirs(run_dir, 'placeholder_flow')
    except ServiceFileError:
        pytest.fail(
            "Unexpected ServiceFileError, Check symlink logic.")


def test_get_workflow_source_dir_numbered_run(tmp_path):
    """Test get_workflow_source_dir returns correct source for numbered run"""
    cylc_install_dir = (
        tmp_path /
        "cylc-run" /
        "flow-name" /
        "_cylc-install")
    cylc_install_dir.mkdir(parents=True)
    run_dir = (tmp_path / "cylc-run" / "flow-name" / "run1")
    run_dir.mkdir()
    source_dir = (tmp_path / "cylc-source" / "flow-name")
    source_dir.mkdir(parents=True)
    assert get_workflow_source_dir(run_dir) == (None, None)
    (cylc_install_dir / "source").symlink_to(source_dir)
    assert get_workflow_source_dir(run_dir) == (
        str(source_dir), cylc_install_dir / "source")


def test_get_workflow_source_dir_named_run(tmp_path):
    """Test get_workflow_source_dir returns correct source for named run"""
    cylc_install_dir = (
        tmp_path /
        "cylc-run" /
        "flow-name" /
        "_cylc-install")
    cylc_install_dir.mkdir(parents=True)
    source_dir = (tmp_path / "cylc-source" / "flow-name")
    source_dir.mkdir(parents=True)
    (cylc_install_dir / "source").symlink_to(source_dir)
    assert get_workflow_source_dir(
        cylc_install_dir.parent) == (
        str(source_dir),
        cylc_install_dir / "source")


def test_reinstall_workflow(tmp_path, capsys):

    cylc_install_dir = (
        tmp_path /
        "cylc-run" /
        "flow-name" /
        "_cylc-install")
    cylc_install_dir.mkdir(parents=True)
    source_dir = (tmp_path / "cylc-source" / "flow-name")
    source_dir.mkdir(parents=True)
    (source_dir / "flow.cylc").touch()

    (cylc_install_dir / "source").symlink_to(source_dir)
    run_dir = cylc_install_dir.parent
    reinstall_workflow("flow-name", run_dir, source_dir)
    assert capsys.readouterr().out == (
        f"REINSTALLED flow-name from {source_dir}\n")


@pytest.mark.parametrize(
    'filename, expected_err',
    [('flow.cylc', None),
     ('suite.rc', None),
     ('fluff.txt', (WorkflowFilesError, "Could not find workflow 'baa/baa'"))]
)
def test_search_install_source_dirs(
        filename: str, expected_err: Optional[Tuple[Type[Exception], str]],
        tmp_path: Path, mock_glbl_cfg: Callable):
    """Test search_install_source_dirs().

    Params:
        filename: A file to insert into one of the source dirs.
        expected_err: Exception and message expected to be raised.
    """
    horse_dir = Path(tmp_path, 'horse')
    horse_dir.mkdir()
    sheep_dir = Path(tmp_path, 'sheep')
    source_dir = sheep_dir.joinpath('baa', 'baa')
    source_dir.mkdir(parents=True)
    source_dir_file = source_dir.joinpath(filename)
    source_dir_file.touch()
    mock_glbl_cfg(
        'cylc.flow.workflow_files.glbl_cfg',
        f'''
        [install]
            source dirs = {horse_dir}, {sheep_dir}
        '''
    )
    if expected_err:
        err, msg = expected_err
        with pytest.raises(err) as exc:
            search_install_source_dirs('baa/baa')
        assert msg in str(exc.value)
    else:
        flow_file = search_install_source_dirs('baa/baa')
        assert flow_file == source_dir


def test_search_install_source_dirs_empty(mock_glbl_cfg: Callable):
    """Test search_install_source_dirs() when no source dirs configured."""
    mock_glbl_cfg(
        'cylc.flow.workflow_files.glbl_cfg',
        '''
        [install]
            source dirs =
        '''
    )
    with pytest.raises(WorkflowFilesError) as exc:
        search_install_source_dirs('foo')
    assert str(exc.value) == (
        "Cannot find workflow as 'global.cylc[install]source dirs' "
        "does not contain any paths")


@pytest.mark.parametrize(
    'flow_file_exists, suiterc_exists, expected_file',
    [(True, False, WorkflowFiles.FLOW_FILE),
     (True, True, WorkflowFiles.FLOW_FILE),
     (False, True, WorkflowFiles.SUITE_RC)]
)
def test_check_flow_file(
    flow_file_exists: bool, suiterc_exists: bool, expected_file: str,
    tmp_path: Path
) -> None:
    """Test check_flow_file() returns the expected path.

    Params:
        flow_file_exists: Whether a flow.cylc file is found in the dir.
        suiterc_exists: Whether a suite.rc file is found in the dir.
        expected_file: Which file's path should get returned.
    """
    if flow_file_exists:
        tmp_path.joinpath(WorkflowFiles.FLOW_FILE).touch()
    if suiterc_exists:
        tmp_path.joinpath(WorkflowFiles.SUITE_RC).touch()

    assert check_flow_file(tmp_path) == tmp_path.joinpath(expected_file)


@pytest.mark.parametrize(
    'flow_file_target, suiterc_exists, err, expected_file',
    [
        pytest.param(
            WorkflowFiles.SUITE_RC, True, None, WorkflowFiles.FLOW_FILE,
            id="flow.cylc symlinked to suite.rc"
        ),
        pytest.param(
            WorkflowFiles.SUITE_RC, False, WorkflowFilesError, None,
            id="flow.cylc symlinked to non-existent suite.rc"
        ),
        pytest.param(
            'other-path', True, None, WorkflowFiles.SUITE_RC,
            id="flow.cylc symlinked to other file, suite.rc exists"
        ),
        pytest.param(
            'other-path', False, WorkflowFilesError, None,
            id="flow.cylc symlinked to other file, no suite.rc"
        ),
        pytest.param(
            None, True, None, WorkflowFiles.SUITE_RC,
            id="no flow.cylc, suite.rc exists"
        ),
        pytest.param(
            None, False, WorkflowFilesError, None,
            id="no flow.cylc, no suite.rc"
        ),
    ]
)
@pytest.mark.parametrize(
    'symlink_suiterc_arg',
    [pytest.param(False, id="symlink_suiterc=False "),
     pytest.param(True, id="symlink_suiterc=True ")]
)
def test_check_flow_file_symlink(
    flow_file_target: Optional[str],
    suiterc_exists: bool,
    err: Optional[Type[Exception]],
    expected_file: Optional[str],
    symlink_suiterc_arg: bool,
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Test check_flow_file() when flow.cylc is a symlink or doesn't exist.

    Params:
        flow_file_target: Relative path of the flow.cylc symlink's target, or
            None if the symlink doesn't exist.
        suiterc_exists: Whether there is a suite.rc file in the dir.
        err: Type of exception if expected to get raised.
        expected_file: Which file's path should get returned, when
            symlink_suiterc_arg is FALSE (otherwise it will always be
            flow.cylc, assuming no exception occurred).
        symlink_suiterc_arg: Value of the symlink_suiterc arg passed to
            check_flow_file().
    """
    flow_file = tmp_path.joinpath(WorkflowFiles.FLOW_FILE)
    suiterc = tmp_path.joinpath(WorkflowFiles.SUITE_RC)
    tmp_path.joinpath('other-path').touch()
    if suiterc_exists:
        suiterc.touch()
    if flow_file_target:
        flow_file.symlink_to(flow_file_target)
    log_msg = (
        f'The filename "{WorkflowFiles.SUITE_RC}" is deprecated '
        f'in favour of "{WorkflowFiles.FLOW_FILE}"')
    caplog.set_level(logging.WARNING, CYLC_LOG)

    if err:
        with pytest.raises(err):
            check_flow_file(tmp_path, symlink_suiterc_arg)
    else:
        assert expected_file is not None  # otherwise test is wrong
        result = check_flow_file(tmp_path, symlink_suiterc_arg)
        if symlink_suiterc_arg is True:
            assert flow_file.samefile(suiterc)
            expected_file = WorkflowFiles.FLOW_FILE
            if flow_file_target != WorkflowFiles.SUITE_RC:
                log_msg = f'{log_msg}. Symlink created.'
        assert result == tmp_path.joinpath(expected_file)
        assert caplog.messages == [log_msg]
