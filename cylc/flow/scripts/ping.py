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

"""cylc ping [OPTIONS] ARGS

Test communication with running workflows.

Print the HOST:PORT of running workflows.
If any are not running, exit with error status.
"""

from functools import partial
import sys
from typing import Any, Dict, TYPE_CHECKING

from cylc.flow.network.client_factory import get_client
from cylc.flow.network.multi import call_multi
from cylc.flow.option_parsers import (
    ID_MULTI_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow.terminal import cli_function

if TYPE_CHECKING:
    from optparse import Values


FLOW_QUERY = '''
query ($wFlows: [ID]) {
  workflows(ids: $wFlows) {
    id
    name
    port
  }
}
'''


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        comms=True,
        multiworkflow=True,
        argdoc=[ID_MULTI_ARG_DOC],
    )

    return parser


async def run(
    options: 'Values',
    workflow_id: str,
    client=None
) -> Dict:

    pclient = client or get_client(workflow_id, timeout=options.comms_timeout)

    ret: Dict[str, Any] = {
        'stdout': [],
        'stderr': [],
        'exit': 0
    }
    flow_kwargs: Dict[str, Any] = {
        'request_string': FLOW_QUERY,
        'variables': {'wFlows': [workflow_id]}
    }

    result = await pclient.async_request('graphql', flow_kwargs)

    for flow in result['workflows']:
        ret['stdout'].append(f"{pclient.host}:{flow['port']}")
    return ret


def report(response):
    return (
        '\n'.join(response['stdout']),
        '\n'.join(response['stderr']),
        response['exit'] == 0,
    )


@cli_function(get_option_parser)
def main(
    parser: COP,
    options: 'Values',
    *ids,
) -> None:
    rets = call_multi(
        partial(run, options),
        *ids,
        report=report,
        constraint='workflows',
    )
    sys.exit(all(rets.values()) is False)
