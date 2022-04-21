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

"""cylc get-workflow-version [OPTIONS] ARGS

Find out what version of Cylc a running workflow is using.

To find the version you've invoked at the command line see "cylc version".
"""

from functools import partial
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


QUERY = '''
query ($wFlows: [ID]) {
  workflows(ids: $wFlows) {
    id
    name
    owner
    cylcVersion
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


async def run(options, workflow_id, *_):
    pclient = get_client(workflow_id, timeout=options.comms_timeout)

    query_kwargs = {
        'request_string': QUERY,
        'variables': {'wFlows': [workflow_id]}
    }

    result = await pclient.async_request('graphql', query_kwargs)

    for workflow in result['workflows']:
        return workflow['cylcVersion']


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', workflow_id: str) -> None:
    call_multi(
        partial(run, options),
        workflow_id,
        report=print,
        # we need the mixed format for call_multi but don't want any tasks
        constraint='mixed',
        max_tasks=0,
    )
