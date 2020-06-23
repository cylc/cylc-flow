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
"""Working documentation for the integration test framework.

Here are some examples which cover a range of uses (and also provide some
useful testing in the process 😀.)

"""

import asyncio
import logging
from pathlib import Path

import pytest

from cylc.flow import __version__


@pytest.mark.asyncio
async def test_create_flow(flow, run_dir):
    """Use the flow fixture to create workflows on the file system."""
    # Ensure a suite.rc file gets written out
    reg = flow({
        'scheduling': {
            'graph': {
                'R1': 'foo'
            }
        }
    })
    suite_dir = run_dir / reg
    suite_rc = suite_dir / 'suite.rc'

    assert suite_dir.exists()
    assert suite_rc.exists()


@pytest.mark.asyncio
async def test_run(flow, scheduler, run, one_conf):
    """Create a workflow, initialise the scheduler and run it."""
    # Ensure the scheduler can survive for one second without crashing
    reg = flow(one_conf)
    schd = scheduler(reg)
    async with run(schd):
        await asyncio.sleep(1)


@pytest.mark.asyncio
async def test_logging(flow, scheduler, run, one_conf, log_filter):
    """We can capture log records when we run a scheduler."""
    # Ensure that the cylc version is logged on startup.
    reg = flow(one_conf)
    schd = scheduler(reg)
    async with run(schd) as log:
        # this returns a list of log records containing __version__
        assert log_filter(log, contains=__version__)


@pytest.mark.asyncio
async def test_scheduler_arguments(flow, scheduler, run, one_conf):
    """We can provide options to the scheduler when we __init__ it.

    These options match their command line equivalents.

    Use the `dest` value specified in the option parser.

    """
    # Ensure the hold_start option is obeyed by the scheduler.
    reg = flow(one_conf)
    schd = scheduler(reg, hold_start=True)
    async with run(schd):
        assert schd.paused()
    reg = flow(one_conf)
    schd = scheduler(reg, hold_start=False)
    async with run(schd):
        assert not schd.paused()


@pytest.mark.asyncio
async def test_shutdown(flow, scheduler, run, one_conf):
    """Shut down a workflow.

    The scheduler automatically shuts down once you exit the `async with`
    block, however you can manually shut it down within this block if you
    like.

    """
    # Ensure the TCP server shuts down with the scheduler.
    reg = flow(one_conf)
    schd = scheduler(reg)
    async with run(schd):
        pass
    assert schd.server.socket.closed


@pytest.mark.asyncio
async def test_install(flow, scheduler, one_conf, run_dir):
    """You don't have to run workflows, it's usually best not to!

    You can take the scheduler through the startup sequence as far as needed
    for your test.

    """
    # Ensure the installation of the job script is completed.
    reg = flow(one_conf)
    schd = scheduler(reg)
    await schd.install()
    assert Path(
        run_dir, schd.suite, '.service', 'etc', 'job.sh'
    ).exists()


@pytest.mark.asyncio
async def test_task_pool(flow, scheduler, one_conf):
    """You don't have to run the scheduler to play with the task pool."""
    # Ensure that the correct number of tasks get added to the task pool.

    # create the flow
    reg = flow(one_conf)
    schd = scheduler(reg)

    # take it as far through the startup sequence as needed
    await schd.install()
    await schd.initialise()
    await schd.configure()

    # pump the scheduler's heart manually
    schd.release_tasks()
    assert len(schd.pool.pool) == 1


@pytest.mark.asyncio
async def test_exception(flow, scheduler, run, one_conf, log_filter):
    """Through an exception into the scheduler to see how it will react.

    You have to do this from within the scheduler itself.
    The easy way is to patch the object.

    """
    # Ensure exceptions are logged.
    reg = flow(one_conf)
    schd = scheduler(reg)

    class MyException(Exception):
        pass

    # replace the main loop with something that raises an exception
    def killer():
        raise MyException('mess')

    schd.main_loop = killer

    # make sure that this error causes the flow to shutdown
    with pytest.raises(MyException):
        async with run(schd) as log:
            # evil sleep - gotta let the except mechanism do its work
            await asyncio.sleep(0.1)

    # make sure the exception was logged
    assert len(log_filter(
        log,
        level=logging.CRITICAL,
        contains='mess'
    )) == 1

    # make sure the server socket has closed - a good indication of a
    # successful clean shutdown
    assert schd.server.socket.closed


@pytest.fixture(scope='module')
async def myflow(mod_flow, mod_scheduler, mod_one_conf):
    """You can save setup/teardown time by reusing fixtures

    Write a module-scoped fixture and it can be shared by all tests in the
    current module.

    The standard fixtures all have `mod_` alternatives to allow you to do
    this.

    Pytest has been configured to run all tests from the same module in the
    same xdist worker, in other words, module scoped fixtures only get
    created once per module, even when distributing tests.

    Obviously this goes with the usual warnings about not mutating the
    object you are testing in the tests.

    """
    reg = mod_flow(mod_one_conf)
    schd = mod_scheduler(reg)
    return schd


def test_module_one(myflow):
    # Ensure can_auto_stop defaults to True
    assert myflow.can_auto_stop is True


def test_module_two(myflow):
    # Ensure the uuid is set on __init__
    assert myflow.uuid_str
