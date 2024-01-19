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

import pytest
from pytest import param
from queue import Queue

from cylc.flow.cycling.iso8601 import ISO8601Point
from cylc.flow.simulation import sim_time_check


def get_msg_queue_item(queue, id_):
    for item in queue.queue:
        if id_ in str(item.job_id):
            return item


@pytest.fixture
def monkeytime(monkeypatch):
    """Convenience function monkeypatching time."""
    def _inner(time_: int):
        monkeypatch.setattr('cylc.flow.task_job_mgr.time', lambda: time_)
        monkeypatch.setattr('cylc.flow.simulation.time', lambda: time_)
    return _inner


@pytest.fixture(scope='module')
async def sim_time_check_setup(
    mod_flow, mod_scheduler, mod_start, mod_one_conf,
):
    schd = mod_scheduler(mod_flow({
        'scheduler': {'cycle point format': '%Y'},
        'scheduling': {
            'initial cycle point': '1066',
            'graph': {
                'R1': 'one & fail_all & fast_forward',
                'P1Y': 'fail_once & fail_all_submits'
            }
        },
        'runtime': {
            'one': {},
            'fail_all': {
                'simulation': {
                    'fail cycle points': 'all',
                    'fail try 1 only': False
                },
                'outputs': {'foo': 'bar'}
            },
            # This task ought not be finished quickly, but for the speed up
            'fast_forward': {
                'execution time limit': 'PT1M',
                'simulation': {'speedup factor': 2}
            },
            'fail_once': {
                'simulation': {
                    'fail cycle points': '1066, 1068',
                }
            },
            'fail_all_submits': {
                'simulation': {
                    'fail cycle points': '1066',
                    'fail try 1 only': False,
                }
            }
        }
    }))
    msg_q = Queue()
    async with mod_start(schd):
        itasks = schd.pool.get_tasks()
        [schd.task_job_mgr._set_retry_timers(i) for i in itasks]
        yield schd, itasks, msg_q


def test_false_if_not_running(sim_time_check_setup, monkeypatch):
    schd, itasks, msg_q = sim_time_check_setup

    # False if task status not running:
    assert sim_time_check(
        msg_q, itasks, schd.task_events_mgr.broadcast_mgr, ''
    ) is False


@pytest.mark.parametrize(
    'itask, point, results',
    (
        # Task fails this CP, first submit.
        param(
            'fail_once', '1066', (True, False, False),
            id='only-fail-on-submit-1'),
        # Task succeeds this CP, all submits.
        param(
            'fail_once', '1067', (False, False, False),
            id='do-not-fail-this-cp'),
        # Task fails this CP, first submit.
        param(
            'fail_once', '1068', (True, False, False),
            id='and-another-cp'),
        # Task fails this CP, all submits.
        param(
            'fail_all_submits', '1066', (True, True, True),
            id='fail-all-submits'),
        # Task succeeds this CP, all submits.
        param(
            'fail_all_submits', '1067', (False, False, False),
            id='fail-no-submits'),
    )
)
def test_fail_once(sim_time_check_setup, itask, point, results):
    """A task with a fail cycle point only fails
    at that cycle point, and then only on the first submission.
    """
    schd, _, msg_q = sim_time_check_setup

    itask = schd.pool.get_task(
        ISO8601Point(point), itask)

    for result in results:
        schd.task_job_mgr._simulation_submit_task_jobs(
            [itask], schd.workflow)
        assert itask.mode_settings.sim_task_fails is result


def test_sim_time_check_sets_started_time(
    scheduler, sim_time_check_setup
):
    """But sim_time_check still returns False

    This only occurs in reality if we've restarted from database and
    not retrieved the started time from itask.summary.
    """
    schd, _, msg_q = sim_time_check_setup
    one_1066 = schd.pool.get_task(ISO8601Point('1066'), 'one')
    # Add info to databse as if it's be started before shutdown:
    schd.task_job_mgr._simulation_submit_task_jobs(
        [one_1066], schd.workflow)
    schd.workflow_db_mgr.process_queued_ops()
    one_1066.summary['started_time'] = None
    one_1066.state.is_queued = False
    one_1066.mode_settings = None
    assert one_1066.summary['started_time'] is None
    assert sim_time_check(
        msg_q, [one_1066], schd.task_events_mgr.broadcast_mgr,
        schd.workflow_db_mgr
    ) is False
    assert one_1066.summary['started_time'] is not None


