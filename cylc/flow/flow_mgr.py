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

"""Manage flow counter and flow metadata."""

from typing import Dict, Set, Optional, TYPE_CHECKING
import datetime

from cylc.flow import LOG

if TYPE_CHECKING:
    from cylc.flow.workflow_db_mgr import WorkflowDatabaseManager

FlowNums = Set[int]
# Flow constants
FLOW_ALL = "all"
FLOW_NEW = "new"
FLOW_NONE = "none"


class FlowMgr:
    """Logic to manage flow counter and flow metadata."""

    def __init__(self, db_mgr: "WorkflowDatabaseManager") -> None:
        """Initialise the flow manager."""
        self.db_mgr = db_mgr
        self.flows: Dict[int, Dict[str, str]] = {}
        self.counter: int = 0

    def get_new_flow(self, description: Optional[str] = None) -> int:
        """Increment flow counter, record flow metadata."""
        self.counter += 1
        # record start time to nearest second
        now = datetime.datetime.now()
        now_sec: str = str(
            now - datetime.timedelta(microseconds=now.microsecond))
        description = description or "no description"
        self.flows[self.counter] = {
            "description": description,
            "start_time": now_sec
        }
        LOG.info(
            f"New flow: {self.counter} "
            f"({description}) "
            f"{now_sec}"
        )
        self.db_mgr.put_insert_workflow_flows(
            self.counter,
            self.flows[self.counter]
        )
        return self.counter

    def load_from_db(self, flow_nums: FlowNums) -> None:
        """Load flow data for scheduler restart.

        Sets the flow counter to the max flow number in the DB.
        Loads metadata for selected flows (those in the task pool at startup).

        """
        self.counter = self.db_mgr.pri_dao.select_workflow_flows_max_flow_num()
        self.flows = self.db_mgr.pri_dao.select_workflow_flows(flow_nums)
        self._log()

    def _log(self) -> None:
        """Write current flow info to log."""
        if not self.flows:
            LOG.info("Flows: (none)")
            return

        LOG.info(
            "Flows:\n" + "\n".join(
                (
                    f"flow: {f} "
                    f"({self.flows[f]['description']}) "
                    f"{self.flows[f]['start_time']}"
                )
                for f in self.flows
            )
        )
