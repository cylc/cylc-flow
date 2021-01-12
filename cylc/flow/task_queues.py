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

"""Cylc internal queues."""

from typing import List, Set, Dict, Deque
from collections import deque

from cylc.flow.task_proxy import TaskProxy
from cylc.flow import LOG
from cylc.flow.task_state import (
    TASK_STATUS_PREPARING,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_QUEUED,
)


class Cqueue:
    """A task proxy queue with limit and active set.

    Uses a deque internally because:
    - iteration of all members is required for some operations
    - overlapping queues (TODO) require returning tasks to the front

    """
    def __init__(self, limit: int) -> None:
        self.limit: int = limit
        self.active: Set[TaskProxy] = set()
        self.deque: Deque[TaskProxy] = deque()

    def put(self, itask: TaskProxy) -> None:
        """Add a task to back of queue."""
        self.deque.appendleft(itask)

    def put_active(self, itask: TaskProxy) -> None:
        """Add a task to the active set."""
        self.active.add(itask)

    def remove(self, itask: TaskProxy) -> None:
        """Remove itask."""
        try:
            self.deque.remove(itask)
        except ValueError:
            pass
        try:
            self.active.remove(itask)
        except KeyError:
            pass

    def release(self) -> List[TaskProxy]:
        """Release tasks if limit not reached, or if manually triggered.

        Note "cylc trigger" queues unqueued tasks and submits queued tasks
        regardless of limit; so two trigger ops may be needed to submit an
        unqueued task that belongs to a limited queue.

        """
        # First purge no-longer-active tasks from the active set.
        finished: Set[TaskProxy] = set()
        for itask in self.active:
            if not itask.state(
                    TASK_STATUS_PREPARING,
                    TASK_STATUS_SUBMITTED,
                    TASK_STATUS_RUNNING,
                    is_held=False):
                finished.add(itask)
        self.active -= finished

        # Release manually-triggered tasks regardless of limit.
        for itask in self.deque:
            if itask.manual_trigger:
                itask.reset_manual_trigger()
                self.active.add(itask)
                self.deque.remove(itask)

        # Release queued tasks according to limit.
        if not self.limit:
            n_free: int = len(self.deque)
        else:
            n_free = self.limit - len(self.active)

        ready: List[TaskProxy] = []
        while n_free > 0:
            try:
                t = self.deque.pop()
            except IndexError:
                # no more to release
                break
            ready.append(t)
            self.active.add(t)
            n_free -= 1

        LOG.debug(f"{len(ready)} task(s) de-queued")
        return ready


class QueueManager:
    """Manage multiple internal queues.

    Anticipating upcoming overlapping queues, some methods already assume a
    task could be in multiple queues.

    """
    def __init__(self, qconfig: dict) -> None:
        """Configure the queue manager: queue names, limits, members."""
        self.queue_name_task_name_map: Dict[str, List[str]] = {}
        self.queues = {}  # queues by quename
        for qname, config in qconfig.items():
            self.queues[qname] = Cqueue(config['limit'])
            for member in config['members']:
                self.queue_name_task_name_map.setdefault(member, [])
                self.queue_name_task_name_map[member].append(qname)

    def queue_tasks_if_ready(self, itasks) -> None:
        """Queue tasks that are ready to run."""
        for itask in itasks:
            if not itask.state(TASK_STATUS_QUEUED) and itask.is_ready():
                itask.state.reset(TASK_STATUS_QUEUED)
                itask.reset_manual_trigger()
                self.put(itask)
            elif itask.state(
                    TASK_STATUS_PREPARING,
                    TASK_STATUS_SUBMITTED,
                    TASK_STATUS_RUNNING):
                self.put_active(itask)

    def put(self, itask: TaskProxy) -> None:
        """Put task instance in the appropriate queue."""
        for qname in self.queue_name_task_name_map[itask.tdef.name]:
            self.queues[qname].put(itask)

    def put_active(self, itask: TaskProxy) -> None:
        """Put task instance in the appropriate queue's active set."""
        for qname in self.queue_name_task_name_map[itask.tdef.name]:
            self.queues[qname].put_active(itask)

    def release(self) -> List[TaskProxy]:
        """Release queued tasks."""
        released: List[TaskProxy] = []
        for queue in self.queues.values():
            released.extend(queue.release())
        for t in released:
            t.state.reset(TASK_STATUS_PREPARING)
        return released

    def remove(self, itask: TaskProxy) -> None:
        """Remove itask from all queues."""
        for queue in self.queues.values():
            queue.remove(itask)
