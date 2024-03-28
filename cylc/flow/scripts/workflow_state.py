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

Retrieve task states from the workflow database.

Print task states retrieved from a workflow database; or (with --task,
--point, and --status) poll until a given task reaches a given state; or (with
--task, --point, and --message) poll until a task receives a given message.
Polling is configurable with --interval and --max-polls; for a one-off
check use --max-polls=1. The workflow database does not need to exist at
the time polling commences but allocated polls are consumed waiting for
it (consider max-polls*interval as an overall timeout).

Note for non-cycling tasks --point=1 must be provided.

For your own workflows the database location is determined by your
site/user config. For other workflows, e.g. those owned by others, or
mirrored workflow databases, use --run-dir=DIR to specify the location.

Examples:
  $ cylc workflow-state WORKFLOW_ID --task=TASK --point=POINT --status=STATUS
  # returns 0 if TASK.POINT reaches STATUS before the maximum number of
  # polls, otherwise returns 1.

  $ cylc workflow-state WORKFLOW_ID --task=TASK --point=POINT --status=STATUS \
  > --offset=PT6H
  # adds 6 hours to the value of CYCLE for carrying out the polling operation.

  $ cylc workflow-state WORKFLOW_ID --task=TASK --status=STATUS --task-point
  # uses CYLC_TASK_CYCLE_POINT environment variable as the value for the
  # CYCLE to poll. This is useful when you want to use cylc workflow-state in a
  # cylc task.
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
            try:
                fmt = self.checker.get_remote_point_format()
            except sqlite3.OperationalError as exc:
                try:
                    fmt = self.checker.get_remote_point_format_compat()
                except sqlite3.OperationalError:
                    raise exc  # original error
            if fmt:
                my_parser = TimePointParser()
                my_point = my_parser.parse(self.args['cycle'], dump_format=fmt)
                self.args['cycle'] = str(my_point)
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
        "-t", "--task", help="Specify a task to check the state of.",
        action="store", dest="task", default=None)

    parser.add_option(
        "-p", "--point",
        help="Specify the cycle point to check task states for.",
        action="store", dest="cycle", default=None)

    parser.add_option(
        "-T", "--task-point",
        help="Use the CYLC_TASK_CYCLE_POINT environment variable as the "
             "cycle point to check task states for. "
             "Shorthand for --point=$CYLC_TASK_CYCLE_POINT",
        action="store_true", dest="use_task_point", default=False)

    parser.add_option(
        "-d", "--run-dir",
        help="The top level cylc run directory if non-standard. The "
             "database should be DIR/WORKFLOW_ID/log/db. Use to interrogate "
             "workflows owned by others, etc.; see note above.",
        metavar="DIR", action="store", dest="alt_run_dir", default=None)

    parser.add_option(
        "-s", "--offset",
        help="Specify an offset to add to the targeted cycle point",
        action="store", dest="offset", default=None)

    conds = ("Valid triggering conditions to check for include: '" +
             ("', '").join(
                 sorted(CylcWorkflowDBChecker.STATE_ALIASES.keys())[:-1]) +
             "' and '" + sorted(
                 CylcWorkflowDBChecker.STATE_ALIASES.keys())[-1] + "'. ")
    states = ("Valid states to check for include: '" +
              ("', '").join(TASK_STATUSES_ORDERED[:-1]) +
              "' and '" + TASK_STATUSES_ORDERED[-1] + "'.")

    parser.add_option(
        "-S", "--status",
        help="Specify a particular status or triggering condition to "
             f"check for. {conds}{states}",
        action="store", dest="status", default=None)

    parser.add_option(
        "-O", "--output", "-m", "--message",
        help="Check custom task output by message string or trigger string.",
        action="store", dest="msg", default=None)

    WorkflowPoller.add_to_cmd_options(parser)

    return parser


@cli_function(get_option_parser, remove_opts=["--db"])
def main(parser: COP, options: 'Values', workflow_id: str) -> None:

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

    if options.msg and not options.task and not options.cycle:
        raise InputError("need a taskname and cyclepoint")

    # Exit if an invalid status is requested
    if (options.status and
            options.status not in TASK_STATUSES_ORDERED and
            options.status not in CylcWorkflowDBChecker.STATE_ALIASES):
        raise InputError(f"invalid status '{options.status}'")

    # this only runs locally
    if options.alt_run_dir:
        run_dir = alt_run_dir = expand_path(options.alt_run_dir)
    else:
        run_dir = get_cylc_run_dir()
        alt_run_dir = None

    workflow_id, *_ = parse_id(
        workflow_id,
        constraint='workflows',
        alt_run_dir=alt_run_dir
    )

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
        # check a task status
        spoller.condition = options.status
        if not asyncio.run(spoller.poll()):
            sys.exit(1)
    elif options.msg:
        # Check for a custom task output
        spoller.condition = "output: %s" % options.msg
        if not asyncio.run(spoller.poll()):
            sys.exit(1)
    else:
        # just display query results
        spoller.checker.display_maps(
            spoller.checker.workflow_state_query(
                task=options.task,
                cycle=formatted_pt,
                status=options.status))
