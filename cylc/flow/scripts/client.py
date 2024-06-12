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

"""cylc client [OPTIONS] ARGS

(This command is for internal use.)

Invoke workflow runtime client, expect JSON from STDIN for keyword arguments.
Use the -n option if client function requires no keyword arguments.
"""

from google.protobuf.json_format import MessageToDict
import json
import sys
from typing import TYPE_CHECKING, cast

from cylc.flow.id_cli import parse_id
from cylc.flow.option_parsers import (
    WORKFLOW_ID_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow.network.client import WorkflowRuntimeClient
from cylc.flow.network.server import PB_METHOD_MAP
from cylc.flow.terminal import cli_function

if TYPE_CHECKING:
    from optparse import Values
    from google.protobuf.message import Message


INTERNAL = True


def get_option_parser():
    parser = COP(
        __doc__, comms=True,
        argdoc=[
            WORKFLOW_ID_ARG_DOC,
            ('METHOD', 'Network API function name')
        ]
    )

    parser.add_option(
        '-n', '--no-input',
        help='Do not read from STDIN, assume null input',
        action='store_true', dest='no_input')

    return parser


@cli_function(get_option_parser)
def main(_, options: 'Values', workflow_id: str, func: str) -> None:
    workflow_id, *_ = parse_id(
        workflow_id,
        constraint='workflows',
    )
    pclient = WorkflowRuntimeClient(workflow_id, timeout=options.comms_timeout)
    if options.no_input:
        kwargs = {}
    else:
        kwargs = json.load(sys.stdin)
    sys.stdin.close()
    res = pclient(func, kwargs)
    if func in PB_METHOD_MAP:
        pb_msg: Message
        if 'element_type' in kwargs:
            pb_msg = PB_METHOD_MAP[func][kwargs['element_type']]()
        else:
            pb_msg = PB_METHOD_MAP[func]()
        pb_msg.ParseFromString(cast('bytes', res))
        res_msg: object = MessageToDict(pb_msg)
    else:
        res_msg = res
    sys.stdout.write(json.dumps(res_msg, indent=4) + '\n')
