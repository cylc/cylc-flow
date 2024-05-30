#!/usr/bin/env python3

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

r"""cylc workflow-state [OPTIONS] ARGS

Repeatedly check (poll) a workflow database for task statuses or completed
outputs, until matching results are found or polling is exhausted (see the
--max-polls and --interval options). For a one-off check set --max-polls=1.

If the database does not exist at first, polls are consumed waiting for it.

In "cycle/task:selector" the selector is interpreted as a status, unless:
  - if not a known status, it will be interpreted as a task output (Cylc 8)
    or as a task message (Cylc 7 DBs)
  - with --output, it will be interpreted as a task output

Selector does not default to "succeeded" - if omitted, any status will match.

The "finished" pseudo-output is an alias for "succeeded or failed".

In the ID, both cycle and task can include "*" to match any sequence of zero
or more characters. Quote the pattern to protect it from shell expansion.

Tasks are only recorded in the DB once they enter the active window (n=0).

Flow numbers are only printed if not the original flow (i.e., if > 1).

USE IN TASK SCRIPTING:
  - To poll a task at the same cycle point in another workflow, just use
    $CYLC_TASK_CYCLE_POINT in the ID (see also the workflow_state xtrigger).
  - To poll a task at an offset cycle point, use the --offset option to
    have Cylc do the datetime arithmetic.

WARNINGS:
 - Typos in the workflow or task ID may result in fruitless polling.
 - To avoid missing transient state ("submitted", "running") poll for the
   corresponding output ("submitted", "started").
 - Cycle points are auto-converted to the DB point format (and UTC mode).

Examples:

  # Print the status of all tasks in WORKFLOW:
  $ cylc workflow-state WORKFLOW

  # Print the status of all tasks in cycle point 2033:
  $ cylc workflow-state WORKFLOW//2033

  # Print the status of all tasks named foo:
  $ cylc workflow-state WORKFLOW//*/foo

  # Print all succeeded tasks:
  $ cylc workflow-state "WORKFLOW//*/*:succeeded"

  # Print all tasks foo that completed output file1:
  $ cylc workflow-state "WORKFLOW//*/foo:file1"

  # Print if task 2033/foo completed output file1:
  $ cylc workflow-state WORKFLOW//2033/foo:file1

See also:
  - the workflow_state xtrigger, for state polling within workflows
  - "cylc dump -t", to query a scheduler for current statuses
  - "cylc show", to query a scheduler for task prerequisites and outputs
"""

import asyncio
import sqlite3
import sys
from typing import TYPE_CHECKING

