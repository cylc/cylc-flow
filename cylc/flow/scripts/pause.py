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

This suspends submission of all tasks in a workflow.

Examples:
  # pause my_workflow
  $ cylc pause my_workflow

  # resume my_workflow
  $ cylc play my_workflow

(Not to be confused with `cylc hold` which suspends submission of individual
tasks within a workflow).
"""

from functools import partial
from typing import TYPE_CHECKING

from cylc.flow.option_parsers import (
    WORKFLOW_ID_MULTI_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow.network.client import WorkflowRuntimeClient
from cylc.flow.network.multi import call_multi
from cylc.flow.terminal import cli_function

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


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        comms=True,
        multitask=False,
        multiworkflow=True,
        argdoc=[WORKFLOW_ID_MULTI_ARG_DOC],
    )
    return parser


async def run(options: 'Values', workflow_id: str) -> None:
    pclient = WorkflowRuntimeClient(workflow_id, timeout=options.comms_timeout)

    mutation_kwargs = {
        'request_string': MUTATION,
        'variables': {
            'wFlows': [workflow_id],
        }
    }

    await pclient.async_request('graphql', mutation_kwargs)


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', *ids) -> None:
    call_multi(
        partial(run, options),
        *ids,
        constraint='workflows',
    )
