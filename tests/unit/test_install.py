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
import shutil
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Optional,
    Tuple,
    Type,
    Union,
)

import pytest

from cylc.flow.exceptions import (
    InputError,
    WorkflowFilesError,
)
from cylc.flow.workflow_files import (
    WorkflowFiles,
    get_workflow_source_dir,
)
from cylc.flow.install import (
    NESTED_DIRS_MSG,
    check_nested_dirs,
    get_rsync_rund_cmd,
    get_run_dir_info,
    get_source_workflow_name,
    install_workflow,
    parse_cli_sym_dirs,
    reinstall_workflow,
    search_install_source_dirs,
    validate_source_dir,
)

NonCallableFixture = Any


# global.cylc[install]scan depth for these tests:
MAX_SCAN_DEPTH = 3


@pytest.fixture
def glbl_cfg_max_scan_depth(mock_glbl_cfg: Callable) -> None:
    mock_glbl_cfg(
        'cylc.flow.install.glbl_cfg',
        f'''
        [install]
            max depth = {MAX_SCAN_DEPTH}
        '''
    )


@pytest.mark.parametrize(
    'workflow_name, err_expected',
    [
        ('foo/' * (MAX_SCAN_DEPTH - 1), False),
        ('foo/' * MAX_SCAN_DEPTH, True)  # /run1 takes it beyond max depth
    ]
)
def test_install_workflow__max_depth(
    workflow_name: str,
    err_expected: bool,
    tmp_run_dir: Callable,
    tmp_src_dir: Callable,
    glbl_cfg_max_scan_depth: NonCallableFixture,
    prevent_symlinking,
):
    """Test that trying to install beyond max depth fails."""
    src_dir = tmp_src_dir('bar')
    if err_expected:
        with pytest.raises(WorkflowFilesError) as exc_info:
            install_workflow(src_dir, workflow_name)
        assert "would exceed global.cylc[install]max depth" in str(
            exc_info.value
        )
    else:
        install_workflow(src_dir, workflow_name)


@pytest.mark.parametrize(
    'flow_file, expected_exc',
    [
        (WorkflowFiles.FLOW_FILE, WorkflowFilesError),
        (WorkflowFiles.SUITE_RC, WorkflowFilesError),
        (None, None)
    ]
)
def test_install_workflow__next_to_flow_file(
    flow_file: Optional[str],
    expected_exc: Optional[Type[Exception]],
    tmp_run_dir: Callable,
    tmp_src_dir: Callable,
    prevent_symlinking,
):
    """Test that you can't install into a dir that contains a workflow file."""
    # Setup
    cylc_run_dir: Path = tmp_run_dir()
    workflow_dir = cylc_run_dir / 'faden'
    workflow_dir.mkdir()
    src_dir: Path = tmp_src_dir('faden')
    if flow_file:
        (workflow_dir / flow_file).touch()
    # Test
    if expected_exc:
        with pytest.raises(expected_exc) as exc_info:
            install_workflow(src_dir, 'faden')
        assert "Nested run directories not allowed" in str(exc_info.value)
    else:
        install_workflow(src_dir, 'faden')


def test_install_workflow__symlink_target_exists(
    tmp_path: Path,
    tmp_src_dir: Callable,
    tmp_run_dir: Callable,
    mock_glbl_cfg: Callable,
):
    """Test that you can't install workflow when run dir symlink dir target
    already exists."""
    id_ = 'smeagol'
    src_dir: Path = tmp_src_dir(id_)
    sym_run = tmp_path / 'sym-run'
    sym_log = tmp_path / 'sym-log'
    mock_glbl_cfg(
        'cylc.flow.pathutil.glbl_cfg',
        f'''
        [install]
            [[symlink dirs]]
                [[[localhost]]]
                    run = {sym_run}
                    log = {sym_log}
        '''
    )
    msg = "Symlink dir target already exists: .*{}"
    # Test:
    (sym_run / 'cylc-run' / id_ / 'run1').mkdir(parents=True)
    with pytest.raises(WorkflowFilesError, match=msg.format(sym_run)):
        install_workflow(src_dir)

    shutil.rmtree(sym_run)
    (
        sym_log / 'cylc-run' / id_ / 'run1' / WorkflowFiles.LogDir.DIRNAME
    ).mkdir(parents=True)
    with pytest.raises(WorkflowFilesError, match=msg.format(sym_log)):
        install_workflow(src_dir)


