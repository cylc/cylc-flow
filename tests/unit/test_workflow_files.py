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

from glob import iglob
import logging
import os
from pathlib import Path
import pytest
import re
import shutil
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type, Union
from unittest import mock

from cylc.flow import CYLC_LOG
from cylc.flow import workflow_files
from cylc.flow.exceptions import (
    CylcError,
    PlatformError,
    ServiceFileError,
    UserInputError,
    WorkflowFilesError,
)
from cylc.flow.pathutil import parse_rm_dirs
from cylc.flow.scripts.clean import CleanOptions
from cylc.flow.workflow_files import (
    REG_CLASH_MSG,
    WorkflowFiles,
    _clean_using_glob,
    _remote_clean_cmd,
    check_flow_file,
    check_nested_run_dirs,
    clean,
    get_rsync_rund_cmd,
    get_symlink_dirs,
    get_workflow_source_dir,
    glob_in_run_dir,
    infer_latest_run,
    init_clean,
    is_installed,
    parse_cli_sym_dirs,
    parse_reg,
    reinstall_workflow,
    search_install_source_dirs
)

from .conftest import MonkeyMock
from .filetree import (
    FILETREE_1,
    FILETREE_2,
    FILETREE_3,
    FILETREE_4,
    create_filetree,
    get_filetree_as_list
)


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


def test_check_nested_run_dirs(tmp_run_dir: Callable):
    """Test that check_nested_run_dirs() raises when a parent dir is a
    workflow directory."""
    cylc_run_dir: Path = tmp_run_dir()
    test_dir = cylc_run_dir.joinpath('a/b/c/d/e')
    test_dir.mkdir(parents=True)
    # Parents are not run dirs - ok:
    check_nested_run_dirs(test_dir)
    # Parent contains a run dir but that run dir is not direct ancestor
    # of our test dir - ok:
    tmp_run_dir('a/Z')
    check_nested_run_dirs(test_dir)
    # Now make run dir out of parent - not ok:
    tmp_run_dir('a')
    with pytest.raises(WorkflowFilesError) as exc:
        check_nested_run_dirs(test_dir)
    assert "Nested run directories not allowed" in str(exc.value)


@pytest.mark.parametrize(
    'reg, expected_err, expected_msg',
    [('foo/bar/', None, None),
     ('/foo/bar', WorkflowFilesError, "cannot be an absolute path"),
     ('$HOME/alone', WorkflowFilesError, "invalid workflow name"),
     ('./foo', WorkflowFilesError, "invalid workflow name"),
     ('meow/..', WorkflowFilesError,
      "cannot be a path that points to the cylc-run directory or above")]
)
def test_validate_workflow_name(reg, expected_err, expected_msg):
    if expected_err:
        with pytest.raises(expected_err) as exc:
            workflow_files.validate_workflow_name(reg)
        if expected_msg:
            assert expected_msg in str(exc.value)
    else:
        workflow_files.validate_workflow_name(reg)


@pytest.mark.parametrize(
    'path, implicit_runN, expected_reg',
    [
        ('{cylc_run}/numbered/workflow', True, 'numbered/workflow/run2'),
        ('{cylc_run}/numbered/workflow', False, 'numbered/workflow'),
        ('{cylc_run}/numbered/workflow/runN', True, 'numbered/workflow/run2'),
        ('{cylc_run}/numbered/workflow/runN', False, 'numbered/workflow/run2'),
        ('{cylc_run}/numbered/workflow/run1', True, 'numbered/workflow/run1'),
        ('{cylc_run}/numbered/workflow/run1', False, 'numbered/workflow/run1'),
        ('{cylc_run}/non_numbered/workflow', True, 'non_numbered/workflow'),
        ('{cylc_run}/non_numbered/workflow', False, 'non_numbered/workflow'),
    ]
)
def test_infer_latest_run(
    path: str,
    implicit_runN: bool,
    expected_reg: str,
    tmp_run_dir: Callable,
) -> None:
    """Test infer_latest_run().

    Params:
        path: Input arg.
        implicit_runN: Input arg.
        expected_reg: The reg part of the expected returned tuple.
    """
    # Setup
    cylc_run_dir: Path = tmp_run_dir()

    run_dir = cylc_run_dir / 'numbered' / 'workflow'
    run_dir.mkdir(parents=True)
    (run_dir / 'run1').mkdir()
    (run_dir / 'run2').mkdir()
    (run_dir / 'runN').symlink_to('run2')

    run_dir = cylc_run_dir / 'non_numbered' / 'workflow' / 'named_run'
    run_dir.mkdir(parents=True)

    path: Path = Path(path.format(cylc_run=cylc_run_dir))
    expected = (cylc_run_dir / expected_reg, Path(expected_reg))

    # Test
    assert infer_latest_run(path, implicit_runN) == expected
    # Check implicit_runN=True is the default:
    if implicit_runN:
        assert infer_latest_run(path) == expected


@pytest.mark.parametrize(
    'reason',
    ['not dir', 'not symlink', 'broken symlink', 'invalid target']
)
def test_infer_latest_run__bad(
    reason: str,
    tmp_run_dir: Callable
) -> None:
    # -- Setup --
    cylc_run_dir: Path = tmp_run_dir()
    run_dir = cylc_run_dir / 'sulu'
    run_dir.mkdir()
    runN_path = run_dir / 'runN'
    err_msg = f"runN directory at {runN_path} is a broken or invalid symlink"
    if reason == 'not dir':
        (run_dir / 'run1').touch()
        runN_path.symlink_to('run1')
    elif reason == 'not symlink':
        runN_path.mkdir()
    elif reason == 'broken symlink':
        runN_path.symlink_to('run1')
    elif reason == 'invalid target':  # noqa: SIM106
        (run_dir / 'palpatine').mkdir()
        runN_path.symlink_to('palpatine')
        err_msg = (
            f"runN symlink at {runN_path} points to invalid "
            "location: palpatine"
        )
    else:
        raise ValueError(reason)
    # -- Test --
    with pytest.raises(WorkflowFilesError) as exc:
        infer_latest_run(run_dir)
    assert str(exc.value) == err_msg


@pytest.fixture(scope='module')
def setup__test_parse_reg(mod_tmp_run_dir: Callable):
    """Setup for test_parse_reg().

    Returns dict of template vars tmp_path, cylc_run_dir and cwd.
    """
    cylc_run_dir: Path = mod_tmp_run_dir()
    numbered_workflow = cylc_run_dir / 'numbered' / 'workflow'
    (numbered_workflow / 'run1').mkdir(parents=True)
    (numbered_workflow / 'run1' / 'flow.cylc').touch()
    (numbered_workflow / 'runN').symlink_to('run1')
    non_numbered_workflow = cylc_run_dir / 'non_numbered' / 'workflow'
    non_numbered_workflow.mkdir(parents=True)
    (non_numbered_workflow / 'flow.cylc').touch()
    (cylc_run_dir / 'empty').mkdir()
    tmp_path = cylc_run_dir.parent
    (tmp_path / 'random_file.cylc').touch()
    mock_cwd = tmp_path / 'mock-cwd'
    mock_cwd.mkdir()
    (mock_cwd / 'flow.cylc').touch()

    def _setup__test_parse_reg() -> Dict[str, Path]:
        return {
            'cylc_run_dir': cylc_run_dir,
            'tmp_path': tmp_path,
            'cwd': mock_cwd
        }

    orig_cwd = os.getcwd()
    os.chdir(mock_cwd)
    yield _setup__test_parse_reg
    os.chdir(orig_cwd)


