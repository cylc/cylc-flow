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

"""cylc set-outputs [OPTIONS] ARGS

Artificially satisfy task outputs.

Mark task outputs as completed and spawn downstream tasks that depend on those
outputs. By default it marks tasks as succeeded.

This allows you to manually intervene with Cylc's scheduling algorithm by
artificially satisfying outputs of tasks.

If a flow number is given, the child tasks will start (or continue) that flow.

Examples:
  # For example, for the following dependency graph:
  R1 = '''
     a => b & c => d
     foo:x => bar => baz
  '''

  # spawn 1/b and 1/c, but 1/d will not subsequently run
  $ cylc set-outputs my_workflow//1/a

  # spawn 1/b and 1/c as flow 2, followed by 1/d
  $ cylc set-outputs --flow=2 my_workflow//1/a

  # spawn 1/bar as flow 3, followed by 1/baz
  $ cylc set-outputs --flow=3 --output=x my_workflow//1/foo

Use --output multiple times to spawn off of several outputs at once.
"""

from functools import partial
from typing import TYPE_CHECKING

from cylc.flow.network.client_factory import get_client
from cylc.flow.network.multi import call_multi
from cylc.flow.option_parsers import (
    FULL_ID_MULTI_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow.terminal import cli_function

if TYPE_CHECKING:
    from optparse import Values

MUTATION = '''
mutation (
  $wFlows: [WorkflowID]!,
  $tasks: [NamespaceIDGlob]!,
  $outputs: [String],
  $flowNum: Int,
) {
  setOutputs (
    workflows: $wFlows,
    tasks: $tasks,
    outputs: $outputs,
    flowNum: $flowNum,
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

    parser.add_option(
        "-o", "--output", metavar="OUTPUT",
        help="Set OUTPUT (default \"succeeded\") completed.",
        action="append", default=None, dest="outputs")

    parser.add_option(
        "-f", "--flow", metavar="FLOW",
        help="Number of the flow to attribute the outputs.",
        action="store", default=None, dest="flow_num")

    return parser


async def run(options: 'Values', workflow_id: str, *tokens_list) -> None:
    pclient = get_client(workflow_id, timeout=options.comms_timeout)

    mutation_kwargs = {
        'request_string': MUTATION,
        'variables': {
            'wFlows': [workflow_id],
            'tasks': [
                tokens.relative_id_with_selectors
                for tokens in tokens_list
            ],
            'outputs': options.outputs,
            'flowNum': options.flow_num
        }
    }

    await pclient.async_request('graphql', mutation_kwargs)


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', *ids) -> None:
    call_multi(
        partial(run, options),
        *ids,
    )
