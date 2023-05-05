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
"""cylc get-resources [OPTIONS] ARGS

Extract resources from the cylc.flow package.

If the directory is omitted the resource will be copied either to your
current working directory for regular resources, or to the first configured
"source" directory (~/cylc-src by default) for the tutorials.

Examples:
    # list all resources
    $ cylc get-resources --list

    # copy the Cylc wrapper script to the current directory:
    $ cylc get-resources cylc

    # copy the Cylc wrapper script to a/b/c:
    $ cylc get-resources cylc a/b/c

    # copy the "runtime-tutorial" to your "source" directory:
    $ cylc get-resources tutorial/runtime-tutorial

    # copy all of the tutorials to your "source" directory:
    $ cylc get-resources tutorial
"""

import sys

from cylc.flow import LOG
import cylc.flow.flags
from cylc.flow.loggingutil import set_timestamps
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.resources import get_resources, list_resources
from cylc.flow.terminal import cli_function


def get_option_parser():
    parser = COP(
        __doc__,
        argdoc=[
            COP.optional(
                ('RESOURCE', 'Resource to extract.')
            ),
            COP.optional(
                ('DIR', 'Target directory.')
            )
        ]
    )

    parser.add_option(
        '--list',
        help="List available resources.",
        default=False,
        action='store_true',
    )

    return parser


@cli_function(get_option_parser)
def main(parser, opts, resource=None, tgt_dir=None):
    if cylc.flow.flags.verbosity < 2:
        set_timestamps(LOG, False)
    if not resource or opts.list:
        list_resources()
        sys.exit(0)
    get_resources(resource, tgt_dir)