@pytest.mark.parametrize('src', [True, False])
@pytest.mark.parametrize(
    'reg, expected_reg, expected_path',
    [
        pytest.param(
            'numbered/workflow',
            'numbered/workflow/run1',
            '{cylc_run_dir}/numbered/workflow/run1',
            id="numbered workflow"
        ),
        pytest.param(
            'numbered/workflow/runN',
            'numbered/workflow/run1',
            '{cylc_run_dir}/numbered/workflow/run1',
            id="numbered workflow targeted by runN"
        ),
        pytest.param(
            'non_numbered/workflow',
            'non_numbered/workflow',
            '{cylc_run_dir}/non_numbered/workflow',
            id="non-numbered workflow"
        ),
    ]
)
def test_parse_reg__ok(
    src: bool,
    reg: str,
    expected_reg: str,
    expected_path: str,
    setup__test_parse_reg: Callable
) -> None:
    """Test parse_reg() with relative reg.

    Params:
        src: Arg passed to parse_reg().
        reg: Arg passed to parse_reg().
        expected_reg: Expected reg returned for both src=True|False.
        expected_path: Expected path returned for src=False (for src=True,
            flow.cylc will be appended).
    """
    paths: dict = setup__test_parse_reg()
    expected_reg = expected_reg.format(**paths)
    expected_path: Path = Path(expected_path.format(**paths))
    if src:
        expected_path = expected_path / WorkflowFiles.FLOW_FILE
    assert parse_reg(reg, src) == (expected_reg, expected_path)


@pytest.mark.parametrize(
    'args, expected_reg, expected_path, expected_err_msg',
    [
        pytest.param(
            ('non_exist', False),
            'non_exist',
            '{cylc_run_dir}/non_exist',
            None,
            id="non-existent workflow, src=False"
        ),
        pytest.param(
            ('non_exist', True),
            None,
            None,
            "no flow.cylc or suite.rc in ",
            id="non-existent workflow, src=True"
        ),
        pytest.param(
            ('empty', True),
            None,
            None,
            "no flow.cylc or suite.rc in ",
            id="empty run dir, src=True"
        ),
        pytest.param(
            ('.', False),
            None,
            None,
            "invalid workflow name",
            id="dot for cwd, src=False"
        ),
        pytest.param(
            ('.', True),
            '{cwd}',
            '{cwd}/flow.cylc',
            None,
            id="dot for cwd, src=True"
        ),
        pytest.param(
            ('non_numbered/workflow/flow.cylc', False),
            None,
            None,
            "Workflow name must refer to a directory, not a file",
            id="reg refers to a file, src=False"
        ),
        pytest.param(
            ('non_numbered/workflow/flow.cylc', True),
            'non_numbered/workflow',
            '{cylc_run_dir}/non_numbered/workflow/flow.cylc',
            None,
            id="reg refers to a file, src=True"
        ),
        pytest.param(
            ('{cylc_run_dir}/non_numbered/workflow', False),
            None,
            None,
            "workflow name cannot be an absolute path",
            id="reg is absolute path, src=False"
        ),
        pytest.param(
            ('{cylc_run_dir}/non_numbered/workflow', True),
            'non_numbered/workflow',
            '{cylc_run_dir}/non_numbered/workflow/flow.cylc',
            None,
            id="reg is absolute path, src=True"
        ),
        pytest.param(
            ('{tmp_path}/random_file.cylc', True),
            '{tmp_path}',
            '{tmp_path}/random_file.cylc',
            None,
            id="reg is absolute path not in ~/cylc-run, src=True"
        ),
        pytest.param(
            ('foo/../../random_file.cylc', False),
            None,
            None,
            "cannot be a path that points to the cylc-run directory or above",
            id="reg points to path above, src=False"
        ),
        pytest.param(
            ('foo/../../random_file.cylc', True),
            '{tmp_path}',
            '{tmp_path}/random_file.cylc',
            None,
            id="reg points to path above, src=True"
        ),
    ]
)
def test_parse_reg__various(
    args: Tuple[str, bool],
    expected_reg: Optional[str],
    expected_path: Optional[str],
    expected_err_msg: Optional[str],
    setup__test_parse_reg: Callable
) -> None:
    """Test parse_reg() with various combinations of reg and src.

    Params:
        args: Args passed to parse_reg().
        expected_reg: Expected reg returned.
        expected_path: Expected path returned.
        expected_err_msg: If an exception is expected, text that is expected
            to be contained in the message.
    """
    paths: Dict[str, Path] = setup__test_parse_reg()
    reg, src = args
    reg = reg.format(**paths)

    if expected_err_msg:
        with pytest.raises(WorkflowFilesError) as exc_info:
            parse_reg(reg, src)
        assert expected_err_msg in str(exc_info.value)
    else:
        assert expected_reg is not None
        assert expected_path is not None
        expected_reg = expected_reg.format(**paths)
        expected_path = expected_path.format(**paths)
        assert parse_reg(reg, src) == (expected_reg, Path(expected_path))


@pytest.mark.parametrize(
    'reg_includes_flow_file', [True, False]
)
@pytest.mark.parametrize(
    'reg, clash_msg_expected',
    [('darmok/jalad', True),
     ('./darmok/jalad', False)]
)
def test_parse_reg__clash(
    reg: str,
    clash_msg_expected: bool,
    reg_includes_flow_file: bool,
    tmp_run_dir: Callable, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture
) -> None:
    """Test parse_reg() with src=True and a reg that exists both under cwd
    and ~/cylc-run

    Params:
        reg: Workflow reg arg.
        clash_msg_expected: Whether the reg clash message should get logged.
        reg_includes_flow_file: Whether to add '/flow.cylc' on the end of the
            reg arg passed to parse_reg().
    """
    caplog.set_level(logging.WARNING, CYLC_LOG)
    FLOW_FILE = WorkflowFiles.FLOW_FILE
    run_dir: Path = tmp_run_dir(reg)
    cwd = tmp_path / 'mock-cwd'
    (cwd / reg).mkdir(parents=True)
    (cwd / reg / FLOW_FILE).touch()
    monkeypatch.chdir(cwd)

    reg_arg = os.path.join(reg, FLOW_FILE) if reg_includes_flow_file else reg
    if reg.startswith(f"{os.curdir}{os.sep}"):
        reg = reg[2:]
    # The workflow file relative to cwd should take precedence
    assert parse_reg(reg_arg, src=True) == (
        str(cwd / reg),
        cwd / reg / FLOW_FILE
    )
    # If reg doesn't begin with './', it should warn that it also found a
    # workflow in ~/cylc-run but didn't use it
    if clash_msg_expected:
        expected_warning = REG_CLASH_MSG.format(
            os.path.join(reg, FLOW_FILE),
            run_dir.relative_to(tmp_path / 'cylc-run') / FLOW_FILE
        )
        assert expected_warning in caplog.messages
    else:
        assert caplog.record_tuples == []
    caplog.clear()
    # Now test that no warning when cwd == ~/cylc-run
    monkeypatch.chdir(tmp_path / 'cylc-run')
    assert parse_reg(reg_arg, src=True) == (reg, run_dir / FLOW_FILE)
    assert caplog.record_tuples == []


