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

"""cylc list [OPTIONS] ARGS

List tasks and families defined in a workflow.

Print runtime namespace names (tasks and families), the first-parent
inheritance graph, or actual tasks for a given cycle range.

The first-parent inheritance graph determines the primary task family
groupings that are collapsible in cylc visualisation tools.

To visualize the full multiple inheritance hierarchy use:
  $ cylc graph -n
"""

import asyncio
import os
import sys
from typing import TYPE_CHECKING

from cylc.flow.config import WorkflowConfig
from cylc.flow.id_cli import parse_id_async
from cylc.flow.option_parsers import (
    AGAINST_SOURCE_OPTION,
    WORKFLOW_ID_OR_PATH_ARG_DOC,
    CylcOptionParser as COP,
    icp_option,
)
from cylc.flow.templatevars import get_template_vars
from cylc.flow.terminal import cli_function

if TYPE_CHECKING:
    from optparse import Values


def get_option_parser():
    parser = COP(
        __doc__,
        jset=True,
        argdoc=[WORKFLOW_ID_OR_PATH_ARG_DOC],
    )

    parser.add_option(
        "-a", "--all-tasks",
        help="Print all tasks, not just those used in the graph.",
        action="store_true", default=False, dest="all_tasks")

    parser.add_option(
        "-n", "--all-namespaces",
        help="Print all runtime namespaces, not just tasks.",
        action="store_true", default=False, dest="all_namespaces")

    parser.add_option(
        "-m", "--mro",
        help="Print the linear \"method resolution order\" for each namespace "
             "(the multiple-inheritance precedence order as determined by the "
             "C3 linearization algorithm).",
        action="store_true", default=False, dest="mro")

    parser.add_option(
        "-t", "--tree",
        help="Print the first-parent inheritance hierarchy in tree form.",
        action="store_true", default=False, dest="tree")

    parser.add_option(
        "-b", "--box",
        help="With -t/--tree, using unicode box characters. Your terminal "
             "must be able to display unicode characters.",
        action="store_true", default=False, dest="box")

    parser.add_option(
        "-w", "--with-titles", help="Print namespaces titles too.",
        action="store_true", default=False, dest="titles")

    parser.add_option(
        "-p", "--points",
        help="Print task IDs from [START] to [STOP] cycle points. Both bounds "
        "are optional and STOP can be an interval from START (or from the "
        "initial cycle point, by default). Use '-p , ' for the default range.",
        metavar="[START],[STOP]", action="store", default=None, dest="prange")

    parser.add_option(
        *AGAINST_SOURCE_OPTION.args, **AGAINST_SOURCE_OPTION.kwargs)

    parser.add_option(icp_option)

    parser.add_cylc_rose_options()
    return parser


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', workflow_id: str) -> None:
    asyncio.run(_main(parser, options, workflow_id))


async def _main(parser: COP, options: 'Values', workflow_id: str) -> None:
    workflow_id, _, flow_file = await parse_id_async(
        workflow_id,
        src=True,
        constraint='workflows',
    )
    template_vars = get_template_vars(options)

    if options.all_tasks and options.all_namespaces:
        parser.error("Choose either -a or -n")
    if options.all_tasks:
        which = "all tasks"
    elif options.all_namespaces:
        which = "all namespaces"
    elif options.prange:
        which = "prange"
        if options.prange == ",":
            tr_start = None
            tr_stop = None
        elif options.prange.endswith(","):
            tr_start = options.prange[:-1]
            tr_stop = None
        elif options.prange.startswith(","):
            tr_start = None
            tr_stop = options.prange[1:]
        else:
            tr_start, tr_stop = options.prange.split(',')
    else:
        which = "graphed tasks"

    if options.tree and os.environ['LANG'] == 'C' and options.box:
        print("WARNING, ignoring -t/--tree: $LANG=C", file=sys.stderr)
        options.tree = False

    if options.titles and options.mro:
        parser.error("Please choose --mro or --title, not both")

    if options.tree and any(
            [options.all_tasks, options.all_namespaces, options.mro]):
        print("WARNING: -t chosen, ignoring non-tree options.",
              file=sys.stderr)
    config = WorkflowConfig(
        workflow_id,
        flow_file,
        options,
        template_vars
    )
    if options.tree:
        config.print_first_parent_tree(
            pretty=options.box, titles=options.titles)
    elif options.prange:
        for node in sorted(config.get_node_labels(tr_start, tr_stop)):
            print(node)
    else:
        result = config.get_namespace_list(which)
        namespaces = list(result)
        namespaces.sort()

        if (options.mro or options.titles):
            # compute padding
            maxlen = 0
            for ns in namespaces:
                if len(ns) > maxlen:
                    maxlen = len(ns)
            padding = maxlen * ' '

        for ns in namespaces:
            if options.mro:
                print(ns, padding[0:len(padding) - len(ns)], end=' ')
                print(' '.join(config.get_mro(ns)))
            elif options.titles:
                print(ns, padding[0:len(padding) - len(ns)], end=' ')
                print(result[ns])
            else:
                print(ns)
