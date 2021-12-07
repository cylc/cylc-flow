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

Note: globs and ":<state>" selectors will only match active tasks;
to release future tasks, use exact identifiers e.g. "1234/mytask".

See also 'cylc hold'.
"""

from functools import partial
from typing import TYPE_CHECKING

from cylc.flow.exceptions import UserInputError
from cylc.flow.network.client_factory import get_client
from cylc.flow.id_cli import call_multi
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.terminal import cli_function

if TYPE_CHECKING:
    from optparse import Values


RELEASE_MUTATION = '''
mutation (
  $wFlows: [WorkflowID]!,
  $tasks: [NamespaceIDGlob]!
) {
  release (
    workflows: $wFlows,
    tasks: $tasks,
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
        argdoc=[('ID [ID ...]', 'Cycle/Family/Task ID(s)')],
    )

    parser.add_option(
        "--all",
        help=(
            "Release all held tasks and remove the 'hold after cycle point', "
            "if set."),
        action="store_true", dest="release_all")

    return parser


def _validate(options: 'Values', *task_globs: str) -> None:
    """Check combination of options and task globs is valid."""
    if options.release_all:
        if task_globs:
            raise UserInputError("Cannot combine --all with TASK_GLOB(s).")
    else:
        if not task_globs:
            raise UserInputError(
                "Missing arguments: TASK_GLOB [...]. "
                "See `cylc release --help`.")


async def run(options: 'Values', workflow, *ids):
    _validate(options, *ids)

    pclient = get_client(workflow, timeout=options.comms_timeout)

    if options.release_all:
        mutation = RELEASE_HOLD_POINT_MUTATION
        args = {}
    else:
        mutation = RELEASE_MUTATION
        args = {'tasks': list(ids)}

    mutation_kwargs = {
        'request_string': mutation,
        'variables': {
            'wFlows': [workflow],
            **args
        }
    }

    await pclient.async_request('graphql', mutation_kwargs)


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', *ids):
    call_multi(
        partial(run, options),
        *ids,
    )
