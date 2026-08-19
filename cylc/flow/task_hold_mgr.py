# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) Earth Sciences New Zealand & British Crown (Met Office)
# & Contributors.
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

"""Manage task hold and release."""

from typing import (
    TYPE_CHECKING,
    Callable,
    Dict,
    Iterable,
    Tuple,
)

from cylc.flow import LOG
from cylc.flow.cycling.loader import get_point

if TYPE_CHECKING:
    from cylc.flow.cycling import PointBase
    from cylc.flow.data_store_mgr import DataStoreMgr
    from cylc.flow.task_proxy import TaskProxy
    from cylc.flow.workflow_db_mgr import WorkflowDatabaseManager


class TaskHoldMgr:
    """Hold/release logic for active and future tasks.

    Active tasks (i.e., task proxies in the pool):
    - hold/release with --flow=n, or (by default) regardless of flow.

    Future tasks (point/name):
    - flagg for future hold, or unflag, with --flow=n, or (by default)
      regardless of flow.

    """
    def __init__(
        self,
        workflow_db_mgr: 'WorkflowDatabaseManager',
        data_store_mgr: 'DataStoreMgr',
    ):
        # (name, point): flow
        self.hold: Dict[Tuple[str, 'PointBase'], int | None] = {}
        # flow may be None: hold future task regardless of its flow number.
        # NOTE: RHS could be a set  of flow numbers, meaning future-hold same
        # task in multiple specific flows. But those instances can't coexist in
        # the pool so serially holding them is probably fine.
        self.data_store_mgr = data_store_mgr
        self.db_mgr = workflow_db_mgr
        self.hold_point: 'PointBase | None' = None
        self.hold_point_flow: int | None = None

    def _flatten(self):
        # possibly-temporary conversion to old-style flat set
        result = set()
        for (name, point), flow in self.hold.items():
            result.add((name, point, flow))
        return result

    def _update_stores(self, name: str, point: 'PointBase', held: bool):
        """Update datastore and database."""
        self.db_mgr.put_tasks_to_hold(self._flatten())
        self.data_store_mgr.delta_task_held(name, point, held)
        LOG.debug(f"Tasks to hold {self.hold}")

    def load_from_db(self):
        """Load the store of tasks-to-hold from the run DB.

        This doesn't actually need to hold the tasks - they're
        automatically held at creation via the is_held attribute.

        """
        if self.db_mgr.pri_dao is not None:
            for name, cycle, flow_num in (
                self.db_mgr.pri_dao.select_tasks_to_hold()
            ):
                nflow: int | None = None
                if flow_num:
                    nflow = int(flow_num)
                self.hold[(name, get_point(cycle))] = nflow

    def hold_active_task(
        self,
        itask: 'TaskProxy',
        flow_num: int | None = None,
    ) -> bool:
        """Hold itask if the specified flow_num matches or is None."""
        if flow_num is not None and flow_num not in itask.flow_nums:
            # specified flow does not match this task
            return False
        if not itask.state_reset(is_held=True):
            # already held
            return False
        self.hold[(itask.tdef.name, itask.point)] = flow_num
        self._update_stores(itask.tdef.name, itask.point, True)
        return True

    def flag_future_task(
        self,
        name: str,
        point: 'PointBase',
        flow_num: int | None = None
    ) -> None:
        """Flag that we should hold a future task."""
        self.hold[(name, point)] = flow_num
        self._update_stores(name, point, True)

    def hold_if_flagged(
        self,
        itask: 'TaskProxy'
    ) -> None:
        """Hold a newly-spawned task if flagged in the future hold list.

        flow None: a future-held specific task regardless of flow.
        """
        if (itask.tdef.name, itask.point) not in self.hold.keys():
            return

        if (
            self.hold[(itask.tdef.name, itask.point)] is None
            or self.hold[(itask.tdef.name, itask.point)] in itask.flow_nums
        ):
            LOG.info(f"[{itask}] holding (as requested earlier)")
            itask.state_reset(is_held=True)

    def release_future_task(
        self,
        name: str,
        cycle: str,
        flow_num: int | None = None
    ) -> None:
        """Un-flag point/name if flow matches or flow is None."""
        point: 'PointBase' = get_point(cycle)
        if (name, point) not in self.hold.keys():
            return
        if (
            flow_num is None
            or self.hold[(name, point)] is None
            or flow_num == self.hold[(name, point)]
        ):
            del self.hold[(name, point)]

        self._update_stores(name, point, False)

    def release_active_task(
        self,
        itask: 'TaskProxy',
        queue_func: Callable,
        flow_num: int | None = None,
    ) -> None:
        """Release a held task if flow matches, and queue it if ready."""
        if (
            flow_num is not None
            and flow_num not in itask.flow_nums
        ):
            return

        if not itask.state_reset(is_held=False):
            # not held
            return

        del self.hold[(itask.tdef.name, itask.point)]
        self._update_stores(itask.tdef.name, itask.point, False)

        if (
            not itask.state.is_runahead
            and itask.is_ready_to_run()
        ):
            queue_func(itask)

    def set_hold_point(
        self,
        point: 'PointBase',
        active_tasks: Iterable['TaskProxy'],
        flow_num: int | None = None
    ) -> None:
        self.hold_point = point
        self.hold_point_flow = flow_num
        self.db_mgr.put_workflow_hold_cycle_point(point, flow_num)
        for itask in active_tasks:
            if itask.point > point:
                self.hold_active_task(itask, flow_num)

    def hold_if_beyond_hold_point(self, itask: 'TaskProxy') -> bool:
        """Hold a task instance if it is beyond the hold point.

        Return True if it was held, else False.

        """
        if (
            self.hold_point and itask.point > self.hold_point
            and (
                self.hold_point_flow is None
                or self.hold_point_flow in itask.flow_nums
            )
        ):
            LOG.info(
                f"[{itask}] holding (beyond workflow "
                f"hold point: {self.hold_point})"
            )
            self.hold_active_task(itask)
            return True
        else:
            return False

    def release_all(
        self,
        active_tasks: Iterable['TaskProxy'],
        queue_func: Callable,
        flow_num: int | None = None
    ):
        """Release all tasks and unset hold point."""
        self.hold_point = None
        self.db_mgr.put_workflow_hold_cycle_point(None, None)
        # Release active tasks
        for itask in active_tasks:
            self.release_active_task(itask, queue_func, flow_num)
        # Release future tasks
        for (name, point), flow_num in self.hold.items():
            self.release_future_task(name, str(point), flow_num)

    def is_held(
        self,
        name: str,
        point: 'PointBase',
    ) -> bool:
        """Is point/name held, regardless of flow."""
        return (name, point) in self.hold
