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

"""Test the workings of simulation mode"""

from pathlib import Path
import pytest
from pytest import param

from cylc.flow import commands
from cylc.flow.cycling.iso8601 import ISO8601Point
from cylc.flow.run_modes.simulation import sim_time_check


async def test_started_trigger(flow, reftest, scheduler):
    """Does the started task output trigger downstream tasks
    in sim mode?

    Long standing Bug discovered in Skip Mode work.
    https://github.com/cylc/cylc-flow/pull/6039#issuecomment-2321147445
    """
    schd = scheduler(flow({
        'scheduler': {'events': {'stall timeout': 'PT0S', 'abort on stall timeout': True}},
        'scheduling': {'graph': {'R1': 'a:started => b'}}
    }), paused_start=False)
    assert await reftest(schd) == {
        ('1/a', None),
        ('1/b', ('1/a',))
    }


@pytest.fixture
def monkeytime(monkeypatch):
    """Convenience function monkeypatching time."""
    def _inner(time_: int):
        monkeypatch.setattr('cylc.flow.task_job_mgr.time', lambda: time_)
        monkeypatch.setattr(
            'cylc.flow.run_modes.simulation.time', lambda: time_)
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
        schd.task_job_mgr.submit_nonlive_task_jobs(
            schd.workflow, [itask], 'simulation')
        monkeytime(itask.mode_settings.timeout + 1)

        # Run Time Check
        assert sim_time_check(
            schd.task_events_mgr, [itask],
            schd.workflow_db_mgr
        ) is True

        # Capture result process queue.
        return itask
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
    async with mod_start(schd):
        itasks = schd.pool.get_tasks()
        [schd.task_job_mgr._set_retry_timers(i) for i in itasks]
        yield schd, itasks


def test_false_if_not_running(
    sim_time_check_setup, monkeypatch
):
    schd, itasks = sim_time_check_setup

    itasks = [i for i in itasks if i.state.status != 'running']

    # False if task status not running:
    assert sim_time_check(schd.task_events_mgr, itasks, '') is False


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
    schd, _ = sim_time_check_setup

    itask = schd.pool.get_task(
        ISO8601Point(point), itask)

    for i, result in enumerate(results):
        itask.try_timers['execution-retry'].num = i
        schd.task_job_mgr.submit_nonlive_task_jobs(
            schd.workflow, [itask], 'simulation')
        assert itask.mode_settings.sim_task_fails is result


def test_task_finishes(sim_time_check_setup, monkeytime, caplog):
    """...and an appropriate message sent.

    Checks that failed and bar are output if a task is set to fail.

    Does NOT check every possible cause of an outcome - this is done
    in unit tests.
    """
    schd, _ = sim_time_check_setup
    monkeytime(0)

    # Setup a task to fail, submit it.
    fail_all_1066 = schd.pool.get_task(ISO8601Point('1066'), 'fail_all')
    fail_all_1066.state.status = 'running'
    fail_all_1066.state.is_queued = False
    schd.task_job_mgr.submit_nonlive_task_jobs(
        schd.workflow, [fail_all_1066], 'simulation')

    # For the purpose of the test delete the started time set by
    # submit_nonlive_task_jobs.
    fail_all_1066.summary['started_time'] = 0

    # Before simulation time is up:
    assert sim_time_check(schd.task_events_mgr, [fail_all_1066], '') is False

    # Time's up...
    monkeytime(12)

    # After simulation time is up it Fails and records custom outputs:
    assert sim_time_check(schd.task_events_mgr, [fail_all_1066], '') is True
    outputs = fail_all_1066.state.outputs
    assert outputs.is_message_complete('succeeded') is False
    assert outputs.is_message_complete('bar') is True
    assert outputs.is_message_complete('failed') is True


def test_task_sped_up(sim_time_check_setup, monkeytime):
    """Task will speed up by a factor set in config."""

    schd, _ = sim_time_check_setup
    fast_forward_1066 = schd.pool.get_task(
        ISO8601Point('1066'), 'fast_forward')

    # Run the job submission method:
    monkeytime(0)
    schd.task_job_mgr.submit_nonlive_task_jobs(
        schd.workflow, [fast_forward_1066], 'simulation')
    fast_forward_1066.state.is_queued = False

    result = sim_time_check(schd.task_events_mgr, [fast_forward_1066], '')
    assert result is False
    monkeytime(29)
    result = sim_time_check(schd.task_events_mgr, [fast_forward_1066], '')
    assert result is False
    monkeytime(31)
    result = sim_time_check(schd.task_events_mgr, [fast_forward_1066], '')
    assert result is True


