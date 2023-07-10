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
import shutil
from glob import iglob
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
)
from unittest import mock

import pytest

from cylc.flow import CYLC_LOG
from cylc.flow import clean as cylc_clean
from cylc.flow.clean import (
    _clean_using_glob,
    _remote_clean_cmd,
    clean,
    glob_in_run_dir,
    init_clean,
)
from cylc.flow.exceptions import (
    ContactFileExists,
    CylcError,
    InputError,
    PlatformError,
    ServiceFileError,
    WorkflowFilesError,
)
from cylc.flow.pathutil import parse_rm_dirs
from cylc.flow.scripts.clean import CleanOptions
from cylc.flow.workflow_files import (
    WorkflowFiles,
    get_symlink_dirs,
)

from .conftest import MonkeyMock
from .filetree import (
    FILETREE_1,
    FILETREE_2,
    FILETREE_3,
    FILETREE_4,
    create_filetree,
    get_filetree_as_list,
)

NonCallableFixture = Any


# global.cylc[install]scan depth for these tests:
MAX_SCAN_DEPTH = 3


@pytest.fixture
def glbl_cfg_max_scan_depth(mock_glbl_cfg: Callable) -> None:
    mock_glbl_cfg(
        'cylc.flow.workflow_files.glbl_cfg',
        f'''
        [install]
            max depth = {MAX_SCAN_DEPTH}
        '''
    )