from cylc.flow.pathutil import get_cylc_run_dir
from cylc.flow.id import Tokens
from cylc.flow.exceptions import InputError
from cylc.flow.option_parsers import (
    ID_MULTI_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow import LOG
from cylc.flow.command_polling import Poller
from cylc.flow.dbstatecheck import CylcWorkflowDBChecker
from cylc.flow.terminal import cli_function
from cylc.flow.workflow_files import infer_latest_run_from_id
from cylc.flow.task_state import TASK_STATUSES_ORDERED

if TYPE_CHECKING:
    from optparse import Values


# TODO: flow=all, none?  Useful for CLI if not xrigger, pt format.

WILDCARD = "*"

# polling defaults
MAX_POLLS = 12
INTERVAL = 5


class WorkflowPoller(Poller):
    """A polling object that queries task states or outputs from a DB."""

    def __init__(
        self, id_, offset, flow_num, alt_cylc_run_dir, default_status,
        is_output, old_format,
        *args, **kwargs
    ):
        self.id_ = id_
        self.offset = offset
        self.flow_num = flow_num
        self.alt_cylc_run_dir = alt_cylc_run_dir
        self.old_format = old_format

        self.db_checker = None

        tokens = Tokens(self.id_)
        self.workflow_id_raw = tokens.workflow_id
        self.task_sel = tokens["task_sel"] or default_status
        self.cycle_raw = tokens["cycle"]
        self.task = tokens["task"]

        self.workflow_id = None
        self.cycle = None
        self.results = None
        self.db_checker = None

        self.is_output = (
            is_output or
            (
                self.task_sel is not None and
                self.task_sel not in TASK_STATUSES_ORDERED
            )
        )

        super().__init__(*args, **kwargs)

    def _find_workflow(self) -> bool:
        """Find workflow and infer run directory, return True if found."""
        try:
            self.workflow_id = infer_latest_run_from_id(
                self.workflow_id_raw,
                self.alt_cylc_run_dir
            )
        except InputError:
            LOG.debug("Workflow not found")
            return False

        # Print inferred workflow ID.
        sys.stderr.write(f"{self.workflow_id}\n")

        return True

    def _db_connect(self) -> bool:
        """Connect to workflow DB, return True if connected."""
        try:
            self.db_checker = CylcWorkflowDBChecker(
                get_cylc_run_dir(self.alt_cylc_run_dir),
                self.workflow_id
            )
        except (OSError, sqlite3.Error):
            LOG.debug("DB not connected")
            return False

        return True

    async def check(self) -> bool:
        """Return True if requested state achieved, else False.

        Called once per poll by super() so only find and connect once.

        Store self.result for external access.

        """
        if self.workflow_id is None and not self._find_workflow():
            return False

        if self.db_checker is None and not self._db_connect():
            return False

        if self.cycle is None:
            # Adjust target cycle point to the DB format.
            self.cycle = self.db_checker.adjust_point_to_db(
                self.cycle_raw, self.offset)

        self.result = self.db_checker.workflow_state_query(
            self.task, self.cycle, self.task_sel, self.is_output, self.flow_num
        )
        if self.result:
            # End the polling dot stream and print inferred runN workflow ID.
            self.db_checker.display_maps(self.result, self.old_format)

        return bool(self.result)


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        argdoc=[ID_MULTI_ARG_DOC]
    )

    parser.add_option(
        "-d", "--alt-cylc-run-dir",
        help="Alternate cylc-run directory, e.g. for others' workflows.",
        metavar="DIR", action="store", dest="alt_cylc_run_dir", default=None)

    parser.add_option(
        "-s", "--offset",
        help="Offset from ID cycle point as an ISO8601 duration for datetime"
        " cycling (e.g. 'PT30M' for 30 minutes) or an integer interval for"
        " integer cycling (e.g. 'P2'). This can be used in task job scripts"
        " to poll offset cycle points without doing the cycle arithmetic"
        " yourself - but see also the workflow_state xtrigger.",
        action="store", dest="offset", metavar="DURATION", default=None)

    parser.add_option(
        "--flow",
        help="Flow number, for target tasks.",
        action="store", type="int", dest="flow_num", default=None)

    parser.add_option(
        "--output",
        help="Interpret task selector as an output rather than as a status."
             "(Note this is not needed for custom outputs).",
        action="store_true", dest="is_output", default=False)

    parser.add_option(
        "--old-format",
        help="Print results in legacy comma-separated format.",
        action="store_true", dest="old_format", default=False)

    WorkflowPoller.add_to_cmd_options(
        parser,
        d_interval=INTERVAL,
        d_max_polls=MAX_POLLS
    )

    return parser


@cli_function(get_option_parser, remove_opts=["--db"])
def main(parser: COP, options: 'Values', *ids: str) -> None:

    if len(ids) != 1:
        raise InputError("Please give a single ID")
    id_ = ids[0]

    poller = WorkflowPoller(
        id_,
        options.offset,
        options.flow_num,
        options.alt_cylc_run_dir,
        None,  # default status
        options.is_output,
        options.old_format,
        f'"{id_}"',
        options.interval,
        options.max_polls,
        args=None
    )

    if not asyncio.run(
        poller.poll()
    ):
        sys.exit(1)
