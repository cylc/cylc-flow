# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
"""Suite status constants."""

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
SUITE_STATUS_RUNNING_TO_STOP = "running to stop at %s"
SUITE_STATUS_RUNNING_TO_HOLD = "running to hold at %s"

# TODO - the suite status should be a property of the Scheduler instance
#        rather than derived from scheduler state?


class SuiteStatus(Enum):
    """The possible statuses of a suite."""

    HELD = "held"
    """Suite will not submit any new jobs."""

    RUNNING = "running"
    """Suite is running as normal."""

    STOPPING = "stopping"
    """Suite is in the process of shutting down."""

    STOPPED = "stopped"
    """Suite is not running."""


class StopMode(Enum):
    """The possible modes of a suite shutdown"""

    AUTO = 'AUTOMATIC'
    """Suite has reached a state where it can automatically stop"""

    AUTO_ON_TASK_FAILURE = 'AUTOMATIC(ON-TASK-FAILURE)'
    """A task has failed and ``abort if any task fails = True``."""

    REQUEST_CLEAN = 'REQUEST(CLEAN)'
    """External shutdown request, will wait for active jobs to complete."""

    REQUEST_NOW = 'REQUEST(NOW)'
    """External shutdown request, will wait for event handlers to complete."""

    REQUEST_NOW_NOW = 'REQUEST(NOW-NOW)'
    """External immediate shutdown request."""

    def describe(self):
        """Return a user-friendly description of this state."""
        if self == self.AUTO:
            return 'Wait until suite has completed.'
        if self == self.AUTO_ON_TASK_FAILURE:
            return 'Wait until the first task fails.'
        if self == self.REQUEST_CLEAN:
            return (
                'Regular shutdown:\n'
                '* Wait for all active jobs to complete.\n'
                '* Run suite event handlers and wait for them to complete.'
            )
        if self == self.REQUEST_NOW:
            return (
                'Immediate shutdown\n'
                "* Don't kill submitted or running jobs.\n"
                '* Run suite event handlers and wait for them to complete.'
            )
        if self == self.REQUEST_NOW_NOW:
            return (
                'Immediate shutdown\n'
                "* Don't kill submitted or running jobs.\n"
                "* Don't run event handlers."
            )
        return ''


class AutoRestartMode(Enum):
    """The possible modes of a suite auto-restart."""

    RESTART_NORMAL = 'stop and restart'
    """Suite will stop immeduately and attempt to restart."""

    FORCE_STOP = 'stop'
    """Suite will stop immeduately but *not* attempt to restart."""


def get_suite_status(schd):
    """Return the status of the provided suite.

    Args:
        schd (cylc.flow.Scheduler): The running suite

    Returns:
        tuple - (state, state_msg)

        state (cylc.flow.suite_status.SuiteStatus):
            The SuiteState.
        state_msg (str):
            Text describing the current state (may be an empty string).

    """
    status = SuiteStatus.RUNNING
    status_msg = ''

    if schd.pool.is_held:
        status = SuiteStatus.HELD
    elif schd.stop_mode is not None:
        status = SuiteStatus.STOPPING
        status_msg = f'Stopping: {schd.stop_mode.describe()}'
    elif schd.pool.hold_point:
        status_msg = (
            SUITE_STATUS_RUNNING_TO_HOLD %
            schd.pool.hold_point)
    elif schd.pool.stop_point:
        status_msg = (
            SUITE_STATUS_RUNNING_TO_STOP %
            schd.pool.stop_point)
    elif schd.stop_clock_time is not None:
        status_msg = (
            SUITE_STATUS_RUNNING_TO_STOP %
            time2str(schd.stop_clock_time))
    elif schd.pool.stop_task_id:
        status_msg = (
            SUITE_STATUS_RUNNING_TO_STOP %
            schd.pool.stop_task_id)
    elif schd.config.final_point:
        status_msg = (
            SUITE_STATUS_RUNNING_TO_STOP %
            schd.config.final_point)

    return (status.value, status_msg)
