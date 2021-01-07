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

"""cylc config [OPTIONS] ARGS

Print parsed configuration, after runtime inheritance. If REG is specified,
print the workflow configuration, otherwise print the global configuration.

Note:
  This is different to `cylc view` which doesn't parse the configuration,
  so is useful for debugging Jinja2.

By default, unset values are printed as an empty string, or (for
historical reasons) as "None" with -o/--one-line. These defaults
can be changed with the -n/--null-value option.

Examples:
  # print global configuration
  $ cylc config

  # print workflow configuration
  $ cylc config myflow

  # print specific setting from the global config
  $ cylc config -i '[platforms][myplatform]hosts

  # print specific section from workflow config
  $ cylc config -i '[scheduling][graph]' myflow

  # print workflow config, first setting the initial cycle point
  $ cylc config --initial-cycle-point=now myflow
"""

from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.config import SuiteConfig
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.platforms import get_platform
from cylc.flow.suite_files import parse_suite_arg
from cylc.flow.templatevars import load_template_vars
from cylc.flow.terminal import cli_function


def get_option_parser():
    parser = COP(
        __doc__,
        argdoc=[("[REG]", "Workflow name or path")],
        jset=True, icp=True
    )

    parser.add_option(
        "-i", "--item", metavar="[SEC...]ITEM",
        help="Item or section to print (multiple use allowed).",
        action="append", dest="item", default=[])

    parser.add_option(
        "-r", "--sparse",
        help="Only print items explicitly set in the config files.",
        action="store_true", default=False, dest="sparse")

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
        "-o", "--one-line",
        help="Print multiple single-value items at once.",
        action="store_true", default=False, dest="oneline")

    parser.add_option(
        "-t", "--tasks",
        help="Print the suite task list "
             "[DEPRECATED: use 'cylc list SUITE'].",
        action="store_true", default=False, dest="tasks")

    parser.add_option(
        "--print-run-dir",
        help="Print the configured top level run directory.",
        action="store_true", default=False, dest="print_run_dir")

    return parser


@cli_function(get_option_parser)
def main(parser, options, reg=None):
    if options.print_run_dir:
        print(get_platform()['run directory'])
        return

    if reg is None:
        glbl_cfg().idump(options.item, sparse=options.sparse)
        return

    suite, flow_file = parse_suite_arg(options, reg)

    config = SuiteConfig(
        suite,
        flow_file,
        options,
        load_template_vars(options.templatevars, options.templatevars_file))
    if options.tasks:
        for task in config.get_task_name_list():
            print(task)
    elif options.alltasks:
        for task in config.get_task_name_list():
            items = ['[runtime][' + task + ']' + i for i in options.item]
            print(task, end=' ')
            config.pcfg.idump(
                items, options.sparse, oneline=options.oneline,
                none_str=options.none_str)
    else:
        config.pcfg.idump(
            options.item, options.sparse, oneline=options.oneline,
            none_str=options.none_str)


if __name__ == "__main__":
    main()
