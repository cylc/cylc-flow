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
  $ cylc trigger WORKFLOW  # trigger all tasks in a running workflow
  # trigger some tasks in a running workflow:
  $ cylc trigger WORKFLOW TASK_GLOB ...

NOTE waiting tasks that are queue-limited will be queued if triggered, to
submit as normal when released by the queue; queued tasks will submit
immediately if triggered, even if that violates the queue limit (so you may
need to trigger a queue-limited task twice to get it to submit immediately).

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
  $reflow: Boolean,
  $flowDescr: String,
) {
  trigger (
    workflows: $wFlows,
    tasks: $tasks,
    reflow: $reflow,
    flowDescr: $flowDescr
  ) {
    result
  }
}
'''


def get_option_parser():
    parser = COP(
        __doc__, comms=True, multitask_nocycles=True,
        argdoc=[
            ('WORKFLOW', 'Workflow name or ID'),
            ('[TASK_GLOB ...]', 'Task matching patterns')])

    parser.add_option(
        "--reflow", action="store_true",
        dest="reflow", default=False,
        help="Start a new flow from the triggered task."
    )

    parser.add_option(
        "--meta", metavar="DESCRIPTION", action="store",
        dest="flow_descr", default=None,
        help="(with --reflow) a descriptive string for the new flow."
    )

    return parser


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', workflow: str, *task_globs: str):
    """CLI for "cylc trigger"."""
    if options.flow_descr and not options.reflow:
        parser.error("--meta requires --reflow")
    workflow, _ = parse_reg(workflow)
    pclient = get_client(workflow, timeout=options.comms_timeout)

    mutation_kwargs = {
        'request_string': MUTATION,
        'variables': {
            'wFlows': [workflow],
            'tasks': list(task_globs),
            'reflow': options.reflow,
            'flowDescr': options.flow_descr,
        }
    }

    pclient('graphql', mutation_kwargs)
