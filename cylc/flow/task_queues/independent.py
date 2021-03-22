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

"""Implement independent limited task queues."""

from typing import List, Set, Dict, Counter, Any
from collections import deque

from cylc.flow.task_proxy import TaskProxy
from cylc.flow.task_queues import TaskQueueManagerBase


class LimitedTaskQueue:
    """One task queue with group members and active limit."""

    def __init__(self, limit: int, members: Set[str]) -> None:
        """Initialize limiter for active tasks."""
        self.limit = limit  # max active tasks
        self.members = members  # member task names
        self.deque: deque = deque()

    def push_tasks(self, itasks: List[TaskProxy]) -> None:
        """Queue tasks in my membership list, reject others."""
        for itask in itasks:
            if itask.tdef.name in self.members:
                self.deque.appendleft(itask)

    def release(self, active: Counter[str]) -> List[TaskProxy]:
        """Release tasks if below the active limit."""
        # The "active" argument counts active tasks by name.
        released: List[TaskProxy] = []
        n_active: int = 0
        for mem in self.members:
            n_active += active[mem]
        while not self.limit or n_active < self.limit:
            try:
                itask = self.deque.pop()
            except IndexError:
                # deque empty
                break
            released.append(itask)
            n_active += 1
            active.update({itask.tdef.name: 1})
        return released

    def remove(self, itask: TaskProxy) -> bool:
        """Remove a single task from queue, return True if removed."""
        try:
            self.deque.remove(itask)
        except ValueError:
            # not a member
            return False
        return True

    def adopt(self, orphans: List[str]) -> None:
        """Add orphan task names to my membership list."""
        self.members.update(orphans)


class IndepQueueManager(TaskQueueManagerBase):
    """Implement independent limited task queues.

    A task can only belong to one queue. Queues release tasks if the number of
    active tasks in its membership list is below its limit, until the limit is
    reached or the queue is empty.

    A limit of zero means unlimited.

    """
    Q_DEFAULT = "default"

    def __init__(self,
                 qconfig: dict,
                 all_task_names: List[str],
                 descendants: dict
                 ) -> None:

        # Map of queues by name.
        self.queues: Dict[str, LimitedTaskQueue] = {}

        # Add all task names to default queue membership list.
        qconfig[self.Q_DEFAULT]['members'] = set(all_task_names)

        # Expand family names in membership lists.
        queues: Dict[str, Any] = self._expand_families(
            qconfig, all_task_names, descendants)

        # Make the queues independent.
        queues = self._make_indep(queues)
        for name, config in queues.items():
            self.queues[name] = LimitedTaskQueue(
                config["limit"], config["members"]
            )

    def push_tasks(self, itasks: List[TaskProxy]) -> None:
        """Queue each task to the appropriate queue."""
        for _, queue in self.queues.items():
            queue.push_tasks(itasks)

    def release_tasks(self, active: Counter[str]) -> List[TaskProxy]:
        """Release tasks up to the queue limits."""
        released: List[TaskProxy] = []
        for _, queue in self.queues.items():
            released += queue.release(active)
        return released

    def remove_task(self, itask: TaskProxy) -> None:
        """Remove a task from whichever queue it belongs to."""
        for _, queue in self.queues.items():
            if queue.remove(itask):
                break

    def adopt_tasks(self, orphans: List[str]) -> None:
        """Adopt orphaned tasks to the default group."""
        self.queues[self.Q_DEFAULT].adopt(orphans)

    def _make_indep(self, in_queues: dict) -> dict:
        """Make queues independent: each task can belong to one queue only.

        If a task is assigned to multiple queues the last assignment takes
        precedence. The "default" queue contains tasks not in another queue.

        """
        queues: Dict[str, Any] = {}
        seen: Dict[str, str] = {}
        for qname, qconfig in in_queues.items():
            queues[qname] = {}
            queues[qname]["members"] = qconfig["members"]
            queues[qname]["limit"] = qconfig["limit"]
            if qname == self.Q_DEFAULT:
                continue
            for qmem in qconfig["members"]:
                # Remove from default queue
                try:
                    queues[self.Q_DEFAULT]["members"].remove(qmem)
                except KeyError:
                    # Already removed.
                    pass
                if qmem in seen:
                    # Override previous queue assignment.
                    oldq = seen[qmem]
                    queues[oldq]["members"].remove(qmem)
                else:
                    queues[qname]["members"].add(qmem)
                seen[qmem] = qname
        return queues

    def dump(self):
        for name, q in self.queues.items():
            print("QUEUE", name)
            for i in q.deque:
                print(' - ', i, i.state.is_queued)
