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

"""cylc set-verbosity [OPTIONS] ARGS

Change the logging severity level of a running workflow.

Only messages at or above the chosen severity level will be logged; for
example, if you choose WARNING, only warnings and critical messages will be
logged.
"""

from functools import partial
from optparse import Values

from cylc.flow import LOG_LEVELS
from cylc.flow.exceptions import InputError
from cylc.flow.network.client_factory import get_client
from cylc.flow.network.multi import call_multi
from cylc.flow.option_parsers import (
    WORKFLOW_ID_MULTI_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow.terminal import cli_function

MUTATION = '''
mutation (
  $wFlows: [WorkflowID]!,
  $level: LogLevels!,
) {
  setVerbosity (
    workflows: $wFlows,
    level: $level,
  ) {
    result
  }
}
'''


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        comms=True,
        multiworkflow=True,
        argdoc=[
            ('LEVEL', ', '.join(LOG_LEVELS.keys())),
            WORKFLOW_ID_MULTI_ARG_DOC,
        ]
    )
    return parser


async def run(options: 'Values', severity: str, workflow_id: str) -> None:
    pclient = get_client(workflow_id, timeout=options.comms_timeout)

    mutation_kwargs = {
        'request_string': MUTATION,
        'variables': {
            'wFlows': [workflow_id],
            'level': severity,
        }
    }

    await pclient.async_request('graphql', mutation_kwargs)


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', severity: str, *ids: str) -> None:
    if severity not in LOG_LEVELS:
        raise InputError(f"Illegal logging level, {severity}")
    call_multi(
        partial(run, options, severity),
        *ids,
        constraint='workflows',
    )
