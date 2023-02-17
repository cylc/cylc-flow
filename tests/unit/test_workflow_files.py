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
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Optional,
    Type,
    Union,
)

import pytest

from cylc.flow import workflow_files
from cylc.flow.exceptions import (
    InputError,
    WorkflowFilesError,
)
from cylc.flow.workflow_files import (
    WorkflowFiles,
    abort_if_flow_file_in_path,
    check_flow_file,
    check_reserved_dir_names,
    detect_both_flow_and_suite,
    get_symlink_dirs,
    infer_latest_run,
    is_forbidden,
    is_installed,
    validate_workflow_name,
)

from .filetree import (
    FILETREE_1,
    FILETREE_2,
    FILETREE_3,
    FILETREE_4,
    create_filetree,
)

NonCallableFixture = Any


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
    flow_file = run_dir.joinpath(WorkflowFiles.FLOW_FILE)
    flow_file.touch()
    assert workflow_files.is_valid_run_dir(Path(prefix, 'foo/bar')) is True
    # What if service dir exists?
    flow_file.unlink()
    run_dir.joinpath(WorkflowFiles.Service.DIRNAME).mkdir()
    assert workflow_files.is_valid_run_dir(Path(prefix, 'foo/bar')) is True


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
            validate_workflow_name(reg)
        if expected_msg:
            assert expected_msg in str(exc.value)
    else:
        validate_workflow_name(reg)


@pytest.mark.parametrize(
    'name, err_expected',
    [
        # Basic ok:
        ('foo/bar/baz', False),
        # Reserved dir names:
        ('foo/log/baz', True),
        ('foo/runN/baz', True),
        ('foo/run9000/baz', True),
        ('work', True),
        # If not exact match, but substring, that's fine:
        ('foo/underrunN/baz', False),
        ('foo/overrun2', False),
        ('slog', False)
    ]
)
def test_check_reserved_dir_names(name: str, err_expected: bool):
    if err_expected:
        with pytest.raises(WorkflowFilesError) as exc_inf:
            check_reserved_dir_names(name)
        assert "cannot contain a directory named" in str(exc_inf.value)
    else:
        check_reserved_dir_names(name)


def test_validate_workflow_name__reserved_name():
    """Check that validate_workflow_name() doesn't check for reserved dir names
    unless we tell it to with the arg."""
    name = 'foo/runN'
    validate_workflow_name(name)
    with pytest.raises(WorkflowFilesError):
        validate_workflow_name(name, check_reserved_names=True)


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
    expected = (cylc_run_dir / expected_reg, expected_reg)

    # Test
    assert infer_latest_run(path, implicit_runN) == expected
    # Check implicit_runN=True is the default:
    if implicit_runN:
        assert infer_latest_run(path) == expected


@pytest.mark.parametrize('warn_arg', [True, False])
def test_infer_latest_run_warns_for_runN(
    warn_arg: bool,
    caplog: pytest.LogCaptureFixture,
    log_filter: Callable,
    tmp_run_dir: Callable,
):
    """Tests warning is produced to discourage use of /runN in workflow_id"""
    (tmp_run_dir() / 'run1').mkdir()
    runN_path = tmp_run_dir() / 'runN'
    runN_path.symlink_to('run1')
    infer_latest_run(runN_path, warn_runN=warn_arg)
    filtered_log = log_filter(
        caplog, level=logging.WARNING,
        contains="You do not need to include runN in the workflow ID"
    )
    assert filtered_log if warn_arg else not filtered_log


