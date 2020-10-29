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
"""cylc extract-resources [OPTIONS] DIR [RESOURCES]

Extract resources from the cylc.flow package.

Options:
    --list      List available resources
Arguments:
    DIR         Target Directory
    [RESOURCES] Specific resources to extract (default all).
"""

import os
import sys

from cylc.flow.exceptions import UserInputError
from cylc.flow.resources import extract_resources, list_resources
from cylc.flow.terminal import cli_function


class ArgParser:
    """Lightweight standin for cylc.flow.option_parsers.CylcOptionParser."""

    @classmethod
    def parser(cls):
        return cls

    @staticmethod
    def parse_args():
        if {'help', '--help', "-h"} & set(sys.argv):
            print(__doc__)
        elif len(sys.argv) < 2:
            raise UserInputError(
                "wrong number of arguments, "
                f"see '{os.path.basename(sys.argv[0])} --help'."
            )
        elif '--list' in sys.argv:
            print('\n'.join(list_resources()))
        else:
            return (None, sys.argv[1:])
        sys.exit()


@cli_function(ArgParser.parser)
def main(parser, _, target_dir, *resources):
    extract_resources(target_dir, resources or None)


if __name__ == '__main__':
    main()
