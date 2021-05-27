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
"""Workflow status constants."""

from enum import Enum

from cylc.flow.wallclock import get_time_string_from_unix_time as time2str

# Keys for identify API call
KEY_GROUP = "group"
KEY_META = "meta"
KEY_NAME = "name"
KEY_OWNER = "owner"
KEY_STATES = "states"
KEY_TASKS_BY_STATE = "tasks-by-state"
KEY_UPDATE_TIME = "update-time"
KEY_VERSION = "version"

# Status message strings
WORKFLOW_STATUS_RUNNING_TO_STOP = "running to stop at %s"
WORKFLOW_STATUS_RUNNING_TO_HOLD = "running to hold at %s"

# TODO - the workflow status should be a property of the Scheduler instance
#        rather than derived from scheduler state?


class WorkflowStatus(Enum):
    """The possible statuses of a workflow."""

    INSTALLED = "installed"
    """Workflow is installed."""

    PAUSED = "paused"
    """Workflow will not submit any new jobs."""

    RUNNING = "running"
    """Workflow is running as normal."""

    STOPPING = "stopping"
    """Workflow is in the process of shutting down."""

    STOPPED = "stopped"
    """Workflow is not running."""


class StopMode(Enum):
    """The possible modes of a workflow shutdown"""

    AUTO = 'AUTOMATIC'
    """Workflow has reached a state where it can automatically stop"""

    AUTO_ON_TASK_FAILURE = 'AUTOMATIC(ON-TASK-FAILURE)'
    """A task has failed and ``--abort-if-any-task-fails`` was used."""

    REQUEST_CLEAN = 'REQUEST(CLEAN)'
    """External shutdown request, will wait for active jobs to complete."""

    REQUEST_KILL = 'REQUEST(KILL)'
    """External shutdown request, will wait for active jobs to be killed."""

    REQUEST_NOW = 'REQUEST(NOW)'
    """External shutdown request, will wait for event handlers to complete."""

    REQUEST_NOW_NOW = 'REQUEST(NOW-NOW)'
    """External immediate shutdown request."""

    def describe(self):
        """Return a user-friendly description of this state."""
        if self == self.AUTO:
            return 'Wait until workflow has completed.'
        if self == self.AUTO_ON_TASK_FAILURE:
            return 'Wait until the first task fails.'
        if self == self.REQUEST_CLEAN:
            return (
                'Regular shutdown:\n'
                '* Wait for all active jobs to complete.\n'
                '* Run workflow event handlers and wait for them to complete.'
            )
        if self == self.REQUEST_KILL:
            return (
                'Kill shutdown:\n'
                '* Wait for all active jobs to be killed.\n'
                '* Run workflow event handlers and wait for them to complete.'
            )
        if self == self.REQUEST_NOW:
            return (
                'Immediate shutdown\n'
                "* Don't kill submitted or running jobs.\n"
                '* Run workflow event handlers and wait for them to complete.'
            )
        if self == self.REQUEST_NOW_NOW:
            return (
                'Immediate shutdown\n'
                "* Don't kill submitted or running jobs.\n"
                "* Don't run event handlers."
            )
        return ''


class AutoRestartMode(Enum):
    """The possible modes of a workflow auto-restart."""

    RESTART_NORMAL = 'stop and restart'
    """Workflow will stop immediately and attempt to restart."""

    FORCE_STOP = 'stop'
    """Workflow will stop immediately but *not* attempt to restart."""


def get_workflow_status(schd):
    """Return the status of the provided workflow.

    Args:
        schd (cylc.flow.Scheduler): The running workflow

    Returns:
        tuple - (state, state_msg)

        state (cylc.flow.workflow_status.WorkflowStatus):
            The WorkflowState.
        state_msg (str):
            Text describing the current state (may be an empty string).

    """
    status = WorkflowStatus.RUNNING
    status_msg = ''

    if schd.is_paused:
        status = WorkflowStatus.PAUSED
    elif schd.stop_mode is not None:
        status = WorkflowStatus.STOPPING
        status_msg = f'Stopping: {schd.stop_mode.describe()}'
    elif schd.pool.hold_point:
        status_msg = (
            WORKFLOW_STATUS_RUNNING_TO_HOLD %
            schd.pool.hold_point)
    elif schd.pool.stop_point:
        status_msg = (
            WORKFLOW_STATUS_RUNNING_TO_STOP %
            schd.pool.stop_point)
    elif schd.stop_clock_time is not None:
        status_msg = (
            WORKFLOW_STATUS_RUNNING_TO_STOP %
            time2str(schd.stop_clock_time))
    elif schd.pool.stop_task_id:
        status_msg = (
            WORKFLOW_STATUS_RUNNING_TO_STOP %
            schd.pool.stop_task_id)
    elif schd.config.final_point:
        status_msg = (
            WORKFLOW_STATUS_RUNNING_TO_STOP %
            schd.config.final_point)

    return (status.value, status_msg)
