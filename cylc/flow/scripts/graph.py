#!/usr/bin/env python3
#
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
"""cylc graph WORKFLOW [START] [STOP]

A text-based graph representation of workflow dependencies.

Implements the old ``cylc graph --reference command`` for producing a textual
graph of a workflow.

Examples:
    # print a textual representation of the graph of the flow one
    $ cylc graph one --reference

    # display the difference between the flows one and two
    $ cylc graph one --diff two
"""

from difflib import unified_diff
import sys

from cylc.flow.config import WorkflowConfig
from cylc.flow.exceptions import UserInputError
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.workflow_files import parse_workflow_arg
from cylc.flow.templatevars import get_template_vars
from cylc.flow.terminal import cli_function
from cylc.flow.scripts.install import add_cylc_rose_options


def sort_integer_node(item):
    """Return sort tokens for nodes with cyclepoints in integer format.

    Example:
        >>> sort_integer_node('foo.11')
        ('foo', 11)

    """
    name, point = item.split('.')
    return (name, int(point))


def sort_integer_edge(item):
    """Return sort tokens for edges with cyclepoints in integer format.

    Example:
        >>> sort_integer_edge(('foo.11', 'foo.12', None))
        (('foo', 11), ('foo', 12))
        >>> sort_integer_edge(('foo.11', None , None))
        (('foo', 11), ('', 0))

    """

    return (
        sort_integer_node(item[0]),
        sort_integer_node(item[1]) if item[1] else ('', 0)
    )


def sort_datetime_edge(item):
    """Return sort tokens for edges with cyclepoints in ISO8601 format.

    Example:
        >>> sort_datetime_edge(('a', None, None))
        ('a', '')

    """
    return (item[0], item[1] or '')


def graph_workflow(
    config,
    start_point_str=None,
    stop_point_str=None,
    grouping=None,
    show_suicide=False,
    write=print
):
    """Implement ``cylc-graph --reference``."""
    graph = config.get_graph_raw(
        start_point_str,
        stop_point_str,
        grouping
    )
    if not graph:
        return

    # set sort keys based on cycling mode
    if config.cfg['scheduling']['cycling mode'] == 'integer':
        # integer sorting
        node_sort = sort_integer_node
        edge_sort = sort_integer_edge
    else:
        # datetime sorting
        node_sort = None  # lexicographically sortable
        edge_sort = sort_datetime_edge

    edges = (
        (left, right)
        for left, right, _, suicide, _ in graph
        if right
        if show_suicide or not suicide
    )
    for left, right in sorted(set(edges), key=edge_sort):
        write('edge "%s" "%s"' % (left, right))

    write('graph')

    # print nodes
    nodes = (
        node
        for left, right, _, suicide, _ in graph
        for node in (left, right)
        if node
        if show_suicide or not suicide
    )
    for node in sorted(set(nodes), key=node_sort):
        write('node "%s" "%s"' % (node, node.replace('.', r'\n')))

    write('stop')


def graph_inheritance(config, write=print):
    """Implement ``cylc-graph --reference --namespaces``."""
    edges = set()
    nodes = set()
    for namespace, tasks in config.get_parent_lists().items():
        for task in tasks:
            edges.add((task, namespace))
            nodes.add(task)

    for namespace in config.get_parent_lists():
        nodes.add(namespace)

    for edge in sorted(edges):
        write('edge %s %s' % edge)

    write('graph')

    for node in sorted(nodes):
        write('node %s %s' % (node, node))

    write('stop')


def get_config(flow, opts, template_vars=None):
    """Return a WorkflowConfig object for the provided reg / path."""
    flow, flow_file = parse_workflow_arg(opts, flow)
    return WorkflowConfig(flow, flow_file, opts, template_vars=template_vars)


def get_option_parser():
    """CLI."""
    parser = COP(
        __doc__, jset=True, prep=True,
        argdoc=[
            ('[WORKFLOW]', 'Workflow name or path'),
            ('[START]', 'Graph start; defaults to initial cycle point'),
            (
                '[STOP]',
                'Graph stop point or interval; defaults to 3 points from START'
            )
        ]
    )

    parser.add_option(
        '-g', '--group',
        help="task family to group. Can be used multiple times. "
        "Use '<all>' to specify all families above root.",
        action='append', default=[], dest='grouping')

    parser.add_option(
        '-n', '--namespaces',
        help='Plot the workflow namespace inheritance hierarchy '
             '(task run time properties).',
        action='store_true', default=False, dest='namespaces')

    parser.add_option(
        '-r', '--reference',
        help='Output in a sorted plain text format for comparison purposes. '
             'If not given, assume --output-file=-.',
        action='store_true', default=False, dest='reference')

    parser.add_option(
        '--show-suicide',
        help='Show suicide triggers. Not shown by default.',
        action='store_true', default=False, dest='show_suicide')

    parser.add_option(
        '--icp', action='store', default=None, metavar='CYCLE_POINT', help=(
            'Set initial cycle point. Required if not defined in flow.cylc.'))

    parser.add_option(
        '--diff',
        help='Show the difference between two workflows (implies --reference)',
        action='store',
    )

    parser = add_cylc_rose_options(parser)

    return parser


@cli_function(get_option_parser)
def main(parser, opts, workflow=None, start=None, stop=None):
    """Implement ``cylc graph``."""
    if opts.grouping and opts.namespaces:
        raise UserInputError('Cannot combine --group and --namespaces.')
    if not (opts.reference or opts.diff):
        raise UserInputError(
            'Only the --reference and --diff use cases are supported'
        )

    template_vars = get_template_vars(opts, workflow)

    write = print
    flows = [(workflow, [])]
    if opts.diff:
        flows.append((opts.diff, []))

    for flow, graph in flows:
        if opts.diff:
            write = graph.append
        config = get_config(flow, opts, template_vars=template_vars)
        if opts.namespaces:
            graph_inheritance(config, write=write)
        else:
            graph_workflow(config, start, stop, grouping=opts.grouping,
                           show_suicide=opts.show_suicide, write=write)

    if opts.diff:
        lines = list(
            unified_diff(
                [f'{line}\n' for line in flows[0][1]],
                [f'{line}\n' for line in flows[1][1]],
                fromfile=flows[0][0],
                tofile=flows[1][0]
            )
        )

        if lines:
            sys.stdout.writelines(lines)
            sys.exit(1)


if __name__ == '__main__':
    main()
