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

Manually trigger tasks.

Examples:
  $ cylc trigger REG  # trigger all tasks in a running workflow
  $ cylc trigger REG TASK_GLOB ...  # trigger some tasks in a running workflow

NOTE waiting tasks that are queue-limited will be queued if triggered, to
submit as normal when released by the queue; queued tasks will submit
immediately if triggered, even if that violates the queue limit (so you may
need to trigger a queue-limited task twice to get it to submit immediately).

"""

import os.path

from cylc.flow.network.client_factory import get_client
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.terminal import cli_function

MUTATION = '''
mutation (
  $wFlows: [WorkflowID]!,
  $tasks: [NamespaceIDGlob]!,
  $flow: String,
) {
  trigger (
    workflows: $wFlows,
    tasks: $tasks,
    flow: $flow
  ) {
    result
  }
}
'''


def get_option_parser():
    parser = COP(
        __doc__, comms=True, multitask_nocycles=True,
        argdoc=[
            ('REG', 'Workflow name'),
            ('[TASK_GLOB ...]', 'Task matching patterns')])

    parser.add_option(
        "-f", "--flow",
        metavar="FLOW",
        help="Start a new flow named FLOW from the triggered task.",
        action="store", default=None, dest="flow")

    return parser


@cli_function(get_option_parser)
def main(parser, options, workflow, *task_globs):
    """CLI for "cylc trigger"."""
    workflow = os.path.normpath(workflow)
    pclient = get_client(workflow, timeout=options.comms_timeout)

    mutation_kwargs = {
        'request_string': MUTATION,
        'variables': {
            'wFlows': [workflow],
            'tasks': list(task_globs),
            'flow': options.flow,
        }
    }

    pclient('graphql', mutation_kwargs)


if __name__ == "__main__":
    main()
