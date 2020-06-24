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

"""cylc [info] get-suite-version [OPTIONS] ARGS

Interrogate running suite REG to find what version of cylc is running it.

To find the version you've invoked at the command line see "cylc version"."""

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.network.client import SuiteRuntimeClient


def main():
    parser = COP(__doc__, comms=True, argdoc=[('REG', 'Suite name')])

    (options, args) = parser.parse_args()
    suite = args[0]

    pclient = SuiteRuntimeClient(suite, timeout=options.comms_timeout)
    print(pclient('get_cylc_version'))


if __name__ == "__main__":
    main()
