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

from types import SimpleNamespace

import pytest
from metomi.isodatetime.data import TimePoint

from cylc.flow.cycling.integer import IntegerPoint
from cylc.flow.workflow_status import (
    WORKFLOW_STATUS_RUNNING_TO_HOLD,
    WORKFLOW_STATUS_RUNNING_TO_STOP,
    StopMode,
    WorkflowStatus,
    get_workflow_status,
    get_workflow_status_msg,
)

STOP_TIME = TimePoint(year=2006).to_local_time_zone()


def schd(
    final_point=None,
    hold_point=None,
    is_paused=False,
    is_stalled=None,
    stop_clock_time=None,
    stop_mode=None,
    stop_point=None,
    stop_task_id=None,
    reload_pending=False,
):
    return SimpleNamespace(
        is_paused=is_paused,
        is_stalled=is_stalled,
        stop_clock_time=stop_clock_time,
        stop_mode=stop_mode,
        reload_pending=reload_pending,
        pool=SimpleNamespace(
            hold_point=hold_point,
            stop_point=stop_point,
            stop_task_id=stop_task_id,
        ),
        config=SimpleNamespace(final_point=final_point),
        options=SimpleNamespace(utc_mode=True),
    )


@pytest.mark.parametrize(
    'kwargs, state, message',
    [
        # test each of the states
        (
            {'is_paused': True},
            WorkflowStatus.PAUSED,
            'paused'
        ),
        (
            {'reload_pending': 'message'},
            WorkflowStatus.PAUSED,
            'reloading: message'
        ),
        (
            {'stop_mode': StopMode.AUTO},
            WorkflowStatus.STOPPING,
            'stopping: waiting for active jobs to complete'
        ),
        (
            {'hold_point': 2},
            WorkflowStatus.RUNNING,
            WORKFLOW_STATUS_RUNNING_TO_HOLD % 2
        ),
        (
            {'stop_point': 4},
            WorkflowStatus.RUNNING,
            WORKFLOW_STATUS_RUNNING_TO_STOP % 4
        ),
        (
            {'stop_clock_time': int(STOP_TIME.seconds_since_unix_epoch)},
            WorkflowStatus.RUNNING,
            WORKFLOW_STATUS_RUNNING_TO_STOP % str(STOP_TIME)
        ),
        (
            {'stop_task_id': '6/foo'},
            WorkflowStatus.RUNNING,
            WORKFLOW_STATUS_RUNNING_TO_STOP % '6/foo'
        ),
        (
            {'final_point': 8},
            WorkflowStatus.RUNNING,
            WORKFLOW_STATUS_RUNNING_TO_STOP % 8
        ),
        (
            {'is_stalled': True},
            WorkflowStatus.RUNNING,
            'stalled'
        ),
        (
            {},
            WorkflowStatus.RUNNING,
            'running'
        ),

        # test combinations
        (
            # stopping should trump stalled, paused & running
            {
                'stop_mode': StopMode.REQUEST_NOW,
                'is_stalled': True,
                'is_paused': True
            },
            WorkflowStatus.STOPPING,
            'stopping: shutting down'
        ),
        (
            {'is_stalled': True, 'is_paused': True},
            WorkflowStatus.PAUSED,
            'stalled and paused',
        ),
        (
            # earliest of stop point, hold point and stop task id
            {
                'stop_point': IntegerPoint(4),
                'hold_point': IntegerPoint(2),
                'stop_task_id': '6/foo',
            },
            WorkflowStatus.RUNNING,
            WORKFLOW_STATUS_RUNNING_TO_HOLD % 2,
        ),
        (
            {
                'stop_point': IntegerPoint(11),
                'hold_point': IntegerPoint(15),
                'stop_task_id': '9/bar',
            },
            WorkflowStatus.RUNNING,
            WORKFLOW_STATUS_RUNNING_TO_STOP % '9/bar',
        ),
        (
            {
                'stop_point': IntegerPoint(3),
                'hold_point': IntegerPoint(3),
            },
            WorkflowStatus.RUNNING,
            WORKFLOW_STATUS_RUNNING_TO_STOP % 3,
        ),
        (
            # stop point trumps final point
            {
                'stop_point': IntegerPoint(1),
                'final_point': IntegerPoint(2),
            },
            WorkflowStatus.RUNNING,
            WORKFLOW_STATUS_RUNNING_TO_STOP % 1,
        ),
    ]
)
def test_get_workflow_status(kwargs, state, message, set_cycling_type):
    set_cycling_type()
    scheduler = schd(**kwargs)
    assert get_workflow_status(scheduler) == state
    assert get_workflow_status_msg(scheduler) == message
