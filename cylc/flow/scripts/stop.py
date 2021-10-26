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

"""cylc stop [OPTIONS] ARGS

Tell a workflow to shut down.

By default stopping workflows wait for submitted and running tasks
to complete before shutting down. You can change this behaviour
with the "mode" option.

There are several shutdown methods:

  1. (default) stop after current active tasks finish
  2. (--now) stop immediately, orphaning current active tasks
  3. (--kill) stop after killing current active tasks
  4. (with STOP as a cycle point) stop after cycle point STOP
  5. (with STOP as a task ID) stop after task ID STOP has succeeded
  6. (--wall-clock=T) stop after time T (an ISO 8601 date-time format e.g.
     CCYYMMDDThh:mm, CCYY-MM-DDThh, etc).

Tasks that become ready after the shutdown is ordered will be submitted
immediately if the workflow is restarted.  Remaining task event handlers and
job poll and kill commands, however, will be executed prior to shutdown, unless
--now is used.

This command exits immediately unless --max-polls is greater than zero, in
which case it polls to wait for workflow shutdown."""

import sys
from typing import Optional, TYPE_CHECKING

from cylc.flow.command_polling import Poller
from cylc.flow.exceptions import ClientError, ClientTimeout, CylcError
from cylc.flow.network.client_factory import get_client
from cylc.flow.network.schema import WorkflowStopMode
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.task_id import TaskID
from cylc.flow.terminal import cli_function
from cylc.flow.workflow_files import parse_reg

if TYPE_CHECKING:
    from optparse import Values


MUTATION = '''
mutation (
  $wFlows: [WorkflowID]!,
  $stopMode: WorkflowStopMode,
  $cyclePoint: CyclePoint,
  $clockTime: TimePoint,
  $task: TaskID,
  $flowNum: Int,
) {
  stop (
    workflows: $wFlows,
    mode: $stopMode,
    cyclePoint: $cyclePoint,
    clockTime: $clockTime,
    task: $task,
    flowNum: $flowNum
  ) {
    result
  }
}
'''

POLLER_QUERY = '''
query ($wFlows: [ID]) {
  workflows(ids: $wFlows) {
    id
  }
}
'''


class StopPoller(Poller):
    """A polling object that checks if a workflow has stopped yet."""

    def __init__(self, pclient, condition, interval, max_polls):
        Poller.__init__(self, condition, interval, max_polls, None)
        self.pclient = pclient
        self.query = {
            'request_string': POLLER_QUERY,
            'variables': {'wFlows': [self.pclient.workflow]}
        }

    def check(self):
        """Return True if workflow has stopped (success) else False"""
        try:
            self.pclient('graphql', self.query)
        except (ClientError, ClientTimeout, CylcError):
            # failed to ping - workflow stopped or (CylcError) restarted on
            # another host:port (in which case it must have stopped first).
            return True
        else:
            # pinged - workflow must be alive
            return False


def get_option_parser():
    parser = COP(
        __doc__, comms=True,
        argdoc=[("WORKFLOW", "Workflow name or ID"),
                ("[STOP]", "task POINT (cycle point), or TASK (task ID).")]
    )

    parser.add_option(
        "-k", "--kill",
        help="Shut down after killing currently active tasks.",
        action="store_true", default=False, dest="kill")

    parser.add_option(
        "--flow", metavar="INT",
        help="Stop flow number INT from spawning more tasks. "
             "The scheduler will shut down if it is the only flow.",
        action="store", dest="flow_num")

    parser.add_option(
        "-n", "--now",
        help=(
            "Shut down without waiting for active tasks to complete." +
            " If this option is specified once," +
            " wait for task event handler, job poll/kill to complete." +
            " If this option is specified more than once," +
            " tell the workflow to terminate immediately."),
        action="count", default=0, dest="now")

    parser.add_option(
        "-w", "--wall-clock", metavar="STOP",
        help="Shut down after time STOP (ISO 8601 formatted)",
        action="store", dest="wall_clock")

    StopPoller.add_to_cmd_options(parser, d_max_polls=0)

    return parser


@cli_function(get_option_parser)
def main(
    parser: COP,
    options: 'Values',
    reg: str,
    shutdown_arg: Optional[str] = None
) -> None:
    if shutdown_arg is not None and options.kill:
        parser.error("ERROR: --kill is not compatible with [STOP]")

    if options.kill and options.now:
        parser.error("ERROR: --kill is not compatible with --now")

    if options.flow_num and int(options.max_polls) > 0:
        parser.error("ERROR: --flow is not compatible with --max-polls")

    reg, _ = parse_reg(reg)
    pclient = get_client(reg, timeout=options.comms_timeout)

    if int(options.max_polls) > 0:
        # (test to avoid the "nothing to do" warning for # --max-polls=0)
        spoller = StopPoller(
            pclient, "workflow stopped", options.interval, options.max_polls)

    # mode defaults to 'Clean'
    mode = None
    task = None
    cycle_point = None
    if shutdown_arg is not None and TaskID.is_valid_id(shutdown_arg):
        # STOP argument detected
        task = shutdown_arg
    elif shutdown_arg is not None:
        # not a task ID, may be a cycle point
        cycle_point = shutdown_arg
    elif options.kill:
        mode = WorkflowStopMode.Kill.name
    elif options.now > 1:
        mode = WorkflowStopMode.NowNow.name
    elif options.now:
        mode = WorkflowStopMode.Now.name

    mutation_kwargs = {
        'request_string': MUTATION,
        'variables': {
            'wFlows': [reg],
            'stopMode': mode,
            'cyclePoint': cycle_point,
            'clockTime': options.wall_clock,
            'task': task,
            'flowNum': options.flow_num
        }
    }

    pclient('graphql', mutation_kwargs)

    if int(options.max_polls) > 0 and not spoller.poll():
        # (test to avoid the "nothing to do" warning for # --max-polls=0)
        sys.exit(1)