@pytest.mark.parametrize(
    'reg, stopped, err, err_msg',
    [
        ('foo/..', True, WorkflowFilesError,
         "cannot be a path that points to the cylc-run directory or above"),
        ('foo/../..', True, WorkflowFilesError,
         "cannot be a path that points to the cylc-run directory or above"),
        ('foo', False, ServiceFileError, "Cannot remove running workflow"),
    ]
)
def test_clean_check__fail(
    reg: str,
    stopped: bool,
    err: Type[Exception],
    err_msg: str,
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that _clean_check() fails appropriately.

    Params:
        reg: Workflow name.
        stopped: Whether the workflow is stopped when _clean_check() is called.
        err: Expected error class.
        err_msg: Message that is expected to be in the exception.
    """
    run_dir = mock.Mock()

    def mocked_detect_old_contact_file(*a, **k):
        if not stopped:
            raise ServiceFileError('Mocked error')

    monkeypatch.setattr(
        'cylc.flow.workflow_files.detect_old_contact_file',
        mocked_detect_old_contact_file
    )

    with pytest.raises(err) as exc:
        workflow_files._clean_check(CleanOptions(), reg, run_dir)
    assert err_msg in str(exc.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'db_platforms, opts, clean_called, remote_clean_called',
    [
        pytest.param(
            ['localhost', 'localhost'], {}, True, False,
            id="Only platform in DB is localhost"
        ),
        pytest.param(
            ['horse'], {}, True, True,
            id="Remote platform in DB"
        ),
        pytest.param(
            ['horse'], {'local_only': True}, True, False,
            id="Local clean only"
        ),
        pytest.param(
            ['horse'], {'remote_only': True}, False, True,
            id="Remote clean only"
        )
    ]
)
def test_init_clean(
    db_platforms: List[str],
    opts: Dict[str, Any],
    clean_called: bool,
    remote_clean_called: bool,
    monkeypatch: pytest.MonkeyPatch, monkeymock: MonkeyMock,
    tmp_run_dir: Callable
) -> None:
    """Test the init_clean() function logic.

    Params:
        db_platforms: Platform names that would be loaded from the database.
        opts: Any options passed to the cylc clean CLI.
        clean_called: If a local clean is expected to go ahead.
        remote_clean_called: If a remote clean is expected to go ahead.
    """
    reg = 'foo/bar/'
    tmp_run_dir(reg, installed=True)
    mock_clean = monkeymock('cylc.flow.workflow_files.clean')
    mock_remote_clean = monkeymock('cylc.flow.workflow_files.remote_clean')
    monkeypatch.setattr('cylc.flow.workflow_files.get_platforms_from_db',
                        lambda x: set(db_platforms))

    init_clean(reg, opts=CleanOptions(**opts))
    assert mock_clean.called is clean_called
    assert mock_remote_clean.called is remote_clean_called


@pytest.mark.asyncio
def test_init_clean__no_dir(
    monkeymock: MonkeyMock, tmp_run_dir: Callable,
    caplog: pytest.LogCaptureFixture
) -> None:
    """Test init_clean() when the run dir doesn't exist"""
    caplog.set_level(logging.INFO, CYLC_LOG)
    tmp_run_dir()
    mock_clean = monkeymock('cylc.flow.workflow_files.clean')
    mock_remote_clean = monkeymock('cylc.flow.workflow_files.remote_clean')

    init_clean('foo/bar', opts=CleanOptions())
    assert "No directory to clean" in caplog.text
    assert mock_clean.called is False
    assert mock_remote_clean.called is False


@pytest.mark.asyncio
def test_init_clean__no_db(
    monkeymock: MonkeyMock, tmp_run_dir: Callable,
    caplog: pytest.LogCaptureFixture
) -> None:
    """Test init_clean() when the workflow database doesn't exist"""
    caplog.set_level(logging.INFO, CYLC_LOG)
    tmp_run_dir('bespin')
    mock_clean = monkeymock('cylc.flow.workflow_files.clean')
    mock_remote_clean = monkeymock('cylc.flow.workflow_files.remote_clean')

    init_clean('bespin', opts=CleanOptions())
    assert "No workflow database - will only clean locally" in caplog.text
    assert mock_clean.called is True
    assert mock_remote_clean.called is False


@pytest.mark.asyncio
def test_init_clean__remote_only_no_db(
    monkeymock: MonkeyMock, tmp_run_dir: Callable
) -> None:
    """Test remote-only init_clean() when the workflow DB doesn't exist"""
    tmp_run_dir('hoth')
    mock_clean = monkeymock('cylc.flow.workflow_files.clean')
    mock_remote_clean = monkeymock('cylc.flow.workflow_files.remote_clean')

    with pytest.raises(ServiceFileError) as exc:
        init_clean('hoth', opts=CleanOptions(remote_only=True))
    assert ("No workflow database - cannot perform remote clean"
            in str(exc.value))
    assert mock_clean.called is False
    assert mock_remote_clean.called is False


@pytest.mark.asyncio
def test_init_clean__running_workflow(
    monkeypatch: pytest.MonkeyPatch, tmp_run_dir: Callable
) -> None:
    """Test init_clean() fails when workflow is still running"""
    def mock_err(*args, **kwargs):
        raise ServiceFileError("Mocked error")
    monkeypatch.setattr('cylc.flow.workflow_files.detect_old_contact_file',
                        mock_err)
    tmp_run_dir('yavin')

    with pytest.raises(ServiceFileError) as exc:
        init_clean('yavin', opts=CleanOptions())
    assert "Cannot remove running workflow" in str(exc.value)


@pytest.mark.asyncio
def test_init_clean__runN(
    monkeymock: MonkeyMock, tmp_run_dir: Callable
):
    """Test that init_clean() resolves the runN symlink"""
    # Setup
    run_dir: Path = tmp_run_dir('coruscant/run2')
    (run_dir.parent / 'runN').symlink_to(run_dir.name)
    tmp_run_dir('coruscant/run1')
    mock_clean = monkeymock('cylc.flow.workflow_files.clean', spec=clean)
    mock_remote_clean = monkeymock('cylc.flow.workflow_files.remote_clean')
    # Test
    # runN should be resolved
    init_clean('coruscant/runN', opts=CleanOptions())
    mock_clean.assert_called_once_with('coruscant/run2', run_dir, None)
    assert mock_remote_clean.called is False
    # It should not infer run number if runN not explicitly given
    with pytest.raises(WorkflowFilesError) as exc_info:
        init_clean('coruscant', opts=CleanOptions())
    assert "contains the following workflows" in str(exc_info.value)



@pytest.mark.asyncio
@pytest.mark.parametrize('number_of_runs', [1, 2])
@pytest.mark.parametrize(
    'force_opt',
    [pytest.param(False, id="normal"),
     pytest.param(True, id="--force")]
)
def test_init_clean__multiple_runs(
    force_opt: bool,
    number_of_runs: int,
    tmp_run_dir: Callable, monkeymock: MonkeyMock,
    caplog: pytest.LogCaptureFixture
) -> None:
    """Test init_clean() for workflow dirs that contain 1 or more run dirs."""
    # -- Setup --
    caplog.set_level(logging.WARNING, CYLC_LOG)
    for n in range(1, number_of_runs + 1):
        last_run_dir: Path = tmp_run_dir(f'foo/run{n}', named=True)
    workflow_dir = last_run_dir.parent  # Path to cylc-run/foo
    mock_clean = monkeymock(
        'cylc.flow.workflow_files.clean', spec=workflow_files.clean
    )
    opts = CleanOptions(force=force_opt)
    # -- Test --
    if number_of_runs > 1:
        if force_opt:
            # It should call clean() with 'foo' and log a warning
            init_clean('foo', opts)
            mock_clean.assert_called_once_with('foo', workflow_dir, None)
            msg = caplog.text
        else:
            # It should raise
            with pytest.raises(WorkflowFilesError) as exc_info:
                init_clean('foo', opts)
            msg = str(exc_info.value)
        assert "contains the following workflows" in msg
    else:
        # It should call clean() with 'foo/run1' followed by 'foo'
        init_clean('foo', opts)
        assert mock_clean.call_args_list == [
            mock.call('foo/run1', last_run_dir, None),
            mock.call('foo', workflow_dir, None)
        ]


@pytest.mark.asyncio
def test_init_clean__parent_rm_dirs(
    tmp_run_dir: Callable, monkeymock: MonkeyMock,
):
    """Test that init_clean() called on a parent dir containing 1 run dir,
    with the --rm dirs option, only cleans in the run dir."""
    # Setup
    run_dir: Path = tmp_run_dir('naboo/run1')
    for p in (run_dir, run_dir.parent):
        (p / 'jarjar').mkdir()
    # Test
    init_clean('naboo', opts=CleanOptions(rm_dirs=['jarjar']))
    assert (run_dir / 'jarjar').exists() is False
    assert (run_dir.parent / 'jarjar').exists() is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'rm_dirs, expected_clean, expected_remote_clean',
    [(None, None, []),
     (["r2d2:c3po"], {"r2d2", "c3po"}, ["r2d2:c3po"])]
)
def test_init_clean__rm_dirs(
    rm_dirs: Optional[List[str]],
    expected_clean: Set[str],
    expected_remote_clean: List[str],
    monkeymock: MonkeyMock, monkeypatch: pytest.MonkeyPatch,
    tmp_run_dir: Callable
) -> None:
    """Test init_clean() with the --rm option.

    Params:
        rm_dirs: Dirs given by --rm option.
        expected_clean: The dirs that are expected to be passed to clean().
        expected_remote_clean: The dirs that are expected to be passed to
            remote_clean().
    """
    reg = 'dagobah'
    run_dir: Path = tmp_run_dir(reg)
    mock_clean = monkeymock('cylc.flow.workflow_files.clean')
    mock_remote_clean = monkeymock('cylc.flow.workflow_files.remote_clean')
    platforms = {'platform_one'}
    monkeypatch.setattr('cylc.flow.workflow_files.get_platforms_from_db',
                        lambda x: platforms)
    opts = CleanOptions(rm_dirs=rm_dirs) if rm_dirs else CleanOptions()

    init_clean(reg, opts=opts)
    mock_clean.assert_called_with(reg, run_dir, expected_clean)
    mock_remote_clean.assert_called_with(
        reg, platforms, expected_remote_clean, opts.remote_timeout)


