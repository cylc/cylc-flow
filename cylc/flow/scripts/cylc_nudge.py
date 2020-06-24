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

"""cylc [control] nudge [OPTIONS] ARGS

Cause the cylc task processing loop to be invoked in a running suite.

This happens automatically when the state of any task changes such that
task processing (dependency negotiation etc.) is required, or if a
clock-trigger task is ready to run.

The main reason to use this command is to update the "estimated time till
completion" intervals, during periods when nothing else is happening.
"""

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.network.client import SuiteRuntimeClient
from cylc.flow.terminal import cli_function


def get_option_parser():
    parser = COP(__doc__, comms=True)

    return parser


@cli_function(get_option_parser)
def main(parser, options, suite):
    pclient = SuiteRuntimeClient(suite, timeout=options.comms_timeout)

    success, msg = pclient('nudge')


if __name__ == "__main__":
    main()
