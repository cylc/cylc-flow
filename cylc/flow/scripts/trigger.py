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

Force one or more tasks to run, respecting dependencies within the group.

This command provides a convenient way to rerun a past sub-graph. It erases
the flow history of the group (by default) to allow rerun in the same flow;
it satisfies off-group task and xtrigger prerequisites to start the flow and
prevent a stall; and it leaves in-group prerequisites to the triggered flow.

Triggering a task that is not yet queued, queues it. Triggering a queued task
runs it. You many need to trigger unqueued tasks twice to run them immediately.

Preparing, submitted, or running tasks will be ignored: they already triggered.

If you trigger tasks when the workflow is paused, only group start tasks will
run immediately. The flow will continue when you resume the workflow.

Note that the flow will only continue from group start tasks if you erase the
original flow (the default) or use `--flow` options to start a new flow.

See `cylc set` for the lower-level flow-based approach to rerunning sub-graphs.

Examples:
  # trigger task foo in cycle 1, in workflow "test"
  $ cylc trigger test//1/foo

  # trigger all failed tasks in workfow "test"
  $ cylc trigger 'test//*:failed'  # (quotes required)

  # start a new flow from 1/foo
  # (beware of off-flow prerequisites downstream of 1/foo)
  $ cylc trigger --flow=new test//1/foo

  # rerun sub-graph "a => b & c" in the same flow, ignoring "off => b"
  $ cylc trigger test //1/a //1/b //1/c

Triggering and flow numbers:
  Waiting n=0 tasks already belong to a flow; if triggered:
  * by default, they run in the same flow, or
  * with --flow=all, they will be assigned all active flows, or
  * with --flow=INT or --flow=new, the original and new flows will be merged
  * (--flow=none is ignored for n=0 tasks)

  Inactive tasks (n>0) do not already belong to a flow; if triggered:
  * by default they are assigned all active flows
  * otherwise, they are assigned the --flow value

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
