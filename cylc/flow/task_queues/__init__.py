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

"""Define the Cylc task queue management API."""

from typing import List, Dict, Counter, Any, TYPE_CHECKING
from abc import ABCMeta, abstractmethod

if TYPE_CHECKING:
    from cylc.flow.task_proxy import TaskProxy


class TaskQueueManagerBase(metaclass=ABCMeta):
    """Base class for queueing implementations."""

    @abstractmethod
    def __init__(self,
                 qconfig: dict,
                 all_task_names: List[str],
                 descendants: dict
                 ) -> None:
        """Initialize task queue manager from workflow config.

        Arguments:
           * qconfig: flow.cylc queues config
           * all_task_names: list of all task names
           * descendants: runtime family dict

        """
        raise NotImplementedError

    @abstractmethod
    def push_task(self, itask: 'TaskProxy') -> None:
        """Queue the given task."""
        raise NotImplementedError

    @abstractmethod
    def push_task_if_limited(
            self, itask: 'TaskProxy', active: Counter[str]
    ) -> bool:
        """Queue the task only if the queue limit is reached.

        Requires current active task counts.
        Return True if queued, else False.
        """
        raise NotImplementedError

    @abstractmethod
    def release_tasks(self, active: Counter[str]) -> 'List[TaskProxy]':
        """Release tasks, given current active task counts."""
        raise NotImplementedError

    @abstractmethod
    def remove_task(self, itask: 'TaskProxy') -> bool:
        """Try to remove a task from the queues. Return True if done."""
        raise NotImplementedError

    @abstractmethod
    def adopt_tasks(self, orphans: List[str]) -> None:
        """Adopt tasks with defs removed by scheduler reload or restart."""
        raise NotImplementedError

    def _expand_families(self,
                         qconfig: dict,
                         all_task_names: List[str],
                         descendants: dict
                         ) -> dict:
        """Expand family names in queue membership lists.

        (All queueing implementations will presumably need this).
        Returns dict of queues config with only task names present.

        """
        queues: Dict[str, Any] = {}
        for qname, queue in qconfig.items():
            qmembers = set()
            for mem in queue["members"]:
                if mem in descendants:
                    # Family name.
                    for fmem in descendants[mem]:
                        if (fmem not in descendants
                                and fmem in all_task_names):
                            # Task name.
                            qmembers.add(fmem)
                elif mem in all_task_names:
                    # Task name.
                    qmembers.add(mem)
            queues[qname] = {}
            queues[qname]["members"] = qmembers
            queues[qname]["limit"] = queue["limit"]
        return queues
