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

from cylc.flow.task_events_mgr import TaskJobLogsRetrieveContext
from cylc.flow.scheduler import Scheduler

import logging
from typing import Any as Fixture


async def test_process_job_logs_retrieval_warns_no_platform(
    one_conf: Fixture, flow: Fixture, scheduler: Fixture, run: Fixture,
    db_select: Fixture, caplog: Fixture
):
    """Job log retrieval handles `NoHostsError`"""

    ctx = TaskJobLogsRetrieveContext(
        platform_name='skarloey',
        max_size=256,
        key='skarloey'
    )
    id_: str = flow(one_conf)
    schd: 'Scheduler' = scheduler(id_, paused_start=True)
    # Run
    async with run(schd):
        schd.task_events_mgr._process_job_logs_retrieval(
            schd, ctx, 'foo'
        )
        warning = caplog.records[-1]
        assert warning.levelname == 'WARNING'
        assert 'Unable to retrieve' in warning.msg


async def test__reset_job_timers(
    one_conf: Fixture, flow: Fixture, scheduler: Fixture,
    start: Fixture, caplog: Fixture, mock_glbl_cfg: Fixture,
):
    """Integration test of pathway leading to
    process_execution_polling_intervals.
    """
    schd = scheduler(flow(one_conf))
    async with start(schd, level=logging.DEBUG):
        itask = schd.pool.get_tasks()[0]
        itask.state.status = 'running'
        itask.platform['execution polling intervals'] = [25]
        itask.platform['execution time limit polling intervals'] = [10]
        itask.summary['execution_time_limit'] = 30
        caplog.records.clear()
        schd.task_events_mgr._reset_job_timers(itask)

    assert (
        'polling intervals=PT25S,PT15S,PT10S,...'
        in caplog.records[0].msg
    )


async def test__insert_task_job(flow, one_conf, scheduler, start, validate):
    """Simulation mode tasks are inserted into the Data Store,
    with correct submit number.
    """
    conf = {
        'scheduling': {'graph': {'R1': 'rhenas'}},
        'runtime': {'rhenas': {'simulation': {
            'fail cycle points': '1',
            'fail try 1 only': False,
    }}}}
    id_ = flow(conf)
    schd = scheduler(id_)
    async with start(schd):
        # Set task to running:
        itask =  schd.pool.get_tasks()[0]
        itask.state.status = 'running'
        itask.submit_num += 1

        # Not run _insert_task_job yet:
        assert not schd.data_store_mgr.added['jobs'].keys()

        # Insert task (twice):
        schd.task_events_mgr._insert_task_job(itask, 'now', 1)
        itask.submit_num += 1
        schd.task_events_mgr._insert_task_job(itask, 'now', 1)

        # Check that there are two entries with correct submit
        # numbers waiting for data-store insertion:
        assert [
            i.submit_num for i
            in schd.data_store_mgr.added['jobs'].values()
        ] == [1, 2]
