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

import asyncio
import logging
import os

import pytest

import cylc.flow.flags
from cylc.flow.main_loop import MainLoopPluginException
from cylc.flow.main_loop.health_check import HealthCheckFailed
from cylc.flow.scheduler import Scheduler
from cylc.flow.workflow_files import get_contact_file_path


@pytest.fixture(autouse=True)
def rapid_health_check(mock_glbl_cfg):
    mock_glbl_cfg(
        'cylc.flow.scheduler.glbl_cfg', '''
        [scheduler]
            [[main loop]]
                plugins = health check
                [[[health check]]]
                    interval = PT0S
    ''')


async def test_bad_contact_file(one, run, log_filter):
    """Test workflow shuts down with error on corrupted contact file."""
    with pytest.raises(MainLoopPluginException):
        async with run(one):
            with open(get_contact_file_path(one.workflow), 'a') as f:
                f.write("Haha! I have corrupted the port file!")
            await asyncio.sleep(2)

    assert log_filter(contains="contact file corrupted/modified")


@pytest.mark.parametrize('debug', [True, False])
async def test_no_contact_file(
    debug,
    one,
    run,
    log_filter,
    caplog: pytest.LogCaptureFixture,
):
    """Test workflow shuts down with error on missing contact file."""
    if debug:
        cylc.flow.flags.verbosity = 2

    with pytest.raises(HealthCheckFailed):
        async with run(one):
            os.unlink(get_contact_file_path(one.workflow))
            await asyncio.sleep(2)

    assert log_filter(
        logging.CRITICAL,
        (
            "Workflow shutting down - health check failed: "
            "Couldn't load contact file"
        ),
    )
    assert ("Traceback" in caplog.text) is debug


async def test_deleted_run_dir(
    one: Scheduler, run, log_filter, monkeypatch: pytest.MonkeyPatch
):
    """Test workflow shuts down with error on missing run directory."""
    with pytest.raises(HealthCheckFailed):
        async with run(one):
            # Cannot actually test removing the run dir as we will get a
            # DB write failure before the health check runs
            # TODO: does this mean this part of the health check is redundant?
            with monkeypatch.context() as mp:
                mp.setattr(
                    'cylc.flow.main_loop.health_check.os.path.exists',
                    lambda path: False,
                )
                await asyncio.sleep(2)

    assert log_filter(
        logging.CRITICAL, "Workflow run directory does not exist"
    )