async def test_settings_restart(
    monkeytime, flow, scheduler, start
):
    """Check that simulation mode settings are correctly restored
    upon restart.

    In the case of start time this is collected from the database
    from task_jobs.start_time.

    tasks:
        one: Runs straighforwardly.
        two: Test case where database is missing started_time
            because it was upgraded from an earlier version of Cylc.
    """
    id_ = flow({
        'scheduler': {'cycle point format': '%Y'},
        'scheduling': {
            'initial cycle point': '1066',
            'graph': {
                'R1': 'one & two'
            }
        },
        'runtime': {
            'root': {
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
        og_timeouts = {}
        for itask in schd.pool.get_tasks():
            schd.task_job_mgr.submit_nonlive_task_jobs(
                schd.workflow, [itask], 'simulation')

            og_timeouts[itask.identity] = itask.mode_settings.timeout

        # Mock wallclock < sim end timeout
        monkeytime(itask.mode_settings.timeout - 1)
        assert sim_time_check(
            schd.task_events_mgr, [itask], schd.workflow_db_mgr
        ) is False

    # Stop and restart the scheduler:
    schd = scheduler(id_)
    async with start(schd):
        for itask in schd.pool.get_tasks():
            # Check that we haven't got mode settings back:
            assert itask.mode_settings is None

            if itask.identity == '1066/two':
                # Delete the database entry for `two`: Ensure that
                # we don't break sim mode on upgrade to this version of Cylc.
                schd.workflow_db_mgr.pri_dao.connect().execute(
                    'UPDATE task_jobs'
                    '\n SET time_submit = NULL'
                    '\n WHERE (name == \'two\')'
                )
                schd.workflow_db_mgr.process_queued_ops()
                monkeytime(42)
                expected_timeout = 102.0
            else:
                monkeytime(og_timeouts[itask.identity] - 1)
                expected_timeout = float(int(og_timeouts[itask.identity]))

            assert sim_time_check(
                schd.task_events_mgr, [itask], schd.workflow_db_mgr
            ) is False

            # Check that the itask.mode_settings is now re-created
            assert itask.mode_settings.simulated_run_length == 60.0
            assert itask.mode_settings.sim_task_fails is True


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
        one_1066 = schd.pool.get_task(ISO8601Point('1066'), 'one')

        itask = run_simjob(schd, one_1066.point, 'one')
        assert itask.state.outputs.is_message_complete('failed') is False

        # Modify config as if reinstall had taken place:
        conf_file = Path(schd.workflow_run_dir) / 'flow.cylc'
        conf_file.write_text(
            conf_file.read_text().replace('False', 'True'))

        # Reload Workflow:
        await commands.run_cmd(commands.reload_workflow, schd)

        # Submit second psuedo-job and "run" to success:
        itask = run_simjob(schd, one_1066.point, 'one')
        assert itask.state.outputs.is_message_complete('succeeded') is True


async def test_settings_broadcast(
    flow, scheduler, start, monkeytime
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
                'execution retry delays': '2*PT5S',
                'simulation': {
                    'speedup factor': 1,
                    'fail cycle points': '1066',
                    'fail try 1 only': False
                }
            },
        }
    }, defaults=False)
    schd = scheduler(id_, paused_start=False, run_mode='simulation')
    async with start(schd) as log:
        itask = schd.pool.get_task(ISO8601Point('1066'), 'one')
        itask.state.is_queued = False

        # Submit the first - the sim task will fail:
        schd.task_job_mgr.submit_nonlive_task_jobs(
            schd.workflow, [itask], 'simulation')
        assert itask.mode_settings.sim_task_fails is True

        # Let task finish.
        monkeytime(itask.mode_settings.timeout + 1)
        assert sim_time_check(
            schd.task_events_mgr, [itask],
            schd.workflow_db_mgr
        ) is True

        # The mode_settings object has been cleared:
        assert itask.mode_settings is None
        # Change a setting using broadcast:
        schd.broadcast_mgr.put_broadcast(
            ['1066'], ['one'], [{
                'simulation': {'fail cycle points': ''}
            }])
        # Submit again - result is different:
        schd.task_job_mgr.submit_nonlive_task_jobs(
            schd.workflow, [itask], 'simulation')
        assert itask.mode_settings.sim_task_fails is False

        # Assert Clearing the broadcast works
        schd.broadcast_mgr.clear_broadcast()
        schd.task_job_mgr.submit_nonlive_task_jobs(
            schd.workflow, [itask], 'simulation')
        assert itask.mode_settings.sim_task_fails is True

        # Assert that list of broadcasts doesn't change if we submit
        # Invalid fail cycle points to broadcast.
        itask.mode_settings = None
        schd.broadcast_mgr.put_broadcast(
            ['1066'], ['one'], [{
                'simulation': {'fail cycle points': 'higadfuhasgiurguj'}
            }])
        schd.task_job_mgr.submit_nonlive_task_jobs(
            schd.workflow, [itask], 'simulation')
        assert (
            'Invalid ISO 8601 date representation: higadfuhasgiurguj'
            in log.messages[-1])

        # Check that the invalid broadcast hasn't
        # changed the itask sim mode settings:
        assert itask.mode_settings.sim_task_fails is True

        schd.broadcast_mgr.put_broadcast(
            ['1066'], ['one'], [{
                'simulation': {'fail cycle points': '1'}
            }])
        schd.task_job_mgr.submit_nonlive_task_jobs(
            schd.workflow, [itask], 'simulation')
        assert (
            'Invalid ISO 8601 date representation: 1'
            in log.messages[-1])

        # Broadcast tasks will reparse correctly:
        schd.broadcast_mgr.put_broadcast(
            ['1066'], ['one'], [{
                'simulation': {'fail cycle points': '1945, 1977, 1066'},
                'execution retry delays': '3*PT2S'
            }])
        schd.task_job_mgr.submit_nonlive_task_jobs(
            schd.workflow, [itask], 'simulation')
        assert itask.mode_settings.sim_task_fails is True
        assert itask.try_timers['execution-retry'].delays == [2.0, 2.0, 2.0]
        # n.b. rtconfig should remain unchanged, lest we cancel broadcasts:
        assert itask.tdef.rtconfig['execution retry delays'] == [5.0, 5.0]
