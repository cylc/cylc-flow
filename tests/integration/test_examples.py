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
"""Working documentation for the integration test framework.

Here are some examples which cover a range of uses (and also provide some
useful testing in the process 😀.)

"""

import asyncio
import logging
from pathlib import Path

import pytest

from cylc.flow import __version__
from cylc.flow.scheduler import Scheduler


async def test_create_flow(flow, run_dir):
    """Use the flow fixture to create workflows on the file system."""
    # Ensure a flow.cylc file gets written out
    id_ = flow({
        'scheduler': {
            'allow implicit tasks': True
        },
        'scheduling': {
            'graph': {
                'R1': 'foo'
            }
        }
    })
    workflow_dir = run_dir / id_
    flow_file = workflow_dir / 'flow.cylc'

    assert workflow_dir.exists()
    assert flow_file.exists()


async def test_run(flow, scheduler, run, one_conf):
    """Create a workflow, initialise the scheduler and run it."""
    # Ensure the scheduler can survive for at least one second without crashing
    id_ = flow(one_conf)
    schd = scheduler(id_)
    async with run(schd):
        await asyncio.sleep(1)  # this yields control to the main loop


async def test_logging(flow, scheduler, start, one_conf, log_filter):
    """We can capture log records when we run a scheduler."""
    # Ensure that the cylc version is logged on startup.
    id_ = flow(one_conf)
    schd = scheduler(id_)
    async with start(schd):
        # this returns a list of log records containing __version__
        assert log_filter(contains=__version__)


async def test_scheduler_arguments(flow, scheduler, start, one_conf):
    """We can provide options to the scheduler when we __init__ it.

    These options match their command line equivalents.

    Use the `dest` value specified in the option parser.

    """
    # Ensure the paused_start option is obeyed by the scheduler.
    id_ = flow(one_conf)
    schd = scheduler(id_, paused_start=True)
    async with start(schd):
        assert schd.is_paused
    id_ = flow(one_conf)
    schd = scheduler(id_, paused_start=False)
    async with start(schd):
        assert not schd.is_paused


async def test_shutdown(flow, scheduler, start, one_conf):
    """Shut down a workflow.

    The scheduler automatically shuts down once you exit the `async with`
    block, however you can manually shut it down within this block if you
    like.

    """
    # Ensure the TCP server shuts down with the scheduler.
    id_ = flow(one_conf)
    schd = scheduler(id_)
    async with start(schd):
        pass
    assert schd.server.replier.socket.closed


async def test_install(flow, scheduler, one_conf, run_dir):
    """You don't have to run workflows, it's usually best not to!

    You can take the scheduler through the startup sequence as far as needed
    for your test.

    """
    # Ensure the installation of the job script is completed.
    id_ = flow(one_conf)
    schd = scheduler(id_)
    await schd.install()
    assert Path(
        run_dir, schd.workflow, '.service', 'etc', 'job.sh'
    ).exists()


async def test_task_pool(one, start):
    """You don't have to run the scheduler to play with the task pool.

    There are two fixtures to start a scheduler:

    `start`
       Takes a scheduler through the startup sequence.
    `run`
       Takes a scheduler through the startup sequence, then sets the main loop
       going.

    Unless you need the Scheduler main loop running, use `start`.

    This test uses a pre-prepared Scheduler called "one".

    """
    # Ensure that the correct number of tasks get added to the task pool.
    async with start(one):
        # pump the scheduler's heart manually
        one.pool.release_runahead_tasks()
        assert len(one.pool.active_tasks) == 1


async def test_exception(one, run, log_filter):
    """Through an exception into the scheduler to see how it will react.

    You have to do this from within the scheduler itself.
    The easy way is to patch the object.

    """
    class MyException(Exception):
        pass

    # replace the main loop with something that raises an exception
    def killer():
        raise MyException('mess')

    one._main_loop = killer

    # make sure that this error causes the flow to shutdown
    with pytest.raises(MyException):
        async with run(one):
            # The `run` fixture's shutdown logic waits for the main loop to run
            pass

    # make sure the exception was logged
    assert len(log_filter(logging.CRITICAL, contains='mess')) == 1

    # make sure the server socket has closed - a good indication of a
    # successful clean shutdown
    assert one.server.replier.socket.closed


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
    id_ = mod_flow(mod_one_conf)
    schd = mod_scheduler(id_)
    return schd


def test_module_scoped_fixture(myflow):
    """Ensure the host is set on __init__.

    The myflow fixture will be shared between all test functions within this
    Python module.

    """
    assert myflow.host


async def test_db_select(one, start, db_select):
    """Demonstrate and test querying the workflow database."""
    # run a workflow
    schd = one
    async with start(schd):
        # Note: can't query database here unfortunately
        pass

    # Now we can query the DB
    # Select all from workflow_params table:
    assert ('UTC_mode', '0') in db_select(schd, False, 'workflow_params')

    # Select name & status columns from task_states table:
    results = db_select(schd, False, 'task_states', 'name', 'status')
    assert results[0] == ('one', 'waiting')

    # Select all columns where name==one & status==waiting from
    # task_states table:
    results = db_select(
        schd, False, 'task_states', name='one', status='waiting')
    assert len(results) == 1


async def test_reflog(flow, scheduler, run, reflog, complete):
    """Test the triggering of tasks.

    This is the integration test version of "reftest" in the funtional tests.

    It works by capturing the triggers which caused each submission so that
    they can be compared with the expected outcome.
    """
    id_ = flow({
        'scheduling': {
            'initial cycle point': '1',
            'final cycle point': '1',
            'cycling mode': 'integer',
            'graph': {
                'P1': '''
                    a => b => c
                    x => b => z
                    b[-P1] => b
                '''
            }
        }
    })
    schd = scheduler(id_, paused_start=False)

    async with run(schd):
        triggers = reflog(schd)  # Note: add flow_nums=True to capture flows
        await complete(schd)

    assert triggers == {
        # 1/a was triggered by nothing (i.e. it's parentless)
        ('1/a', None),
        # 1/b was triggered by three tasks (note the pre-initial dependency)
        ('1/b', ('0/b', '1/a', '1/x')),
        ('1/c', ('1/b',)),
        ('1/x', None),
        ('1/z', ('1/b',)),
    }


async def test_reftest(flow, scheduler, reftest):
    """Test the triggering of tasks.

    This uses the reftest fixture which combines the reflog and
    complete fixtures. Suitable for use when you just want to do a simple
    reftest.
    """
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': 'a => b'
            }
        }
    })
    schd = scheduler(id_, paused_start=False)

    assert await reftest(schd) == {
        ('1/a', None),
        ('1/b', ('1/a',)),
    }


async def test_show(one: Scheduler, start, cylc_show):
    """Demonstrate the `cylc_show` fixture"""
    async with start(one):
        out = await cylc_show(one, '1/one')
    assert list(out.keys()) == ['1/one']
    assert out['1/one']['state'] == 'waiting'
