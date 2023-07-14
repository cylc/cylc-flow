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

from pathlib import Path
from typing import Any as Fixture


async def test_process_job_logs_retrieval_warns_no_platform(
    one_conf: Fixture, flow: Fixture, scheduler: Fixture, run: Fixture,
    db_select: Fixture, caplog: Fixture
):
    """Job log retrieval handles `NoHostsError`"""

    ctx = TaskJobLogsRetrieveContext(
        ctx_type='raa',
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


async def test_process_message_no_repeat(
    one_conf: Fixture, flow: Fixture, scheduler: Fixture, run: Fixture
):
    """Don't log received messages if they are found again when."""
    reg: str = flow(one_conf)
    schd: 'Scheduler' = scheduler(reg, paused_start=True)
    message: str = 'The dead swans lay in the stagnant pool'
    message_time: str = 'Thursday Lunchtime'

    async with run(schd) as log:
        # Set up the database with a message already received:
        itask = schd.pool.get_tasks()[0]
        itask.tdef.run_mode = 'live'
        schd.workflow_db_mgr.put_insert_task_events(
            itask, {'time': message_time, 'event': '', 'message': message})
        schd.process_workflow_db_queue()

        # Task event manager returns None:
        assert schd.task_events_mgr.process_message(
            itask=itask, severity='comical', message=message,
            event_time=message_time, submit_num=0,
            flag=schd.task_events_mgr.FLAG_POLLED
        ) is None

        # Log doesn't contain a repeat message:
        assert (
            schd.task_events_mgr.FLAG_POLLED
            not in log.records[-1].message
        )
