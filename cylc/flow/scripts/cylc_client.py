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

"""cylc client [OPTIONS] ARGS

(This command is for internal use.)
Invoke suite runtime client, expect JSON from STDIN for keyword arguments.
Use the -n option if client function requires no keyword arguments.
"""

import json
import sys

from google.protobuf.json_format import MessageToDict

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.network.client import SuiteRuntimeClient
from cylc.flow.terminal import cli_function
from cylc.flow.network.server import PB_METHOD_MAP


def get_option_parser():
    parser = COP(__doc__, comms=True, argdoc=[
        ('REG', 'Suite name'),
        ('METHOD', 'Network API function name')])

    parser.add_option(
        '-n', '--no-input',
        help='Do not read from STDIN, assume null input',
        action='store_true', dest='no_input')

    return parser


@cli_function(get_option_parser)
def main(_, options, suite, func):
    pclient = SuiteRuntimeClient(
        suite, options.owner, options.host, options.port)
    if options.no_input:
        kwargs = {}
    else:
        kwargs = json.load(sys.stdin)
    sys.stdin.close()
    res = pclient(func, kwargs, timeout=options.comms_timeout)
    if func in PB_METHOD_MAP:
        if 'element_type' in kwargs:
            pb_msg = PB_METHOD_MAP[func][kwargs['element_type']]()
        else:
            pb_msg = PB_METHOD_MAP[func]()
        pb_msg.ParseFromString(res)
        res_msg = MessageToDict(pb_msg)
    else:
        res_msg = res
    sys.stdout.write(json.dumps(res_msg, indent=4) + '\n')


if __name__ == '__main__':
    main()
