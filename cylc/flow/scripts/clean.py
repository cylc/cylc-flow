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

"""cylc clean [OPTIONS] ARGS

Remove a stopped workflow from the local scheduler filesystem.

NOTE: this command is intended for workflows installed with `cylc install`. If
this is run for a workflow that was instead written directly in ~/cylc-run and
not backed up elsewhere, it will be lost.

It will also remove an symlink directory targets. For now, it will fail if
run on a host which doesn't have access to that filesystem.

Suite names can be hierarchical, corresponding to the path under ~/cylc-run.

Examples:
  # Remove the workflow at ~/cylc-run/foo
  $ cylc clean foo

"""

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.terminal import cli_function
from cylc.flow.suite_files import clean


def get_option_parser():
    parser = COP(
        __doc__,
        argdoc=[("REG", "Suite name")]
    )
    return parser


@cli_function(get_option_parser)
def main(parser, opts, reg):
    clean(reg)


if __name__ == "__main__":
    main()
