#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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

"""cylc [control] spawn [OPTIONS] TASK_GLOB [...]

Force spawning (and prerequisite update) downstream of target task ouputs.

Default is spawn on <target-tasks>:succeed.

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
        __doc__, comms=True, multitask_nocycles=True,
        argdoc=[
            ("REG", "Suite name"),
            ('TASK-GLOB [...]', 'Task match pattern')])

    parser.add_option(
        "--failed",
        help="Spawn on <target-tasks>:fail.",
        action="store_true", default=False, dest="failed")

    parser.add_option(
        "--non-failed",
        help="Spawn on all non-failure outputs.",
        action="store_true", default=False, dest="non_failed")

    return parser


@cli_function(get_option_parser)
def main(parser, options, suite, *task_globs):
    if options.failed and options.non_failed:
        sys.exit("--failed and --non-failed are mutually exclusive")

    prompt('Spawn task(s) %s in %s' % (task_globs, suite), options.force)
    pclient = SuiteRuntimeClient(
        suite, options.owner, options.host, options.port,
        options.comms_timeout)

    pclient(
        'spawn_tasks',
        {'tasks': task_globs,
         'failed': options.failed,
         'non_failed': options.non_failed
        }
    )


if __name__ == "__main__":
    main()
