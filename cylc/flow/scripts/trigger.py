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

"""cylc trigger [OPTIONS] ARGS

Force a group of tasks to run, respecting any dependencies within the group.

This command automatically identifies and satisfies the task (and xtrigger)
prerequisites of group start tasks, to start the flow; and the off-group
task (and xtrigger) prerequisites of other group members, to prevent a stall.
It leaves in-group prerequisites to be satisfied by the flow.

By default, it removes the flow history of target tasks to allow rerun in the
same flow. Alternatively, use the `--flow` option to trigger a new flow.

Triggering a task that is not yet queued will queue it; triggering a queued
task will run it - so un-queued tasks may need to be triggered twice.

Tasks can't be triggered if already preparing, submitted, or running a job.

If the workflow is paused, group start tasks will run immediately. The rest
of the group will run when the workflow is unpaused.

Use `-flow=all` to trigger without erasing flow history or starting a new flow,
e.g. to trigger a task twice with `--wait` to complete different outputs.

Group trigger automatically handles flow history and off-group prerequisites.
For a lower-level way to rerun a sub-graph of tasks, see `cylc set`.

Examples:
  # trigger task foo in cycle 1234 in test
  $ cylc trigger test//1234/foo

  # trigger all failed tasks in test
  $ cylc trigger 'test//*:failed'

  # start a new flow by triggering 1234/foo in test
  $ cylc trigger --flow=new test//1234/foo

  # rerun (same flow) `a => b & c` ignoring off-group prerequisite `off => b`
  $ cylc trigger test //1234/a //1234/b //1234/c

  # rerun (same flow) `a => b & c` ignoring `off => b`, the flow-native way
  $ cylc remove test //1234/a //1234/b //1234/c  # erase flow history
  $ cylc trigger test//1234/a  # trigger initial task
  $ cylc set --pre=1234/off test//1234/b  # satisfy off-flow prerequisites

Cylc queues:
  Queues limit how many tasks can be active (preparing, submitted, running) at
  once. Tasks that are ready to run will remained queued until the active task
  count drops below the queue limit.

Flows:
  Waiting tasks in the active window (n=0) already belong to a flow.
  * by default, if triggered, they run in the same flow
  * or with --flow=all, they are assigned all active flows
  * or with --flow=INT or --flow=new, the original and new flows are merged
  * (--flow=none is ignored for active tasks)

  Inactive tasks (n>0) do not already belong to a flow.
  * by default they are assigned all active flows
  * otherwise, they are assigned the --flow value

  Note --flow=new increments the global flow counter with each use. If it takes
  multiple commands to start a new flow use the actual flow number
  after the first command (you can read it from the scheduler log).
"""

from functools import partial
import sys
from typing import TYPE_CHECKING

from cylc.flow.network.client_factory import get_client
from cylc.flow.network.multi import call_multi
from cylc.flow.option_parsers import (
    FULL_ID_MULTI_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow.terminal import cli_function
from cylc.flow.flow_mgr import add_flow_opts


if TYPE_CHECKING:
    from optparse import Values


MUTATION = '''
mutation (
  $wFlows: [WorkflowID]!,
  $tasks: [NamespaceIDGlob]!,
  $flow: [Flow!],
  $flowWait: Boolean,
  $flowDescr: String,
  $onResume: Boolean,
) {
  trigger (
    workflows: $wFlows,
    tasks: $tasks,
    flow: $flow,
    flowWait: $flowWait,
    flowDescr: $flowDescr,
    onResume: $onResume,
  ) {
    result
  }
}
'''


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        comms=True,
        multitask=True,
        multiworkflow=True,
        argdoc=[FULL_ID_MULTI_ARG_DOC],
    )

    add_flow_opts(parser)

    parser.add_option(
        "--on-resume",
        help=(
            "If the workflow is paused, wait until it is resumed before "
            "running the triggered task(s). DEPRECATED - this will be "
            "removed at Cylc 8.5."
        ),
        action="store_true",
        default=False,
        dest="on_resume"
    )
    return parser


async def run(options: 'Values', workflow_id: str, *tokens_list):
    pclient = get_client(workflow_id, timeout=options.comms_timeout)

    mutation_kwargs = {
        'request_string': MUTATION,
        'variables': {
            'wFlows': [workflow_id],
            'tasks': [
                tokens.relative_id_with_selectors
                for tokens in tokens_list
            ],
            'flow': options.flow,
            'flowWait': options.flow_wait,
            'flowDescr': options.flow_descr,
            'onResume': options.on_resume,
        }
    }
    return await pclient.async_request('graphql', mutation_kwargs)


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', *ids: str):
    """CLI for "cylc trigger"."""
    rets = call_multi(
        partial(run, options),
        *ids,
    )
    sys.exit(all(rets.values()) is False)
