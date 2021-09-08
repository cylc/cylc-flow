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

from typing import Dict, Set, TYPE_CHECKING
from datetime import datetime, timedelta

from cylc.flow import LOG

if TYPE_CHECKING:
    from cylc.flow.workflow_db_mgr import WorkflowDatabaseManager


class FlowMgr:
    """Logic to manage flow counter and flow metadata."""

    def __init__(self, db_mgr: "WorkflowDatabaseManager") -> None:
        """Initialise the flow manager."""
        self.db_mgr = db_mgr
        self.counter = 0
        self.flows: Dict[int, Dict[str, str]] = {}

    def get_new_flow(self, description: str = "no description") -> int:
        """Increment flow counter, record flow metadata."""
        self.counter += 1
        # record start time to nearest second
        now = datetime.now()
        now_sec: str = str(now - timedelta(microseconds=now.microsecond))
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
        self.db_mgr.put_workflow_params_1("flow_counter", self.counter)
        self.dump_to_log()
        return self.counter

    def load_flows_db(self, flow_nums: Set[int]) -> None:
        """Load metadata for selected flows from DB - on restart."""
        self.flows = self.db_mgr.pri_dao.select_workflow_flows(flow_nums)
        self.dump_to_log()

    def dump_to_log(self) -> None:
        """Dump current flow info to log."""
        for f in self.flows:
            LOG.info(
                f"flow: {f}: "
                f"({self.flows[f]['description']}) "
                f"{self.flows[f]['start_time']} "
            )
