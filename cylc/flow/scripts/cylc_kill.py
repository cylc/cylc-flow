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

"""cylc [control] kill [OPTIONS] ARGS

Kill jobs of active tasks and update their statuses accordingly.
 cylc kill REG TASK_GLOB ... - kill one or more active tasks
 cylc kill REG - kill all active tasks in the workflow
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
            ('REG', 'Suite name'),
            ('[TASK_GLOB ...]', 'Task matching patterns')])

    return parser


@cli_function(get_option_parser)
def main(parser, options, suite, *task_globs):
    """CLI of "cylc kill"."""
    if task_globs:
        prompt('Kill task %s in %s' % (task_globs, suite), options.force)
    else:
        prompt('Kill ALL tasks in %s' % (suite), options.force)
    pclient = SuiteRuntimeClient(
        suite, options.owner, options.host, options.port)
    pclient(
        'kill_tasks',
        {'tasks': task_globs},
        timeout=options.comms_timeout
    )


if __name__ == "__main__":
    main()
