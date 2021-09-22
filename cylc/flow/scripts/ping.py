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

If workflow REG is running or TASK in workflow REG is currently running,
exit with success status, else exit with error status."""

from ansimarkup import parse as cparse
import sys
from typing import Any, Dict, Optional, TYPE_CHECKING

from cylc.flow import ID_DELIM
from cylc.flow.exceptions import UserInputError
import cylc.flow.flags
from cylc.flow.network.client_factory import get_client
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.task_id import TaskID
from cylc.flow.task_state import TASK_STATUS_RUNNING
from cylc.flow.terminal import cli_function
from cylc.flow.workflow_files import parse_reg

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


def get_option_parser():
    parser = COP(
        __doc__, comms=True,
        argdoc=[('REG', 'Workflow name'), ('[TASK]', 'Task ' + TaskID.SYNTAX)])

    return parser


@cli_function(get_option_parser)
def main(
    parser: COP,
    options: 'Values',
    workflow: str,
    task_id: Optional[str] = None
) -> None:
    workflow, _ = parse_reg(workflow)
    pclient = get_client(workflow, timeout=options.comms_timeout)

    if task_id and not TaskID.is_valid_id(task_id):
        raise UserInputError("Invalid task ID: %s" % task_id)

    flow_kwargs = {
        'request_string': FLOW_QUERY,
        'variables': {'wFlows': [workflow]}
    }
    task_kwargs: Dict[str, Any] = {
        'request_string': TASK_QUERY,
    }
    # cylc ping WORKFLOW
    result = pclient('graphql', flow_kwargs)
    msg = ""
    for flow in result['workflows']:
        w_name = flow['name']
        w_port = flow['port']
        w_pub_port = flow['pubPort']
        if cylc.flow.flags.verbosity > 0:
            sys.stdout.write(
                f'{w_name} running on '
                f'{pclient.host}:{w_port} {w_pub_port}\n'
            )
        # cylc ping WORKFLOW TASKID
        if task_id:
            task, point = TaskID.split(task_id)
            w_id = flow['id']
            task_kwargs['variables'] = {
                'tProxy': f'{w_id}{ID_DELIM}{point}{ID_DELIM}{task}'
            }
            task_result = pclient('graphql', task_kwargs)
            if not task_result.get('taskProxy'):
                msg = "task not found"
            elif task_result['taskProxy']['state'] != TASK_STATUS_RUNNING:
                msg = f"task not {TASK_STATUS_RUNNING}"
            if msg:
                print(cparse(f'<red>{msg}</red>'))
                sys.exit(1)


if __name__ == "__main__":
    main()
