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
"""

import sys

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.resources import (
    get_resources, list_resources, extract_tutorials
)
from cylc.flow.terminal import cli_function


def get_option_parser():
    parser = COP(
        __doc__,
        argdoc=[
            (
                '[RESOURCES...]', (
                    'Resources to extract (default all except the tutorials).'
                ),
                ('[DIR]', 'Target directory.')
            )
        ]
    )

    parser.add_option(
        '--list',
        help="List available package resources.",
        default=False,
        action='store_true',
    )

    parser.add_option(
        '--tutorials',
        help=(
            "Extract tutorials workflows to ~/cylc-src/. If you already have"
            "a tutorial folder that folder will be moved to a timestamped"
            "backup."
        ),
        default=False,
        action='store_true',
    )

    return parser


@cli_function(get_option_parser)
def main(parser, opts, *args):
    if opts.list:
        print('\n'.join(list_resources()))
        sys.exit(0)
    elif opts.tutorials:
        extract_tutorials()
        sys.exit(0)
    elif not args:
        print(parser.usage)
        sys.exit(0)
    target_dir = args[-1]
    resources = args[:-1]
    get_resources(target_dir, resources or None)
