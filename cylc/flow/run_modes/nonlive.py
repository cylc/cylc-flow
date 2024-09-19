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
"""Utilities supporting all nonlive modes
"""
from typing import TYPE_CHECKING, Dict, List

from cylc.flow import LOG
from cylc.flow.run_modes.skip import check_task_skip_config
from cylc.flow.run_modes import RunMode

if TYPE_CHECKING:
    from cylc.flow.taskdef import TaskDef


def run_mode_validate_checks(taskdefs: 'Dict[str, TaskDef]') -> None:
    """Warn user if any tasks have "run mode" set to skip.
    """
    warn_nonlive: Dict[str, List[str]] = {
        RunMode.SKIP.value: [],
    }

    # Run through taskdefs looking for those with nonlive modes
    for taskdef in taskdefs.values():
        # Add to list of tasks to be run in non-live modes:
        if (
            taskdef.rtconfig.get('run mode', None)
            in {
                RunMode.SIMULATION.value,
                RunMode.SKIP.value,
                RunMode.DUMMY.value
            }
        ):
            warn_nonlive[taskdef.rtconfig['run mode']].append(taskdef.name)

        # Run any mode specific validation checks:
        check_task_skip_config(taskdef)

    if any(warn_nonlive.values()):
        message = 'The following tasks are set to run in skip mode:'
        for taskname in warn_nonlive[RunMode.SKIP.value]:
            message += f'\n    * {taskname}'
        LOG.warning(message)
