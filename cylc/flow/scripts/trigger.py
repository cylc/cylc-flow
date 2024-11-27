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

Manually trigger tasks to run regardless of their prerequisites.

In a paused workflow use --now to trigger tasks now; otherwise they will run
when the workflow is played (un-paused) again.

Triggering an already-active task (submitted, running) has no effect.

Two triggers may be needed to run a task if its queue is full:
* Triggering an unqueued waiting task queues it, regardless of prerequisites.
* Triggering a queued task submits it, regardless of queue limiting.

Examples:
  # trigger task foo in cycle 1234 in test
  $ cylc trigger test//1234/foo

  # trigger all failed tasks in test
  $ cylc trigger 'test//*:failed'

  # start a new flow by triggering 1234/foo in test
  $ cylc trigger --flow=new test//1234/foo

Flows:
  Active tasks (in the n=0 window) already belong to a flow.
  * by default, if triggered, they run in the same flow
  * or with --flow=all, they are assigned all active flows
  * or with --flow=INT or --flow=new, the original and new flows are merged
  * (--flow=none is ignored for active tasks)

  Inactive tasks (n>0) do not already belong to a flow.
  * by default they are assigned all active flows
  * otherwise, they are assigned the --flow value

  Note --flow=new increments the global flow counter with each use. If it
  takes multiple commands to start a new flow use the actual flow number
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
  $now: Boolean,
) {
  trigger (
    workflows: $wFlows,
    tasks: $tasks,
    flow: $flow,
    flowWait: $flowWait,
    flowDescr: $flowDescr,
    now: $now,
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
        "--now",
        help=r"Trigger now, even if the workflow is paused.",
        action="store_true",
        default=False,
        dest="now"
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
            'now': options.now,
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