@pytest.mark.parametrize(
    'reg, symlink_dirs, rm_dirs, expected_deleted, expected_remaining',
    [
        pytest.param(
            'foo/bar',
            {},
            None,
            ['cylc-run/foo'],
            ['cylc-run'],
            id="Basic clean"
        ),
        pytest.param(
            'foo/bar/baz',
            {
                'log': 'sym-log',
                'share': 'sym-share',
                'share/cycle': 'sym-cycle',
                'work': 'sym-work'
            },
            None,
            ['cylc-run/foo', 'sym-log/cylc-run/foo', 'sym-share/cylc-run/foo',
             'sym-cycle/cylc-run/foo', 'sym-work/cylc-run/foo'],
            ['cylc-run', 'sym-log/cylc-run', 'sym-share/cylc-run',
             'sym-cycle/cylc-run', 'sym-work/cylc-run'],
            id="Symlink dirs"
        ),
        pytest.param(
            'foo',
            {
                'run': 'sym-run',
                'log': 'sym-log',
                'share': 'sym-share',
                'share/cycle': 'sym-cycle',
                'work': 'sym-work'
            },
            None,
            ['cylc-run/foo', 'sym-run/cylc-run/foo', 'sym-log/cylc-run/foo',
             'sym-share/cylc-run/foo', 'sym-cycle/cylc-run/foo',
             'sym-work/cylc-run/foo'],
            ['cylc-run', 'sym-run/cylc-run', 'sym-log/cylc-run',
             'sym-share/cylc-run', 'sym-cycle/cylc-run',
             'sym-work'],
            id="Symlink dirs including run dir"
        ),
        pytest.param(
            'foo',
            {},
            {'log', 'share'},
            ['cylc-run/foo/log', 'cylc-run/foo/share'],
            ['cylc-run/foo/work'],
            id="Targeted clean"
        ),
        pytest.param(
            'foo',
            {'log': 'sym-log'},
            {'log'},
            ['cylc-run/foo/log', 'sym-log/cylc-run/foo'],
            ['cylc-run/foo/work', 'cylc-run/foo/share/cycle',
             'sym-log/cylc-run'],
            id="Targeted clean with symlink dirs"
        ),
        pytest.param(
            'foo',
            {},
            {'share/cy*'},
            ['cylc-run/foo/share/cycle'],
            ['cylc-run/foo/log', 'cylc-run/foo/work', 'cylc-run/foo/share'],
            id="Targeted clean with glob"
        ),
        pytest.param(
            'foo',
            {'log': 'sym-log'},
            {'w*', 'wo*', 'l*', 'lo*'},
            ['cylc-run/foo/work', 'cylc-run/foo/log', 'sym-log/cylc-run/foo'],
            ['cylc-run/foo/share', 'cylc-run/foo/share/cycle'],
            id="Targeted clean with degenerate glob"
        ),
    ]
)
def test_clean(
    reg: str,
    symlink_dirs: Dict[str, str],
    rm_dirs: Optional[Set[str]],
    expected_deleted: List[str],
    expected_remaining: List[str],
    tmp_path: Path, tmp_run_dir: Callable
) -> None:
    """Test the clean() function.

    Params:
        reg: Workflow name.
        symlink_dirs: As you would find in the global config
            under [symlink dirs][platform].
        rm_dirs: As passed to clean().
        expected_deleted: Dirs (relative paths under tmp_path) that are
            expected to be cleaned.
        expected_remaining: Any dirs (relative paths under tmp_path) that are
            not expected to be cleaned.
    """
    # --- Setup ---
    run_dir: Path = tmp_run_dir(reg)

    if 'run' in symlink_dirs:
        target = tmp_path / symlink_dirs['run'] / 'cylc-run' / reg
        target.mkdir(parents=True)
        shutil.rmtree(run_dir)
        run_dir.symlink_to(target)
        symlink_dirs.pop('run')
    for symlink_name, target_name in symlink_dirs.items():
        target = tmp_path / target_name / 'cylc-run' / reg / symlink_name
        target.mkdir(parents=True)
        symlink = run_dir / symlink_name
        symlink.symlink_to(target)
    for d_name in ('log', 'share', 'share/cycle', 'work'):
        if d_name not in symlink_dirs:
            (run_dir / d_name).mkdir()

    for rel_path in [*expected_deleted, *expected_remaining]:
        assert (tmp_path / rel_path).exists()

    # --- The actual test ---
    workflow_files.clean(reg, run_dir, rm_dirs)
    for rel_path in expected_deleted:
        assert (tmp_path / rel_path).exists() is False
        assert (tmp_path / rel_path).is_symlink() is False
    for rel_path in expected_remaining:
        assert (tmp_path / rel_path).exists()


