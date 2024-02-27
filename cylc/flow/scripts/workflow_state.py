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

Print or poll for task states or outputs in a workflow database.

For specific cycle/task instances poll until the given status or output is
achieved (command success) or the max number of polls is reached (failure).

For less specific queries, immediate results are printed (no polling is done).

Override default polling parameters with --max-polls and --interval.

If the database does not exist at first, polls are consumed waiting for it.

For task outputs, give the task message, not the output label.

For non-cycling workflows, provide --point=1 for specific queries.

This command can be used to make polling tasks that trigger off of tasks in
other workflows - but see also the built-in workflow_state xtrigger for that.

NOTE: the DB only records the latest task statuses, so for transient states
like "submitted" it may be safer to poll for the associated standard output.

Examples:

  # Print the current or latest status of all tasks:
  $ cylc workflow-state WORKFLOW_ID

  # Print the current or latest status of all tasks named "foo":
  $ cylc workflow-state --task=foo WORKFLOW_ID

  # Print the current or latest status of all tasks in point 2033:
  $ cylc workflow-state --point=2033 WORKFLOW_ID

  # Print all tasks with the current or latest status "succeeded":
  $ cylc workflow-state --status=succeeded CYLC_WORKFLOW_ID

  # Print all tasks that generated the output message "file1 ready":
  $ cylc workflow-state --message="file1 ready" WORKFLOW_ID

  # Print all tasks "foo" that generated the output message "file1 ready":
  $ cylc workflow-state --task=foo --message="file1 ready" WORKFLOW_ID

  # POLL UNTIL task 2033/foo succeeds:
  $ cylc workflow-state --task=foo --point=2033 --status=succeeded WORKFLOW_ID

  # POLL UNTIL task 2033/foo generates output message "hello":
  $ cylc workflow-state --task=foo --point=2033 --message="hello" WORKFLOW_ID
