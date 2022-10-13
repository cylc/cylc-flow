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
"""Test file-system interaction aspects of scan functionality."""

from contextlib import suppress
from pathlib import Path
import re
from shutil import rmtree
from tempfile import TemporaryDirectory
from typing import List

import pytest

from cylc.flow.network.scan import (
    filter_name,
    graphql_query,
    is_active,
    scan,
    scan_multi,
    workflow_params,
)
from cylc.flow.workflow_db_mgr import WorkflowDatabaseManager
from cylc.flow.workflow_files import WorkflowFiles


SRV_DIR = Path(WorkflowFiles.Service.DIRNAME)
CONTACT = Path(WorkflowFiles.Service.CONTACT)
RUN_N = Path(WorkflowFiles.RUN_N)
INSTALL = Path(WorkflowFiles.Install.DIRNAME)


def init_flows(tmp_path, running=None, registered=None, un_registered=None):
    """Create some dummy workflows for scan to discover.

    Assume "run1, run2, ..., runN" structure if flow name constains "run".
    """
    def make_registered(name, running=False):
        run_d = Path(tmp_path, name)
        run_d.mkdir(parents=True, exist_ok=True)
        (run_d / "flow.cylc").touch()
        if "run" in name:
            root = Path(tmp_path, name).parent
            with suppress(FileExistsError):
                (root / "runN").symlink_to(run_d, target_is_directory=True)
        else:
            root = run_d
        (root / INSTALL).mkdir(parents=True, exist_ok=True)
        srv_d = (run_d / SRV_DIR)
        srv_d.mkdir(parents=True, exist_ok=True)
        if running:
            (srv_d / CONTACT).touch()

    for name in (running or []):
        make_registered(name, running=True)
    for name in (registered or []):
        make_registered(name)
    for name in (un_registered or []):
        Path(tmp_path, name).mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope='session')
def sample_run_dir():
    tmp_path = Path(TemporaryDirectory().name)
    tmp_path.mkdir()
    init_flows(
        tmp_path,
        running=('foo', 'bar/pub', 'cheese/run2'),
        registered=('baz', 'cheese/run1'),
        un_registered=('qux',)
    )
    yield tmp_path
    rmtree(tmp_path)


@pytest.fixture
def badly_messed_up_cylc_run_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch
) -> Path:
    monkeypatch.setattr('cylc.flow.pathutil._CYLC_RUN_DIR', tmp_path)
    # one regular workflow
    init_flows(
        tmp_path,
        running=('foo',)
    )
    # and an erroneous service dir at the top level for no reason
    Path(tmp_path, SRV_DIR).mkdir()
    return tmp_path


@pytest.fixture(scope='session')
def run_dir_with_symlinks():
    tmp_path = Path(TemporaryDirectory().name)
    tmp_path.mkdir()
    # one regular workflow
    init_flows(
        tmp_path,
        running=('foo',)
    )
    # one symlinked workflow
    tmp_path2 = Path(TemporaryDirectory().name)
    tmp_path2.mkdir()
    init_flows(
        tmp_path2,
        # make it nested to prove that the link is followed
        running=('bar/baz',)
    )
    Path(tmp_path, 'bar').symlink_to(Path(tmp_path2, 'bar'))
    yield tmp_path
    rmtree(tmp_path)


@pytest.fixture(scope='session')
def run_dir_with_nasty_symlinks():
    tmp_path = Path(TemporaryDirectory().name)
    tmp_path.mkdir()
    # one regular workflow
    init_flows(
        tmp_path,
        running=('foo',)
    )
    # and a symlink pointing back at it in the same dir
    Path(tmp_path, 'bar').symlink_to(Path(tmp_path, 'foo'))
    yield tmp_path
    rmtree(tmp_path)


@pytest.fixture(scope='session')
def nested_dir():
    tmp_path = Path(TemporaryDirectory().name)
    tmp_path.mkdir()
    init_flows(
        tmp_path,
        running=('a', 'b/c', 'd/e/f', 'g/h/i/j'),
    )
    yield tmp_path
    rmtree(tmp_path)


@pytest.fixture
def source_dirs(mock_glbl_cfg):
    src = Path(TemporaryDirectory().name)
    src.mkdir()
    src1 = src / '1'
    src1.mkdir()
    init_flows(
        src1,
        registered=('a', 'b/c')
    )
    src2 = src / '2'
    src2.mkdir()
    init_flows(
        src2,
        registered=('d', 'e/f')
    )
    mock_glbl_cfg(
        'cylc.flow.scripts.scan.glbl_cfg',
        f'''
            [install]
                source dirs = {src1}, {src2}
        '''
    )
    yield [src1, src2]
    rmtree(src)


