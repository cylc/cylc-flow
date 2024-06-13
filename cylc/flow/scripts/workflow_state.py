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

Check a workflow database for current task statuses or completed outputs.

Repeatedly check (poll) until results are matched or polling is exhausted
(see --max-polls and --interval). Use --max-polls=1 for a single check.

Legacy (pre-8.3.0) options are supported, but deprecated, for existing scripts:
    cylc workflow-state --task=NAME --point=CYCLE --status=STATUS
       --output=MESSAGE --message=MESSAGE WORKFLOW

If the database does not exist at first, polls are consumed waiting for it.

In "cycle/task:selector" the selector will match task statuses, unless:
  - if it is not a known status, it will match task output triggers
    (Cylc 8 DB) or task ouput messages (Cylc 7 DB)
  - with --triggers, it will only match task output triggers
  - with --messages (deprecated), it will only match task output messages.
    Triggers are more robust - they match manually and naturally set outputs.

Selector does not default to "succeeded". If omitted, any status will match.

The "finished" pseudo-output is an alias for "succeeded or failed".

In the ID, both cycle and task can include "*" to match any sequence of zero
or more characters. Quote the pattern to protect it from shell expansion.

Note tasks get recorded in the DB once they enter the active window (n=0).

Flow numbers are only printed for flow numbers > 1.

USE IN TASK SCRIPTING:
  - To poll a task at the same cycle point in another workflow, just use
    $CYLC_TASK_CYCLE_POINT in the ID.
  - To poll a task at an offset cycle point, use the --offset option to
    have Cylc do the datetime arithmetic for you.
  - However, see also the workflow_state xtrigger for this use case.

WARNINGS:
 - Typos in the workflow or task ID will result in fruitless polling.
 - To avoid missing transient states ("submitted", "running") poll for the
   corresponding output trigger instead ("submitted", "started").
 - Cycle points are auto-converted to the DB point format (and UTC mode).
 - Task outputs manually completed by "cylc set" have "(force-completed)"
   recorded as the task message in the DB, so it is best to query trigger
   names, not messages, unless specifically interested in forced outputs.

Examples:

  # Print the status of all tasks in WORKFLOW:
  $ cylc workflow-state WORKFLOW

  # Print the status of all tasks in cycle point 2033:
  $ cylc workflow-state WORKFLOW//2033

  # Print the status of all tasks named foo:
  $ cylc workflow-state "WORKFLOW//*/foo"

  # Print all succeeded tasks:
  $ cylc workflow-state "WORKFLOW//*/*:succeeded"

  # Print all tasks foo that completed output (trigger name) file1:
  $ cylc workflow-state "WORKFLOW//*/foo:file1"

  # Print if task 2033/foo completed output (trigger name) file1:
  $ cylc workflow-state WORKFLOW//2033/foo:file1

See also:
  - the workflow_state xtrigger, for state polling within workflows
  - "cylc dump -t", to query a scheduler for current statuses
  - "cylc show", to query a scheduler for task prerequisites and outputs
