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

from cylc.flow import CYLC_LOG
from cylc.flow.task_state import TASK_STATUS_RUNNING


async def test_run_job_cmd_no_hosts_error(
    flow,
    scheduler,
    start,
    mock_glbl_cfg,
    log_filter,
):
    """It should catch NoHostsError.

    NoHostsError's should be caught and handled rather than raised because
    they will cause problems (i.e. trigger shutdown) if they make it to the
    Scheduler.

    NoHostError's can occur in the poll & kill logic, this test ensures that
    these methods catch the NoHostsError and handle the event as a regular
    SSH failure by pushing the issue down the 255 callback.

    See https://github.com/cylc/cylc-flow/pull/5195
    """
    # define a platform
    mock_glbl_cfg(
        'cylc.flow.platforms.glbl_cfg',
        '''
            [platforms]
                [[no-host-platform]]
        ''',
    )

    # define a workflow with a task which runs on that platform
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': 'foo'
            }
        },
        'runtime': {
            'foo': {
                'platform': 'no-host-platform'
            }
        }
    })

    # start the workflow
    schd = scheduler(id_)
    async with start(schd) as log:
        # set logging to debug level
        log.set_level(logging.DEBUG, CYLC_LOG)

        # tell Cylc the task is running on that platform
        schd.pool.get_tasks()[0].state_reset(TASK_STATUS_RUNNING)
        schd.pool.get_tasks()[0].platform = {
            'name': 'no-host-platform',
            'hosts': ['no-host-platform'],
        }

        # tell Cylc that that platform is not contactable
        # (i.e. all hosts are in bad_hosts)
        # (this casuses the NoHostsError to be raised)
        schd.task_job_mgr.bad_hosts.add('no-host-platform')

        # polling the task should not result in an error...
        schd.task_job_mgr.poll_task_jobs(
            schd.workflow,
            schd.pool.get_tasks()
        )

        # ...but the failure should be logged
        assert log_filter(
            log,
            contains='No available hosts for no-host-platform',
        )
        log.clear()

        # killing the task should not result in an error...
        schd.task_job_mgr.kill_task_jobs(
            schd.workflow,
            schd.pool.get_tasks()
        )

        # ...but the failure should be logged
        assert log_filter(
            log,
            contains='No available hosts for no-host-platform',
        )