def test_clean__broken_symlink_run_dir(
    tmp_path: Path, tmp_run_dir: Callable
) -> None:
    """Test clean() successfully remove a run dir that is a broken symlink."""
    # Setup
    reg = 'foo/bar'
    run_dir: Path = tmp_run_dir(reg)
    target = tmp_path.joinpath('rabbow/cylc-run', reg)
    target.mkdir(parents=True)
    shutil.rmtree(run_dir)
    run_dir.symlink_to(target)
    target.rmdir()
    assert run_dir.parent.exists() is True  # cylc-run/foo should exist
    # Test
    workflow_files.clean(reg, run_dir)
    assert run_dir.parent.exists() is False  # cylc-run/foo should be gone
    assert target.parent.exists() is False  # rabbow/cylc-run/foo too


def test_clean__bad_symlink_dir_wrong_type(
    tmp_path: Path, tmp_run_dir: Callable
) -> None:
    """Test clean() raises error when a symlink dir actually points to a file
    instead of a dir"""
    reg = 'foo'
    run_dir: Path = tmp_run_dir(reg)
    symlink = run_dir.joinpath('log')
    target = tmp_path.joinpath('sym-log', 'cylc-run', reg, 'meow.txt')
    target.parent.mkdir(parents=True)
    target.touch()
    symlink.symlink_to(target)

    with pytest.raises(WorkflowFilesError) as exc:
        workflow_files.clean(reg, run_dir)
    assert "Target is not a directory" in str(exc.value)
    assert symlink.exists() is True


def test_clean__bad_symlink_dir_wrong_form(
    tmp_path: Path, tmp_run_dir: Callable
) -> None:
    """Test clean() raises error when a symlink dir points to an
    unexpected dir"""
    run_dir: Path = tmp_run_dir('foo')
    symlink = run_dir.joinpath('log')
    target = tmp_path.joinpath('sym-log', 'oops', 'log')
    target.mkdir(parents=True)
    symlink.symlink_to(target)

    with pytest.raises(WorkflowFilesError) as exc:
        workflow_files.clean('foo', run_dir)
    assert 'Expected target to end with "cylc-run/foo/log"' in str(exc.value)
    assert symlink.exists() is True


@pytest.mark.parametrize('pattern', ['thing/', 'thing/*'])
def test_clean__rm_dir_not_file(pattern: str, tmp_run_dir: Callable):
    """Test clean() does not remove a file when the rm_dir glob pattern would
    match a dir only."""
    reg = 'foo'
    run_dir: Path = tmp_run_dir(reg)
    a_file = run_dir.joinpath('thing')
    a_file.touch()
    rm_dirs = parse_rm_dirs([pattern])

    workflow_files.clean(reg, run_dir, rm_dirs)
    assert a_file.exists()


@pytest.mark.parametrize(
    'filetree, expected',
    [
        pytest.param(
            FILETREE_1,
            {'log': 'sym/cylc-run/foo/bar/log'},
            id="filetree1"
        ),
        pytest.param(
            FILETREE_2,
            {
                'share/cycle': 'sym-cycle/cylc-run/foo/bar/share/cycle',
                'share': 'sym-share/cylc-run/foo/bar/share',
                '': 'sym-run/cylc-run/foo/bar/'
            },
            id="filetree2"
        ),
        pytest.param(
            FILETREE_3,
            {
                'share/cycle': 'sym-cycle/cylc-run/foo/bar/share/cycle',
                '': 'sym-run/cylc-run/foo/bar/'
            },
            id="filetree3"
        ),
        pytest.param(
            FILETREE_4,
            {'share/cycle': 'sym-cycle/cylc-run/foo/bar/share/cycle'},
            id="filetree4"
        ),
    ]
)
def test_get_symlink_dirs(
    filetree: Dict[str, Any],
    expected: Dict[str, Union[Path, str]],
    tmp_run_dir: Callable, tmp_path: Path
):
    """Test get_symlink_dirs().

    Params:
        filetree: The directory structure to test against.
        expected: The expected return dictionary, except with the values being
            relative to tmp_path instead of absolute paths.
    """
    # Setup
    cylc_run_dir = tmp_run_dir()
    create_filetree(filetree, tmp_path, tmp_path)
    reg = 'foo/bar'
    for k, v in expected.items():
        expected[k] = Path(tmp_path / v)
    # Test
    assert get_symlink_dirs(reg, cylc_run_dir / reg) == expected


@pytest.mark.parametrize(
    'pattern, filetree, expected_matches',
    [
        pytest.param(
            '**',
            FILETREE_1,
            ['cylc-run/foo/bar',
             'cylc-run/foo/bar/log'],
            id="filetree1 **"
        ),
        pytest.param(
            '*',
            FILETREE_1,
            ['cylc-run/foo/bar/flow.cylc',
             'cylc-run/foo/bar/log',
             'cylc-run/foo/bar/mirkwood',
             'cylc-run/foo/bar/rincewind.txt'],
            id="filetree1 *"
        ),
        pytest.param(
            '**/*.txt',
            FILETREE_1,
            ['cylc-run/foo/bar/log/bib/fortuna.txt',
             'cylc-run/foo/bar/log/temba.txt',
             'cylc-run/foo/bar/rincewind.txt'],
            id="filetree1 **/*.txt"
        ),
        pytest.param(
            '**',
            FILETREE_2,
            ['cylc-run/foo/bar',
             'cylc-run/foo/bar/share',
             'cylc-run/foo/bar/share/cycle'],
            id="filetree2 **"
        ),
        pytest.param(
            '**',
            FILETREE_3,
            ['cylc-run/foo/bar',
             'cylc-run/foo/bar/share/cycle'],
            id="filetree3 **"
        ),
        pytest.param(
            '**/s*',
            FILETREE_3,
            ['cylc-run/foo/bar/share',
             'cylc-run/foo/bar/share/cycle/sokath.txt'],
            id="filetree3 **/s*"
        ),
        pytest.param(
            '**',
            FILETREE_4,
            ['cylc-run/foo/bar',
             'cylc-run/foo/bar/share/cycle'],
            id="filetree4 **"
        ),
    ]
)
def test_glob_in_run_dir(
    pattern: str,
    filetree: Dict[str, Any],
    expected_matches: List[str],
    tmp_path: Path, tmp_run_dir: Callable
) -> None:
    """Test that glob_in_run_dir() returns the minimal set of results with
    no redundant paths.
    """
    # Setup
    cylc_run_dir: Path = tmp_run_dir()
    reg = 'foo/bar'
    run_dir = cylc_run_dir / reg
    create_filetree(filetree, tmp_path, tmp_path)
    symlink_dirs = [run_dir / i for i in get_symlink_dirs(reg, run_dir)]
    expected = [tmp_path / i for i in expected_matches]
    # Test
    assert glob_in_run_dir(run_dir, pattern, symlink_dirs) == expected


