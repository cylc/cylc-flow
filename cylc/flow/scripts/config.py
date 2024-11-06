#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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

Print parsed configuration, after runtime inheritance. If WORKFLOW is
specified, print the workflow configuration, otherwise print the global
configuration.

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

import asyncio

import os.path
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.config import WorkflowConfig
from cylc.flow.id_cli import parse_id_async
from cylc.flow.exceptions import InputError
from cylc.flow.option_parsers import (
    AGAINST_SOURCE_OPTION,
    WORKFLOW_ID_OR_PATH_ARG_DOC,
    CylcOptionParser as COP,
    icp_option,
)
from cylc.flow.pathutil import get_workflow_run_dir
from cylc.flow.templatevars import get_template_vars
from cylc.flow.terminal import cli_function
from cylc.flow.workflow_files import WorkflowFiles

if TYPE_CHECKING:
    from optparse import Values


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        argdoc=[COP.optional(WORKFLOW_ID_OR_PATH_ARG_DOC)],
        jset=True,
    )

    parser.add_option(
        "-i", "--item", metavar="[SEC...]ITEM",
        help="Item or section to print (multiple use allowed).",
        action="append", dest="item", default=[])

    parser.add_option(
        '-d', '--defaults',
        help='Include the hard-coded Cylc default values in the output.',
        action='store_true',
        default=False
    )

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

    parser.add_option(icp_option)

    platform_listing_options_group = parser.add_option_group(
        'Platform printing options')
    platform_listing_options_group.add_option(
        '--platform-names',
        help=(
            'Print a list of platforms and platform group names from the '
            'configuration.'
        ),
        action='store_true', default=False, dest='print_platform_names'
    )
    platform_listing_options_group.add_option(
        '--platforms',
        help=(
            'Print platform and platform group configurations, '
            'including metadata.'
        ),
        action='store_true', default=False, dest='print_platforms'
    )

    parser.add_option(
        *AGAINST_SOURCE_OPTION.args, **AGAINST_SOURCE_OPTION.kwargs)

    parser.add_cylc_rose_options()

    return parser


def get_config_file_hierarchy(workflow_id: Optional[str] = None) -> List[str]:
    filepaths = [os.path.join(path, glbl_cfg().CONF_BASENAME)
                 for _, path in glbl_cfg().conf_dir_hierarchy]
    if workflow_id is not None:
        filepaths.append(
            get_workflow_run_dir(workflow_id, WorkflowFiles.FLOW_FILE)
        )
    return filepaths


@cli_function(get_option_parser)
def main(
    parser: COP,
    options: 'Values',
    *ids,
) -> None:
    asyncio.run(_main(parser, options, *ids))


async def _main(
    parser: COP,
    options: 'Values',
    *ids,
) -> None:

    if options.print_platform_names and options.print_platforms:
        options.print_platform_names = False

    if options.print_platform_names or options.print_platforms:
        # Get platform information:
        if ids:
            raise InputError(
                "Workflow IDs are incompatible with --platform options."
            )
        glbl_cfg().platform_dump(
            options.print_platform_names,
            options.print_platforms
        )
        return

    if not ids:
        if options.print_hierarchy:
            print("\n".join(get_config_file_hierarchy()))
            return

        glbl_cfg().idump(
            options.item,
            not options.defaults,
            oneline=options.oneline,
            none_str=options.none_str
        )
        return

    workflow_id, _, flow_file = await parse_id_async(
        *ids,
        src=True,
        constraint='workflows',
    )

    if options.print_hierarchy:
        print("\n".join(get_config_file_hierarchy(workflow_id)))
        return

    # Save the location of the existing workflow run dir in the
    # against source option:
    if options.against_source:
        options.against_source = Path(get_workflow_run_dir(workflow_id))

    config = WorkflowConfig(
        workflow_id,
        flow_file,
        options,
        get_template_vars(options)
    )

    config.pcfg.idump(
        options.item,
        not options.defaults,
        oneline=options.oneline,
        none_str=options.none_str
    )
