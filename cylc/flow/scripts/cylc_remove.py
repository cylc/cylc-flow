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

"""cylc [control] remove [OPTIONS] ARGS

Remove one or more task instances from a running workflow.

Tasks will be forced to spawn successors before removal if they have not done
so already, unless you use '--no-spawn'.
"""

import sys
if '--use-ssh' in sys.argv[1:]:
    sys.argv.remove('--use-ssh')
    from cylc.flow.remote import remrun
    if remrun():
        sys.exit(0)

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.network.client import SuiteRuntimeClient
from cylc.flow.terminal import prompt, cli_function


def get_option_parser():
    parser = COP(
        __doc__, comms=True, multitask=True,
        argdoc=[
            ("REG", "Suite name"),
            ('TASK_GLOB [...]', 'Task matching patterns')])

    parser.add_option(
        "--no-spawn",
        help="Do not spawn successors before removal.",
        action="store_true", default=False, dest="no_spawn")

    return parser


@cli_function(get_option_parser)
def main(parser, options, suite, *task_globs):
    prompt('remove task(s) %s in %s' % (task_globs, suite), options.force)
    pclient = SuiteRuntimeClient(
        suite, options.owner, options.host, options.port,
        options.comms_timeout)
    pclient(
        'remove_tasks',
        {'tasks': task_globs, 'spawn': (not options.no_spawn)}
    )


if __name__ == "__main__":
    main()
