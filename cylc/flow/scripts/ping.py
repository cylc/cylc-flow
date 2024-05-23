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

Test communication with a running workflow.

If workflow WORKFLOW is running or TASK in WORKFLOW is currently running,
exit with success status, else exit with error status.
"""

from functools import partial
import sys
from typing import Any, Dict, TYPE_CHECKING

import cylc.flow.flags
from cylc.flow.network.client_factory import get_client
from cylc.flow.network.multi import call_multi
from cylc.flow.option_parsers import (
    FULL_ID_MULTI_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow.task_state import TASK_STATUS_RUNNING
from cylc.flow.terminal import cli_function

if TYPE_CHECKING:
    from optparse import Values


FLOW_QUERY = '''
query ($wFlows: [ID]) {
  workflows(ids: $wFlows) {
    id
    name
    port
    pubPort
  }
}
'''

TASK_QUERY = '''
query ($tProxy: ID!) {
  taskProxy (id: $tProxy) {
    state
    id
  }
}
'''


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        comms=True,
        multitask=True,
        multiworkflow=True,
        argdoc=[FULL_ID_MULTI_ARG_DOC],
    )

    return parser


async def run(
    options: 'Values',
    workflow_id: str,
    *tokens_list,
) -> Dict:
    pclient = get_client(workflow_id, timeout=options.comms_timeout)

    ret: Dict[str, Any] = {
        'stdout': [],
        'stderr': [],
        'exit': 0
    }
    flow_kwargs: Dict[str, Any] = {
        'request_string': FLOW_QUERY,
        'variables': {'wFlows': [workflow_id]}
    }
    task_kwargs: Dict[str, Any] = {
        'request_string': TASK_QUERY,
    }

    # ping called on the workflow
    result = await pclient.async_request('graphql', flow_kwargs)
    msg = ""
    for flow in result['workflows']:
        w_name = flow['name']
        w_port = flow['port']
        w_pub_port = flow['pubPort']
        if cylc.flow.flags.verbosity > 0:
            ret['stdout'].append(
                f'{w_name} running on '
                f'{pclient.host}:{w_port} {w_pub_port}\n'
            )

        # ping called with task-like objects
        for tokens in tokens_list:
            task_kwargs['variables'] = {
                'tProxy': tokens.relative_id
            }
            task_result = await pclient.async_request('graphql', task_kwargs)
            string_id = tokens.relative_id
            if not task_result.get('taskProxy'):
                msg = f"task not found: {string_id}"
            elif task_result['taskProxy']['state'] != TASK_STATUS_RUNNING:
                msg = f"task not {TASK_STATUS_RUNNING}: {string_id}"
            if msg:
                ret['stderr'].append(msg)
                ret['exit'] = 1

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
        constraint='mixed',
    )
    sys.exit(all(rets.values()) is False)
