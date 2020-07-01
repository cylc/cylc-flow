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
from pathlib import Path
from uuid import uuid1

from cylc.flow import CYLC_LOG
from cylc.flow.scheduler import Scheduler
from cylc.flow.scheduler_cli import (
    RunOptions,
    RestartOptions
)
from cylc.flow.suite_status import StopMode

from .db_faker import fake_db
from .flow_writer import suiterc
from . import _poll_file


def _make_flow(run_dir, test_dir, conf, name=None):
    """Construct a workflow on the filesystem.

    Args:
        run_dir (pathlib.Path):
            The top-level Cylc run directory.
        test-dir (pathlib.Path):
            The location of the directory for this test to create its files in.
            Note this should be within the run_dir.
        conf (dict/str):
            The Flow configuration either as a multiline string or as a
            nested dictionary.
        name (str):
            The name to register this Flow with.
            If unspecified we use a random hash.

    Returns:
        str - Cylc registration.

    """
    if not name:
        name = str(uuid1())
    flow_run_dir = (test_dir / name)
    flow_run_dir.mkdir()
    reg = str(flow_run_dir.relative_to(run_dir))
    if isinstance(conf, dict):
        conf = suiterc(conf)
    with open((flow_run_dir / 'suite.rc'), 'w+') as suiterc_file:
        suiterc_file.write(conf)
    return reg


def _make_scheduler(reg, is_restart=False, tasks=None, **opts):
    """Return a scheduler object for a flow registration.

    Args:
        reg (str):
            The registered name for the flow to load (from the filesystem).
        is_restart (bool):
            If True the Scheduler will be configured in restart mode.
        tasks (list):
            List of db_faker.Task instances.

            Fakes a previous run of the suite allowing you to pre-define the
            state of the task pool.

            This implies ``is_restart=True``.
        opts (cylc.flow.option_parser.Options):
            Options for initiating the new Scheduler object. See:

            * cylc.flow.scheduler_cli.RunOptions
            * cylc.flow.scheduler_cli.RestartOptions

    Returns:
        cylc.flow.scheduler.Scheduler

    """
    if tasks:
        is_restart = True
    opts = {'hold_start': True, **opts}
    # get options object
    if is_restart:
        options = RestartOptions(**opts)
    else:
        options = RunOptions(**opts)
    # create workflow
    schd = Scheduler(reg, options, is_restart=is_restart)
    if tasks:
        fake_db(tasks, Path(schd.suite_dir, '.service', 'db'))
    return schd


@asynccontextmanager
async def _run_flow(run_dir, caplog, scheduler, level=logging.INFO):
    """Start a scheduler.

    Args:
        run_dir (pathlib.Path):
            The top-level Cylc run directory.
        caplog (Object):
            Instance of the Pytest caplog fixture for log capturing or None.
        scheduler (cylc.flow.scheduler.Scheduler):
            The Scheduler instance to run.
        level (int):
            Sets the minimum level for capturing log messages.

    Yields:
        Object - Instance of the Pytest caplog fixture configured jus
        for this flow.

    """
    contact = (run_dir / scheduler.suite / '.service' / 'contact')
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
