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

"""cylc get-suite-config [OPTIONS] ARGS

Print parsed suite configuration items, after runtime inheritance.

Note:
  This is different to `cylc view` which doesn't parse the configuration
  so is useful for debugging Jinja2.

By default all settings are printed. For specific sections or items
use -i/--item and wrap sections in square brackets, e.g.:
  $ cylc get-suite-config --item '[scheduling]initial cycle point'
Multiple items can be retrieved at once.

By default, unset values are printed as an empty string, or (for
historical reasons) as "None" with -o/--one-line. These defaults
can be changed with the -n/--null-value option.

Example:
  |# FLOW.CYLC
  |[runtime]
  |    [[modelX]]
  |        [[[environment]]]
  |            FOO = foo
  |            BAR = bar

  $ cylc get-suite-config --item=[runtime][modelX][environment]FOO SUITE
  foo

  $ cylc get-suite-config --item=[runtime][modelX][environment] SUITE
  FOO = foo
  BAR = bar

  $ cylc get-suite-config --item=[runtime][modelX] SUITE
  ...
  [[[environment]]]
      FOO = foo
      BAR = bar
  ..."""

from cylc.flow.config import SuiteConfig
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.suite_files import parse_suite_arg
from cylc.flow.templatevars import load_template_vars
from cylc.flow.terminal import cli_function


def get_option_parser():
    parser = COP(__doc__, jset=True, prep=True, icp=True)

    parser.add_option(
        "-i", "--item", metavar="[SEC...]ITEM",
        help="Item or section to print (multiple use allowed).",
        action="append", dest="item", default=[])

    parser.add_option(
        "-r", "--sparse",
        help="Only print items explicitly set in the config files.",
        action="store_true", default=False, dest="sparse")

    parser.add_option(
        "-p", "--python",
        help="Print native Python format.",
        action="store_true", default=False, dest="pnative")

    parser.add_option(
        "-a", "--all-tasks",
        help="For [runtime] items (e.g. --item='script') report "
        "values for all tasks prefixed by task name.",
        action="store_true", default=False, dest="alltasks")

    parser.add_option(
        "-n", "--null-value",
        help="The string to print for unset values (default nothing).",
        metavar="STRING", action="store", default='', dest="none_str")

    parser.add_option(
        "-m", "--mark-up",
        help="Prefix each line with '!cylc!'.",
        action="store_true", default=False, dest="markup")

    parser.add_option(
        "-o", "--one-line",
        help="Print multiple single-value items at once.",
        action="store_true", default=False, dest="oneline")

    parser.add_option(
        "-t", "--tasks",
        help="Print the suite task list "
             "[DEPRECATED: use 'cylc list SUITE'].",
        action="store_true", default=False, dest="tasks")

    parser.add_option(
        "-u", "--run-mode",
        help="Get config for suite run mode.", action="store", default="live",
        dest="run_mode", choices=['live', 'dummy', 'simulation'])

    return parser


@cli_function(get_option_parser)
def main(parser, options, reg):
    suite, flow_file = parse_suite_arg(options, reg)

    if options.markup:
        prefix = '!cylc!'
    else:
        prefix = ''

    config = SuiteConfig(
        suite,
        flow_file,
        options,
        load_template_vars(options.templatevars, options.templatevars_file))
    if options.tasks:
        for task in config.get_task_name_list():
            print(prefix + task)
    elif options.alltasks:
        for task in config.get_task_name_list():
            items = ['[runtime][' + task + ']' + i for i in options.item]
            print(prefix + task, end=' ')
            config.pcfg.idump(
                items, options.sparse, options.pnative, prefix,
                options.oneline, none_str=options.none_str)
    else:
        config.pcfg.idump(
            options.item, options.sparse, options.pnative, prefix,
            options.oneline, none_str=options.none_str)


if __name__ == "__main__":
    main()
