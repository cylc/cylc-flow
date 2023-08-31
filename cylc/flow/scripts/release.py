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

"""cylc release [OPTIONS] ARGS

Release held tasks in a workflow.

Examples:
  # Release mytask at cycle 1234 in my_flow
  $ cylc release my_flow//1234/mytask

  # Release all active tasks at cycle 1234 in my_flow
  $ cylc release 'my_flow//1234/*'

  # Release all active instances of mytask in my_flow
  $ cylc release 'my_flow//*/mytask'

  # Release all held tasks and remove the hold point
  $ cylc release my_flow --all

Held tasks do not submit their jobs even if ready to run.

See also 'cylc hold'.
"""

from functools import partial
from typing import TYPE_CHECKING

from cylc.flow.exceptions import InputError
from cylc.flow.flow_mgr import validate_flow_opt
from cylc.flow.network.client_factory import get_client
from cylc.flow.network.multi import call_multi
from cylc.flow.option_parsers import (
    FULL_ID_MULTI_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow.terminal import cli_function

if TYPE_CHECKING:
    from optparse import Values


RELEASE_MUTATION = '''
mutation (
  $wFlows: [WorkflowID]!,
  $tasks: [NamespaceIDGlob]!,
  $flowNum: Int
) {
  release (
    workflows: $wFlows,
    tasks: $tasks,
    flowNum: $flowNum
  ) {
    result
  }
}
'''

RELEASE_HOLD_POINT_MUTATION = '''
mutation (
  $wFlows: [WorkflowID]!
) {
  releaseHoldPoint (
    workflows: $wFlows
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
        "--all",
        help=(
            "Release all held tasks and remove the 'hold after cycle point', "
            "if set."),
        action="store_true", dest="release_all")

    parser.add_option(
        "--flow",
        help="Release tasks that belong to a specific flow.",
        metavar="INT", action="store", dest="flow_num")

    return parser


def _validate(options: 'Values', *tokens_list: str) -> None:
    """Check combination of options and task globs is valid."""
    if options.release_all:
        if tokens_list:
            raise InputError("Cannot combine --all with Cycle/Task IDs")
    else:
        if not tokens_list:
            raise InputError(
                "Must define Cycles/Tasks. See `cylc release --help`."
            )

    validate_flow_opt(options.flow_num)
 

async def run(options: 'Values', workflow_id, *tokens_list):
    _validate(options, *tokens_list)

    pclient = get_client(workflow_id, timeout=options.comms_timeout)

    if options.release_all:
        mutation = RELEASE_HOLD_POINT_MUTATION
        args = {'tasks': ['*/*']}
    else:
        mutation = RELEASE_MUTATION
        args = {
            'tasks': [
                tokens.relative_id_with_selectors
                for tokens in tokens_list
            ],
            'flowNum': options.flow_num
        }

    mutation_kwargs = {
        'request_string': mutation,
        'variables': {
            'wFlows': [workflow_id],
            **args
        }
    }

    await pclient.async_request('graphql', mutation_kwargs)


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', *ids):
    call_multi(
        partial(run, options),
        *ids,
        constraint='mixed',
    )
