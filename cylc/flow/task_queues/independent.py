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

"""Implement independent limited task queues."""

from collections import deque
from contextlib import suppress
from typing import TYPE_CHECKING, List, Set, Dict, Counter, Any

from cylc.flow.task_queues import TaskQueueManagerBase

if TYPE_CHECKING:
    from cylc.flow.task_proxy import TaskProxy


class LimitedTaskQueue:
    """One task queue with group members and active limit."""

    def __init__(self, limit: int, members: Set[str]) -> None:
        """Initialize limiter for active tasks."""
        self.limit = limit  # max active tasks
        self.members = members  # member task names
        self.deque: deque = deque()

    def push_task(self, itask: 'TaskProxy') -> None:
        """Queue task if in my membership list."""
        if itask.tdef.name in self.members:
            self.deque.appendleft(itask)

    def push_task_if_limited(
        self, itask: 'TaskProxy', active: Counter[str]
    ) -> bool:
        """Queue task if in my membership and the queue limit is reached."""
        n_active: int = 0
        for mem in self.members:
            n_active += active[mem]
        if (
            self.limit and n_active >= self.limit
            and itask.tdef.name in self.members
        ):
            self.deque.appendleft(itask)
            return True
        return False

    def release(self, active: Counter[str]) -> List['TaskProxy']:
        """Release tasks if below the active limit."""
        # The "active" argument counts active tasks by name.
        released: List['TaskProxy'] = []
        held: List['TaskProxy'] = []
        n_active: int = 0
        for mem in self.members:
            n_active += active[mem]
        while not self.limit or n_active < self.limit:
            try:
                itask = self.deque.pop()
            except IndexError:
                # deque empty
                break
            if itask.state.is_held:
                held.append(itask)
            else:
                released.append(itask)
                n_active += 1
                active.update({itask.tdef.name: 1})
        for itask in held:
            self.deque.appendleft(itask)
        return released

    def remove(self, itask: 'TaskProxy') -> bool:
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

    def push_task(self, itask: 'TaskProxy') -> None:
        """Push a task to the appropriate queue."""
        for queue in self.queues.values():
            queue.push_task(itask)

    def push_task_if_limited(
        self, itask: 'TaskProxy', active: Counter[str]
    ) -> bool:
        """Push a task to its queue only if the queue limit is reached."""
        return any(
            queue.push_task_if_limited(itask, active)
            for queue in self.queues.values()
        )

    def release_tasks(self, active: Counter[str]) -> List['TaskProxy']:
        """Release tasks up to the queue limits."""
        released: List['TaskProxy'] = []
        for queue in self.queues.values():
            released += queue.release(active)
        return released

    def remove_task(self, itask: 'TaskProxy') -> bool:
        """Try to remove a task from the queues. Return True if done."""
        return any(queue.remove(itask) for queue in self.queues.values())

    def force_release_task(self, itask: 'TaskProxy') -> bool:
        """Remove a task from whichever queue it belongs to.

        Return True if released, else False.
        """
        return self.remove_task(itask)

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
                with suppress(KeyError):
                    # may already have been removed
                    queues[self.Q_DEFAULT]["members"].remove(qmem)
                if qmem in seen:
                    # Override previous queue assignment.
                    oldq = seen[qmem]
                    queues[oldq]["members"].remove(qmem)
                else:
                    queues[qname]["members"].add(qmem)
                seen[qmem] = qname
        return queues
