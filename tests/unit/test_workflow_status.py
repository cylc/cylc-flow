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

from cylc.flow.workflow_status import (
    StopMode,
    WorkflowStatus,
    WORKFLOW_STATUS_RUNNING_TO_HOLD,
    WORKFLOW_STATUS_RUNNING_TO_STOP,
    get_workflow_status,
)


def schd(
    final_point=None,
    hold_point=None,
    is_paused=False,
    is_stalled=None,
    stop_clock_time=None,
    stop_mode=None,
    stop_point=None,
    stop_task_id=None,
):
    return SimpleNamespace(
        is_paused=is_paused,
        is_stalled=is_stalled,
        stop_clock_time=stop_clock_time,
        stop_mode=stop_mode,
        pool=SimpleNamespace(
            hold_point=hold_point,
            stop_point=stop_point,
            stop_task_id=stop_task_id,
        ),
        config=SimpleNamespace(final_point=final_point),
    )


@pytest.mark.parametrize(
    'kwargs, state, message',
    [
        # test each of the states
        (
            {'is_paused': True},
            WorkflowStatus.PAUSED,
            'paused'),
        (
            {'stop_mode': StopMode.AUTO},
            WorkflowStatus.STOPPING,
            'stopping: waiting for active jobs to complete'
        ),
        (
            {'hold_point': 'point'},
            WorkflowStatus.RUNNING,
            WORKFLOW_STATUS_RUNNING_TO_HOLD % 'point'
        ),
        (
            {'stop_point': 'point'},
            WorkflowStatus.RUNNING,
            WORKFLOW_STATUS_RUNNING_TO_STOP % 'point'
        ),
        (
            {'stop_clock_time': 1234},
            WorkflowStatus.RUNNING,
            WORKFLOW_STATUS_RUNNING_TO_STOP % ''
        ),
        (
            {'stop_task_id': 'foo'},
            WorkflowStatus.RUNNING,
            WORKFLOW_STATUS_RUNNING_TO_STOP % 'foo'
        ),
        (
            {'final_point': 'point'},
            WorkflowStatus.RUNNING,
            WORKFLOW_STATUS_RUNNING_TO_STOP % 'point'
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
                'stop_mode': StopMode.AUTO,
                'is_stalled': True,
                'is_paused': True
            },
            WorkflowStatus.STOPPING,
            'stopping'
        ),
        (
            # stalled should trump paused & running
            {'is_stalled': True, 'is_paused': True},
            WorkflowStatus.RUNNING,
            'stalled'
        ),
    ]
)
def test_get_workflow_status(kwargs, state, message):
    state_, message_ = get_workflow_status(schd(**kwargs))
    assert state_ == state.value
    assert message in message_
