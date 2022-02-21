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
"""Wrappers for creating and launching flows.

These utilities are not intended for direct use by tests
(hence the underscore function names).
Use the fixtures provided in the conftest instead.

"""

import asyncio
from async_timeout import timeout
from contextlib import asynccontextmanager, contextmanager
import logging
import pytest
from typing import Any, Optional
from uuid import uuid1

from cylc.flow import CYLC_LOG
from cylc.flow.workflow_files import WorkflowFiles
from cylc.flow.scheduler import Scheduler, SchedulerStop
from cylc.flow.scheduler_cli import RunOptions
from cylc.flow.workflow_status import StopMode

from .flow_writer import flow_config_str


def _make_flow(run_dir, test_dir, conf, name=None):
    """Construct a workflow on the filesystem."""
    if not name:
        name = str(uuid1())
    flow_run_dir = (test_dir / name)
    flow_run_dir.mkdir(parents=True)
    reg = str(flow_run_dir.relative_to(run_dir))
    if isinstance(conf, dict):
        conf = flow_config_str(conf)
    with open((flow_run_dir / WorkflowFiles.FLOW_FILE), 'w+') as flow_file:
        flow_file.write(conf)
    return reg


@contextmanager
def _make_scheduler():
    """Return a scheduler object for a flow registration."""
    schd: Scheduler = None  # type: ignore

    def __make_scheduler(reg: str, **opts: Any) -> Scheduler:
        # This allows paused_start to be overriden:
        opts = {'paused_start': True, **opts}
        options = RunOptions(**opts)
        # create workflow
        nonlocal schd
        schd = Scheduler(reg, options)
        return schd

    yield __make_scheduler
    # Teardown
    if hasattr(schd, 'workflow_db_mgr'):
        schd.workflow_db_mgr.on_workflow_shutdown()


@asynccontextmanager
async def _start_flow(
    caplog: Optional[pytest.LogCaptureFixture],
    schd: Scheduler,
    level: int = logging.INFO
):
    """Start a scheduler but don't set it running."""
    if caplog:
        caplog.set_level(level, CYLC_LOG)

    # install
    await schd.install()

    # start
    try:
        await schd.start()
        yield caplog

    # stop
    finally:
        async with timeout(5):
            await schd.shutdown(SchedulerStop("that'll do"))


@asynccontextmanager
async def _run_flow(
    caplog: Optional[pytest.LogCaptureFixture],
    schd: Scheduler,
    level: int = logging.INFO
):
    """Start a scheduler and set it running."""
    if caplog:
        caplog.set_level(level, CYLC_LOG)

    # install
    await schd.install()

    # start
    try:
        await schd.start()
    except Exception as exc:
        async with timeout(5):
            await schd.shutdown(exc)
    # run
    try:
        task = asyncio.create_task(schd.run_scheduler())
        yield caplog

    # stop
    finally:
        async with timeout(5):
            # ask the scheduler to shut down nicely
            schd._set_stop(StopMode.REQUEST_NOW_NOW)
            await task

        if task:
            # leave everything nice and tidy
            task.cancel()
