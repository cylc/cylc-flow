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

Manually trigger workflow tasks.

Examples:
  # trigger task foo in cycle 1234 in my_flow
  $ cylc trigger my_flow//1234/foo

  # trigger all failed tasks in my_flow
  $ cylc trigger 'my_flow//*:failed'

  # start a new "flow" by triggering 1234/foo
  $ cylc trigger --reflow my_flow//1234/foo

Manually triggering a task queues it to run regardless of satisfaction of its
prerequisites. (This refers to Cylc internal queues).

Manually triggering a queued task causes it to submit immediately, regardless
of the queue limit.

Manually triggering an active task has no effect, because multiple concurrent
instances of the same task job aren't allowed. Active tasks are in the
submitted or running states.

Manually triggering an incomplete task queues it to run again and continue its
assigned flow. Incomplete tasks finished without completing expected outputs.

Manually triggering an "active-waiting" task queues it to run immediately in
its flow. Active-waiting tasks have satisfied task-prerequisites but are held
back by queue limit, runahead limit, clock trigger, xtrigger, or task hold.
They are already assigned to a flow - that of the parent tasks that satisfied
their prerequisites.

Other tasks (those outside of the n=0 graph window) do not yet belong to a
flow. Manual triggering of these with --reflow will start a new flow; otherwise
only the triggered task will run.

"""

from functools import partial
from typing import TYPE_CHECKING

from cylc.flow.exceptions import UserInputError
from cylc.flow.network.client_factory import get_client
from cylc.flow.network.multi import call_multi
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.terminal import cli_function

if TYPE_CHECKING:
    from optparse import Values


MUTATION = '''
mutation (
  $wFlows: [WorkflowID]!,
  $tasks: [NamespaceIDGlob]!,
  $reflow: Boolean,
  $flowDescr: String,
) {
  trigger (
    workflows: $wFlows,
    tasks: $tasks,
    reflow: $reflow,
    flowDescr: $flowDescr
  ) {
    result
  }
}
'''


def get_option_parser():
    parser = COP(
        __doc__,
        comms=True,
        multitask=True,
        multiworkflow=True,
        argdoc=[('ID [ID ...]', 'Cycle/Family/Task ID(s)')],
    )

    parser.add_option(
        "--reflow", action="store_true",
        dest="reflow", default=False,
        help="Start a new flow from the triggered task."
    )

    parser.add_option(
        "--meta", metavar="DESCRIPTION", action="store",
        dest="flow_descr", default=None,
        help="(with --reflow) a descriptive string for the new flow."
    )

    return parser


async def run(options: 'Values', workflow_id: str, *tokens_list):
    pclient = get_client(workflow_id, timeout=options.comms_timeout)

    mutation_kwargs = {
        'request_string': MUTATION,
        'variables': {
            'wFlows': [workflow_id],
            'tasks': [
                tokens.relative_id
                for tokens in tokens_list
            ],
            'reflow': options.reflow,
            'flowDescr': options.flow_descr,
        }
    }

    await pclient.async_request('graphql', mutation_kwargs)


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', *ids: str):
    """CLI for "cylc trigger"."""
    if options.flow_descr and not options.reflow:
        raise UserInputError("--meta requires --reflow")
    call_multi(
        partial(run, options),
        *ids,
    )
