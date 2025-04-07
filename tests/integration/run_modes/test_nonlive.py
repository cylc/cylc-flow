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
from typing import Any, Dict

from cylc.flow.cycling.integer import IntegerPoint
from cylc.flow.cycling.iso8601 import ISO8601Point
from cylc.flow.scheduler import Scheduler


# Define here to ensure test doesn't just mirror code:
KGO = {
    'live': {
        'flow_nums': '[1]',
        'is_manual_submit': 0,
        'try_num': 1,
        'submit_status': 0,
        'run_signal': None,
        'run_status': 0,
        # capture_live_submissions fixture submits jobs in sim mode
        'platform_name': 'simulation',
        'job_runner_name': 'simulation',
        'job_id': None,
    },
    'skip': {
        'flow_nums': '[1]',
        'is_manual_submit': 0,
        'try_num': 1,
        'submit_status': 0,
        'run_signal': None,
        'run_status': 0,
        'platform_name': 'skip',
        'job_runner_name': 'skip',
        'job_id': None,
    },
}


def not_time(data: Dict[str, Any]):
    """Filter out fields containing times to reduce risk of
    flakiness"""
    return {k: v for k, v in data.items() if 'time' not in k}


@pytest.fixture
def submit_and_check_db():
    """Wraps up testing that we want to do repeatedly in
    test_db_task_jobs.
    """
    def _inner(schd):
        # Submit task jobs:
        schd.submit_task_jobs(schd.pool.get_tasks())
        # Make sure that db changes are enacted:
        schd.workflow_db_mgr.process_queued_ops()

        for mode, kgo in KGO.items():
            task_jobs = schd.workflow_db_mgr.pub_dao.select_task_job(1, mode)

            # Check all non-datetime items against KGO:
            assert not_time(task_jobs) == kgo, (
                f'Mode {mode}: incorrect db entries.')

            # Check that timestamps have been created:
            for timestamp in [
                'time_submit', 'time_submit_exit', 'time_run', 'time_run_exit'
            ]:
                assert task_jobs[timestamp] is not None
    return _inner


async def test_db_task_jobs(
    flow, scheduler, start, capture_live_submissions,
    submit_and_check_db
):
    """Ensure that task job data is added to the database correctly
    for each run mode.
    """
    schd: Scheduler = scheduler(
        flow({
            'scheduling': {
                'graph': {
                    'R1': ' & '.join(KGO)
                }
            },
            'runtime': {
                mode: {'run mode': mode} for mode in KGO
            },
        }),
        run_mode='live'
    )
    async with start(schd):
        # Reference all task proxies so we can examine them
        # at the end of the test:
        itask_skip = schd.pool.get_task(IntegerPoint('1'), 'skip')
        itask_live = schd.pool.get_task(IntegerPoint('1'), 'live')

        submit_and_check_db(schd)

        # Set outputs to failed:
        schd.pool.set_prereqs_and_outputs('*', ['failed'], [], [])

        submit_and_check_db(schd)

        # capture_live_submissions fixture submits jobs in sim mode
        assert itask_live.run_mode.value == 'simulation'
        assert itask_skip.run_mode.value == 'skip'


async def test_db_task_states(
    one_conf, flow, scheduler, start
):
    """Test that tasks will have the same information entered into the task
    state database whichever mode is used.
    """
    conf = one_conf
    conf['runtime'] = {'one': {'run mode': 'skip'}}
    schd = scheduler(flow(conf))
    async with start(schd):
        schd.submit_task_jobs(schd.pool.get_tasks())
        schd.workflow_db_mgr.process_queued_ops()
        result = schd.workflow_db_mgr.pri_dao.connect().execute(
            'SELECT * FROM task_states').fetchone()

        # Submit number has been added to the table:
        assert result[5] == 1
        # time_created added to the table
        assert result[3]


async def test_mean_task_time(
    flow, scheduler, start, complete, capture_live_submissions
):
    """Non-live tasks are not added to the list of task times,
    so skipping tasks will not affect how long Cylc expects tasks to run.
    """
    schd = scheduler(flow({
        'scheduling': {
            'initial cycle point': '1000',
            'final cycle point': '1002',
            'graph': {'P1Y': 'foo'}}
    }), run_mode='live')

    async with start(schd):
        itask = schd.pool.get_task(ISO8601Point('10000101T0000Z'), 'foo')
        assert list(itask.tdef.elapsed_times) == []

        # Make the task run in skip mode at one cycle:
        schd.broadcast_mgr.put_broadcast(
            ['1000'], ['foo'], [{'run mode': 'skip'}])

        # Fake adding some other examples of the task:
        itask.tdef.elapsed_times.extend([133.0, 132.4])

        # Submit two tasks:
        schd.submit_task_jobs([itask])

        # Ensure that the skipped task has succeeded, and that the
        # number of items in the elapsed_times has not changed.
        assert itask.state.status == 'succeeded'
        assert len(itask.tdef.elapsed_times) == 2
