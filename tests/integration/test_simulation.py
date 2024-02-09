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

from pathlib import Path
import pytest
from pytest import UsageError, param
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


@pytest.fixture
def q_clean():
    """Clear message queue to revent test interference.
    """
    def _inner(msg_q):
        if not msg_q.empty():
            msg_q.get()
    return _inner


@pytest.fixture
def run_simjob(monkeytime):
    """Run a simulated job to completion.

    Returns the output status.
    """
    def _run_simjob(schd, point, task):
        itask = schd.pool.get_task(point, task)
        itask.state.is_queued = False
        monkeytime(0)
        schd.task_job_mgr._simulation_submit_task_jobs(
            [itask], schd.workflow)
        monkeytime(itask.mode_settings.timeout + 1)

        # Run Time Check
        assert sim_time_check(
            schd.message_queue, [itask], schd.task_events_mgr.broadcast_mgr,
            schd.workflow_db_mgr
        ) is True

        # Capture result process queue.
        out = schd.message_queue.queue[0].message
        schd.process_queued_task_messages()
        return out
    return _run_simjob


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


def test_false_if_not_running(
    sim_time_check_setup, monkeypatch, q_clean
):
    schd, itasks, msg_q = sim_time_check_setup

    itasks = [i for i in itasks if i.state.status != 'running']

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
def test_fail_once(sim_time_check_setup, itask, point, results, monkeypatch):
    """A task with a fail cycle point only fails
    at that cycle point, and then only on the first submission.
    """
    schd, _, msg_q = sim_time_check_setup

    itask = schd.pool.get_task(
        ISO8601Point(point), itask)

    for i, result in enumerate(results):
        itask.try_timers['execution-retry'].num = i
        schd.task_job_mgr._simulation_submit_task_jobs(
            [itask], schd.workflow)
        assert itask.mode_settings.sim_task_fails is result


def test_task_finishes(sim_time_check_setup, monkeytime, q_clean):
    """...and an appropriate message sent.

    Checks that failed and bar are output if a task is set to fail.

    Does NOT check every possible cause of an outcome - this is done
    in unit tests.
    """
    schd, _, msg_q = sim_time_check_setup

    q_clean(msg_q)

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


async def test_settings_restart(
    monkeytime, flow, scheduler, start
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
                'execution retry delays': 'P0Y',
                'simulation': {
                    'speedup factor': 1,
                    'fail cycle points': 'all',
                    'fail try 1 only': True,
                }
            },
        }
    })
    schd = scheduler(id_)

    # Start the workflow:
    async with start(schd):
        itask = schd.pool.get_tasks()[0]
        schd.task_job_mgr._simulation_submit_task_jobs(
            [itask], schd.workflow)

        og_timeout = itask.mode_settings.timeout

        # Mock wallclock < sim end timeout
        monkeytime(itask.mode_settings.timeout - 1)
        assert sim_time_check(
            schd.message_queue, [itask], schd.task_events_mgr.broadcast_mgr,
            schd.workflow_db_mgr
        ) is False

    # Stop and restart the scheduler:
    schd = scheduler(id_)
    async with start(schd):
        # Get our tasks and fix wallclock:
        itask = schd.pool.get_tasks()[0]

        # Check that we haven't got started time & mode settings back:
        assert itask.summary['started_time'] is None
        assert itask.mode_settings is None

        # Set the current time:
        monkeytime(og_timeout - 1)
        assert sim_time_check(
            schd.message_queue, [itask], schd.task_events_mgr.broadcast_mgr,
            schd.workflow_db_mgr
        ) is False

        # Check that the itask.mode_settings is now re-created
        assert itask.mode_settings.__dict__ == {
            'simulated_run_length': 60.0,
            'sim_task_fails': True,
            'timeout': float(int(og_timeout))
        }


async def test_settings_reload(
    flow, scheduler, start, run_simjob
):
    """Check that simulation mode settings are changed for future
    pseudo jobs on reload.

    """
    id_ = flow({
        'scheduler': {'cycle point format': '%Y'},
        'scheduling': {
            'initial cycle point': '1066',
            'graph': {'R1': 'one'}
        },
        'runtime': {
            'one': {
                'execution time limit': 'PT1M',
                'execution retry delays': 'P0Y',
                'simulation': {
                    'speedup factor': 1,
                    'fail cycle points': 'all',
                    'fail try 1 only': False,
                }
            },
        }
    })
    schd = scheduler(id_)
    async with start(schd):
        # Submit first psuedo-job and "run" to failure:
        one_1066 = schd.pool.get_tasks()[0]
        assert run_simjob(schd, one_1066.point, 'one') == 'failed'

        # Modify config as if reinstall had taken place:
        conf_file = Path(schd.workflow_run_dir) / 'flow.cylc'
        conf_file.write_text(
            conf_file.read_text().replace('False', 'True'))

        # Reload Workflow:
        await schd.command_reload_workflow()

        # Submit second psuedo-job and "run" to success:
        assert run_simjob(
            schd, one_1066.point, 'one') == 'succeeded'


async def test_settings_broadcast(
    flow, scheduler, start, complete, monkeytime
):
    """Assert that broadcasting a change in the settings for a task
    affects subsequent psuedo-submissions.
    """
    id_ = flow({
        'scheduler': {'cycle point format': '%Y'},
        'scheduling': {
            'initial cycle point': '1066',
            'graph': {'R1': 'one'}
        },
        'runtime': {
            'one': {
                'execution time limit': 'PT1S',
                'simulation': {
                    'speedup factor': 1,
                    'fail cycle points': '1066',
                }
            },
        }
    }, defaults=False)
    schd = scheduler(id_, paused_start=False, run_mode='simulation')
    async with start(schd):
        itask = schd.pool.get_tasks()[0]
        itask.state.is_queued = False

        # Submit the first - the sim task will fail:
        schd.task_job_mgr._simulation_submit_task_jobs(
            [itask], schd.workflow)
        assert itask.mode_settings.sim_task_fails is True

        # Let task finish.
        monkeytime(itask.mode_settings.timeout + 1)
        assert sim_time_check(
            schd.message_queue, [itask], schd.task_events_mgr.broadcast_mgr,
            schd.workflow_db_mgr
        ) is True

        # The mode_settings object has been cleared:
        assert itask.mode_settings is None

        # Change a setting using broadcast:
        schd.task_events_mgr.broadcast_mgr.put_broadcast(
            ['1066'], ['one'], [{
                'simulation': {'fail cycle points': ''}
            }])

        # Submit again - result is different:
        schd.task_job_mgr._simulation_submit_task_jobs(
            [itask], schd.workflow)
        assert itask.mode_settings.sim_task_fails is False
