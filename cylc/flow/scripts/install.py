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

"""cylc install [OPTIONS] ARGS

Test communication with a running suite.

If suite REG is running or TASK in suite REG is currently running,
exit with success status, else exit with error status."""

import os
import pkg_resources
from pathlib import Path

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.terminal import cli_function
from cylc.flow.pathutil import get_suite_run_dir
from cylc.flow.suite_files import parse_suite_arg


def get_option_parser():
    parser = COP(
        __doc__, comms=True, prep=True,
        argdoc=[('REG', 'Suite name')])

    return parser


@cli_function(get_option_parser)
def main(parser, options, reg):
    suite, flow_file = parse_suite_arg(options, reg)

    for entry_point in pkg_resources.iter_entry_points(
        'cylc.pre_configure'
    ):
        entry_point.resolve()(Path(flow_file).parent)

    for entry_point in pkg_resources.iter_entry_points(
        'cylc.post_install'
    ):
        entry_point.resolve()(
            dir_=os.getcwd(),
            opts=options,
            dest_root=get_suite_run_dir(suite)
        )


if __name__ == "__main__":
    main()
