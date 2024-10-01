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

Force tasks to run regardless of prerequisites.

* Triggering an unqueued waiting task queues it, regardless of prerequisites.
* Triggering a queued task submits it, regardless of queue limiting.
* Triggering an active task has no effect (it already triggered).

Future tasks (n>0) do not already belong to a flow.
* by default they are assigned to all active flows
* otherwise, according to the --flow option

Active tasks (n=0) already belong to a flow.
* by default they run in the same flow
* with --flow=all, they are assigned to all active flows
* with --flow=INT or --flow=new, the new flow merges with the old one
* --flow=none is ignored

Note --flow=new increments the global flow counter so if you need multiple
commands to start a single new flow only use --flow=new in the first command,
then use the actual new flow number (e.g. read it from the scheduler log).

Examples:
  # trigger task foo in cycle 1234 in test
  $ cylc trigger test//1234/foo

  # trigger all failed tasks in test
  $ cylc trigger 'test//*:failed'

  # start a new flow by triggering 1234/foo in test
  $ cylc trigger --flow=new test//1234/foo
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
) {
  trigger (
    workflows: $wFlows,
    tasks: $tasks,
    flow: $flow,
    flowWait: $flowWait,
    flowDescr: $flowDescr
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
