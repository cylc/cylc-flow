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

"""cylc remove [OPTIONS] ARGS

Remove active (n=0) tasks, and erase flow history.

The primary use cases for this command are:
 * Remove final-status incomplete tasks from n=0 to prevent or release a stall,
   if you don't want to rerun them to complete required outputs.
 * Erase the flow history of tasks to allow them to rerun without starting a
   new flow. (Note that `cylc trigger` now does this automatically, however).

Tasks will be removed from ALL flows, by defaut.

Tasks removed from all flows, and any waiting downstream tasks spawned by
their outputs, will be recorded with no flow numbers and will not affect
the evolution of the workflow.

If you remove a task from some of its flows, it will still exist in the
remaining flows but will not affect the evolution of the removed flows.

Removing a submitted or running task also kills it (see "cylc kill").

Examples:
  # Remove a task that already ran.
  # (Any downstream tasks that are already running or finished will be
  # left alone. The task and its outputs will be left in the None flow.)
  $ cylc remove <id>

  # Remove a task from a specified flow.
  # (The task may remain in other flows)
  $ cylc remove <id> --flow=1
"""

from functools import partial
import sys
from typing import TYPE_CHECKING

from cylc.flow.flow_mgr import add_flow_opts_for_remove
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
  $flow: [Flow!],
  $noSpawn: Boolean,
) {
  remove (
    workflows: $wFlows,
    tasks: $tasks,
    flow: $flow,
    noSpawn: $noSpawn
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

    add_flow_opts_for_remove(parser)
    parser.add_option(
        "--no-spawn",
        help="Do not spawn successors before removal.",
        action="store_true", default=False, dest="no_spawn")
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
            'noSpawn': options.no_spawn,
        }
    }

    return await pclient.async_request('graphql', mutation_kwargs)


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', *ids: str):
    rets = call_multi(
        partial(run, options),
        *ids,
    )
    sys.exit(all(rets.values()) is False)
