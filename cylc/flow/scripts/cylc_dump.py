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

"""cylc [info] dump [OPTIONS] ARGS

Print state information (e.g. the state of each task) from a running
suite.

For command line monitoring:
* `cylc tui`
* `watch cylc dump SUITE` works for small simple suites

For more information about a specific task, such as the current state of
its prerequisites and outputs, see 'cylc [info] show'.

Examples:
 Display the state of all running tasks, sorted by cycle point:
 % cylc [info] dump --tasks --sort SUITE | grep running

 Display the state of all tasks in a particular cycle point:
 % cylc [info] dump -t SUITE | grep 2010082406"""

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.network.client import SuiteRuntimeClient
from cylc.flow.dump import dump_to_stdout
from cylc.flow.terminal import cli_function


def get_option_parser():
    parser = COP(__doc__, comms=True, noforce=True)
    parser.add_option(
        "-g", "--global", help="Global information only.",
        action="store_const", const="global", dest="disp_form")
    parser.add_option(
        "-t", "--tasks", help="Task states only.",
        action="store_const", const="tasks", dest="disp_form")
    parser.add_option(
        "-r", "--raw", "--raw-format",
        help='Display raw format.',
        action="store_const", const="raw", dest="disp_form")
    parser.add_option(
        "-s", "--sort",
        help="Task states only; sort by cycle point instead of name.",
        action="store_true", default=False, dest="sort_by_cycle")

    return parser


@cli_function(get_option_parser)
def main(_, options, suite):
    pclient = SuiteRuntimeClient(suite, timeout=options.comms_timeout)
    summary = pclient('get_suite_state_summary')

    if options.disp_form == "raw":
        print(summary)
    else:
        if options.disp_form != "tasks":
            for key, value in sorted(summary[0].items()):
                print("%s=%s" % (key, value))
        if options.disp_form != "global":
            dump_to_stdout(summary[1], options.sort_by_cycle)


if __name__ == "__main__":
    main()