def test_check_nested_dirs(
    tmp_run_dir: Callable,
    glbl_cfg_max_scan_depth: NonCallableFixture
):
    """Test that check_nested_dirs() raises when a parent dir is a
    workflow directory."""
    cylc_run_dir: Path = tmp_run_dir()
    test_dir = cylc_run_dir.joinpath('a/' * (MAX_SCAN_DEPTH + 3))
    # note we check beyond max scan depth (because we're checking upwards)
    test_dir.mkdir(parents=True)
    # Parents are not run dirs - ok:
    check_nested_dirs(test_dir)
    # Parent contains a run dir but that run dir is not direct ancestor
    # of our test dir - ok:
    tmp_run_dir('a/Z')
    check_nested_dirs(test_dir)
    # Now make run dir out of parent - not ok:
    tmp_run_dir('a')
    with pytest.raises(WorkflowFilesError) as exc:
        check_nested_dirs(test_dir)
    assert str(exc.value) == NESTED_DIRS_MSG.format(
        dir_type='run', dest=test_dir, existing=(cylc_run_dir / 'a')
    )


@pytest.mark.parametrize(
    'named_run', [True, False]
)
@pytest.mark.parametrize(
    'test_install_path, existing_install_path',
    [
        pytest.param(
            f'{"child/" * (MAX_SCAN_DEPTH + 3)}',
            '',
            id="Check parents (beyond max scan depth)"
        ),
        pytest.param(
            '',
            f'{"child/" * MAX_SCAN_DEPTH}',
            id="Check children up to max scan depth"
        )
    ]
)
def test_check_nested_dirs_install_dirs(
    tmp_run_dir: Callable,
    glbl_cfg_max_scan_depth: NonCallableFixture,
    test_install_path: str,
    existing_install_path: str,
    named_run: bool
):
    """Test that check nested dirs looks both up and down a tree for
    WorkflowFiles.Install.DIRNAME.

    Params:
        test_install_path: Path relative to ~/cylc-run/thing where we are
            trying to install a workflow.
        existing_install_path: Path relative to ~/cylc-run/thing where there
            is an existing install dir.
        named_run: Whether the workflow we are trying to install has
            named/numbered run.
    """
    cylc_run_dir: Path = tmp_run_dir()
    existing_install: Path = tmp_run_dir(
        f'thing/{existing_install_path}/run1', installed=True, named=True
    ).parent
    test_install_dir = cylc_run_dir / 'thing' / test_install_path
    test_run_dir = test_install_dir / 'run1' if named_run else test_install_dir
    with pytest.raises(WorkflowFilesError) as exc:
        check_nested_dirs(test_run_dir, test_install_dir)
    assert str(exc.value) == NESTED_DIRS_MSG.format(
        dir_type='install', dest=test_run_dir, existing=existing_install
    )


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
    reinstall_workflow(source_dir, "flow-name", run_dir)
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
    horse_dir = tmp_path / 'horse'
    horse_dir.mkdir()
    sheep_dir = tmp_path / 'sheep'
    source_dir = sheep_dir / 'baa' / 'baa'
    source_dir.mkdir(parents=True)
    source_dir_file = source_dir / filename
    source_dir_file.touch()
    mock_glbl_cfg(
        'cylc.flow.install.glbl_cfg',
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
        ret = search_install_source_dirs('baa/baa')
        assert ret == source_dir
        assert ret.is_absolute()


def test_search_install_source_dirs_empty(mock_glbl_cfg: Callable):
    """Test search_install_source_dirs() when no source dirs configured."""
    mock_glbl_cfg(
        'cylc.flow.install.glbl_cfg',
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
    'path, expected',
    [
        ('~/isla/nublar/dennis/nedry', 'dennis/nedry'),
        ('~/isla/sorna/paul/kirby', 'paul/kirby'),
        ('~/mos/eisley/owen/skywalker', 'skywalker')
    ]
)
def test_get_source_workflow_name(
    path: str,
    expected: str,
    mock_glbl_cfg: Callable
):
    mock_glbl_cfg(
        'cylc.flow.install.glbl_cfg',
        '''
        [install]
            source dirs = ~/isla/nublar, ${HOME}/isla/sorna
        '''
    )
    assert get_source_workflow_name(
        Path(path).expanduser().resolve()) == expected


def test_get_rsync_rund_cmd(
    tmp_src_dir: Callable,
    tmp_run_dir: Callable
):
    """Test rsync command for cylc install/reinstall excludes cylc dirs.
    """
    src_dir = tmp_src_dir('foo')
    cylc_run_dir: Path = tmp_run_dir('rsync_flow', installed=True, named=False)
    for wdir in [
        WorkflowFiles.WORK_DIR,
        WorkflowFiles.SHARE_DIR,
        WorkflowFiles.LogDir.DIRNAME,
    ]:
        cylc_run_dir.joinpath(wdir).mkdir(exist_ok=True)
    actual_cmd = get_rsync_rund_cmd(src_dir, cylc_run_dir)
    assert actual_cmd == [
        'rsync', '-a', '--checksum', '--out-format=%o %n%L', '--no-t',
        '--exclude=/log', '--exclude=/work', '--exclude=/share',
        '--exclude=/_cylc-install', '--exclude=/.service',
        f'{src_dir}/', f'{cylc_run_dir}/']


@pytest.mark.parametrize(
    'args, expected_relink, expected_run_num, expected_run_dir',
    [
        (
            ['{cylc_run}/numbered', None, False],
            True, 1, '{cylc_run}/numbered/run1'
        ),
        (
            ['{cylc_run}/named', 'dukat', False],
            False, None, '{cylc_run}/named/dukat'
        ),
        (
            ['{cylc_run}/unnamed', None, True],
            False, None, '{cylc_run}/unnamed'
        ),
    ]
)
def test_get_run_dir_info(
    args: list,
    expected_relink: bool,
    expected_run_num: Optional[int],
    expected_run_dir: Union[Path, str],
    tmp_run_dir: Callable
):
    """Test get_run_dir_info().

    Params:
        args: Input args to function.
        expected_*: Expected return values.
    """
    # Setup
    cylc_run_dir: Path = tmp_run_dir()
    sub = lambda x: Path(x.format(cylc_run=cylc_run_dir))  # noqa: E731
    args[0] = sub(args[0])
    expected_run_dir = sub(expected_run_dir)
    # Test
    assert get_run_dir_info(*args) == (
        expected_relink, expected_run_num, expected_run_dir
    )
    assert expected_run_dir.is_absolute()


def test_get_run_dir_info__increment_run_num(tmp_run_dir: Callable):
    """Test that get_run_dir_info() increments run number and unlinks runN."""
    # Setup
    cylc_run_dir: Path = tmp_run_dir()
    run_dir: Path = tmp_run_dir('gowron/run1')
    runN = run_dir.parent / WorkflowFiles.RUN_N
    assert os.path.lexists(runN)
    # Test
    assert get_run_dir_info(cylc_run_dir / 'gowron', None, False) == (
        True, 2, cylc_run_dir / 'gowron' / 'run2'
    )
    assert not os.path.lexists(runN)


def test_get_run_dir_info__fail(tmp_run_dir: Callable):
    # Test that you can't install named runs when numbered runs exist
    cylc_run_dir: Path = tmp_run_dir()
    run_dir: Path = tmp_run_dir('martok/run1')
    with pytest.raises(WorkflowFilesError) as excinfo:
        get_run_dir_info(run_dir.parent, 'targ', False)
    assert "contains installed numbered runs" in str(excinfo.value)

    # Test that you can install numbered run in an empty dir
    base_dir = cylc_run_dir / 'odo'
    base_dir.mkdir()
    get_run_dir_info(base_dir, None, False)
    # But not when named runs exist
    tmp_run_dir('odo/meter')
    with pytest.raises(WorkflowFilesError) as excinfo:
        get_run_dir_info(base_dir, None, False)
    assert "contains an installed workflow"


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
        with pytest.raises(InputError) as exc:
            parse_cli_sym_dirs(symlink_dirs)
            assert(err_msg) in str(exc)

    else:
        actual = parse_cli_sym_dirs(symlink_dirs)

        assert actual == expected


def test_validate_source_dir(tmp_run_dir: Callable, tmp_src_dir: Callable):
    cylc_run_dir: Path = tmp_run_dir()
    src_dir: Path = tmp_src_dir('ludlow')
    validate_source_dir(src_dir, 'ludlow')
    # Test that src dir must have flow file
    (src_dir / WorkflowFiles.FLOW_FILE).unlink()
    with pytest.raises(WorkflowFilesError):
        validate_source_dir(src_dir, 'ludlow')
    # Test that reserved dirnames not allowed in src dir
    src_dir = tmp_src_dir('roland')
    (src_dir / 'log').mkdir()
    with pytest.raises(WorkflowFilesError) as exc_info:
        validate_source_dir(src_dir, 'roland')
    assert "exists in source directory" in str(exc_info.value)
    # Test that src dir is allowed to be inside ~/cylc-run
    src_dir = cylc_run_dir / 'dieter'
    src_dir.mkdir()
    (src_dir / WorkflowFiles.FLOW_FILE).touch()
    validate_source_dir(src_dir, 'dieter')
    # Test that src dir is not allowed to be an installed dir.
    src_dir = cylc_run_dir / 'ajay'
    src_dir.mkdir()
    (src_dir / WorkflowFiles.Install.DIRNAME).mkdir()
    (src_dir / WorkflowFiles.FLOW_FILE).touch()
    with pytest.raises(WorkflowFilesError) as exc_info:
        validate_source_dir(src_dir, 'ajay')
    assert "exists in source directory" in str(exc_info.value)


def test_install_workflow_failif_name_name(tmp_src_dir, tmp_run_dir):
    """If a run_name is given validate_workflow_name is called on
    the workflow and the run name in combination.
    """
    src_dir: Path = tmp_src_dir('ludlow')
    # It only has a workflow name:
    with pytest.raises(WorkflowFilesError, match='can only contain'):
        install_workflow(src_dir, workflow_name='foo?')
    # It only has a run name:
    with pytest.raises(WorkflowFilesError, match='can only contain'):
        install_workflow(src_dir, run_name='foo?')
    # It has a legal workflow name, but an invalid run name:
    with pytest.raises(WorkflowFilesError, match='can only contain'):
        install_workflow(src_dir, workflow_name='foo', run_name='bar?')


def test_install_workflow_failif_reserved_name(tmp_src_dir, tmp_run_dir):
    """Reserved names cause install validation failure.

    n.b. manually defined to avoid test dependency on workflow_files.
    """
    src_dir = tmp_src_dir('ludlow')
    is_reserved = '(that filename is reserved)'
    reserved_names = {
        'share',
        'log',
        'runN',
        'suite.rc',
        'work',
        '_cylc-install',
        'flow.cylc',
        # .service fails because starting a workflow/run can't start with "."
        # And that check fails first.
        # '.service'
    }
    install_workflow(src_dir, workflow_name='ok', run_name='also_ok')
    for name in reserved_names:
        with pytest.raises(WorkflowFilesError, match=is_reserved):
            install_workflow(src_dir, workflow_name='ok', run_name=name)
        with pytest.raises(WorkflowFilesError, match=is_reserved):
            install_workflow(src_dir, workflow_name=name)
        with pytest.raises(WorkflowFilesError, match=is_reserved):
            install_workflow(src_dir, workflow_name=name, run_name='ok')
