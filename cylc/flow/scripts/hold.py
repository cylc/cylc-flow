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

Hold one or more tasks in a workflow.

Held tasks do not submit their jobs even if ready to run.

Examples:
  # Hold mytask at cycle point 1234 in my_flow (if it has not yet spawned, it
  # will hold as soon as it spawns)
  $ cylc hold my_flow mytask.1234

  # Hold all active tasks at cycle 1234 in my_flow (note: tasks before/after
  # this cycle point will not be held)
  $ cylc hold my_flow '*.1234'

  # Hold all active instances of mytask in my_flow (note: this will not hold
  # any unspawned tasks that might spawn in the future)
  $ cylc hold my_flow 'mytask.*'
  # or
  $ cylc hold my_flow mytask

  # Hold all active failed tasks
  $ cylc hold my_flow '*:failed'

  # Hold all tasks after cycle point 1234 in my_flow
  $ cylc hold my_flow --after=1234

Note: To pause a workflow (immediately preventing all job submission), use
'cylc pause' instead.

Note: globs and ":<state>" selectors will only match active tasks;
to hold future tasks when they spawn, use exact identifiers e.g. "mytask.1234".

See also 'cylc release'.
"""

from typing import TYPE_CHECKING

from cylc.flow.exceptions import UserInputError
from cylc.flow.network.client_factory import get_client
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.terminal import cli_function
from cylc.flow.workflow_files import parse_reg

if TYPE_CHECKING:
    from optparse import Values


HOLD_MUTATION = '''
mutation (
  $wFlows: [WorkflowID]!,
  $tasks: [NamespaceIDGlob]!
) {
  hold (
    workflows: $wFlows,
    tasks: $tasks
  ) {
    result
  }
}
'''

SET_HOLD_POINT_MUTATION = '''
mutation (
  $wFlows: [WorkflowID]!,
  $point: CyclePoint!
) {
  setHoldPoint (
    workflows: $wFlows,
    point: $point
  ) {
    result
  }
}
'''


def get_option_parser() -> COP:
    parser = COP(
        __doc__, comms=True, multitask=True,
        argdoc=[
            ('REG', "Workflow name"),
            # TODO: switch back to TASK_ID?
            ('[TASK_GLOB ...]', "Task matching patterns")]
    )

    parser.add_option(
        "--after",
        help="Hold all tasks after this cycle point.",
        metavar="CYCLE_POINT", action="store", dest="hold_point_string")

    return parser


def _validate(options: 'Values', *task_globs: str) -> None:
    """Check combination of options and task globs is valid."""
    if options.hold_point_string:
        if task_globs:
            raise UserInputError(
                "Cannot combine --after with TASK_GLOB(s).\n"
                "`cylc hold --after` holds all tasks after the given "
                "cycle point.")
    elif not task_globs:
        raise UserInputError(
            "Missing arguments: TASK_GLOB [...]. See `cylc hold --help`.")


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', workflow: str, *task_globs: str):

    _validate(options, *task_globs)

    workflow, _ = parse_reg(workflow)
    pclient = get_client(workflow, timeout=options.comms_timeout)

    if options.hold_point_string:
        mutation = SET_HOLD_POINT_MUTATION
        args = {'point': options.hold_point_string}
    else:
        mutation = HOLD_MUTATION
        args = {'tasks': list(task_globs)}

    mutation_kwargs = {
        'request_string': mutation,
        'variables': {
            'wFlows': [workflow],
            **args
        }
    }

    pclient('graphql', mutation_kwargs)


if __name__ == "__main__":
    main()
