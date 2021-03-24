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

Parse and print Cylc configuration files.

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

import os.path
from typing import List, Optional

from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.config import SuiteConfig
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.pathutil import get_workflow_run_dir
from cylc.flow.suite_files import SuiteFiles, parse_suite_arg
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
        "-n", "--null-value",
        help="The string to print for unset values (default nothing).",
        metavar="STRING", action="store", default='', dest="none_str")

    parser.add_option(
        "-o", "--one-line",
        help="Print multiple single-value items at once.",
        action="store_true", default=False, dest="oneline")

    parser.add_option(
        "--print-hierarchy", "--print-filenames", "--hierarchy",
        help=(
            "Print the list of locations in which configuration files are "
            "looked for. An existing configuration file lower down the list "
            "overrides any settings it shares with those higher up."),
        action="store_true", default=False, dest="print_hierarchy")

    return parser


def get_config_file_hierarchy(reg: Optional[str] = None) -> List[str]:
    filepaths = [os.path.join(path, glbl_cfg().CONF_BASENAME)
                 for _, path in glbl_cfg().conf_dir_hierarchy]
    if reg is not None:
        filepaths.append(get_workflow_run_dir(reg, SuiteFiles.FLOW_FILE))
    return filepaths


@cli_function(get_option_parser)
def main(parser, options, reg=None):
    if options.print_hierarchy:
        print("\n".join(get_config_file_hierarchy(reg)))
        return

    if reg is None:
        glbl_cfg().idump(
            options.item, sparse=options.sparse, oneline=options.oneline,
            none_str=options.none_str)
        return

    suite, flow_file = parse_suite_arg(options, reg)

    config = SuiteConfig(
        suite,
        flow_file,
        options,
        load_template_vars(options.templatevars, options.templatevars_file))

    config.pcfg.idump(
        options.item, options.sparse, oneline=options.oneline,
        none_str=options.none_str)


if __name__ == "__main__":
    main()