@pytest.fixture
def filetree_for_testing_cylc_clean(tmp_path: Path):
    """Fixture that creates a filetree from the given dict, and returns which
    files are expected to be deleted and which aren't.

    See tests/unit/filetree.py

    Args:
        reg: Workflow name.
        initial_filetree: The filetree before cleaning.
        filetree_left_behind: The filetree that is expected to be left behind
            after cleaning, excluding the 'you-shall-not-pass/' directory,
            which is always expected to be left behind.

    Returns:
        run_dir: Workflow run dir.
        files_to_delete: List of files that are expected to be deleted.
        files_not_to_delete: List of files that are not expected to be deleted.
    """
    def _filetree_for_testing_cylc_clean(
        reg: str,
        initial_filetree: Dict[str, Any],
        filetree_left_behind: Dict[str, Any]
    ) -> Tuple[Path, List[str], List[str]]:
        create_filetree(initial_filetree, tmp_path, tmp_path)
        files_not_to_delete = [
            os.path.normpath(i) for i in
            iglob(str(tmp_path / 'you-shall-not-pass/**'), recursive=True)
        ]
        files_not_to_delete.extend(
            get_filetree_as_list(filetree_left_behind, tmp_path)
        )
        files_to_delete = list(
            set(get_filetree_as_list(initial_filetree, tmp_path)).difference(
                files_not_to_delete
            )
        )
        run_dir = tmp_path / 'cylc-run' / reg
        return run_dir, files_to_delete, files_not_to_delete
    return _filetree_for_testing_cylc_clean


@pytest.mark.parametrize(
    'pattern, initial_filetree, filetree_left_behind',
    [
        pytest.param(
            '**',
            FILETREE_1,
            {
                'cylc-run': {'foo': {}},
                'sym': {'cylc-run': {'foo': {'bar': {}}}}
            }
        ),
        pytest.param(
            '*/**',
            FILETREE_1,
            {
                'cylc-run': {'foo': {'bar': {
                    '.service': {'db': None},
                    'flow.cylc': None,
                    'rincewind.txt': Path('whatever')
                }}},
                'sym': {'cylc-run': {'foo': {'bar': {}}}}
            }
        ),
        pytest.param(
            '**/*.txt',
            FILETREE_1,
            {
                'cylc-run': {'foo': {'bar': {
                    '.service': {'db': None},
                    'flow.cylc': None,
                    'log': Path('whatever'),
                    'mirkwood': Path('whatever')
                }}},
                'sym': {'cylc-run': {'foo': {'bar': {
                    'log': {
                        'darmok': Path('whatever'),
                        'bib': {}
                    }
                }}}}
            }
        )
    ]
)
def test__clean_using_glob(
    pattern: str,
    initial_filetree: Dict[str, Any],
    filetree_left_behind: Dict[str, Any],
    filetree_for_testing_cylc_clean: Callable
) -> None:
    """Test _clean_using_glob(), particularly that it does not follow and
    delete symlinks (apart from the standard symlink dirs).

    Params:
        pattern: The glob pattern to test.
        initial_filetree: The filetree to test against.
        files_left_behind: The filetree expected to remain after
            _clean_using_glob() is called (excluding
            <tmp_path>/you-shall-not-pass, which is always expected to remain).
    """
    # --- Setup ---
    run_dir: Path
    files_to_delete: List[str]
    files_not_to_delete: List[str]
    run_dir, files_to_delete, files_not_to_delete = (
        filetree_for_testing_cylc_clean(
            'foo/bar', initial_filetree, filetree_left_behind)
    )
    # --- Test ---
    _clean_using_glob(run_dir, pattern, symlink_dirs=['log'])
    for file in files_not_to_delete:
        assert os.path.exists(file) is True
    for file in files_to_delete:
        assert os.path.lexists(file) is False


