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
from cylc.flow.exceptions import InputError


if TYPE_CHECKING:
    from cylc.flow.workflow_db_mgr import WorkflowDatabaseManager

FlowNums = Set[int]
# Flow constants
FLOW_ALL = "all"
FLOW_NEW = "new"
FLOW_NONE = "none"

# For flow-related CLI options:
ERR_OPT_FLOW_VAL = "Flow values must be an integer, or 'all', 'new', or 'none'"
ERR_OPT_FLOW_INT = "Multiple flow options must all be integer valued"
ERR_OPT_FLOW_WAIT = (
    f"--wait is not compatible with --flow={FLOW_NEW} or --flow={FLOW_NONE}"
)


def add_flow_opts(parser):
    parser.add_option(
        "--flow", action="append", dest="flow", metavar="FLOW",
        help=f'Assign new tasks to all active flows ("{FLOW_ALL}");'
             f' no flow ("{FLOW_NONE}"); a new flow ("{FLOW_NEW}");'
             f' or a specific flow (e.g. "2"). The default is "{FLOW_ALL}".'
             ' Specific flow numbers can be new or existing.'
             ' Reuse the option to assign multiple flow numbers.'
    )

    parser.add_option(
        "--meta", metavar="DESCRIPTION", action="store",
        dest="flow_descr", default=None,
        help=f"description of new flow (with --flow={FLOW_NEW})."
    )

    parser.add_option(
        "--wait", action="store_true", default=False, dest="flow_wait",
        help="Wait for merge with current active flows before flowing on."
    )


def validate_flow_opts(options):
    """Check validity of flow-related CLI options."""
    if options.flow is None:
        # Default to all active flows
        options.flow = [FLOW_ALL]

    for val in options.flow:
        val = val.strip()
        if val in [FLOW_NONE, FLOW_NEW, FLOW_ALL]:
            if len(options.flow) != 1:
                raise InputError(ERR_OPT_FLOW_INT)
        else:
            try:
                int(val)
            except ValueError:
                raise InputError(ERR_OPT_FLOW_VAL.format(val))

    if options.flow_wait and options.flow[0] in [FLOW_NEW, FLOW_NONE]:
        raise InputError(ERR_OPT_FLOW_WAIT)


def stringify_flow_nums(flow_nums: Set[int], full: bool = False) -> str:
    """Return a string representation of a set of flow numbers

    If the set contains only the original flow 1, return an empty string
    so that users can disregard flows unless they trigger new ones.

    Otherwise return e.g. "(1,2,3)".

    Examples:
        >>> stringify_flow_nums({})
        '(none)'

        >>> stringify_flow_nums({1})
        ''

        >>> stringify_flow_nums({1}, True)
        '(1)'

        >>> stringify_flow_nums({1,2,3})
        '(1,2,3)'

    """
    if not full and flow_nums == {1}:
        return ""
    return (
        "("
        f"{','.join(str(i) for i in flow_nums) or 'none'}"
        ")"
    )


class FlowMgr:
    """Logic to manage flow counter and flow metadata."""

    def __init__(self, db_mgr: "WorkflowDatabaseManager") -> None:
        """Initialise the flow manager."""
        self.db_mgr = db_mgr
        self.flows: Dict[int, Dict[str, str]] = {}
        self.counter: int = 0

    def get_flow_num(
        self,
        flow_num: Optional[int] = None,
        meta: Optional[str] = None
    ) -> int:
        """Return a valid flow number, and record a new flow if necessary.

        If asked for a new flow:
           - increment the automatic counter until we find an unused number

        If given a flow number:
           - record a new flow if the number is unused
           - else return it, as an existing flow number.

        The metadata string is only used if it is a new flow.

        """
        if flow_num is None:
            self.counter += 1
            while self.counter in self.flows:
                # Skip manually-created out-of-sequence flows.
                self.counter += 1
            flow_num = self.counter

        if flow_num in self.flows:
            if meta is not None:
                LOG.warning(
                    f'Ignoring flow metadata "{meta}":'
                    f' {flow_num} is not a new flow'
                )
        else:
            # Record a new flow.
            now = datetime.datetime.now()
            now_sec: str = str(
                now - datetime.timedelta(microseconds=now.microsecond))
            meta = meta or "no description"
            self.flows[flow_num] = {
                "description": meta,
                "start_time": now_sec
            }
            LOG.info(
                f"New flow: {flow_num} ({meta}) {now_sec}"
            )
            self.db_mgr.put_insert_workflow_flows(
                flow_num,
                self.flows[flow_num]
            )
        return flow_num

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
