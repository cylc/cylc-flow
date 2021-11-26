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
"""cylc extract-resources [OPTIONS] ARGS

Extract resources from
- the cylc.flow package.
- Cylc tutorial workflows.
"""

import sys

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.resources import extract_resources, list_resources
from cylc.flow.terminal import cli_function


def get_option_parser():
    parser = COP(
        __doc__,
        argdoc=[
            (
                '[DIR]',
                'Target directory. (defaults to ~/cylc-src for tutorials)'
            ),
            ('[RESOURCES...]', 'Resources to extract (default all).')
        ]
    )

    parser.add_option(
        '--list',
        default=False, action='store_true',
        help='List all available resources (including tutorials).'
    )
    parser.add_option(
        '--tutorials', '--list-tutorials',
        default=False, action='store_true',
        help='List available tutorials.'
    )

    return parser


@cli_function(get_option_parser)
def main(parser, opts, *args):
    resources = None
    tutorial = False
    if opts.list:
        # -- list - List _all_ resources:
        print('\n'.join(list_resources()))
        sys.exit(0)
    if opts.tutorials:
        # --tutorials - List tutorials:
        print('\n'.join(list_resources(tutorials=True)))
        sys.exit(0)
    elif len(args) == 1 and 'tutorial' in args[0]:
        # get a tutorial and put it in ~/cylc-src
        tutorial = args[0]
        target_dir = glbl_cfg.get(['install', 'source dirs'][0])
    elif len(args) < 2:
        # If there are no args print help:
        print(parser.usage)
        sys.exit(0)
    else:
        # Get Cylc Package resources.
        target_dir, *resources = args

    extract_resources(target_dir, resources, tutorial)