@pytest.mark.parametrize(
    'rm_dirs, initial_filetree, filetree_left_behind',
    [
        pytest.param(
            {'**'},
            FILETREE_1,
            {
                'cylc-run': {},
                'sym': {'cylc-run': {}}
            },
            id="filetree1 **"
        ),
        pytest.param(
            {'*/**'},
            FILETREE_1,
            {
                'cylc-run': {'foo': {'bar': {
                    '.service': {'db': None},
                    'flow.cylc': None,
                    'rincewind.txt': Path('whatever')
                }}},
                'sym': {'cylc-run': {}}
            },
            id="filetree1 */**"
        ),
        pytest.param(
            {'**/*.txt'},
            FILETREE_1,
            {
                'cylc-run': {'foo': {'bar': {
                    '.service': {'db': None},
                    'flow.cylc': None,
                    'log': Path('whatever'),
                    'mirkwood': Path('whatever')
                }}},
                'sym': {'cylc-run': {'foo': {'bar': {
                    'log': {
                        'darmok': Path('whatever'),
                        'bib': {}
                    }
                }}}}
            },
            id="filetree1 **/*.txt"
        ),
        pytest.param(
            {'**/cycle'},
            FILETREE_2,
            {
                'cylc-run': {'foo': {'bar': Path('sym-run/cylc-run/foo/bar')}},
                'sym-run': {'cylc-run': {'foo': {'bar': {
                    '.service': {'db': None},
                    'flow.cylc': None,
                    'share': Path('sym-share/cylc-run/foo/bar/share')
                }}}},
                'sym-share': {'cylc-run': {'foo': {'bar': {
                    'share': {}
                }}}},
                'sym-cycle': {'cylc-run': {}}
            },
            id="filetree2 **/cycle"
        ),
        pytest.param(
            {'share'},
            FILETREE_2,
            {
                'cylc-run': {'foo': {'bar': Path('sym-run/cylc-run/foo/bar')}},
                'sym-run': {'cylc-run': {'foo': {'bar': {
                    '.service': {'db': None},
                    'flow.cylc': None,
                }}}},
                'sym-share': {'cylc-run': {}},
                'sym-cycle': {'cylc-run': {'foo': {'bar': {
                    'share': {
                        'cycle': {
                            'macklunkey.txt': None
                        }
                    }
                }}}}
            },
            id="filetree2 share"
        ),
        pytest.param(
            {'**'},
            FILETREE_2,
            {
                'cylc-run': {},
                'sym-run': {'cylc-run': {}},
                'sym-share': {'cylc-run': {}},
                'sym-cycle': {'cylc-run': {}}
            },
            id="filetree2 **"
        ),
        pytest.param(
            {'*'},
            FILETREE_2,
            {
                'cylc-run': {'foo': {'bar': Path('sym-run/cylc-run/foo/bar')}},
                'sym-run': {'cylc-run': {'foo': {'bar': {
                    '.service': {'db': None},
                }}}},
                'sym-share': {'cylc-run': {}},
                'sym-cycle': {'cylc-run': {'foo': {'bar': {
                    'share': {
                        'cycle': {
                            'macklunkey.txt': None
                        }
                    }
                }}}}
            },
            id="filetree2 *"
        ),
        pytest.param(  # Check https://bugs.python.org/issue35201 has no effect
            {'non-exist/**'},
            FILETREE_2,
            FILETREE_2,
            id="filetree2 non-exist/**"
        ),
        pytest.param(
            {'**'},
            FILETREE_3,
            {
                'cylc-run': {},
                'sym-run': {'cylc-run': {}},
                'sym-cycle': {'cylc-run': {}},
            },
            id="filetree3 **"
        ),
        pytest.param(
            {'**'},
            FILETREE_4,
            {
                'cylc-run': {},
                'sym-cycle': {'cylc-run': {}},
            },
            id="filetree4 **"
        )
    ],
)
def test_clean__targeted(
    rm_dirs: Set[str],
    initial_filetree: Dict[str, Any],
    filetree_left_behind: Dict[str, Any],
    caplog: pytest.LogCaptureFixture, tmp_run_dir: Callable,
    filetree_for_testing_cylc_clean: Callable
) -> None:
    """Test clean(), particularly that it does not follow and delete symlinks
    (apart from the standard symlink dirs).

    This is similar to test__clean_using_glob(), but the filetree expected to
    remain after cleaning is different due to the tidy up of empty dirs.

    Params:
        rm_dirs: The glob patterns to test.
        initial_filetree: The filetree to test against.
        files_left_behind: The filetree expected to remain after
            clean() is called (excluding <tmp_path>/you-shall-not-pass,
            which is always expected to remain).
    """
    # --- Setup ---
    caplog.set_level(logging.DEBUG, CYLC_LOG)
    tmp_run_dir()
    reg = 'foo/bar'
    run_dir: Path
    files_to_delete: List[str]
    files_not_to_delete: List[str]
    run_dir, files_to_delete, files_not_to_delete = (
        filetree_for_testing_cylc_clean(
            reg, initial_filetree, filetree_left_behind)
    )
    # --- Test ---
    workflow_files.clean(reg, run_dir, rm_dirs)
    for file in files_not_to_delete:
        assert os.path.exists(file) is True
    for file in files_to_delete:
        assert os.path.lexists(file) is False


@pytest.mark.parametrize(
    'rm_dirs',
    [
        [".."],
        ["foo:.."],
        ["foo/../../meow"]
    ]
)
def test_init_clean__targeted_bad(
    rm_dirs: List[str],
    tmp_run_dir: Callable,
    monkeymock: MonkeyMock
):
    """Test init_clean() fails when abusing --rm option."""
    tmp_run_dir('chalmers')
    mock_clean = monkeymock('cylc.flow.workflow_files.clean')
    mock_remote_clean = monkeymock('cylc.flow.workflow_files.remote_clean')
    with pytest.raises(UserInputError) as exc_info:
        init_clean('chalmers', opts=CleanOptions(rm_dirs=rm_dirs))
    assert "cannot take paths that point to the run directory or above" in str(
        exc_info.value
    )
    mock_clean.assert_not_called()
    mock_remote_clean.assert_not_called()


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
    ('install_targets_map', 'failed_platforms', 'expected_platforms',
     'exc_expected', 'expected_err_msgs'),
    [
        pytest.param(
            {'localhost': [PLATFORMS['exeter']]}, None, None, False, [],
            id="Only localhost install target - no remote clean"
        ),
        pytest.param(
            {
                'localhost': [PLATFORMS['exeter']],
                'picard': [PLATFORMS['enterprise']]
            },
            None, ['enterprise'], False, [],
            id="Localhost and remote install target"
        ),
        pytest.param(
            {
                'picard': [PLATFORMS['enterprise'], PLATFORMS['stargazer']],
                'janeway': [PLATFORMS['voyager']]
            },
            None, ['enterprise', 'voyager'], False, [],
            id="Only remote install targets"
        ),
        pytest.param(
            {
                'picard': [PLATFORMS['enterprise'], PLATFORMS['stargazer']],
                'janeway': [PLATFORMS['voyager']]
            },
            {'enterprise': 255},
            ['enterprise', 'stargazer', 'voyager'],
            False,
            [],
            id="Install target with 1 failed, 1 successful platform"
        ),
        pytest.param(
            {
                'picard': [PLATFORMS['enterprise'], PLATFORMS['stargazer']],
                'janeway': [PLATFORMS['voyager']]
            },
            {'enterprise': 255, 'stargazer': 255},
            ['enterprise', 'stargazer', 'voyager'],
            True,
            ["Could not clean on install target: picard"],
            id="Install target with all failed platforms"
        ),
        pytest.param(
            {
                'picard': [PLATFORMS['enterprise']],
                'janeway': [PLATFORMS['voyager']]
            },
            {'enterprise': 255, 'voyager': 255},
            ['enterprise', 'voyager'],
            True,
            ["Could not clean on install target: picard",
             "Could not clean on install target: janeway"],
            id="All install targets have all failed platforms"
        ),
        pytest.param(
            {
                'picard': [PLATFORMS['enterprise'], PLATFORMS['stargazer']]
            },
            {'enterprise': 1},
            ['enterprise'],
            True,
            ["Could not clean on install target: picard"],
            id=("Remote clean cmd fails on a platform for non-SSH reason - "
                "does not retry")
        ),
    ]
)
def test_remote_clean(
    install_targets_map: Dict[str, Any],
    failed_platforms: Optional[Dict[str, int]],
    expected_platforms: Optional[List[str]],
    exc_expected: bool,
    expected_err_msgs: List[str],
    monkeymock: MonkeyMock, monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture, log_filter: Callable
) -> None:
    """Test remote_clean() logic.

    Params:
        install_targets_map The map that would be returned by
            platforms.get_install_target_to_platforms_map()
        failed_platforms: If specified, any platforms that clean will
            artificially fail on in this test case. The key is the platform
            name, the value is the remote clean cmd return code.
        expected_platforms: If specified, all the platforms that the
            remote clean cmd is expected to run on.
        exc_expected: If a CylcError is expected to be raised.
        expected_err_msgs: List of error messages expected to be in the log.
    """
    # ----- Setup -----
    caplog.set_level(logging.DEBUG, CYLC_LOG)
    monkeypatch.setattr(
        'cylc.flow.workflow_files.get_install_target_to_platforms_map',
        lambda x: install_targets_map)
    # Remove randomness:
    monkeymock('cylc.flow.workflow_files.shuffle')

    def mocked_remote_clean_cmd_side_effect(reg, platform, rm_dirs, timeout):
        proc_ret_code = 0
        if failed_platforms and platform['name'] in failed_platforms:
            proc_ret_code = failed_platforms[platform['name']]
        return mock.Mock(
            poll=lambda: proc_ret_code,
            communicate=lambda: ("Mocked stdout", "Mocked stderr"),
            args=[]
        )

    mocked_remote_clean_cmd = monkeymock(
        'cylc.flow.workflow_files._remote_clean_cmd',
        spec=_remote_clean_cmd,
        side_effect=mocked_remote_clean_cmd_side_effect)
    rm_dirs = ["whatever"]
    # ----- Test -----
    reg = 'foo'
    platform_names = (
        "This arg bypassed as we provide the install targets map in the test")
    if exc_expected:
        with pytest.raises(CylcError) as exc:
            workflow_files.remote_clean(
                reg, platform_names, rm_dirs, timeout='irrelevant')
        assert "Remote clean failed" in str(exc.value)
    else:
        workflow_files.remote_clean(
            reg, platform_names, rm_dirs, timeout='irrelevant')
    for msg in expected_err_msgs:
        assert log_filter(caplog, level=logging.ERROR, contains=msg)
    if expected_platforms:
        for p_name in expected_platforms:
            mocked_remote_clean_cmd.assert_any_call(
                reg, PLATFORMS[p_name], rm_dirs, 'irrelevant')
    else:
        mocked_remote_clean_cmd.assert_not_called()
    if failed_platforms:
        for p_name in failed_platforms:
            assert f"{p_name} - {PlatformError.MSG_TIDY}" in caplog.text

