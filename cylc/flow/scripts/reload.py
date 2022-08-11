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

"""cylc reload [OPTIONS] ARGS

Reload the configuration of a running workflow.

Example:
  # install and run the workflow
  $ cylc install
  $ cylc play my_workflow

  # make changes to the workflow source directory

  # reinstall the workflow
  $ cylc reinstall my_workflow

  # reload the workflow to pick up changes
  $ cylc reload my_workflow
  # the workflow is now running with the new config

All settings including task definitions, with the exception of workflow log
config, can be changed on reload. Changes to task definitions take effect
immediately, unless a task is already running at reload time.

Upon reload, remote file installation will be triggered for all relevant
platforms on the next job submit. Any changed files that are configured to be
included in the file installation will be transferred to the appropriate remote
platform(s).

If the workflow was started with Jinja2 template variables set on the command
line (cylc play --set 'FOO="bar"' WORKFLOW_ID) the same template settings apply
to the reload (only changes to the flow.cylc file itself are reloaded).

If the modified workflow definition does not parse, failure to reload will
be reported but no harm will be done to the running workflow.
"""

from functools import partial
import sys
from typing import TYPE_CHECKING

from cylc.flow.network.client_factory import get_client
from cylc.flow.network.multi import call_multi
from cylc.flow.option_parsers import (
    WORKFLOW_ID_MULTI_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow.terminal import cli_function

if TYPE_CHECKING:
    from optparse import Values


MUTATION = '''
mutation (
  $wFlows: [WorkflowID]!
) {
  reload (
    workflows: $wFlows
  ) {
    results
  }
}
'''


def get_option_parser():
    parser = COP(
        __doc__,
        comms=True,
        multiworkflow=True,
        argdoc=[WORKFLOW_ID_MULTI_ARG_DOC],
    )
    return parser


async def run(options: 'Values', workflow_id: str):
    pclient = get_client(workflow_id, timeout=options.comms_timeout)

    mutation_kwargs = {
        'request_string': MUTATION,
        'variables': {
            'wFlows': [workflow_id],
        }
    }

    return await pclient.async_request('graphql', mutation_kwargs)


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', *ids) -> None:
    reload_cli(options, *ids)


def reload_cli(options: 'Values', *ids) -> None:
    rets = call_multi(
        partial(run, options),
        *ids,
        constraint='workflows',
    )
    sys.exit(all(rets.values()) is False)