@pytest.mark.parametrize(
    ('reason', 'error_type'),
    [
        ('not dir', WorkflowFilesError),
        ('not symlink', WorkflowFilesError),
        ('broken symlink', WorkflowFilesError),
        ('invalid target', WorkflowFilesError),
        ('not exist', InputError)
    ]
)
def test_infer_latest_run__bad(
    reason: str,
    error_type: Type[Exception],
    tmp_run_dir: Callable,
) -> None:
    # -- Setup --
    cylc_run_dir: Path = tmp_run_dir()
    run_dir = cylc_run_dir / 'sulu'
    run_dir.mkdir()
    runN_path = run_dir / 'runN'
    err_msg = f"{runN_path} symlink not valid"
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
            f"{runN_path} symlink target not valid: palpatine"
        )
    elif reason == 'not exist':
        run_dir = run_dir / 'not-exist'
        err_msg = (
            f"Workflow ID not found: sulu/not-exist\n"
            f"(Directory not found: {run_dir})"
        )
    else:
        raise ValueError(reason)
    # -- Test --
    with pytest.raises(error_type) as excinfo:
        infer_latest_run(run_dir)
    assert str(excinfo.value) == err_msg


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
    'flow_file_exists, suiterc_exists, expected_file',
    [(True, False, WorkflowFiles.FLOW_FILE),
     (True, True, None),
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
    if expected_file is None:
        with pytest.raises(WorkflowFilesError) as exc:
            check_flow_file(tmp_path)
        assert str(exc.value) == (
            "Both flow.cylc and suite.rc files are present in "
            f"{tmp_path}. Please remove one and try again. "
            "For more information visit: "
            "https://cylc.github.io/cylc-doc/stable/html/7-to-8/summary.html"
            "#backward-compatibility"
        )

    else:
        assert check_flow_file(tmp_path) == tmp_path.joinpath(expected_file)


def test_detect_both_flow_and_suite(tmp_path):
    """Test flow.cylc and suite.rc (as files) together in dir raises error."""
    tmp_path.joinpath(WorkflowFiles.FLOW_FILE).touch()
    tmp_path.joinpath(WorkflowFiles.SUITE_RC).touch()

    forbidden = is_forbidden(tmp_path / WorkflowFiles.FLOW_FILE)
    assert forbidden is True
    with pytest.raises(WorkflowFilesError) as exc:
        detect_both_flow_and_suite(tmp_path)
    assert str(exc.value) == (
        f"Both flow.cylc and suite.rc files are present in {tmp_path}. Please "
        "remove one and try again. For more information visit: "
        "https://cylc.github.io/cylc-doc/stable/html/7-to-8/"
        "summary.html#backward-compatibility"
    )


def test_detect_both_flow_and_suite_symlinked(tmp_path):
    """Test flow.cylc symlinked to suite.rc together in dir is permitted."""
    (tmp_path / WorkflowFiles.SUITE_RC).touch()
    flow_file = tmp_path.joinpath(WorkflowFiles.FLOW_FILE)
    flow_file.symlink_to(WorkflowFiles.SUITE_RC)
    detect_both_flow_and_suite(tmp_path)


def test_flow_symlinked_elsewhere_and_suite_present(tmp_path: Path):
    """flow.cylc symlinked to suite.rc elsewhere, and suite.rc in dir raises"""
    tmp_path.joinpath('some_other_dir').mkdir(exist_ok=True)
    suite_file = tmp_path.joinpath('some_other_dir', WorkflowFiles.SUITE_RC)
    suite_file.touch()
    run_dir = tmp_path.joinpath('run_dir')
    run_dir.mkdir(exist_ok=True)
    flow_file = (run_dir / WorkflowFiles.FLOW_FILE)
    flow_file.symlink_to(suite_file)
    forbidden_external = is_forbidden(flow_file)
    assert forbidden_external is False
    (run_dir / WorkflowFiles.SUITE_RC).touch()
    forbidden = is_forbidden(flow_file)
    assert forbidden is True
    with pytest.raises(WorkflowFilesError) as exc:
        detect_both_flow_and_suite(run_dir)
    assert str(exc.value).startswith(
        "Both flow.cylc and suite.rc files are present in "
        f"{run_dir}. Please remove one and try again."
    )


def test_is_forbidden_symlink_returns_false_for_non_symlink(tmp_path):
    """Test sending a non symlink path is not marked as forbidden"""
    flow_file = (tmp_path / WorkflowFiles.FLOW_FILE)
    flow_file.touch()
    forbidden = is_forbidden(Path(flow_file))
    assert forbidden is False


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
            'inside.cylc', True, WorkflowFilesError, None,
            id="flow.cylc symlinked to file in run dir, suite.rc exists"
        ),
        pytest.param(
            'inside.cylc', False, None, WorkflowFiles.FLOW_FILE,
            id="flow.cylc symlinked to file in run dir, no suite.rc"
        ),
        pytest.param(
            '../outside.cylc', True, WorkflowFilesError, None,
            id="flow.cylc symlinked to file outside, suite.rc exists"
        ),
        pytest.param(
            '../outside.cylc', False, None, WorkflowFiles.FLOW_FILE,
            id="flow.cylc symlinked to file outside, no suite.rc"
        ),
        pytest.param(
            None, True, None, WorkflowFiles.SUITE_RC,
            id="No flow.cylc, suite.rc exists"
        ),
        pytest.param(
            None, False, WorkflowFilesError, None,
            id="No flow.cylc, no suite.rc"
        ),
    ]
)
def test_check_flow_file_symlink(
    flow_file_target: Optional[str],
    suiterc_exists: bool,
    err: Optional[Type[Exception]],
    expected_file: Optional[str],
    tmp_path: Path
) -> None:
    """Test check_flow_file() when flow.cylc is a symlink or doesn't exist.

    Params:
        flow_file_target: Relative path of the flow.cylc symlink's target,
            or None if the symlink doesn't exist.
        suiterc_exists: Whether there is a suite.rc file in the dir.
        err: Type of exception if expected to get raised.
        expected_file: Which file's path should get returned, when
            symlink_suiterc_arg is FALSE (otherwise it will always be
            flow.cylc, assuming no exception occurred).
    """
    run_dir = tmp_path / 'espresso'
    flow_file = run_dir / WorkflowFiles.FLOW_FILE
    suiterc = run_dir / WorkflowFiles.SUITE_RC
    run_dir.mkdir()
    (run_dir / '../outside.cylc').touch()
    (run_dir / 'inside.cylc').touch()
    if suiterc_exists:
        suiterc.touch()
    if flow_file_target:
        flow_file.symlink_to(flow_file_target)

    if err:
        with pytest.raises(err):
            check_flow_file(run_dir)
    else:
        assert expected_file is not None  # otherwise test is wrong
        result = check_flow_file(run_dir)
        assert result == run_dir / expected_file


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


def test_validate_abort_if_flow_file_in_path():
    assert abort_if_flow_file_in_path(Path("path/to/wflow")) is None
    with pytest.raises(InputError) as exc_info:
        abort_if_flow_file_in_path(Path("path/to/wflow/flow.cylc"))
    assert "Not a valid workflow ID or source directory" in str(exc_info.value)
