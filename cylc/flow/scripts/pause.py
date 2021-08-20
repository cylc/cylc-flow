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

"""cylc pause [OPTIONS] ARGS

Pause a workflow.

This prevents submission of any task jobs.

Examples:
  $ cylc pause my_flow

To resume a paused workflow, use 'cylc play'.

Not to be confused with `cylc hold`.
"""

from typing import TYPE_CHECKING

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.network.client import WorkflowRuntimeClient
from cylc.flow.terminal import cli_function
from cylc.flow.workflow_files import parse_reg

if TYPE_CHECKING:
    from optparse import Values


MUTATION = '''
mutation (
  $wFlows: [WorkflowID]!
) {
  pause (
    workflows: $wFlows
  ) {
    result
  }
}
'''


def get_option_parser():
    parser = COP(
        __doc__, comms=True, multitask=True,
        argdoc=[('REG', "Workflow name")]
    )
    return parser


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', workflow: str) -> None:
    workflow, _ = parse_reg(workflow)
    pclient = WorkflowRuntimeClient(workflow, timeout=options.comms_timeout)

    mutation_kwargs = {
        'request_string': MUTATION,
        'variables': {
            'wFlows': [workflow],
        }
    }

    pclient('graphql', mutation_kwargs)


if __name__ == '__main__':
    main()
