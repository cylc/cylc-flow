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
from typing import Tuple, TYPE_CHECKING

from cylc.flow.wallclock import get_time_string_from_unix_time as time2str

if TYPE_CHECKING:
    from cylc.flow.scheduler import Scheduler

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

    def explain(self) -> str:
        """Return an explanation of what a workflow in this state is doing.

        This is used in the workflow status message if the workflow is stopping
        to clarify what the scheduler is doing.
        """
        if self in (self.AUTO, self.REQUEST_CLEAN):  # type: ignore
            return 'waiting for active jobs to complete'
        if self == self.REQUEST_KILL:  # type: ignore
            return 'killing active jobs'
        if self in (  # type: ignore
            self.AUTO_ON_TASK_FAILURE,  # type: ignore
            self.REQUEST_NOW,
            self.REQUEST_NOW_NOW,
        ):
            return 'shutting down'
        return ''

    def describe(self) -> str:
        """Return a user-friendly description of this state.

        This is used in the schema to convey what the different stop modes do.
        """
        if self == self.AUTO:  # type: ignore
            return 'Wait until workflow has completed.'
        if self == self.AUTO_ON_TASK_FAILURE:  # type: ignore
            return 'Wait until the first task fails.'
        if self == self.REQUEST_CLEAN:  # type: ignore
            return (
                'Regular shutdown:\n'
                '* Wait for all active jobs to complete.\n'
                '* Run workflow event handlers and wait for them to complete.'
            )
        if self == self.REQUEST_KILL:  # type: ignore
            return (
                'Kill shutdown:\n'
                '* Wait for all active jobs to be killed.\n'
                '* Run workflow event handlers and wait for them to complete.'
            )
        if self == self.REQUEST_NOW:  # type: ignore
            return (
                'Immediate shutdown\n'
                "* Don't kill submitted or running jobs.\n"
                '* Run workflow event handlers and wait for them to complete.'
            )
        if self == self.REQUEST_NOW_NOW:  # type: ignore
            return (
                'Immediate shutdown\n'
                "* Don't kill submitted or running jobs.\n"
                "* Don't run event handlers."
            )
        raise KeyError(f'No description for {self}.')


class AutoRestartMode(Enum):
    """The possible modes of a workflow auto-restart."""

    RESTART_NORMAL = 'stop and restart'
    """Workflow will stop immediately and attempt to restart."""

    FORCE_STOP = 'stop'
    """Workflow will stop immediately but *not* attempt to restart."""


def get_workflow_status(schd: 'Scheduler') -> Tuple[str, str]:
    """Return the status of the provided workflow.

    This should be a short, concise description of the workflow state.

    Args:
        schd: The running workflow

    Returns:
        tuple - (state, state_msg)

        state:
            The WorkflowState.
        state_msg:
            Text describing the current state (may be an empty string).

    """
    status = WorkflowStatus.RUNNING
    status_msg = ''

    if schd.stop_mode is not None:
        status = WorkflowStatus.STOPPING
        status_msg = f'stopping: {schd.stop_mode.explain()}'
    elif schd.reload_pending:
        status = WorkflowStatus.PAUSED
        status_msg = f'reloading: {schd.reload_pending}'
    elif schd.is_stalled:
        status_msg = 'stalled'
    elif schd.is_paused:
        status = WorkflowStatus.PAUSED
        status_msg = 'paused'
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
    elif schd.config and schd.config.final_point:
        status_msg = (
            WORKFLOW_STATUS_RUNNING_TO_STOP %
            schd.config.final_point)
    else:
        # fallback - running indefinitely
        status_msg = 'running'

    return (status.value, status_msg)
