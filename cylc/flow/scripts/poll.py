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

"""cylc poll [OPTIONS] ARGS

Poll pollable task jobs to verify and update their statuses in the scheduler.

This checks the job status file and queries the job runner on the job platform.

Pollable tasks are those in the n=0 window with an associated job ID, including
incomplete finished tasks.

Examples:
  $ cylc poll WORKFLOW  # poll all pollable tasks
  $ cylc poll WORKFLOW TASK_GLOB  # poll multiple pollable tasks or families
"""

from typing import TYPE_CHECKING

from cylc.flow.network.client_factory import get_client
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.terminal import cli_function
from cylc.flow.workflow_files import parse_reg

if TYPE_CHECKING:
    from optparse import Values


MUTATION = '''
mutation (
  $wFlows: [WorkflowID]!,
  $tasks: [NamespaceIDGlob]!,
) {
  poll (
    workflows: $wFlows,
    tasks: $tasks,
  ) {
    result
  }
}
'''


def get_option_parser():
    parser = COP(
        __doc__, comms=True, multitask=True,
        argdoc=[
            ('WORKFLOW', 'Workflow name or ID'),
            ('[TASK_GLOB ...]', 'Task matching patterns')]
    )
    return parser


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', workflow: str, *task_globs: str):
    workflow, _ = parse_reg(workflow)
    pclient = get_client(workflow, timeout=options.comms_timeout)

    mutation_kwargs = {
        'request_string': MUTATION,
        'variables': {
            'wFlows': [workflow],
            'tasks': list(task_globs),
        }
    }

    pclient('graphql', mutation_kwargs)
