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

"""Manage the store of tasks held and to-be-held."""

from typing import (
    Callable,
    Dict,
    List,
    Set,
    Tuple,
    TYPE_CHECKING,
)

from cylc.flow import LOG
from cylc.flow.task_state import TASK_STATUS_WAITING
from cylc.flow.cycling.loader import get_point


if TYPE_CHECKING:
    from cylc.flow.cycling import PointBase
    from cylc.flow.task_proxy import TaskProxy
    from cylc.flow.workflow_db_mgr import WorkflowDatabaseManager
    from cylc.flow.data_store_mgr import DataStoreMgr


class PseudoTaskProxy:
    """Used to present a pseudo task pool, for task filtering."""

    def __init__(
        self,
        name: str,
        point: 'PointBase',
        ancestors: List[str],
        state: str = TASK_STATUS_WAITING
    ):
        self.point = point
        self.tdef = self.PseudoTaskdef(name, ancestors)
        self.state = self.PseudoTaskState(state)

    class PseudoTaskState:
        def __init__(self, state):
            self.status = state

    class PseudoTaskdef:
        def __init__(self, name: str, ancestors: List[str]):
            self.name = name
            self.namespace_hierarchy = ancestors


class TaskHoldMgr:
    """Central logic for active and future task hold/release management."""

    def __init__(
        self,
        workflow_db_mgr: 'WorkflowDatabaseManager',
        data_store_mgr: 'DataStoreMgr',
        ancestors: Dict[str, List[str]]
    ) -> None:
        self.ancestors = ancestors
        self.workflow_db_mgr = workflow_db_mgr
        self.data_store_mgr = data_store_mgr
        self.store: Set[Tuple[str, 'PointBase']] = set()

    def load_from_db(self):
        """Update the task hold store from the database."""
        self.store.update(
            (name, get_point(cycle)) for name, cycle in
            self.workflow_db_mgr.pri_dao.select_tasks_to_hold()
        )

    def is_held(self, name: str, point: 'PointBase') -> bool:
        """Is this task listed in the hold store?"""
        return (name, point) in self.store

    def hold_active_tasks(self, itasks: List['TaskProxy']) -> None:
        """Hold an active task and add it to the hold store."""
        for itask in itasks:
            itask.state_reset(is_held=True)
            self.store.add((itask.tdef.name, itask.point))
            self.data_store_mgr.delta_task_held(itask)
            self.workflow_db_mgr.put_tasks_to_hold(self.store)

    def hold_future_tasks(
        self, tasks: Set[Tuple[str, 'PointBase']]
    ) -> None:
        """Add a future task to the hold store."""
        for name, cycle in tasks:
            self.data_store_mgr.delta_task_held((name, cycle, True))
        self.store.update(tasks)
        self.workflow_db_mgr.put_tasks_to_hold(self.store)

    def remove_active_task(
        self, itask: 'TaskProxy'
    ) -> None:
        """Remove (not release) an active task from the hold store."""
        self.store.discard((itask.tdef.name, itask.point))
        self.workflow_db_mgr.put_tasks_to_hold(self.store)

    def release_future_tasks(
        self, ftasks: List['PseudoTaskProxy']
    ) -> None:
        """Release future tasks from the hold store."""
        matched = set()
        for ftask in ftasks:
            name = ftask.tdef.name
            cycle = ftask.point
            matched.add((ftask.tdef.name, ftask.point))
            self.data_store_mgr.delta_task_held((name, cycle, False))

        self.store.difference_update(matched)
        self.workflow_db_mgr.put_tasks_to_hold(self.store)

    def release_active_tasks(
        self, itasks: List['TaskProxy'], queue_func: Callable
    ) -> None:
        """Release active tasks, remove from store, and queue if ready."""
        for itask in itasks:
            if not itask.state_reset(is_held=False):
                continue
            self.data_store_mgr.delta_task_held(itask)
            if (
                not itask.state.is_runahead
                and all(itask.is_ready_to_run())
            ):
                queue_func(itask)
            self.remove_active_task(itask)

    def clear(self) -> None:
        """Empty the hold store."""
        self.store.clear()
        self.workflow_db_mgr.put_tasks_to_hold(self.store)

    def log(self) -> None:
        """Log content of hold store."""
        msg = "Task hold list: "
        if self.store:
            msg += '\n * ' + '\n * '.join(
                [f"{p}/{n}" for (n, p) in self.store]
            )
        else:
            msg += "none"
        LOG.info(msg)

    def get_as_pool(self) -> Dict['PointBase', Dict[str, 'PseudoTaskProxy']]:
        """Return hold store in the form of the scheduler task pool.

        Uses PseudoTaskProxy with just bits needed for task pool filtering.

        """
        pseudo_pool: Dict['PointBase', Dict[str, 'PseudoTaskProxy']] = {}
        for (name, point) in self.store:
            if point not in pseudo_pool:
                pseudo_pool[point] = {}
            pseudo_pool[point][f"{point}/{name}"] = PseudoTaskProxy(
                name, point, ancestors=self.ancestors[name]
            )
        return pseudo_pool
