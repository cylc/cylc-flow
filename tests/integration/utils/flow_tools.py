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
from pathlib import Path
from async_timeout import timeout
from contextlib import asynccontextmanager, contextmanager
import logging
import pytest
from typing import Any, Optional, Union
from secrets import token_hex

from cylc.flow import CYLC_LOG
from cylc.flow.run_modes import RunMode
from cylc.flow.workflow_files import WorkflowFiles
from cylc.flow.scheduler import Scheduler, SchedulerStop
from cylc.flow.scheduler_cli import RunOptions
from cylc.flow.workflow_status import StopMode

from .flow_writer import flow_config_str


def _make_src_flow(src_path, conf, filename=WorkflowFiles.FLOW_FILE):
    """Construct a workflow on the filesystem"""
    flow_src_dir = (src_path / token_hex(4))
    flow_src_dir.mkdir(parents=True, exist_ok=True)
    if isinstance(conf, dict):
        conf = flow_config_str(conf)
    with open((flow_src_dir / filename), 'w+') as flow_file:
        flow_file.write(conf)
    return flow_src_dir


def _make_flow(
    cylc_run_dir: Union[Path, str],
    test_dir: Path,
    conf: Union[dict, str],
    name: Optional[str] = None,
    id_: Optional[str] = None,
    defaults: Optional[bool] = True,
    filename: str = WorkflowFiles.FLOW_FILE,
) -> str:
    """Construct a workflow on the filesystem.

    Args:
        conf: Either a workflow config dictionary, or a graph string to be
            used as the R1 graph in the workflow config.
        defaults: Set up a common defaults.
            * [scheduling]allow implicit tasks = true

            Set false for Cylc 7 upgrader tests.
    """
    if id_:
        flow_run_dir = (cylc_run_dir / id_)
    else:
        if name is None:
            name = token_hex(4)
        flow_run_dir = (test_dir / name)
    flow_run_dir.mkdir(parents=True, exist_ok=True)
    id_ = str(flow_run_dir.relative_to(cylc_run_dir))
    if isinstance(conf, str):
        conf = {
            'scheduling': {
                'graph': {
                    'R1': conf
                }
            }
        }
    if defaults:
        # set the default simulation runtime to zero (can be overridden)
        (
            conf.setdefault('runtime', {})
            .setdefault('root', {})
            .setdefault('simulation', {})
            .setdefault('default run length', 'PT0S')
        )
        # allow implicit tasks by default:
        conf.setdefault('scheduler', {}).setdefault(
            'allow implicit tasks', 'True')

    with open((flow_run_dir / filename), 'w+') as flow_file:
        flow_file.write(flow_config_str(conf))
    return id_


@contextmanager
def _make_scheduler():
    """Return a scheduler object for a flow registration."""
    schd: Scheduler = None  # type: ignore[assignment]

    def __make_scheduler(id_: str, **opts: Any) -> Scheduler:
        opts = {
            # safe n sane defaults for integration tests
            'paused_start': True,
            'run_mode': 'simulation',
            **opts,
        }
        options = RunOptions(**opts)
        # create workflow
        nonlocal schd
        schd = Scheduler(id_, options)
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
    """Start a scheduler but don't set the main loop running."""
    if caplog:
        caplog.set_level(level, CYLC_LOG)

    await schd.install()

    try:
        # Nested `try...finally` to ensure caplog always yielded even if
        # exception occurs in Scheduler
        try:
            await schd.start()
        finally:
            # After this `yield`, the `with` block of the context manager
            # is executed:
            yield caplog
    finally:
        # Cleanup - this always runs after the `with` block of the
        # context manager.
        # Need to shut down Scheduler, but time out in case something
        # goes wrong:
        async with timeout(5):
            await schd.shutdown(SchedulerStop("integration test teardown"))


@asynccontextmanager
async def _run_flow(
    caplog: Optional[pytest.LogCaptureFixture],
    schd: Scheduler,
    level: int = logging.INFO
):
    """Start a scheduler and set the main loop running."""
    if caplog:
        caplog.set_level(level, CYLC_LOG)

    await schd.install()

    task: Optional[asyncio.Task] = None
    try:
        # Nested `try...finally` to ensure caplog always yielded even if
        # exception occurs in Scheduler
        try:
            await schd.start()
            # Do not await as we need to yield control to the main loop:
            task = asyncio.create_task(schd.run_scheduler())
        finally:
            # After this `yield`, the `with` block of the context manager
            # is executed:
            yield caplog
    finally:
        # Cleanup - this always runs after the `with` block of the
        # context manager.
        # Need to shut down Scheduler, but time out in case something
        # goes wrong:
        async with timeout(5):
            if task:
                # ask the scheduler to shut down nicely,
                # let main loop handle it:
                schd._set_stop(StopMode.REQUEST_NOW_NOW)
                await task
        if schd.contact_data:
            async with timeout(5):
                # Scheduler still running... try more forceful tear down:
                await schd.shutdown(SchedulerStop("integration test teardown"))
        if task:
            # Brute force cleanup if something went wrong:
            task.cancel()