@pytest.mark.parametrize(
    'reg, stopped, err, err_msg',
    [
        ('foo/..', True, WorkflowFilesError,
         "cannot be a path that points to the cylc-run directory or above"),
        ('foo/../..', True, WorkflowFilesError,
         "cannot be a path that points to the cylc-run directory or above"),
        ('foo', False, ServiceFileError, "Cannot clean running workflow"),
    ]
)
def test_clean_check__fail(
    reg: str,
    stopped: bool,
    err: Type[Exception],
    err_msg: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Test that _clean_check() fails appropriately.

    Params:
        reg: Workflow name.
        stopped: Whether the workflow is stopped when _clean_check() is called.
        err: Expected error class.
        err_msg: Message that is expected to be in the exception.
    """
    def mocked_detect_old_contact_file(*a, **k):
        if not stopped:
            raise ContactFileExists('Mocked error')

    monkeypatch.setattr(
        'cylc.flow.clean.detect_old_contact_file',
        mocked_detect_old_contact_file
    )

    with pytest.raises(err) as exc:
        cylc_clean._clean_check(CleanOptions(), reg, tmp_path)
    assert err_msg in str(exc.value)


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
    rdir = tmp_run_dir(reg, installed=True)
    Path(rdir, WorkflowFiles.Service.DIRNAME, WorkflowFiles.Service.DB).touch()
    mock_clean = monkeymock('cylc.flow.clean.clean')
    mock_remote_clean = monkeymock('cylc.flow.clean.remote_clean')
    monkeypatch.setattr('cylc.flow.clean.get_platforms_from_db',
                        lambda x: set(db_platforms))

    init_clean(reg, opts=CleanOptions(**opts))
    assert mock_clean.called is clean_called
    assert mock_remote_clean.called is remote_clean_called


def test_init_clean__no_dir(
    monkeymock: MonkeyMock, tmp_run_dir: Callable,
    caplog: pytest.LogCaptureFixture
) -> None:
    """Test init_clean() when the run dir doesn't exist"""
    caplog.set_level(logging.INFO, CYLC_LOG)
    tmp_run_dir()
    mock_clean = monkeymock('cylc.flow.clean.clean')
    mock_remote_clean = monkeymock('cylc.flow.clean.remote_clean')

    init_clean('foo/bar', opts=CleanOptions())
    assert "No directory to clean" in caplog.text
    assert mock_clean.called is False
    assert mock_remote_clean.called is False


def test_init_clean__no_db(
    monkeymock: MonkeyMock, tmp_run_dir: Callable,
    caplog: pytest.LogCaptureFixture
) -> None:
    """Test init_clean() when the workflow database doesn't exist"""
    caplog.set_level(logging.INFO, CYLC_LOG)
    tmp_run_dir('bespin')
    mock_clean = monkeymock('cylc.flow.clean.clean')
    mock_remote_clean = monkeymock('cylc.flow.clean.remote_clean')

    init_clean('bespin', opts=CleanOptions())
    assert (
        "No workflow database for bespin - will only clean locally"
    ) in caplog.text
    assert mock_clean.called is True
    assert mock_remote_clean.called is False


def test_init_clean__remote_only_no_db(
    monkeymock: MonkeyMock, tmp_run_dir: Callable
) -> None:
    """Test remote-only init_clean() when the workflow DB doesn't exist"""
    tmp_run_dir('hoth')
    mock_clean = monkeymock('cylc.flow.clean.clean')
    mock_remote_clean = monkeymock('cylc.flow.clean.remote_clean')

    with pytest.raises(ServiceFileError) as exc:
        init_clean('hoth', opts=CleanOptions(remote_only=True))
    assert (
        "No workflow database for hoth - cannot perform remote clean"
    ) in str(exc.value)
    assert mock_clean.called is False
    assert mock_remote_clean.called is False


def test_init_clean__running_workflow(
    monkeypatch: pytest.MonkeyPatch, tmp_run_dir: Callable
) -> None:
    """Test init_clean() fails when workflow is still running"""
    def mock_err(*args, **kwargs):
        raise ContactFileExists("Mocked error")
    monkeypatch.setattr('cylc.flow.clean.detect_old_contact_file',
                        mock_err)
    tmp_run_dir('yavin')

    with pytest.raises(ServiceFileError) as exc:
        init_clean('yavin', opts=CleanOptions())
    assert "Cannot clean running workflow" in str(exc.value)


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
    Path(run_dir, WorkflowFiles.Service.DIRNAME, WorkflowFiles.Service.DB).touch()
    mock_clean = monkeymock('cylc.flow.clean.clean')
    mock_remote_clean = monkeymock('cylc.flow.clean.remote_clean')
    platforms = {'platform_one'}
    monkeypatch.setattr('cylc.flow.clean.get_platforms_from_db',
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
    cylc_clean.clean(reg, run_dir, rm_dirs)
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
    cylc_clean.clean(reg, run_dir)
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
        cylc_clean.clean(reg, run_dir)
    assert "Invalid symlink at" in str(exc.value)
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
        cylc_clean.clean('foo', run_dir)
    assert 'should end with "cylc-run/foo/log"' in str(exc.value)
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

    cylc_clean.clean(reg, run_dir, rm_dirs)
    assert a_file.exists()


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
    cylc_clean.clean(reg, run_dir, rm_dirs)
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
    mock_clean = monkeymock('cylc.flow.clean.clean')
    mock_remote_clean = monkeymock('cylc.flow.clean.remote_clean')
    with pytest.raises(InputError) as exc_info:
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
            ["Could not clean foo on install target: picard"],
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
            ["Could not clean foo on install target: picard",
             "Could not clean foo on install target: janeway"],
            id="All install targets have all failed platforms"
        ),
        pytest.param(
            {
                'picard': [PLATFORMS['enterprise'], PLATFORMS['stargazer']]
            },
            {'enterprise': 1},
            ['enterprise'],
            True,
            ["Could not clean foo on install target: picard"],
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
        'cylc.flow.clean.get_install_target_to_platforms_map',
        lambda x: install_targets_map)
    # Remove randomness:
    monkeymock('cylc.flow.clean.shuffle')

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
        'cylc.flow.clean._remote_clean_cmd',
        spec=_remote_clean_cmd,
        side_effect=mocked_remote_clean_cmd_side_effect)
    rm_dirs = ["whatever"]
    # ----- Test -----
    reg = 'foo'
    platform_names = (
        "This arg bypassed as we provide the install targets map in the test")
    if exc_expected:
        with pytest.raises(CylcError) as exc:
            cylc_clean.remote_clean(
                reg, platform_names, rm_dirs, timeout='irrelevant')
        assert "Remote clean failed" in str(exc.value)
    else:
        cylc_clean.remote_clean(
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
        'cylc.flow.clean.construct_ssh_cmd', return_value=['blah'])
    monkeymock('cylc.flow.clean.Popen')

    cylc_clean._remote_clean_cmd(reg, platform, rm_dirs, timeout='dunno')
    args, kwargs = mock_construct_ssh_cmd.call_args
    constructed_cmd = args[0]
    assert constructed_cmd == ['clean', '--local-only', reg, *expected_args]


def test_clean_top_level(tmp_run_dir: Callable):
    """Test that cleaning last remaining run dir inside a workflow dir removes
    the top level dir if it's empty (excluding _cylc-install)."""
    # Setup
    reg = 'blue/planet/run1'
    run_dir: Path = tmp_run_dir(reg, installed=True, named=True)
    cylc_install_dir = run_dir.parent / WorkflowFiles.Install.DIRNAME
    assert cylc_install_dir.is_dir()
    runN_symlink = run_dir.parent / WorkflowFiles.RUN_N
    assert runN_symlink.exists()
    # Test
    clean(reg, run_dir)
    assert not run_dir.parent.parent.exists()
    # Now check that if the top level dir is not empty, it doesn't get removed
    run_dir: Path = tmp_run_dir(reg, installed=True, named=True)
    jellyfish_file = (run_dir.parent / 'jellyfish.txt')
    jellyfish_file.touch()
    clean(reg, run_dir)
    assert cylc_install_dir.is_dir()
    assert jellyfish_file.exists()


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
