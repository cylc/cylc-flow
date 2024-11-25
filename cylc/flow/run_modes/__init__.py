# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.

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

from enum import Enum
from typing import TYPE_CHECKING, Callable, Optional, Tuple

if TYPE_CHECKING:
    from optparse import Values
    from cylc.flow.task_job_mgr import TaskJobManager
    from cylc.flow.task_proxy import TaskProxy

    # The interface for submitting jobs
    SubmissionInterface = Callable[
        [  # Args:
            # the task job manager instance
            'TaskJobManager',
            # the task to submit
            'TaskProxy',
            # the task's runtime config (with broadcasts applied)
            dict,
            # the workflow ID
            str,
            # the current time as (float_unix_time, str_ISO8601)
            Tuple[float, str]
        ],
        # Return False if the job requires live-mode submission
        # (dummy mode does this), else return True.
        bool
    ]


class RunMode(Enum):
    """The possible run modes of a task/workflow."""

    LIVE = 'live'
    """Tasks will run normally."""

    SIMULATION = 'simulation'
    """Simulates job submission with configurable exection time
    and succeeded/failed outcomes (but does not submit real jobs)."""

    DUMMY = 'dummy'
    """Submits real jobs with empty scripts."""

    SKIP = 'skip'
    """Skips job submission; sets required outputs (by default) or
    configured outputs."""

    def describe(self):
        """Return user friendly description of run mode.

        For use by configuration spec documenter.
        """
        if self == self.LIVE:
            return "Task will run normally."
        elif self == self.SKIP:
            return (
                "Skips job submission; sets required outputs"
                " (by default) or configured outputs.")
        elif self == self.DUMMY:
            return "Submits real jobs with empty scripts."
        else:   # self == self.SIMULATION:
            return (
                "Simulates job submission with configurable"
                " exection time and succeeded/failed outcomes"
                " (but does not submit real jobs).")

    @staticmethod
    def get(options: 'Values') -> "RunMode":
        """Return the workflow run mode from the options."""
        run_mode = getattr(options, 'run_mode', None)
        if run_mode:
            return RunMode(run_mode)
        return RunMode.LIVE

    def get_submit_method(self) -> 'Optional[SubmissionInterface]':
        """Return the job submission method for this run mode.

        This returns None for live-mode jobs as these use a
        different code pathway for job submission.
        """
        if self == RunMode.DUMMY:
            from cylc.flow.run_modes.dummy import (
                submit_task_job as dummy_submit_task_job)
            return dummy_submit_task_job
        elif self == RunMode.SIMULATION:
            from cylc.flow.run_modes.simulation import (
                submit_task_job as simulation_submit_task_job)
            return simulation_submit_task_job
        elif self == RunMode.SKIP:
            from cylc.flow.run_modes.skip import (
                submit_task_job as skip_submit_task_job)
            return skip_submit_task_job
        return None


def disable_task_event_handlers(itask: 'TaskProxy'):
    """Should we disable event handlers for this task?

    No event handlers in simulation mode, or in skip mode
    if we don't deliberately enable them:
    """
    mode = itask.run_mode
    return (
        mode == RunMode.SIMULATION
        or (
            mode == RunMode.SKIP
            and itask.platform.get(
                'disable task event handlers', False)
        )
    )


# Modes available for running a whole workflow:
WORKFLOW_RUN_MODES = frozenset(i.value for i in {
    RunMode.LIVE, RunMode.DUMMY, RunMode.SIMULATION})

# Modes which can be set in task config:
TASK_CONFIG_RUN_MODES = frozenset(
    i.value for i in (RunMode.LIVE, RunMode.SKIP))
# And those only available to the workflow:
WORKFLOW_ONLY_MODES = frozenset(
    i.value for i in RunMode) - TASK_CONFIG_RUN_MODES

# Modes which completely ignore the standard submission path:
JOBLESS_MODES = frozenset(i.value for i in {
    RunMode.SKIP, RunMode.SIMULATION})
