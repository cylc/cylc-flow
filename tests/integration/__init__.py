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

import asyncio
from async_timeout import timeout
from async_generator import asynccontextmanager
import logging
from pathlib import Path
from textwrap import dedent
from uuid import uuid1

from cylc.flow import CYLC_LOG
from cylc.flow.scheduler import Scheduler
from cylc.flow.scheduler_cli import (
    RunOptions,
    RestartOptions
)
from cylc.flow.suite_status import StopMode


def _write_header(name, level):
    """Write a cylc section definition."""
    indent = '    ' * (level - 1)
    return [f'{indent}{"[" * level}{name}{"]" * level}']


def _write_setting(key, value, level):
    """Write a cylc setting definition."""
    indent = '    ' * (level - 1)
    value = str(value)
    if '\n' in value:
        value = dedent(value).strip()
        ret = [f'{indent}{key} = """']
        if 'script' in key:
            ret.extend(value.splitlines())
        else:
            ret.extend([
                f'{indent}    {line}'
                for line in value.splitlines()
            ])
        ret += [f'{indent}"""']
    else:
        ret = [f'{"    " * (level - 1)}{key} = {value}']
    return ret


def _write_section(name, section, level):
    """Write an entire cylc section including headings and settings."""
    ret = []
    ret.extend(_write_header(name, level))
    for key, value in section.items():
        # write out settings first
        if not isinstance(value, dict):
            ret.extend(
                _write_setting(key, value, level + 1)
            )
    for key, value in section.items():
        # then sections after
        if isinstance(value, dict):
            ret.extend(
                _write_section(key, value, level + 1)
            )
    return ret


def suiterc(conf):
    """Convert a configuration dictionary into cylc/parsec format.

    Args:
        conf (dict):
            A [nested] dictionary of configurations.

    Returns:
        str - Multiline string in cylc/parsec format.

    """
    ret = []
    for key, value in conf.items():
        ret.extend(_write_section(key, value, 1))
    return '\n'.join(ret) + '\n'


def _rm_if_empty(path):
    """Convenience wrapper for removing empty directories."""
    try:
        path.rmdir()
    except OSError:
        return False
    return True


async def _poll_file(path, timeout=2, step=0.1, exists=True):
    """Poll a file to wait for its creation or removal.

    Arguments:
        timeout (number):
            Maximum time to wait in seconds.
        step (number):
            Polling interval in seconds.
        exists (bool):
            Set to True to check if a file exists, otherwise False.

    Raises:
        Exception:
            If polling hits the timeout.

    """
    elapsed = 0
    while path.exists() != exists:
        await asyncio.sleep(step)
        elapsed += step
        if elapsed > timeout:
            raise Exception(f'Timeout waiting for file creation: {path}')
    return True


def _expanduser(path):
    """Expand $HOME and ~ in paths.

    This code may well become obsolete after job platforms work has been
    merged.

    """
    path = str(path)
    path = path.replace('$HOME', '~')
    path = path.replace('${HOME}', '~')
    path = Path(path).expanduser()
    return path


def _make_flow(run_dir, test_dir, conf, name=None):
    """Construct a workflow on the filesystem."""
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
