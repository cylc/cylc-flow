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

"""cylc [control] spawn [OPTIONS] TASK-GLOB [...]

Force a task to spawn downstream children that depend on specified ouputs.
The --output=OUTPUT option can be used multiple times on the command line.

"""

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.network.client import SuiteRuntimeClient
from cylc.flow.terminal import prompt, cli_function


def get_option_parser():
    parser = COP(
        __doc__, comms=True, multitask_nocycles=True,
        argdoc=[
            ("REG", "Suite name"),
            ('TASK-GLOB [...]', 'Task match pattern')])
    parser.add_option(
        "--output", metavar="OUTPUT",
        help="Spawn on OUTPUT",
        action="append", dest="outputs")
    return parser


@cli_function(get_option_parser)
def main(parser, options, suite, *task_globs):
    prompt('Spawn task(s) %s in %s' % (task_globs, suite), options.force)
    pclient = SuiteRuntimeClient(suite, timeout=options.comms_timeout)
    pclient(
        'force_spawn_children',
        {'tasks': task_globs,
         'outputs': options.outputs})


if __name__ == "__main__":
    main()
