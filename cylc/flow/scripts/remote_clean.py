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

"""cylc remote-clean [OPTIONS] ARGS

(This command is for internal use.)

Remove a stopped workflow from the remote host. This is called on any remote
hosts when "cylc clean" is called on localhost.

"""

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.terminal import cli_function
from cylc.flow.suite_files import clean


INTERNAL = True


def get_option_parser():
    parser = COP(
        __doc__,
        argdoc=[
            ("REG", "Suite name"),
            ("[RUND]", "The run directory of the suite")
        ]
    )
    return parser


@cli_function(get_option_parser)
def main(parser, opts, reg, rund=None):
    clean(reg, rund)


if __name__ == "__main__":
    main()