async def listify(async_gen, field='name'):
    """Convert an async generator into a list."""
    ret = []
    async for item in async_gen:
        ret.append(item[field])
    ret.sort()
    return ret


async def test_scan(sample_run_dir):
    """It should list all flows."""
    assert await listify(
        scan(sample_run_dir)
    ) == [
        'bar/pub',
        'baz',
        'cheese/run1',
        'cheese/run2',
        'foo'
    ]


async def test_scan_with_files(sample_run_dir):
    """It shouldn't be perturbed by arbitrary files."""
    Path(sample_run_dir, 'abc').touch()
    Path(sample_run_dir, 'def').touch()
    assert await listify(
        scan(sample_run_dir)
    ) == [
        'bar/pub',
        'baz',
        'cheese/run1',
        'cheese/run2',
        'foo',
    ]


async def test_scan_horrible_mess(badly_messed_up_cylc_run_dir):
    """It shouldn't be affected by erroneous cylc files/dirs.

    How could you end up with a .service dir in ~/cylc-run? Well misuse of
    Cylc7 can result in this situation so this test ensures Cylc7 workflows
    can't mess up a Cylc8 scan.

    """
    assert await listify(
        scan(badly_messed_up_cylc_run_dir)
    ) == [
        'foo'
    ]


async def test_scan_symlinks(run_dir_with_symlinks):
    """It should follow symlinks to flows in other dirs."""
    assert await listify(
        scan(run_dir_with_symlinks)
    ) == [
        'bar/baz',
        'foo'
    ]


async def test_scan_nasty_symlinks(run_dir_with_nasty_symlinks):
    """It should handle strange symlinks because users can be nasty."""
    assert await listify(
        scan(run_dir_with_nasty_symlinks)

    ) == [
        'bar',  # well you got what you asked for
        'foo'
    ]


async def test_scan_non_exist(tmp_path: Path):
    """Calling scan() on a scan_dir that doesn't exist should not raise."""
    assert await listify(
        scan(scan_dir=(tmp_path / 'HORSE'))
    ) == []


async def test_is_active(sample_run_dir):
    """It should filter flows by presence of a contact file."""
    # running flows
    assert await is_active.func(
        {'path': sample_run_dir / 'foo'},
        True
    )
    assert await is_active.func(
        {'path': sample_run_dir / 'bar/pub'},
        True
    )
    # registered flows
    assert not await is_active.func(
        {'path': sample_run_dir / 'baz'},
        True
    )
    # unregistered flows
    assert not await is_active.func(
        {'path': sample_run_dir / 'qux'},
        True
    )
    # non-existent flows
    assert not await is_active.func(
        {'path': sample_run_dir / 'elephant'},
        True
    )


@pytest.mark.parametrize(
    'depth, expected',
    [
        (1, ['a']),
        (3, ['a', 'b/c', 'd/e/f'])
    ]
)
async def test_max_depth(nested_dir, depth: int, expected: List[str]):
    """It should descend only as far as permitted."""
    assert await listify(
        scan(nested_dir, max_depth=depth)
    ) == expected


async def test_max_depth_configurable(nested_dir, mock_glbl_cfg):
    """Default scan depth should be configurable in global.cylc."""
    mock_glbl_cfg(
        'cylc.flow.network.scan.glbl_cfg',
        '''
        [install]
            max depth = 2
        '''
    )
    assert await listify(
        scan(nested_dir)
    ) == [
        'a',
        'b/c',
    ]


async def test_scan_one(one, start, test_dir):
    """Ensure that a running workflow appears in the scan results."""
    async with start(one):
        pipe = (
            # scan just this workflow
            scan(scan_dir=test_dir)
            | filter_name(rf'^{re.escape(one.workflow)}$')
            | is_active(True)
            | workflow_params
        )
        async for flow in pipe:
            assert flow['name'] == one.workflow
            break
        else:
            raise Exception('Expected one scan result')


async def test_workflow_params(
    one,
    start,
    one_conf,
    run_dir,
    mod_test_dir
):
    """It should extract workflow params from the workflow database.

    Note:
        For this test we ensure that the workflow UUID is present in the params
        table.
    """
    async with start(one):
        pipe = (
            # scan just this workflow
            scan(scan_dir=mod_test_dir)
            | filter_name(rf'^{re.escape(one.workflow)}$')
            | is_active(True)
            | workflow_params
        )
        async for flow in pipe:
            # check the workflow_params field has been provided
            assert 'workflow_params' in flow
            # check the workflow uuid key has been read from the DB
            uuid_key = WorkflowDatabaseManager.KEY_UUID_STR
            assert uuid_key in flow['workflow_params']
            # check the workflow uuid key matches the scheduler value
            assert flow['workflow_params'][uuid_key] == one.uuid_str
            break
        else:
            raise Exception('Expected one scan result')


