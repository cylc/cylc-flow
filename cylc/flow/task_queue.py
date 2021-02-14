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

"""Cylc task queue."""

from typing import List, Set, Dict, Counter, Any

from cylc.flow.task_proxy import TaskProxy


class Limiter:
    """Limit group logic: group members and active task limit."""
    def __init__(self, limit: int, members: Set[str]) -> None:
        """Initialize limiter for active tasks."""
        self.limit = limit  # max active tasks
        self.members = members  # member task names

    def is_limited(self, itask: TaskProxy, active: Counter[str]) -> bool:
        """Return True if itask is limited, else False.

        The "active" arg counts active tasks by name.
        """
        if itask.tdef.name not in self.members or not self.limit:
            return False
        n_active: int = 0
        for mem in self.members:
            n_active += active[mem]
        return n_active >= self.limit

    def adopt(self, orphans: List[str]) -> None:
        """Add orphan task names to members."""
        self.members.update(orphans)


class TaskQueue:
    """Cylc task queue with multiple limit groups.

    A single queue that is FIFO for not-limited tasks; others remain in place.

    1. "classic" queue (as for Cylc 7 and earlier):
     No overlap between limit groups; "default" retains only un-assigned tasks.

    2. "overlapping" queue:
     Tasks can appear in multiple limit groups; "default" is a global limit.

    """
    Q_DEFAULT = "default"

    def __init__(self,
                 qconfig: dict,
                 all_task_names: List[str],
                 descendants: dict) -> None:
        """Configure the task queue."""
        self.queue_type = qconfig["type"]
        self.queue: List[TaskProxy] = []
        self.limiters: Dict[str, Limiter] = {}

        # Expand family names.
        queues: Dict[str, Any] = self._expand_families(
            qconfig, all_task_names, descendants)
        if qconfig["type"] == "classic":
            queues = self._make_indep(queues)
        self._configure_limiters(queues)

    def _expand_families(self, qconfig: dict, all_task_names: List[str],
                         descendants: dict) -> dict:
        """Expand family names in the queue config."""
        queues: Dict[str, Any] = {}
        for qname, queue in qconfig.items():
            if qname == "type":
                continue
            if qname == self.Q_DEFAULT:
                # Add all tasks to the default queue.
                qmembers = set(all_task_names)
            else:
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

    def _make_indep(self, in_queues: dict) -> dict:
        """For classic queues tasks cannot belong to multiple limit groups.

        Latest assigned group takes precedence. So, for example, the "default"
        group will only contain tasks not assigned to any other queue.

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

    def _configure_limiters(self, queues: dict) -> None:
        """Create a Limiter for each limit group."""
        for name, config in queues.items():
            self.limiters[name] = Limiter(config["limit"], config["members"])

    def push_tasks(self, itasks: List[TaskProxy]) -> None:
        """Append tasks to back of queue."""
        self.queue += itasks

    def release_tasks(self, active: Counter[str]) -> List[TaskProxy]:
        """Release tasks from front of queue if not limited."""
        released: List[TaskProxy] = []
        for itask in list(self.queue):
            if (itask.state.is_held or
                any(limiter.is_limited(itask, active)
                    for name, limiter in self.limiters.items())):
                # Task held, or limited by at least one limit group
                continue
            else:
                released.append(itask)
                # Not limited by any groups.
                self.queue.remove(itask)
                active.update({itask.tdef.name: 1})
        return released

    def remove_task(self, itask: TaskProxy) -> None:
        """Remove a task from the queue."""
        try:
            self.queue.remove(itask)
        except ValueError:
            pass

    def adopt_tasks(self, orphans: List[str]) -> None:
        """Adopt orphaned tasks to the default group."""
        self.limiters[self.Q_DEFAULT].adopt(orphans)
