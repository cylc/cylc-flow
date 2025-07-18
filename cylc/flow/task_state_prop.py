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
"""Task state properties for display."""

from cylc.flow.task_state import (
    TASK_STATUS_WAITING,
    TASK_STATUS_PREPARING,
    TASK_STATUS_EXPIRED,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_FAILED,
    TASK_STATUS_UNKNOWN,
)


def extract_group_state(child_states, is_stopped=False):
    """Summarise child states as a group."""
    ordered_states = [
        TASK_STATUS_SUBMIT_FAILED,
        TASK_STATUS_FAILED,
        TASK_STATUS_EXPIRED,
        TASK_STATUS_RUNNING,
        TASK_STATUS_SUBMITTED,
        TASK_STATUS_PREPARING,
        TASK_STATUS_WAITING,
        TASK_STATUS_SUCCEEDED,
        TASK_STATUS_UNKNOWN
    ]
    if is_stopped:
        ordered_states = [
            TASK_STATUS_SUBMIT_FAILED,
            TASK_STATUS_FAILED,
            TASK_STATUS_RUNNING,
            TASK_STATUS_SUBMITTED,
            TASK_STATUS_EXPIRED,
            TASK_STATUS_PREPARING,
            TASK_STATUS_SUCCEEDED,
            TASK_STATUS_WAITING,
            TASK_STATUS_UNKNOWN
        ]
    for state in ordered_states:
        if state in child_states:
            return state
    return None