"""

import asyncio
import sqlite3
import sys
from typing import TYPE_CHECKING, List, Optional

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


WILDCARD = "*"

# polling defaults
MAX_POLLS = 12
INTERVAL = 5

OPT_DEPR_MSG = "DEPRECATED, use ID"
OPT_DEPR_MSG1 = 'DEPRECATED, use "ID:STATUS"'
OPT_DEPR_MSG2 = 'DEPRECATED, use "ID:MSG"'


def unquote(s: str) -> str:
    """Remove leading & trailing quotes from a string.

    Examples:
    >>> unquote('"foo"')
    'foo'
    >>> unquote("'foo'")
    'foo'
    >>> unquote('foo')
    'foo'
    >>> unquote("'tis a fine morning")
    "'tis a fine morning"
    """
    if (
        s.startswith('"') and s.endswith('"')
        or s.startswith("'") and s.endswith("'")
    ):
        return s[1:-1]
    return s


class WorkflowPoller(Poller):
    """An object that polls for task states or outputs in a workflow DB."""

    def __init__(
        self,
        id_: str,
        offset: Optional[str],
        flow_num: Optional[int],
        alt_cylc_run_dir: Optional[str],
        default_status: Optional[str],
        is_output: bool,
        is_message: bool,
        old_format: bool = False,
        pretty_print: bool = False,
        **kwargs
    ):
        self.id_ = id_
        self.offset = offset
        self.flow_num = flow_num
        self.alt_cylc_run_dir = alt_cylc_run_dir
        self.old_format = old_format
        self.pretty_print = pretty_print

        try:
            tokens = Tokens(self.id_)
        except ValueError as exc:
            raise InputError(exc)

        self.workflow_id_raw = tokens.workflow_id
        self.selector = (
            tokens["cycle_sel"] or
            tokens["task_sel"] or
            default_status
        )
        if self.selector:
            self.selector = unquote(self.selector)
        self.cycle_raw = tokens["cycle"]
        self.task = tokens["task"]

        self.workflow_id: Optional[str] = None
        self.cycle: Optional[str] = None
        self.result: Optional[List[List[str]]] = None
        self._db_checker: Optional[CylcWorkflowDBChecker] = None

        self.is_message = is_message
        if is_message:
            self.is_output = False
        else:
            self.is_output = (
                is_output or
                (
                    self.selector is not None and
                    self.selector not in TASK_STATUSES_ORDERED
                )
            )
        super().__init__(**kwargs)

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

        if self.workflow_id != self.workflow_id_raw:
            # Print inferred ID.
            sys.stderr.write(f"Inferred workflow ID: {self.workflow_id}\n")
        return True

    @property
    def db_checker(self) -> Optional[CylcWorkflowDBChecker]:
        """Connect to workflow DB if not already connected.

        Returns DB checker if connected.
        """
        if not self._db_checker:
            try:
                self._db_checker = CylcWorkflowDBChecker(
                    get_cylc_run_dir(self.alt_cylc_run_dir),
                    self.workflow_id
                )
            except (OSError, sqlite3.Error):
                LOG.debug("DB not connected")
                return None

        return self._db_checker

    async def check(self) -> bool:
        """Return True if requested state achieved, else False.

        Called once per poll by super() so only find and connect once.

        Store self.result for external access.

        """
        if self.workflow_id is None and not self._find_workflow():
            return False

        if self.db_checker is None:
            return False

        if self.cycle is None:
            # Adjust target cycle point to the DB format.
            self.cycle = self.db_checker.adjust_point_to_db(
                self.cycle_raw, self.offset)

        self.result = self.db_checker.workflow_state_query(
            self.task, self.cycle, self.selector, self.is_output,
            self.is_message, self.flow_num
        )
        if self.result:
            # End the polling dot stream and print inferred runN workflow ID.
            self.db_checker.display_maps(
                self.result, self.old_format, self.pretty_print)

        return bool(self.result)


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        argdoc=[ID_MULTI_ARG_DOC]
    )

    # --run-dir for pre-8.3.0 back-compat
    parser.add_option(
        "-d", "--alt-cylc-run-dir", "--run-dir",
        help="Alternate cylc-run directory, e.g. for other users' workflows.",
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
        help="Flow number, for target tasks. By default, any flow.",
        action="store", type="int", dest="flow_num", default=None)

    parser.add_option(
        "--triggers",
        help="Task selector should match output triggers rather than status."
             " (Note this is not needed for custom outputs).",
        action="store_true", dest="is_output", default=False)

    parser.add_option(
        "--messages",
        help="Task selector should match output messages rather than status.",
        action="store_true", dest="is_message", default=False)

    parser.add_option(
        "--pretty",
        help="Pretty-print outputs (the default is single-line output).",
        action="store_true", dest="pretty_print", default=False)

    parser.add_option(
        "--old-format",
        help="Print results in legacy comma-separated format.",
        action="store_true", dest="old_format", default=False)

    # Back-compat support for pre-8.3.0 command line options.
    parser.add_option(
        "-t", "--task", help=f"Task name. {OPT_DEPR_MSG}.",
        metavar="NAME",
        action="store", dest="depr_task", default=None)

    parser.add_option(
        "-p", "--point",
        metavar="CYCLE",
        help=f"Cycle point. {OPT_DEPR_MSG}.",
        action="store", dest="depr_point", default=None)

    parser.add_option(
        "-T", "--task-point",
        help="In task job scripts, task cycle point from the environment"
             " (i.e., --point=$CYLC_TASK_CYCLE_POINT)",
        action="store_true", dest="use_task_point", default=False)

    parser.add_option(
        "-S", "--status",
        metavar="STATUS",
        help=f"Task status. {OPT_DEPR_MSG1}.",
        action="store", dest="depr_status", default=None)

    # Prior to 8.3.0 --output was just an alias for --message
    parser.add_option(
        "-O", "--output", "-m", "--message",
        metavar="MSG",
        help=f"Task output message. {OPT_DEPR_MSG2}.",
        action="store", dest="depr_msg", default=None)

    WorkflowPoller.add_to_cmd_options(
        parser,
        d_interval=INTERVAL,
        d_max_polls=MAX_POLLS
    )

    return parser


@cli_function(get_option_parser, remove_opts=["--db"])
def main(parser: COP, options: 'Values', *ids: str) -> None:

    # Note it would be cleaner to use 'id_cli.parse_ids()' here to get the
    # workflow ID and tokens, but that function infers run number and fails
    # if the workflow is not installed yet. We want to be able to start polling
    # before the workflow is installed, which makes it easier to get set of
    # interdependent workflows up and running, so runN inference is done inside
    # the poller. TODO: consider using id_cli.parse_ids inside the poller.

    if len(ids) != 1:
        raise InputError("Please give a single ID")

    id_ = ids[0].rstrip('/')  # might get 'id/' due to autcomplete

    if any(
        [
            options.depr_task,
            options.depr_status,
            options.depr_msg,  # --message and --output
            options.depr_point
        ]
    ):
        depr_opts = "options --task, --status, --message, --output, --point"

        if id_ != Tokens(id_)["workflow"]:
            raise InputError(
                f"with deprecated {depr_opts}, the argument must be a"
                " plain workflow ID (i.e. with no cycle, task, or :selector)."
            )

        if options.depr_point is not None:
            id_ += f"//{options.depr_point}"
        elif (
            options.depr_task is not None or
            options.depr_status is not None or
            options.depr_msg is not None
        ):
            id_ += "//*"
        if options.depr_task is not None:
            id_ += f"/{options.depr_task}"
        if options.depr_status is not None:
            id_ += f":{options.depr_status}"
        elif options.depr_msg is not None:
            id_ += f":{options.depr_msg}"
            options.is_message = True

        LOG.warning(
            f"{depr_opts} are deprecated. Please use the ID format: {id_}."
        )

    poller = WorkflowPoller(
        id_,
        options.offset,
        options.flow_num,
        options.alt_cylc_run_dir,
        default_status=None,
        is_output=options.is_output,
        is_message=options.is_message,
        old_format=options.old_format,
        pretty_print=options.pretty_print,
        condition=id_,
        interval=options.interval,
        max_polls=options.max_polls,
        args=None
    )

    if not asyncio.run(
        poller.poll()
    ):
        sys.exit(1)
