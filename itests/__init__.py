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

from contextlib import contextmanager
from multiprocessing import Process
from pathlib import Path
from shlex import quote
from shutil import rmtree
from subprocess import Popen, DEVNULL
import sys
from textwrap import dedent
from time import sleep

import pytest

from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.exceptions import (
    SuiteServiceFileError
)
from cylc.flow.network.client import SuiteRuntimeClient
from cylc.flow.scheduler import Scheduler
from cylc.flow.scheduler_cli import (
    RunOptions,
    RestartOptions
)
from cylc.flow.suite_files import ContactFileFields, load_contact_file
from cylc.flow.wallclock import get_current_time_string


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


def _poll_file(path, timeout=2, step=0.1, exists=True):
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
        sleep(step)
        elapsed += step
        if elapsed > timeout:
            raise Exception(f'Timeout waiting for file creation: {path}')


def _kill_flow(reg):
    """Kill a [remote] flow process."""
    try:
        contact = load_contact_file(str(reg))
    except SuiteServiceFileError:
        # flow has already shutdown
        return
    # host = contact[ContactFileFields.HOST]
    pid = contact[ContactFileFields.PROCESS].split(' ')[0]
    # Popen(
    #     ['ssh', quote(host), 'kill', '-9', quote(pid)],
    #     stdin=DEVNULL, stdout=DEVNULL
    # ).wait()
    Popen(['kill', '-9', quote(pid)], stdin=DEVNULL, stdout=DEVNULL).wait()


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


@pytest.fixture(scope='session')
def run_dir(request):
    """The cylc run directory for this host."""
    path = _expanduser(
        glbl_cfg().get_host_item('run directory')
    )
    path.mkdir(exist_ok=True)
    yield path


@pytest.fixture(scope='session')
def test_dir(request, run_dir):
    """The root registration directory for test flows in this test session."""
    timestamp = get_current_time_string(use_basic_format=True)
    uuid = f'cit-{timestamp}'
    path = Path(run_dir, uuid)
    path.mkdir(exist_ok=True)
    yield path
    # remove the dir if empty
    _rm_if_empty(path)


@pytest.fixture(scope='function')
def flow_dir(request, test_dir):
    """The root registration directory for flows in this test function."""
    path = Path(
        test_dir,
        request.module.__name__,
        request.function.__name__
    )
    path.mkdir(parents=True, exist_ok=True)
    yield path
    # remove the dir if empty
    _rm_if_empty(path)
    _rm_if_empty(path.parent)


@pytest.fixture
def make_flow(run_dir, flow_dir, request):
    """A function for creating test flows on the filesystem."""
    def _make_flow(name, conf):
        reg = str(flow_dir.relative_to(run_dir))
        if isinstance(conf, dict):
            conf = suiterc(conf)
        with open((flow_dir / 'suite.rc'), 'w+') as suiterc_file:
            suiterc_file.write(conf)
        return reg
    yield _make_flow


@pytest.fixture
def run_flow(run_dir):
    """A function for running test flows from Python."""
    @contextmanager
    def _run_flow(reg, is_restart=False, **opts):
        # set default options
        opts = {'no_detach': True, **opts}
        # get options object
        if is_restart:
            options = RestartOptions(**opts)
        else:
            options = RunOptions(**opts)
        # create workflow
        schd = Scheduler(reg, options, is_restart=is_restart)
        proc = Process(target=schd.start)

        client = None
        success = True
        contact = (run_dir / reg / '.service' / 'contact')
        try:
            # start the flow process
            print('Starting flow...')
            proc.start()
            print('Confirming startup...')
            # wait for the flow to finish starting
            if options.no_detach:
                _poll_file(contact)
            else:
                proc.join()
            print('Flow started.')
            # yield control back to the test
            client = SuiteRuntimeClient(reg)
            print('Entering Test...')
            yield reg, proc, client
            print('Exited Test.')
        except Exception as exc:
            # something went wrong in the test
            success = False
            raise exc from None  # raise the exception so the test fails
        finally:
            if contact.exists():
                # shutdown the flow
                try:
                    # make sure the flow goes through the shutdown process
                    # even if it did not complete the startup process
                    if client is None:
                        raise ValueError('Failed to launch flow properly')
                    # try asking the flow to stop nicely
                    client('stop_now', {'terminate': True})
                    if options.no_detach:
                        proc.join()  # TODO: timeout
                    else:
                        _poll_file(contact, exists=False)
                except Exception:  # purposefully vague exception
                    # if asking nicely doesn't help try harsher measures
                    if options.no_detach:
                        proc.kill()
                    else:
                        _kill_flow(reg)
            if success:
                # tidy up if the test was successful
                rmtree(run_dir / reg)
    return _run_flow
