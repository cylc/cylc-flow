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

import logging
from types import SimpleNamespace
from typing import Any as Fixture

import pytest

from cylc.flow.data_store_mgr import (
    JOBS,
    TASK_STATUS_WAITING,
)
from cylc.flow.id import Tokens
from cylc.flow.run_modes import RunMode
from cylc.flow.scheduler import Scheduler
from cylc.flow.task_events_mgr import (
    EventKey,
    TaskJobLogsRetrieveContext,
)

from .test_workflow_events import TEMPLATES


# NOTE: we do not test custom event handlers here because these are tested
# as a part of workflow validation (now also performed by cylc play)


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
        'runtime': {
            'rhenas': {
                'simulation': {
                    'fail cycle points': '1',
                    'fail try 1 only': False,
                }
            }
        },
    }
    id_ = flow(conf)
    schd = scheduler(id_)
    async with start(schd):
        # Set task to running:
        itask = schd.pool.get_tasks()[0]
        itask.state.status = 'running'
        itask.submit_num += 1
        itask.run_mode = RunMode.SIMULATION

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


async def test__always_insert_task_job(
    flow, scheduler, mock_glbl_cfg, start, run
):
    """Insert Task Job _Always_ inserts a task into the data store.

    Bug https://github.com/cylc/cylc-flow/issues/6172 was caused
    by passing task state to data_store_mgr.insert_job: Where
    a submission retry was in progress the task state would be
    "waiting" which caused the data_store_mgr.insert_job
    to return without adding the task to the data store.
    This is testing two different cases:

    * Could not select host from platform
    * Could not select host from platform group
    """
    global_config = """
        [platforms]
            [[broken1]]
                hosts = no-such-host-1
            [[broken2]]
                hosts = no-such-host-2
        [platform groups]
            [[broken]]
                platforms = broken1
    """
    mock_glbl_cfg('cylc.flow.platforms.glbl_cfg', global_config)

    id_ = flow({
        'scheduling': {'graph': {'R1': 'broken & broken2'}},
        'runtime': {
            'root': {'submission retry delays': 'PT10M'},
            'broken': {'platform': 'broken'},
            'broken2': {'platform': 'broken2'}
        }
    })

    schd: Scheduler = scheduler(id_, run_mode='live')
    schd.bad_hosts.update({'no-such-host-1', 'no-such-host-2'})
    async with start(schd):
        schd.submit_task_jobs(schd.pool.get_tasks())
        await schd.update_data_structure()

        # Both tasks are in a waiting state:
        assert all(
            i.state.status == TASK_STATUS_WAITING
            for i in schd.pool.get_tasks()
        )

        # Both jobs are in the data store with submit-failed state:
        updates = {
            k.split('//')[-1]: v.state
            for k, v in schd.data_store_mgr.data[schd.id][JOBS].items()
        }
        assert updates == {
            '1/broken/01': 'submit-failed',
            '1/broken2/01': 'submit-failed'
        }


async def test__process_message_failed_with_retry(one, start, log_filter):
    """Log job failure, even if a retry is scheduled.

    See: https://github.com/cylc/cylc-flow/pull/6169

    """

    async with start(one) as LOG:
        fail_once = one.pool.get_tasks()[0]
        # Add retry timers:
        one.task_job_mgr._set_retry_timers(
            fail_once, {
                'execution retry delays': [1],
                'submission retry delays': [1]
            })

        # Process submit failed message with and without retries:
        one.task_events_mgr._process_message_submit_failed(
            fail_once, None, False)
        record = log_filter(contains='1/one:waiting(queued)] retrying in')
        assert record[0][0] == logging.WARNING

        one.task_events_mgr._process_message_submit_failed(
            fail_once, None, False)
        failed_record = log_filter(level=logging.ERROR)[-1]
        assert 'submission failed' in failed_record[1]

        # Process failed message with and without retries:
        one.task_events_mgr._process_message_failed(
            fail_once, None, 'failed', False, 'failed/OOK')
        last_record = LOG.records[-1]
        assert last_record.levelno == logging.WARNING
        assert 'retrying in' in last_record.message

        one.task_events_mgr._process_message_failed(
            fail_once, None, 'failed', False, 'failed/OOK')
        failed_record = log_filter(level=logging.ERROR)[-1]
        assert 'failed/OOK' in failed_record[1]


@pytest.mark.parametrize('template', TEMPLATES)
async def test_mail_footer_template(
    mod_one,  # use the same scheduler for each test
    start,
    mock_glbl_cfg,
    log_filter,
    capcall,
    template,
):
    """It should handle templating issues with the mail footer."""
    # prevent emails from being sent
    mail_calls = capcall(
        'cylc.flow.task_events_mgr.TaskEventsManager._send_mail'
    )

    # configure mail footer
    mock_glbl_cfg(
        'cylc.flow.workflow_events.glbl_cfg',
        f'''
            [scheduler]
                [[mail]]
                    footer = 'footer={template}'
        ''',
    )

    # start the workflow and get it to send an email
    ctx = SimpleNamespace(mail_to=None, mail_from=None)
    id_keys = [EventKey('none', 'failed', 'failed', Tokens('//1/a'))]
    async with start(mod_one):
        mod_one.task_events_mgr._process_event_email(mod_one, ctx, id_keys)

    # warnings should appear only when the template is invalid
    should_log = 'workflow' not in template

    # check that template issues are handled correctly
    assert bool(log_filter(
        contains='Ignoring bad mail footer template',
    )) == should_log
    assert bool(log_filter(
        contains=template,
    )) == should_log

    # check that the mail is sent even if there are issues with the footer
    assert len(mail_calls) == 1


async def test_event_email_body(
    mod_one,
    start,
    capcall,
):
    """It should send an email with the event context."""
    mail_calls = capcall(
        'cylc.flow.task_events_mgr.TaskEventsManager._send_mail'
    )

    # start the workflow and get it to send an email
    ctx = SimpleNamespace(mail_to=None, mail_from=None)
    async with start(mod_one):
        # send a custom task message with the warning severity level
        id_keys = [
            EventKey('none', 'warning', 'warning message', Tokens('//1/a/01'))
        ]
        mod_one.task_events_mgr._process_event_email(mod_one, ctx, id_keys)

    # test the email which would have been sent for this message
    email_body = mail_calls[0][0][3]
    assert 'event: warning'
    assert 'job: 1/a/01' in email_body
    assert 'message: warning message' in email_body
    assert f'workflow: {mod_one.tokens["workflow"]}' in email_body
    assert f'host: {mod_one.host}' in email_body
    assert f'port: {mod_one.server.port}' in email_body
    assert f'owner: {mod_one.owner}' in email_body