"""

import asyncio
import os
import sqlite3
import sys
from time import sleep
from typing import TYPE_CHECKING

from cylc.flow.exceptions import CylcError, InputError
import cylc.flow.flags
from cylc.flow.id_cli import parse_id
from cylc.flow.option_parsers import (
    WORKFLOW_ID_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow.dbstatecheck import CylcWorkflowDBChecker
from cylc.flow.command_polling import Poller
from cylc.flow.task_state import TASK_STATUSES_ORDERED
from cylc.flow.terminal import cli_function
from cylc.flow.cycling.util import add_offset
from cylc.flow.pathutil import expand_path, get_cylc_run_dir

from metomi.isodatetime.parsers import TimePointParser

if TYPE_CHECKING:
    from optparse import Values


class WorkflowPoller(Poller):
    """A polling object that checks workflow state."""

    def connect(self):
        """Connect to the workflow db, polling if necessary in case the
        workflow has not been started up yet."""

        # Returns True if connected, otherwise (one-off failed to
        # connect, or max number of polls exhausted) False
        connected = False

        if cylc.flow.flags.verbosity > 0:
            sys.stderr.write(
                "connecting to workflow db for " +
                self.args['run_dir'] + "/" + self.args['workflow_id'])

        # Attempt db connection even if no polls for condition are
        # requested, as failure to connect is useful information.
        max_polls = self.max_polls or 1
        # max_polls*interval is equivalent to a timeout, and we
        # include time taken to connect to the run db in this...
        while not connected:
            self.n_polls += 1
            try:
                self.checker = CylcWorkflowDBChecker(
                    self.args['run_dir'], self.args['workflow_id'])
                connected = True
                # ... but ensure at least one poll after connection:
                self.n_polls -= 1
            except (OSError, sqlite3.Error):
                if self.n_polls >= max_polls:
                    raise
                if cylc.flow.flags.verbosity > 0:
                    sys.stderr.write('.')
                sleep(self.interval)
        if cylc.flow.flags.verbosity > 0:
            sys.stderr.write('\n')

        if connected and self.args['cycle']:
            fmt = self.checker.get_point_format()
            if fmt:
                # convert cycle point to DB format
                self.args['cycle'] = str(
                    TimePointParser().parse(
                        self.args['cycle'], fmt
                    )
                )
        return connected, self.args['cycle']

    async def check(self):
        """Return True if desired workflow state achieved, else False"""
        return self.checker.task_state_met(
            self.args['task'], self.args['cycle'],
            self.args['status'], self.args['message'])


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        argdoc=[WORKFLOW_ID_ARG_DOC]
    )

    parser.add_option(
        "-t", "--task", help="Task name to query.",
        metavar="NAME", action="store", dest="task", default=None)

    parser.add_option(
        "-p", "--point", metavar="POINT",
        help="Cycle point to query.",
        action="store", dest="cycle", default=None)

    parser.add_option(
        "-T", "--task-point",
        help="Short for --point=$CYLC_TASK_CYCLE_POINT, in job environments.",
        action="store_true", dest="use_task_point", default=False)

    parser.add_option(
        "-d", "--run-dir",
        help="cylc-run directory location, for workflows owned by others."
             " The database location will be DIR/WORKFLOW_ID/log/db.",
        metavar="DIR", action="store", dest="run_dir", default=None)

    parser.add_option(
        "-s", "--offset",
        help="Specify an offset from the target cycle point. Can be useful"
        " along with --task-point when polling one workflow from another.",
        action="store", dest="offset", metavar="OFFSET", default=None)

    parser.add_option(
        "-S", "--status", metavar="STATUS",
        help=f"Task status: {', '.join(TASK_STATUSES_ORDERED)};"
        " plus: started, finished.",
        action="store", dest="status", default=None)

    parser.add_option(
        "-O", "--output", "-m", "--message", metavar="MESSAGE",
        help="Task output message (not the label used in the graph).",
        action="store", dest="msg", default=None)

    WorkflowPoller.add_to_cmd_options(parser)

    return parser


@cli_function(get_option_parser, remove_opts=["--db"])
def main(parser: COP, options: 'Values', workflow_id: str) -> None:
    workflow_id, *_ = parse_id(
        workflow_id,
        constraint='workflows',
    )

    if options.use_task_point and options.cycle:
        raise InputError(
            "cannot specify a cycle point and use environment variable")

    if options.use_task_point:
        if "CYLC_TASK_CYCLE_POINT" not in os.environ:
            raise InputError("CYLC_TASK_CYCLE_POINT is not defined")
        options.cycle = os.environ["CYLC_TASK_CYCLE_POINT"]

    if options.offset and not options.cycle:
        raise InputError(
            "You must target a cycle point to use an offset")

    # Attempt to apply specified offset to the targeted cycle
    if options.offset:
        options.cycle = str(add_offset(options.cycle, options.offset))

    # Exit if both task state and message are to being polled
    if options.status and options.msg:
        raise InputError("cannot poll both status and custom output")

    # Exit if an invalid status is requested
    if (options.status and
            options.status not in TASK_STATUSES_ORDERED and
            options.status not in CylcWorkflowDBChecker.STATE_ALIASES):
        raise InputError(f"invalid status '{options.status}'")

    # this only runs locally
    if options.run_dir:
        run_dir = expand_path(options.run_dir)
    else:
        run_dir = get_cylc_run_dir()

    pollargs = {
        'workflow_id': workflow_id,
        'run_dir': run_dir,
        'task': options.task,
        'cycle': options.cycle,
        'status': options.status,
        'message': options.msg,
    }

    spoller = WorkflowPoller(
        "requested state",
        options.interval,
        options.max_polls,
        args=pollargs,
    )

    connected, formatted_pt = spoller.connect()

    if not connected:
        raise CylcError("cannot connect to the workflow_id DB")

    if options.status and options.task and options.cycle:
        # poll for a task status
        spoller.condition = options.status
        if not asyncio.run(spoller.poll()):
            sys.exit(1)
    elif options.msg and options.task and options.cycle:
        # poll for a custom task output
        spoller.condition = "output: %s" % options.msg
        if not asyncio.run(spoller.poll()):
            sys.exit(1)
    else:
        # just display query results
        spoller.checker.display_maps(
            spoller.checker.workflow_state_query(
                task=options.task,
                cycle=formatted_pt,
                status=options.status,
                message=options.msg,
            ))
