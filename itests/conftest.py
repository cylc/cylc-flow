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
"""Default fixtures for functional tests."""

from functools import partial
import logging
from pathlib import Path

import pytest

from cylc.flow import CYLC_LOG
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.network.client import SuiteRuntimeClient
from cylc.flow.wallclock import get_current_time_string

from . import (
    _expanduser,
    _rm_if_empty,
    _make_flow,
    _make_scheduler,
    _flow,
    _run_flow
)


@pytest.fixture(scope='session')
def run_dir(request):
    """The cylc run directory for this host."""
    path = _expanduser(
        glbl_cfg().get_host_item('run directory')
    )
    path.mkdir(exist_ok=True)
    yield path


@pytest.fixture(scope='session')
def ses_test_dir(request, run_dir):
    """The root reg dir for test flows in this test session."""
    timestamp = get_current_time_string(use_basic_format=True)
    uuid = f'cit-{timestamp}'
    path = Path(run_dir, uuid)
    path.mkdir(exist_ok=True)
    yield path
    _rm_if_empty(path)


@pytest.fixture(scope='module')
def mod_test_dir(request, ses_test_dir):
    """The root reg dir for test flows in this test module."""
    path = Path(ses_test_dir, request.module.__name__)
    path.mkdir(exist_ok=True)
    yield path
    _rm_if_empty(path)


@pytest.fixture
def test_dir(request, mod_test_dir):
    """The root reg dir for test flows in this test function."""
    path = Path(mod_test_dir, request.function.__name__)
    path.mkdir(parents=True, exist_ok=True)
    yield path
    _rm_if_empty(path)


@pytest.fixture(scope='session')
def ses_make_flow(run_dir, ses_test_dir):
    """A function for creating session-level flows."""
    yield partial(_make_flow, run_dir, ses_test_dir)


@pytest.fixture(scope='module')
def mod_make_flow(run_dir, mod_test_dir):
    """A function for creating module-level flows."""
    yield partial(_make_flow, run_dir, mod_test_dir)


@pytest.fixture
def make_flow(run_dir, test_dir):
    """A function for creating function-level flows."""
    yield partial(_make_flow, run_dir, test_dir)


@pytest.fixture(scope='session')
def ses_make_scheduler():
    """Return a scheduler object for a flow."""
    return _make_scheduler


@pytest.fixture(scope='module')
def mod_make_scheduler():
    """Return a scheduler object for a flow."""
    return _make_scheduler


@pytest.fixture
def make_scheduler():
    """Return a scheduler object for a flow."""
    return _make_scheduler


@pytest.fixture(scope='session')
def ses_flow(ses_make_flow, ses_make_scheduler):
    """Make a session-level flow and return a scheduler object."""
    return partial(_flow, ses_make_flow, ses_make_scheduler)


@pytest.fixture(scope='module')
def mod_flow(mod_make_flow, mod_make_scheduler):
    """Make a module-level flow and return a scheduler object."""
    return partial(_flow, mod_make_flow, mod_make_scheduler)


@pytest.fixture
def flow(make_flow, make_scheduler):
    """Make a function-level flow and return a scheduler object."""
    return partial(_flow, make_flow, make_scheduler)


@pytest.fixture(scope='session')
def ses_run_flow(run_dir, caplog):
    """Run a session-level flow."""
    caplog.set_level(logging.DEBUG, logger=CYLC_LOG)
    return partial(_run_flow, run_dir, caplog)


@pytest.fixture(scope='module')
def mod_run_flow(run_dir):
    """Run a module-level flow."""
    return partial(_run_flow, run_dir, None)


@pytest.fixture
def run_flow(run_dir):
    """Run a function-level flow."""
    return partial(_run_flow, run_dir, None)


@pytest.fixture
def simple_conf():
    return {
        'scheduling': {
            'dependencies': {
                'graph': 'foo'
            }
        }
    }


@pytest.fixture(scope='module')
def mod_simple_conf():
    return {
        'scheduling': {
            'dependencies': {
                'graph': 'foo'
            }
        }
    }


@pytest.fixture(scope='module')
async def flow_a(mod_flow, mod_run_flow, mod_simple_conf):
    """A simple workflow with module-level scoping."""
    scheduler = mod_flow(mod_simple_conf, hold_start=True)
    async with mod_run_flow(scheduler):
        yield scheduler


@pytest.fixture(scope='module')
async def flow_a_w_client(mod_flow, mod_run_flow, mod_simple_conf):
    """A simple workflow + runtime client with module-level scoping."""
    scheduler = mod_flow(mod_simple_conf, hold_start=True)
    async with mod_run_flow(scheduler):
        client = SuiteRuntimeClient(scheduler.suite)
        yield scheduler, client
