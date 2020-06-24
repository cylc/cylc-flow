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

"""cylc [discovery] ping [OPTIONS] ARGS

If suite REG is running or TASK in suite REG is currently running,
exit with success status, else exit with error status."""

import sys

from ansimarkup import parse as cparse

from cylc.flow.exceptions import UserInputError
import cylc.flow.flags
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.task_id import TaskID
from cylc.flow.network.client import SuiteRuntimeClient
from cylc.flow.terminal import cli_function


def get_option_parser():
    parser = COP(
        __doc__, comms=True,
        argdoc=[('REG', 'Suite name'), ('[TASK]', 'Task ' + TaskID.SYNTAX)])

    return parser


@cli_function(get_option_parser)
def main(parser, options, suite, task_id=None):
    pclient = SuiteRuntimeClient(
        suite, options.owner, options.host, options.port,
        options.comms_timeout)

    # cylc ping SUITE
    pclient('ping_suite')  # (no need to check the result)
    if cylc.flow.flags.verbose:
        host, port = SuiteRuntimeClient.get_location(
            suite, options.owner, options.host)
        sys.stdout.write("Running on %s:%s\n" % (host, port))
    if task_id is None:
        sys.exit(0)

    # cylc ping SUITE TASKID
    if not TaskID.is_valid_id(task_id):
        raise UserInputError("Invalid task ID: %s" % task_id)
    success, msg = pclient('ping_task', {'task_id': task_id})

    if not success:
        print(cparse(f'<red>{msg}</red>'))
        sys.exit(1)


if __name__ == "__main__":
    main()
