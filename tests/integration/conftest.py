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

import asyncio
from functools import partial
from pathlib import Path
import re
from shutil import rmtree

import pytest

from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.wallclock import get_current_time_string
from cylc.flow.platforms import platform_from_name

from .utils import (
    _expanduser,
    _rm_if_empty
)
from .utils.flow_tools import (
    _make_flow,
    _make_scheduler,
    _run_flow
)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Expose the result of tests to their fixtures.

    This will add a variable to the "node" object which differs depending on
    the scope of the test.

    scope=function
        `_function_outcome` will be set to the result of the test function.
    scope=module
        `_module_outcome will be set to a list of all test results in
        the module.

    https://github.com/pytest-dev/pytest/issues/230#issuecomment-402580536

    """
    outcome = yield
    rep = outcome.get_result()

    # scope==function
    item._function_outcome = rep

    # scope==module
    _module_outcomes = getattr(item.module, '_module_outcomes', {})
    _module_outcomes[(item.nodeid, rep.when)] = rep
    item.module._module_outcomes = _module_outcomes


def _pytest_passed(request):
    """Returns True if the test(s) a fixture was used in passed."""
    if hasattr(request.node, '_function_outcome'):
        return request.node._function_outcome in {'passed', 'skipped'}
    return all((
        report.outcome in {'passed', 'skipped'}
        for report in request.node.obj._module_outcomes.values()
    ))


@pytest.fixture(scope='session')
def run_dir(request):
    """The cylc run directory for this host."""
    path = _expanduser(
        platform_from_name()['run directory']
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
    if _pytest_passed(request):
        # test passed -> remove all files
        rmtree(path, ignore_errors=True)
    else:
        # test failed -> remove the test dir if empty
        _rm_if_empty(path)


@pytest.fixture
def test_dir(request, mod_test_dir):
    """The root reg dir for test flows in this test function."""
    path = Path(mod_test_dir, request.function.__name__)
    path.mkdir(parents=True, exist_ok=True)
    yield path
    if _pytest_passed(request):
        # test passed -> remove all files
        rmtree(path, ignore_errors=True)
    else:
        # test failed -> remove the test dir if empty
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


@pytest.fixture(scope='module')
def event_loop():
    """This fixture defines the event loop used for each test.

    The default scoping for this fixture is "function" which means that all
    async fixtures must have "function" scoping.

    Defining `event_loop` as a module scoped fixture opens the door to
    module scoped fixtures but means all tests in a module will run in the same
    event loop. This is fine, it's actually an efficiency win but also
    something to be aware of.

    See: https://github.com/pytest-dev/pytest-asyncio/issues/171

    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    # gracefully exit async generators
    loop.run_until_complete(loop.shutdown_asyncgens())
    # cancel any tasks still running in this event loop
    for task in asyncio.all_tasks(loop):
        task.cancel()
    loop.close()