async def test_source_dirs(source_dirs):
    """It should list uninstalled workflows from configured source dirs."""
    src1, src2 = source_dirs
    assert await listify(
        scan_multi(source_dirs, max_depth=3)
    ) == [
        # NOTE: flow names from scan_multi are full paths
        (src1 / 'a'),
        (src1 / 'b/c'),
        (src2 / 'd'),
        (src2 / 'e/f'),
    ]


async def test_scan_sigstop(
    flow,
    scheduler,
    start,
    one_conf,
    test_dir,
    caplog,
):
    """It should log warnings if workflows are un-contactable.

    Note:
        This replaces tests/functional/cylc-scan/02-sigstop.t
        last found in Cylc Flow 8.0a2 which used sigstop to make the flow
        unresponsive.

    """
    # run a workflow
    reg = flow(one_conf)
    schd = scheduler(reg)
    async with start(schd):
        # stop the server to make the flow un-responsive
        await schd.server.stop('make-unresponsive')
        # try scanning the workflow
        pipe = scan(test_dir) | graphql_query(['status'])
        caplog.clear()
        async for flow in pipe:
            raise Exception("There shouldn't be any scan results")
        # there should, however, be a warning
        name = Path(reg).name
        assert (
            (30, f'Workflow not running: {name}')
            in [(level, msg) for _, level, msg in caplog.record_tuples]
        )


@pytest.fixture
def cylc7_run_dir(tmp_path):
    """A run directory containing three Cylc 7 workflows."""
    # a workflow that has not yet been run
    # (could be run by either cylc 7 or 8 so should appear in scan results)
    either = tmp_path / 'either'
    either.mkdir()
    (either / WorkflowFiles.SUITE_RC).touch()

    # a Cylc 7 workflow that has been / is being run by Cylc 7
    # (should not appear in scan results)
    cylc7 = tmp_path / 'cylc7'
    cylc7.mkdir()
    (cylc7 / WorkflowFiles.SUITE_RC).touch()
    Path(cylc7, WorkflowFiles.LogDir.DIRNAME, 'suite').mkdir(parents=True)
    Path(cylc7, WorkflowFiles.LogDir.DIRNAME, 'suite', 'log').touch()

    # a Cylc 7 workflow running under Cylc 8 in compatibility mode
    # (should appear in scan results)
    cylc8 = tmp_path / 'cylc8'
    cylc8.mkdir()
    (cylc8 / WorkflowFiles.SUITE_RC).touch()
    Path(cylc8, WorkflowFiles.LogDir.DIRNAME, 'scheduler').mkdir(parents=True)
    Path(cylc8, WorkflowFiles.LogDir.DIRNAME, 'scheduler', 'log').touch()

    # a Cylc 7 workflow installed by Cylc 8 but not run yet.
    # (should appear in scan results)
    cylc8a = tmp_path / 'cylc8a'
    cylc8a.mkdir()
    (cylc8a / WorkflowFiles.SUITE_RC).touch()
    Path(cylc8a, WorkflowFiles.LogDir.DIRNAME, 'install').mkdir(parents=True)

    # crazy niche case of a Cylc 7 workflow that has had its DB removed
    # and re-run under Cylc 8
    # (should appear in scan results)
    cylc8 = tmp_path / 'cylc78'
    cylc8.mkdir()
    (cylc8 / WorkflowFiles.SUITE_RC).touch()
    Path(cylc8, WorkflowFiles.LogDir.DIRNAME, 'suite').mkdir(parents=True)
    Path(cylc8, WorkflowFiles.LogDir.DIRNAME, 'suite', 'log').touch()
    Path(cylc8, WorkflowFiles.LogDir.DIRNAME, 'scheduler').mkdir(parents=True)
    Path(cylc8, WorkflowFiles.LogDir.DIRNAME, 'scheduler', 'log').touch()

    return tmp_path


async def test_scan_cylc7(cylc7_run_dir):
    """It should exclude Cylc 7 workflows from scan results.

    Unless they are running under Cylc 8 in Cylc 7 compatibility mode.
    """
    assert await listify(
        scan(cylc7_run_dir)
    ) == [
        'cylc78', 'cylc8', 'cylc8a', 'either'
    ]
