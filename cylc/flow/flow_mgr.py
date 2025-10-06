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

import datetime
from typing import (
    TYPE_CHECKING,
    Dict,
    Iterable,
    List,
    Optional,
    Set,
)

from cylc.flow import LOG


if TYPE_CHECKING:
    from cylc.flow.workflow_db_mgr import WorkflowDatabaseManager

FlowNums = Set[int]
FLOW_NEW = "new"
FLOW_NONE = "none"


def add_flow_opts_for_trigger_and_set(parser):
    """Add flow options for the trigger and set commands."""
    parser.add_option(
        "--flow",
        action="append",
        dest="flow",
        metavar=f"INT|{FLOW_NEW}|{FLOW_NONE}",
        default=[],
        help=(
            'Assign affected tasks to specified flows.'  # nosec
            # (false positive, this is not an SQL statement Bandit!)
            ' By default, active tasks (n=0) stay in their assigned flow(s)'
            ' and inactive tasks (n>0) will be assigned to all active flows.'
            ' Use this option to manually specify an integer flow to assign'
            ' tasks to, e.g, "--flow=2". Use this option multiple times to'
            ' select multiple flows.'
            f' Alternatively, use "--flow={FLOW_NEW}" to start a new'
            f' flow, or "--flow={FLOW_NONE}" to trigger an inactive task in'
            ' no flows (this means the workflow will not run on from the'
            ' triggered task, only works for inactive tasks).'
        )
    )

    parser.add_option(
        "--meta", metavar="DESCRIPTION", action="store",
        dest="flow_descr", default=None,
        help=f"description of new flow (with --flow={FLOW_NEW})."
    )

    parser.add_option(
        "--wait", action="store_true", default=False, dest="flow_wait",
        help="Wait for merge with current active flows before flowing on."
             " Note you can use 'cylc set --pre=all' to unset a flow-wait."
    )


def add_flow_opts_for_remove(parser):
    """Add flow options for the remove command."""
    parser.add_option(
        '--flow',
        action='append',
        dest='flow',
        metavar='INT',
        default=[],
        help=(
            "Remove the task(s) from the specified flow."
            " Use this option multiple times to specify multiple flows."
            " By default, the tasks will be removed from all flows."
        ),
    )


def stringify_flow_nums(flow_nums: Iterable[int]) -> str:
    """Return the canonical string for a set of flow numbers.

    Examples:
        >>> stringify_flow_nums({1})
        '1'

        >>> stringify_flow_nums({3, 1, 2})
        '1,2,3'

        >>> stringify_flow_nums({})
        ''

    """
    return ','.join(str(i) for i in sorted(flow_nums))


def repr_flow_nums(flow_nums: FlowNums, full: bool = False) -> str:
    """Return a representation of a set of flow numbers

    If `full` is False, return an empty string for flows=1.

    Examples:
        >>> repr_flow_nums({})
        '(flows=none)'

        >>> repr_flow_nums({1})
        ''

        >>> repr_flow_nums({1}, full=True)
        '(flows=1)'

        >>> repr_flow_nums({1,2,3})
        '(flows=1,2,3)'

    """
    if not full and flow_nums == {1}:
        return ""
    return f"(flows={stringify_flow_nums(flow_nums) or 'none'})"


class FlowMgr:
    """Logic to manage flow counter and flow metadata."""

    def __init__(
        self,
        db_mgr: "WorkflowDatabaseManager",
        utc: bool = True
    ) -> None:
        """Initialise the flow manager."""
        self.db_mgr = db_mgr
        self.flows: Dict[int, Dict[str, str]] = {}
        self.counter: int = 0
        self._timezone = datetime.timezone.utc if utc else None

    def cli_to_flow_nums(
        self,
        flow: List[str],
        meta: Optional[str] = None,
    ) -> Set[int]:
        """Convert validated --flow command options to valid int flow numbers.

        Args:
            flow:
                Strings: [int,], or [FLOW_NEW], or [FLOW_NONE].
            meta:
                Flow description, for FLOW_NEW.

        Returns:
            Set of int flow nums. Note empty set can mean no-flow (FLOW_NONE);
            or all flows or all active flows (for default empty inputs).

        """
        if flow == [FLOW_NONE]:
            return set()

        if flow == [FLOW_NEW]:
            return {self.get_flow(meta=meta)}

        return {
            self.get_flow(flow_num=int(n), meta=meta)
            for n in flow
        }

    def get_flow(
        self,
        flow_num: Optional[int] = None,
        meta: Optional[str] = None
    ) -> int:
        """Record and return a valid flow number.

        If asked for a new flow:
           - increment the automatic counter to find an unused number

        If given a flow number:
           - record a new flow if the number is unused
           - or just return it as an existing flow number

        The metadata string is only stored if it is a new flow.

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
            now_sec = datetime.datetime.now(tz=self._timezone).isoformat(
                timespec="seconds"
            )
            meta = meta or "no description"
            self.flows[flow_num] = {
                "description": meta,
                "start_time": now_sec
            }
            LOG.info(
                f"New flow: {flow_num} ({meta})"
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
