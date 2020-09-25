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

"""cylc [prep] get-directory REG

Retrieve and print the source directory location of suite REG.
Here's an easy way to move to a suite source directory:
  $ cd $(cylc get-dir REG)."""

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.suite_files import get_suite_source_dir
from cylc.flow.terminal import cli_function


def get_option_parser():
    return COP(__doc__, prep=True)


@cli_function(get_option_parser)
def main(parser, options, suite):
    """Implement "cylc get-directory"."""
    print(get_suite_source_dir(suite, options.suite_owner))


if __name__ == "__main__":
    main()
