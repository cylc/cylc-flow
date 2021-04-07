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

"""cylc ping [OPTIONS] ARGS

Test communication with a running suite.

If workflow REG is running or TASK in workflow REG is currently running,
exit with success status, else exit with error status."""

import sys

from ansimarkup import parse as cparse

from cylc.flow import ID_DELIM
from cylc.flow.exceptions import UserInputError
import cylc.flow.flags
from cylc.flow.network.client_factory import get_client
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.task_id import TaskID
from cylc.flow.task_state import TASK_STATUS_RUNNING
from cylc.flow.terminal import cli_function

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
        argdoc=[('REG', 'Suite name'), ('[TASK]', 'Task ' + TaskID.SYNTAX)])

    return parser


@cli_function(get_option_parser)
def main(parser, options, suite, task_id=None):
    pclient = get_client(suite, timeout=options.comms_timeout)

    if task_id and not TaskID.is_valid_id(task_id):
        raise UserInputError("Invalid task ID: %s" % task_id)

    flow_kwargs = {
        'request_string': FLOW_QUERY,
        'variables': {'wFlows': [suite]}
    }
    task_kwargs = {
        'request_string': TASK_QUERY,
    }
    # cylc ping SUITE
    result = pclient('graphql', flow_kwargs)
    msg = ""
    for flow in result['workflows']:
        w_name = flow['name']
        w_port = flow['port']
        w_pub_port = flow['pubPort']
        if cylc.flow.flags.verbose:
            sys.stdout.write(
                f'{w_name} running on '
                f'{pclient.host}:{w_port} {w_pub_port}\n'
            )
        # cylc ping workflow TASKID
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
