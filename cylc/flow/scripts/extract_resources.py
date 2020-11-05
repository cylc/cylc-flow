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
"""cylc extract-resources [OPTIONS] [DIR] [RESOURCES...]

Extract resources from the cylc.flow package."""

import sys

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.resources import extract_resources, list_resources
from cylc.flow.terminal import cli_function


def get_option_parser():
    parser = COP(
        __doc__,
        argdoc=[
            ('[DIR]', 'Target directory.'),
            ('[RESOURCES...]', 'Resources to extract (default all).')
        ]
    )

    parser.add_option('--list', default=False, action='store_true')

    return parser


@cli_function(get_option_parser)
def main(parser, opts, *args):
    if opts.list:
        print('\n'.join(list_resources()))
        sys.exit(0)
    elif not args:
        print(parser.usage)
        sys.exit(0)
    target_dir, *resources = args
    extract_resources(target_dir, resources or None)


if __name__ == '__main__':
    main()
