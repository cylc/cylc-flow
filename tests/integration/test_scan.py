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
"""Test file-system interaction aspects of scan functionality."""

from pathlib import Path
from shutil import rmtree
from tempfile import TemporaryDirectory

import pytest

from cylc.flow.network.scan import (
    graphql_query,
    is_active,
    scan
)
from cylc.flow.suite_files import SuiteFiles


SRV_DIR = Path(SuiteFiles.Service.DIRNAME)
CONTACT = Path(SuiteFiles.Service.CONTACT)


def init_flows(tmp_path, running=None, registered=None, un_registered=None):
    """Create some dummy workflows for scan to discover."""
    for name in (running or []):
        path = Path(tmp_path, name, SRV_DIR)
        path.mkdir(parents=True, exist_ok=True)
        (path / CONTACT).touch()
    for name in (registered or []):
        Path(tmp_path, name, SRV_DIR).mkdir(parents=True, exist_ok=True)
    for name in (un_registered or []):
        Path(tmp_path, name).mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope='session')
def sample_run_dir():
    tmp_path = Path(TemporaryDirectory().name)
    tmp_path.mkdir()
    init_flows(
        tmp_path,
        running=('foo', 'bar/pub'),
        registered=('baz',),
        un_registered=('qux',)
    )
    yield tmp_path
    rmtree(tmp_path)


@pytest.fixture(scope='session')
def badly_messed_up_run_dir():
    tmp_path = Path(TemporaryDirectory().name)
    tmp_path.mkdir()
    # one regular workflow
    init_flows(
        tmp_path,
        running=('foo',)
    )
    # and an erroneous service dir at the top level for no reason
    Path(tmp_path, SRV_DIR).mkdir()
    yield tmp_path
    rmtree(tmp_path)


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
def nested_run_dir():
    tmp_path = Path(TemporaryDirectory().name)
    tmp_path.mkdir()
    init_flows(
        tmp_path,
        running=('a', 'b/c', 'd/e/f', 'g/h/i/j'),
    )
    yield tmp_path
    rmtree(tmp_path)


async def listify(async_gen, field='name'):
    """Convert an async generator into a list."""
    ret = []
    async for item in async_gen:
        ret.append(item[field])
    ret.sort()
    return ret


@pytest.mark.asyncio
async def test_scan(sample_run_dir):
    """It should list all flows."""
    assert await listify(
        scan(sample_run_dir)
    ) == [
        'bar/pub',
        'baz',
        'foo'
    ]


@pytest.mark.asyncio
async def test_scan_with_files(sample_run_dir):
    """It shouldn't be perturbed by arbitrary files."""
    Path(sample_run_dir, 'abc').touch()
    Path(sample_run_dir, 'def').touch()
    assert await listify(
        scan(sample_run_dir)
    ) == [
        'bar/pub',
        'baz',
        'foo'
    ]


@pytest.mark.asyncio
async def test_scan_horrible_mess(badly_messed_up_run_dir):
    """It shouldn't be affected by erroneous cylc files/dirs.

    How could you end up with a .service dir in cylc-run, well misuse of
    Cylc7 can result in this situation so this test ensures Cylc7 suites
    can't mess up a Cylc8 scan.

    """
    assert await listify(
        scan(badly_messed_up_run_dir)
    ) == [
        'foo'
    ]


@pytest.mark.asyncio
async def test_scan_symlinks(run_dir_with_symlinks):
    """It should follow symlinks to flows in other dirs."""
    assert await listify(
        scan(run_dir_with_symlinks)
    ) == [
        'bar/baz',
        'foo'
    ]


@pytest.mark.asyncio
async def test_scan_nasty_symlinks(run_dir_with_nasty_symlinks):
    """It should handle strange symlinks because users can be nasty."""
    assert await listify(
        scan(run_dir_with_nasty_symlinks)

    ) == [
        'bar',  # well you got what you asked for
        'foo'
    ]


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_max_depth(nested_run_dir):
    """It should descend only as far as permitted."""
    assert await listify(
        scan(nested_run_dir, max_depth=1)
    ) == [
        'a'
    ]

    assert await listify(
        scan(nested_run_dir, max_depth=3)
    ) == [
        'a',
        'b/c',
        'd/e/f'
    ]


@pytest.mark.asyncio
async def test_scan_sigstop(flow, scheduler, run, one_conf, test_dir, caplog):
    """It should log warnings if workflows are un-contactable.

    Note:
        This replaces tests/functional/cylc-scan/02-sigstop.t
        last found in Cylc Flow 8.0a2 which used sigstop to make the flow
        unresponsive.

    """
    # run a workflow
    reg = flow(one_conf)
    schd = scheduler(reg)
    async with run(schd):
        # stop the server to make the flow un-responsive
        schd.server.stop()
        # try scanning the workflow
        pipe = scan(test_dir) | graphql_query(['status'])
        caplog.clear()
        async for flow in pipe:
            raise Exception("There shouldn't be any scan results")
        # there should, however, be a warning
        name = Path(reg).name
        assert [(level, msg) for _, level, msg in caplog.record_tuples] == [
            (30, f'Workflow not running: {name}')
        ]
