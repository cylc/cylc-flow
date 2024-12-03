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

from typing import (
    Any as Fixture,
    Callable
)

import logging

async def test_trigger_workflow_paused(
    flow: 'Fixture',
    scheduler: 'Fixture',
    start: 'Fixture',
    capture_submission: 'Fixture',
    log_filter: Callable
):
    """
    Test manual triggering when the workflow is paused.

    The usual queue limiting behaviour is expected.

    https://github.com/cylc/cylc-flow/issues/6192

    """
    id_ = flow({
        'scheduling': {
            'queues': {
                'default': {
                    'limit': 1,
                },
            },
            'graph': {
                'R1': '''
                    a => x & y & z
                ''',
            },
        },
    })
    schd = scheduler(id_, paused_start=True)

    # start the scheduler (but don't set the main loop running)
    async with start(schd) as log:

        # capture task submissions (prevents real submissions)
        submitted_tasks = capture_submission(schd)

        # paused at start-up so no tasks should be submitted
        assert len(submitted_tasks) == 0

        # manually trigger 1/x - it should be submitted
        schd.pool.force_trigger_tasks(['1/x'], [1])
        schd.release_tasks_to_run()
        assert len(submitted_tasks) == 1

        # manually trigger 1/y - it should not be queued but not submitted
        # (queue limit reached)
        schd.pool.force_trigger_tasks(['1/y'], [1])
        schd.release_tasks_to_run()
        assert len(submitted_tasks) == 1

        # manually trigger 1/y again - it should be submitted
        # (triggering a queued task runs it)
        schd.pool.force_trigger_tasks(['1/y'], [1])
        schd.release_tasks_to_run()
        assert len(submitted_tasks) == 2

        # manually trigger 1/y yet again - the trigger should be ignored
        # (task already active)
        schd.pool.force_trigger_tasks(['1/y'], [1])
        schd.release_tasks_to_run()
        assert len(submitted_tasks) == 2
        assert log_filter(
            level=logging.ERROR,
            contains="ignoring trigger - already active"
        )
