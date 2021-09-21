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

"""cylc set-outputs [OPTIONS] ARGS

Override the outputs of tasks in a running workflow.

Tell the scheduler that specified outputs (the "succeeded" output by default)
of tasks are complete.

Downstream tasks will be spawned or updated just as if the outputs were
completed normally.

The --output=OUTPUT option can be used multiple times on the command line.

"""

from optparse import Values

from cylc.flow.network.client_factory import get_client
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.terminal import cli_function
from cylc.flow.workflow_files import parse_reg

MUTATION = '''
mutation (
  $wFlows: [WorkflowID]!,
  $tasks: [NamespaceIDGlob]!,
  $outputs: [String],
) {
  setOutputs (
    workflows: $wFlows,
    tasks: $tasks,
    outputs: $outputs
  ) {
    result
  }
}
'''


def get_option_parser():
    parser = COP(
        __doc__, comms=True, multitask_nocycles=True,
        argdoc=[
            ("REG", "Workflow name"),
            ('TASK-GLOB [...]', 'Task match pattern')])
    parser.add_option(
        "--output", metavar="OUTPUT",
        help="Set task output OUTPUT completed, defaults to 'succeeded'.",
        action="append", dest="outputs")
    return parser


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', reg: str, *task_globs: str) -> None:
    reg, _ = parse_reg(reg)
    pclient = get_client(reg, timeout=options.comms_timeout)

    mutation_kwargs = {
        'request_string': MUTATION,
        'variables': {
            'wFlows': [reg],
            'tasks': list(task_globs),
            'outputs': options.outputs,
        }
    }

    pclient('graphql', mutation_kwargs)


if __name__ == "__main__":
    main()
