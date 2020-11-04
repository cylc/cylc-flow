#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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

Release a held workflow or tasks.

Examples:
  $ cylc release REG  # release the workflow
  $ cylc release REG TASK_GLOB ...  # release one or more tasks

Held tasks do not submit their jobs even if ready to run.

See also 'cylc hold'.
"""

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.network.client import SuiteRuntimeClient
from cylc.flow.terminal import cli_function

MUTATION = '''
mutation (
  $wFlows: [WorkflowID]!,
  $tasks: [NamespaceIDGlob],
) {
  release (
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
            ("REG", 'Suite name'),
            ('[TASK_GLOB ...]', 'Task matching patterns')])

    return parser


@cli_function(get_option_parser)
def main(parser, options, suite, *task_globs):
    pclient = SuiteRuntimeClient(suite, timeout=options.comms_timeout)

    mutation_kwargs = {
        'request_string': MUTATION,
        'variables': {
            'wFlows': [suite],
            'tasks': list(task_globs),
        }
    }

    pclient('graphql', mutation_kwargs)


if __name__ == "__main__":
    main()