def test_task_finishes(sim_time_check_setup, monkeytime):
    """...and an appropriate message sent.

    Checks that failed and bar are output if a task is set to fail.

    Does NOT check every possible cause of an outcome - this is done
    in unit tests.
    """
    schd, _, msg_q = sim_time_check_setup
    monkeytime(0)

    # Setup a task to fail, submit it.
    fail_all_1066 = schd.pool.get_task(ISO8601Point('1066'), 'fail_all')
    fail_all_1066.state.status = 'running'
    fail_all_1066.state.is_queued = False
    schd.task_job_mgr._simulation_submit_task_jobs(
        [fail_all_1066], schd.workflow)

    # For the purpose of the test delete the started time set by
    # _simulation_submit_task_jobs.
    fail_all_1066.summary['started_time'] = 0

    # Before simulation time is up:
    assert sim_time_check(
        msg_q, [fail_all_1066], schd.task_events_mgr.broadcast_mgr, ''
    ) is False

    # Time's up...
    monkeytime(12)

    # After simulation time is up it Fails and records custom outputs:
    assert sim_time_check(
        msg_q, [fail_all_1066], schd.task_events_mgr.broadcast_mgr, ''
    ) is True
    assert sorted(i.message for i in msg_q.queue) == ['bar', 'failed']


def test_task_sped_up(sim_time_check_setup, monkeytime):
    """Task will speed up by a factor set in config."""

    schd, _, msg_q = sim_time_check_setup
    fast_forward_1066 = schd.pool.get_task(
        ISO8601Point('1066'), 'fast_forward')

    # Run the job submission method:
    monkeytime(0)
    schd.task_job_mgr._simulation_submit_task_jobs(
        [fast_forward_1066], schd.workflow)
    fast_forward_1066.state.is_queued = False

    assert sim_time_check(
        msg_q, [fast_forward_1066], schd.task_events_mgr.broadcast_mgr, ''
    ) is False
    monkeytime(29)
    assert sim_time_check(
        msg_q, [fast_forward_1066], schd.task_events_mgr.broadcast_mgr, ''
    ) is False
    monkeytime(31)
    assert sim_time_check(
        msg_q, [fast_forward_1066], schd.task_events_mgr.broadcast_mgr, ''
    ) is True


async def test_simulation_mode_settings_restart(
    monkeytime, flow, scheduler, run, start
):
    """Check that simulation mode settings are correctly restored
    upon restart.

    In the case of start time this is collected from the database
    from task_jobs.start_time.
    """
    id_ = flow({
        'scheduler': {'cycle point format': '%Y'},
        'scheduling': {
            'initial cycle point': '1066',
            'graph': {
                'R1': 'one'
            }
        },
        'runtime': {
            'one': {
                'execution time limit': 'PT1M',
                'simulation': {
                    'speedup factor': 1
                }
            },
        }
    })
    schd = scheduler(id_)
    msg_q = Queue()

    # Start the workflow:
    async with start(schd):
        # Pick the task proxy, Mock its start time, set state to running:
        itask = schd.pool.get_tasks()[0]
        itask.summary['started_time'] = 0
        itask.state.status = 'running'

        # Submit it, then mock the wallclock and assert that it's not finshed.
        schd.task_job_mgr._simulation_submit_task_jobs(
            [itask], schd.workflow)
        monkeytime(0)

        assert sim_time_check(
            msg_q, [itask], schd.task_events_mgr.broadcast_mgr,
            schd.workflow_db_mgr
        ) is False

    # Stop and restart the scheduler:
    schd = scheduler(id_)
    async with start(schd):
        # Get our tasks and fix wallclock:
        itask = schd.pool.get_tasks()[0]
        monkeytime(12)
        itask.state.status = 'running'

        # Check that we haven't got started time back
        assert itask.summary['started_time'] is None

        # Set the start time in the database to 0 to make the
        # test simpler:
        schd.workflow_db_mgr.put_insert_task_jobs(
            itask, {'time_submit': '19700101T0000Z'})
        schd.workflow_db_mgr.process_queued_ops()

        # Set the current time:
        monkeytime(12)
        assert sim_time_check(
            msg_q, [itask], schd.task_events_mgr.broadcast_mgr,
            schd.workflow_db_mgr
        ) is False

        # Set the current time > timeout
        monkeytime(61)
        assert sim_time_check(
            msg_q, [itask], schd.task_events_mgr.broadcast_mgr,
            schd.workflow_db_mgr
        ) is True
