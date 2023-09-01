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

"""cylc hold [OPTIONS] ARGS

Hold task(s) in a workflow.

Held tasks do not submit their jobs even if ready to run.

To pause an entire workflow use "cylc pause".

Examples:
  # Hold mytask at cycle point 1234 in my_flow (if it has not yet spawned, it
  # will hold as soon as it spawns):
  $ cylc hold my_flow//1234/mytask

  # Hold all active tasks at cycle 1234 in my_flow (note: tasks before/after
  # this cycle point will not be held):
  $ cylc hold 'my_flow//1234/*'

  # Hold all active instances of mytask in my_flow (note: this will not hold
  # any unspawned tasks that might spawn in the future):
  $ cylc hold 'my_flow//*/mytask'

  # Hold all active failed tasks:
  $ cylc hold 'my_flow//*:failed'

  # Hold all tasks after cycle point 1234 in my_flow:
  $ cylc hold my_flow// --after=1234

  # Hold cycles 1, 2 & 3 in my_flow:
  $ cylc hold my_flow// //1 //2 //3

  # Hold cycle "1" in "my_flow_1" and "my_flow_2":
  $ cylc hold my_flow_1//1 my_flow_2//1

Note: To pause a workflow (immediately preventing all job submission), use
'cylc pause' instead.

See also 'cylc release'.
"""

from functools import partial
from typing import TYPE_CHECKING

from cylc.flow.exceptions import InputError
from cylc.flow.flow_mgr import validate_flow_opt
from cylc.flow.network.client_factory import get_client
from cylc.flow.option_parsers import (
    FULL_ID_MULTI_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow.terminal import cli_function
from cylc.flow.network.multi import call_multi


if TYPE_CHECKING:
    from optparse import Values


HOLD_MUTATION = '''
mutation (
  $wFlows: [WorkflowID]!,
  $tasks: [NamespaceIDGlob]!,
  $flowNum: Int
) {
  hold (
    workflows: $wFlows,
    tasks: $tasks,
    flowNum: $flowNum
  ) {
    result
  }
}
'''

SET_HOLD_POINT_MUTATION = '''
mutation (
  $wFlows: [WorkflowID]!,
  $point: CyclePoint!,
  $flowNum: Int
) {
  setHoldPoint (
    workflows: $wFlows,
    point: $point,
    flowNum: $flowNum
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
        "--after",
        help="Hold all tasks after this cycle point.",
        metavar="CYCLE_POINT", action="store", dest="hold_point_string")

    parser.add_option(
        "--flow",
        help="Hold tasks that belong to a specific flow.",
        metavar="INT", action="store", dest="flow_num")

    return parser


def _validate(options: 'Values', *task_globs: str) -> None:
    """Check combination of options and task globs is valid."""
    if options.hold_point_string:
        if task_globs:
            raise InputError(
                "Cannot combine --after with Cylc/Task IDs.\n"
                "`cylc hold --after` holds ALL tasks after the given "
                "cycle point. Can be used with `--flow`.")
    elif not task_globs:
        raise InputError(
            "Must define Cycles/Tasks. See `cylc hold --help`.")

    validate_flow_opt(options.flow_num)


async def run(options, workflow_id, *tokens_list):
    _validate(options, *tokens_list)

    pclient = get_client(workflow_id, timeout=options.comms_timeout)

    if options.hold_point_string:
        mutation = SET_HOLD_POINT_MUTATION
        args = {
            'point': options.hold_point_string,
            'flowNum': options.flow_num
        }
    else:
        mutation = HOLD_MUTATION
        args = {
            'tasks': [
                id_.relative_id_with_selectors
                for id_ in tokens_list
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
