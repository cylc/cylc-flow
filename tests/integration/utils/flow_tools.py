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
from async_generator import asynccontextmanager
import logging
from pathlib import Path
import pytest
from typing import Optional
from uuid import uuid1

from cylc.flow import CYLC_LOG
from cylc.flow.workflow_files import WorkflowFiles
from cylc.flow.scheduler import Scheduler
from cylc.flow.scheduler_cli import RunOptions
from cylc.flow.workflow_status import StopMode

from .flow_writer import flow_config_str
from . import _poll_file


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


def _make_scheduler(reg, **opts):
    """Return a scheduler object for a flow registration."""
    # This allows paused_start to be overriden:
    opts = {'paused_start': True, **opts}
    options = RunOptions(**opts)
    # create workflow
    return Scheduler(reg, options)


@asynccontextmanager
async def _run_flow(
    run_dir: Path,
    caplog: Optional[pytest.LogCaptureFixture],
    scheduler: Scheduler,
    level: int = logging.INFO
):
    """Start a scheduler."""
    contact = (run_dir / scheduler.workflow / WorkflowFiles.Service.DIRNAME /
               WorkflowFiles.Service.CONTACT)
    if caplog:
        caplog.set_level(level, CYLC_LOG)
    task = None
    started = False
    await scheduler.install()
    try:
        task = asyncio.get_event_loop().create_task(scheduler.run())
        started = await _poll_file(contact)
        yield caplog
    finally:
        if started:
            # ask the scheduler to shut down nicely
            async with timeout(5):
                scheduler._set_stop(StopMode.REQUEST_NOW_NOW)
                await task

        if task:
            # leave everything nice and tidy
            task.cancel()
