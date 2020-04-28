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

"""cylc [control] insert [OPTIONS] TASK_GLOB [...]

Insert new task proxies into the task pool of a running workflow, to enable
(for example) re-triggering earlier tasks already removed from the pool.

NOTE: inserted cycling tasks cycle on as normal, even if another instance of
the same task exists at a later cycle (instances of the same task at different
cycles can coexist, but a newly spawned task will not be added to the pool if
it catches up to another task with the same ID).

See also 'cylc submit', for running tasks without the scheduler.
"""

import sys
if '--use-ssh' in sys.argv[1:]:
    sys.argv.remove('--use-ssh')
    from cylc.flow.remote import remrun
    if remrun():
        sys.exit(0)

from cylc.flow.exceptions import UserInputError
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.network.client import SuiteRuntimeClient
from cylc.flow.task_id import TaskID
from cylc.flow.terminal import prompt, cli_function


def get_option_parser():
    parser = COP(
        __doc__, comms=True, multitask_nocycles=True,
        argdoc=[
            ("REG", "Suite name"),
            ('TASKID [...]', 'Task identifier')])

    parser.add_option(
        "--stop-point", "--remove-point",
        help="Optional hold/stop cycle point for inserted task.",
        metavar="CYCLE_POINT", action="store", dest="stop_point_string")
    parser.add_option(
        "--no-check", help="Add task even if the provided cycle point is not "
        "valid for the given task.", action="store_true", default=False)

    return parser


@cli_function(get_option_parser)
def main(parser, options, suite, *items):
    for i, item in enumerate(items):
        if not TaskID.is_valid_id_2(item):
            raise UserInputError(
                '"%s": invalid task ID (argument %d)' % (item, i + 1))
    prompt('Insert %s in %s' % (items, suite), options.force)

    pclient = SuiteRuntimeClient(
        suite, options.owner, options.host, options.port)

    pclient(
        'insert_tasks',
        {'tasks': items, 'check_point': not options.no_check,
         'stop_point': options.stop_point_string},
        timeout=options.comms_timeout
    )


if __name__ == "__main__":
    main()
