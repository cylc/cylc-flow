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

from typing import TYPE_CHECKING

import pytest

from cylc.flow import commands

if TYPE_CHECKING:
    from cylc.flow.scheduler import Scheduler


@pytest.fixture
def param_workflow(flow, scheduler):
    def _schd(paused_start, queue_limit):
        id_ = flow({
            'scheduler': {
                'allow implicit tasks': True,
            },
            'task parameters': {
                'x': '1..10',
            },
            'scheduling': {
                'queues': {
                    'default': {
                        'limit': queue_limit,
                    },
                },
                'graph': {
                    'R1': '''
                        <x>
                    ''',
                },
            },
        })
        return scheduler(id_, paused_start=paused_start)
    return _schd


@pytest.mark.parametrize(
    'start_paused,queue_limit',
    [
        (False, 1),
        (False, 5),
        (True, 1),
        (True, 5),
    ]
)
async def test_queue_release(
    param_workflow,
    start,
    capture_submission,
    start_paused,
    queue_limit,
):
    """Tasks should be released up to the limit if the scheduler is not paused.

    When the scheudler is paused the scheduler should not release tasks from
    queues because tasks may subsequently be held by the user and we don't
    want them clogging up the queue limit.

    https://github.com/cylc/cylc-flow/issues/4627
    """
    expected_submissions = queue_limit if not start_paused else 0

    # start the scheduler (but don't set the main loop running)
    schd = param_workflow(start_paused, queue_limit)
    async with start(schd):
        # capture task submissions (prevents real submissions)
        submitted_tasks = capture_submission(schd)

        # release runahead/queued tasks
        # (if scheduler is paused we should not have any submissions)
        # (otherwise a number of tasks up to the limit should be released)
        schd.pool.release_runahead_tasks()
        schd.release_queued_tasks()
        assert len(submitted_tasks) == expected_submissions

        for _ in range(3):
            # release runahead/queued tasks
            # (no further tasks should be released)
            schd.release_queued_tasks()
            assert len(submitted_tasks) == expected_submissions


async def test_queue_held_tasks(
    param_workflow,
    start,
    capture_submission
):
    """Held tasks should not be released from queues.

    Users can hold tasks whilst they are queued. These held tasks should not
    be released from their queues.

    https://github.com/cylc/cylc-flow/issues/4628
    """
    schd: Scheduler = param_workflow(paused_start=True, queue_limit=1)

    async with start(schd):
        # capture task submissions (prevents real submissions)
        submitted_tasks = capture_submission(schd)

        # release runahead tasks to their queues
        schd.pool.release_runahead_tasks()

        # hold all tasks and resume the workflow
        # (nothing should have run yet because the workflow started paused)
        await commands.run_cmd(commands.hold, schd, ['*/*'])
        schd.resume_workflow()

        # release queued tasks
        # (no tasks should be released from the queues because they are held)
        schd.release_queued_tasks()
        assert len(submitted_tasks) == 0

        # un-hold tasks
        await commands.run_cmd(commands.release, schd, ['*/*'])

        # release queued tasks
        # (tasks should now be released from the queues)
        schd.release_queued_tasks()
        assert len(submitted_tasks) == 1
