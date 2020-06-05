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
from pathlib import Path
import re

import pytest

from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.wallclock import get_current_time_string

from . import (
    _expanduser,
    _rm_if_empty,
    _make_flow,
    _make_scheduler,
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


@pytest.fixture(scope='module')
def mod_flow(run_dir, mod_test_dir):
    """A function for creating module-level flows."""
    yield partial(_make_flow, run_dir, mod_test_dir)


@pytest.fixture
def flow(run_dir, test_dir):
    """A function for creating function-level flows."""
    yield partial(_make_flow, run_dir, test_dir)


@pytest.fixture(scope='module')
def mod_scheduler():
    """Return a scheduler object for a flow."""
    return _make_scheduler


@pytest.fixture
def scheduler():
    """Return a scheduler object for a flow."""
    return _make_scheduler


@pytest.fixture(scope='module')
def mod_run(run_dir):
    """Run a module-level flow."""
    return partial(_run_flow, run_dir, None)


@pytest.fixture
def run(run_dir, caplog):
    """Run a function-level flow."""
    return partial(_run_flow, run_dir, caplog)


@pytest.fixture
def one_conf():
    return {
        'scheduling': {
            'graph': {
                'R1': 'one'
            }
        }
    }


@pytest.fixture(scope='module')
def mod_one_conf():
    return {
        'scheduling': {
            'graph': {
                'R1': 'one'
            }
        }
    }


@pytest.fixture
def one(one_conf, flow, scheduler):
    reg = flow(one_conf)
    schd = scheduler(reg)
    return schd


@pytest.fixture(scope='module')
def mod_one(mod_one_conf, mod_flow, mod_scheduler):
    reg = mod_flow(mod_one_conf)
    schd = mod_scheduler(reg)
    return schd


@pytest.fixture
def log_filter():
    def _log_filter(log, name=None, level=None, contains=None, regex=None):
        return [
            (log_name, log_level, log_message)
            for log_name, log_level, log_message in log.record_tuples
            if (name is None or name == log_name)
            and (level is None or level == log_level)
            and (contains is None or contains in log_message)
            and (regex is None or re.match(regex, log_message))
        ]
    return _log_filter


@pytest.fixture(scope='session')
def port_range():
    ports = glbl_cfg().get(['suite servers', 'run ports'])
    return min(ports), max(ports)