@pytest.mark.parametrize(
    'rm_dirs, expected_args',
    [
        (None, []),
        (['holodeck', 'ten_forward'],
         ['--rm', 'holodeck', '--rm', 'ten_forward'])
    ]
)
def test_remote_clean_cmd(
    rm_dirs: Optional[List[str]],
    expected_args: List[str],
    monkeymock: MonkeyMock
) -> None:
    """Test _remote_clean_cmd()

    Params:
        rm_dirs: Argument passed to _remote_clean_cmd().
        expected_args: Expected CLI arguments of the cylc clean command that
            gets constructed.
    """
    reg = 'jean/luc/picard'
    platform = {
        'name': 'enterprise',
        'install target': 'mars',
        'hosts': ['Trill'],
        'selection': {'method': 'definition order'}
    }
    mock_construct_ssh_cmd = monkeymock(
        'cylc.flow.workflow_files.construct_ssh_cmd', return_value=['blah'])
    monkeymock('cylc.flow.workflow_files.Popen')

    workflow_files._remote_clean_cmd(reg, platform, rm_dirs, timeout='dunno')
    args, kwargs = mock_construct_ssh_cmd.call_args
    constructed_cmd = args[0]
    assert constructed_cmd == ['clean', '--local-only', reg, *expected_args]


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

    caplog.set_level(logging.INFO, CYLC_LOG)
    log_msg = ""

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
                log_msg = "Symlink created: flow.cylc -> suite.rc"
        assert result == tmp_path.joinpath(expected_file)

    if log_msg:
        assert log_msg in caplog.messages


@pytest.mark.parametrize(
    'symlink_dirs, err_msg, expected',
    [
        ('log=$shortbread, share= $bourbon,share/cycle= $digestive, ',
         "There is an error in --symlink-dirs option:",
            None
         ),
        ('log=$shortbread share= $bourbon share/cycle= $digestive ',
         "There is an error in --symlink-dirs option:"
         " log=$shortbread share= $bourbon share/cycle= $digestive . "
         "Try entering option in the form --symlink-dirs="
         "'log=$DIR, share=$DIR2, ...'",
            None
         ),
        ('run=$NICE, log= $Garibaldi, share/cycle=$RichTea', None,
            {'localhost': {
                'run': '$NICE',
                'log': '$Garibaldi',
                'share/cycle': '$RichTea'
            }}
         ),
        ('some_other_dir=$bourbon',
         'some_other_dir not a valid entry for --symlink-dirs',
            {'some_other_dir': '£bourbon'}
         ),
    ]
)
def test_parse_cli_sym_dirs(
    symlink_dirs: str,
    err_msg: str,
    expected: Dict[str, Dict[str, Any]]
):
    """Test parse_cli_sym_dirs returns dict or correctly raises errors on cli
    symlink dir options"""
    if err_msg is not None:
        with pytest.raises(UserInputError) as exc:
            parse_cli_sym_dirs(symlink_dirs)
            assert(err_msg) in str(exc)

    else:
        actual = parse_cli_sym_dirs(symlink_dirs)

        assert actual == expected


@pytest.mark.parametrize(
    'reg, installed, named,  expected',
    [('reg1/run1', True, True, True),
     ('reg2', True, False, True),
     ('reg3', False, False, False)]
)
def test_is_installed(tmp_run_dir: Callable, reg, installed, named, expected):
    """Test is_installed correctly identifies presence of _cylc-install dir"""
    cylc_run_dir: Path = tmp_run_dir(reg, installed=installed, named=named)
    actual = is_installed(cylc_run_dir)
    assert actual == expected


def test_get_rsync_rund_cmd(tmp_run_dir: Callable):
    """Test rsync command for cylc install/reinstall excludes cylc dirs.
    """
    cylc_run_dir: Path = tmp_run_dir('rsync_flow', installed=True, named=False)
    for wdir in [
        WorkflowFiles.WORK_DIR,
        WorkflowFiles.SHARE_DIR,
        WorkflowFiles.LOG_DIR,
    ]:
        cylc_run_dir.joinpath(wdir).mkdir(exist_ok=True)
    actual_cmd = get_rsync_rund_cmd('blah', cylc_run_dir)
    assert actual_cmd == [
        'rsync', '-a', '--checksum', '--out-format=%o %n%L', '--no-t',
        '--exclude=log', '--exclude=work', '--exclude=share',
        '--exclude=_cylc-install', '--exclude=.service',
        'blah/', f'{cylc_run_dir}/']


@pytest.mark.parametrize(
    'expect, dirs',
    [
        (['run1'], ['run1', 'run2']),
        (['run1', 'run11'], ['run1', 'run11', 'run2']),
        (['run1200'], ['run1200', 'run1201']),
        (['foo'], ['foo', 'bar']),
    ]
)
def test_delete_runN(tmp_path, expect, dirs):
    """It deletes the runN symlink.
    """
    for dir_ in dirs:
        (tmp_path / dir_).mkdir()
    if re.findall(r'run\d*', dirs[-1]):
        (Path(tmp_path / 'runN')).symlink_to(dirs[-1])
    clean(str(tmp_path.name) + '/' + dirs[-1], tmp_path / dirs[-1])
    assert sorted([i.stem for i in tmp_path.glob('*')]) == sorted(expect)


def test_delete_runN_skipif_cleanedrun_not_runN(tmp_path):
    """It doesn't delete the symlink dir to be cleaned is not runN"""
    for folder in ['run1', 'run2']:
        (tmp_path / folder).mkdir()
    (tmp_path / 'runN').symlink_to(tmp_path / 'run2')
    clean(str(tmp_path.name) + '/' + 'run1', tmp_path / 'run1')
    assert sorted([i.stem for i in tmp_path.glob('*')]) == ['run2', 'runN']
