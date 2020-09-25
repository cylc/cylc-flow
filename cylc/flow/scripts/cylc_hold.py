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

"""cylc [control] hold [OPTIONS] ARGS

Hold a workflow or tasks:
  cylc hold REG - hold a workflow
  cylc hold REG TASK_GLOB ... - hold one or more tasks in a workflow

Held tasks do not submit their jobs even if ready to run.

See also 'cylc [control] release'.
"""

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.network.client import SuiteRuntimeClient
from cylc.flow.terminal import cli_function

MUTATION = '''
mutation (
  $wFlows: [WorkflowID]!,
  $tasks: [NamespaceIDGlob],
  $time: TimePoint
) {
  hold (
    workflows: $wFlows,
    tasks: $tasks,
    time: $time
  ) {
    result
  }
}
'''


def get_option_parser():
    parser = COP(
        __doc__, comms=True, multitask=True,
        argdoc=[
            ("REG", "Suite name"),
            ('[TASK_GLOB ...]', 'Task matching patterns')])

    parser.add_option(
        "--after",
        help="Hold whole suite AFTER this cycle point.",
        metavar="CYCLE_POINT", action="store", dest="hold_point_string")

    return parser


@cli_function(get_option_parser)
def main(parser, options, suite, *task_globs):
    pclient = SuiteRuntimeClient(suite, timeout=options.comms_timeout)

    mutation_kwargs = {
        'request_string': MUTATION,
        'variables': {
            'wFlows': [suite],
            'tasks': list(task_globs),
            'time': options.hold_point_string,
        }
    }

    pclient('graphql', mutation_kwargs)


if __name__ == "__main__":
    main()
