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
"""Wrappers for creating and launching flows.

These utilities are not intended for direct use by tests
(hence the underscore function names).
Use the fixtures provided in the conftest instead.

"""

import asyncio
from async_timeout import timeout
from async_generator import asynccontextmanager
import logging
from uuid import uuid1

from cylc.flow import CYLC_LOG
from cylc.flow.suite_files import SuiteFiles
from cylc.flow.scheduler import Scheduler
from cylc.flow.scheduler_cli import (
    RunOptions,
    RestartOptions
)
from cylc.flow.suite_status import StopMode

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
    with open((flow_run_dir / SuiteFiles.FLOW_FILE), 'w+') as flow_file:
        flow_file.write(conf)
    return reg


def _make_scheduler(reg, is_restart=False, **opts):
    """Return a scheduler object for a flow registration."""
    opts = {'hold_start': True, **opts}
    # get options object
    if is_restart:
        options = RestartOptions(**opts)
    else:
        options = RunOptions(**opts)
    # create workflow
    return Scheduler(reg, options, is_restart=is_restart)


@asynccontextmanager
async def _run_flow(run_dir, caplog, scheduler, level=logging.INFO):
    """Start a scheduler."""
    contact = (run_dir / scheduler.suite / SuiteFiles.Service.DIRNAME /
               SuiteFiles.Service.CONTACT)
    if caplog:
        caplog.set_level(level, CYLC_LOG)
    task = None
    started = False
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
