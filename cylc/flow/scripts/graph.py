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

"""cylc graph [OPTIONS] ARGS

Produces graphical and textual representations of workflow dependencies.

Examples:
    # generate a graphical representation of workflow dependencies
    # (requires graphviz to be installed in the Cylc environment)
    $ cylc graph one

    # print a textual representation of the graph of the flow one
    $ cylc graph one --reference

    # display the difference between the flows one and two
    $ cylc graph one --diff two

    # render the graph to a svg file
    $ cylc graph one -o 'one.svg'
"""

import asyncio
from difflib import unified_diff
from shutil import which
from subprocess import Popen, PIPE
import sys
from tempfile import NamedTemporaryFile
from typing import Dict, List, Optional, TYPE_CHECKING, Tuple, Callable

from cylc.flow.config import WorkflowConfig
from cylc.flow.exceptions import InputError, CylcError
from cylc.flow.id import Tokens
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


def sort_integer_node(id_):
    """Return sort tokens for nodes with cyclepoints in integer format.

    Example:
        >>> sort_integer_node('11/foo')
        ('foo', 11)

    """
    tokens = Tokens(id_, relative=True)
    return (tokens['task'], int(tokens['cycle']))


def sort_integer_edge(id_):
    """Return sort tokens for edges with cyclepoints in integer format.

    Example:
        >>> sort_integer_edge(('11/foo', '12/foo', None))
        (('foo', 11), ('foo', 12))
        >>> sort_integer_edge(('11/foo', None , None))
        (('foo', 11), ('', 0))

    """

    return (
        sort_integer_node(id_[0]),
        sort_integer_node(id_[1]) if id_[1] else ('', 0)
    )


def sort_datetime_edge(item):
    """Return sort tokens for edges with cyclepoints in ISO8601 format.

    Example:
        >>> sort_datetime_edge(('a', None, None))
        ('a', '')

    """
    return (item[0], item[1] or '')


# node/edge types
Node = str  # node ID
Edge = Tuple[str, str]   # left, right


def get_nodes_and_edges(
    opts,
    workflow_id,
    start,
    stop,
    flow_file,
) -> Tuple[List[Node], List[Edge]]:
    """Return graph sorted nodes and edges."""
    config = get_config(workflow_id, opts, flow_file)
    if opts.namespaces:
        nodes, edges = _get_inheritance_nodes_and_edges(config)
    else:
        nodes, edges = _get_graph_nodes_edges(
            config,
            start,
            stop,
            grouping=opts.grouping,
            show_suicide=opts.show_suicide,
        )
    return nodes, edges


def _get_graph_nodes_edges(
    config,
    start_point_str=None,
    stop_point_str=None,
    grouping=None,
    show_suicide=False,
) -> Tuple[List[Node], List[Edge]]:
    """Return nodes and edges for a workflow graph."""
    graph = config.get_graph_raw(
        start_point_str,
        stop_point_str,
        grouping
    )
    if not graph:
        return [], []

    # set sort keys based on cycling mode
    # (note sorting is very important for the reference format)
    node_sort: Optional[Callable]
    edge_sort: Optional[Callable]
    if config.cfg['scheduling']['cycling mode'] == 'integer':
        # integer sorting
        node_sort = sort_integer_node
        edge_sort = sort_integer_edge
    else:
        # datetime sorting
        node_sort = None  # lexicographically sortable
        edge_sort = sort_datetime_edge

    # get nodes
    nodes = sorted(
        {
            node
            for left, right, _, suicide, _ in graph
            for node in (left, right)
            if node
            if show_suicide or not suicide
        },
        key=node_sort,
    )

    # get edges
    edges = sorted(
        {
            (left, right)
            for left, right, _, suicide, _ in graph
            if right
            if show_suicide or not suicide
        },
        key=edge_sort,
    )

    return nodes, edges


def _get_inheritance_nodes_and_edges(
    config
) -> Tuple[List[Node], List[Edge]]:
    """Return nodes and edges for an inheritance graph."""
    nodes = set()
    edges = set()
    for namespace, tasks in config.get_parent_lists().items():
        nodes.add(namespace)
        for task in tasks:
            edges.add((task, namespace))
            nodes.add(task)

    return sorted(nodes), sorted(edges)


def get_config(workflow_id: str, opts: 'Values', flow_file) -> WorkflowConfig:
    """Return a WorkflowConfig object for the provided id_ / path."""
    template_vars = get_template_vars(opts)
    return WorkflowConfig(
        workflow_id, flow_file, opts, template_vars=template_vars
    )


def format_graphviz(
    opts,
    nodes: List[Node],
    edges: List[Edge],
) -> List[str]:
    """Write graph in graphviz format."""
    # write graph header
    dot_lines = [
        'digraph {',
        '  graph [fontname="sans" fontsize="25"]',
        '  node [fontname="sans"]',
    ]
    if opts.transpose:
        dot_lines.append('  rankdir="LR"')
    if opts.namespaces:
        dot_lines.append('  node [shape="rect"]')
    dot_lines.append('')

    # write nodes
    if opts.namespaces:
        dot_lines.extend([
            rf'  "{node}"'
            for node in nodes
        ])
        dot_lines.append('')
    else:
        # group by cycle
        cycles: Dict[str, List[str]] = {}
        for node in nodes:
            tokens = Tokens(node, relative=True)
            cycle: str = tokens['cycle']
            task: str = tokens['task']
            cycles.setdefault(cycle, []).append(task)
        # write nodes by cycle
        if opts.cycles:
            indent = '    '
        else:
            indent = '  '
        for cycle, tasks in cycles.items():
            if opts.cycles:
                dot_lines.extend(
                    [
                        f'  subgraph "cluster_{cycle}" {{ ',
                        f'    label="{cycle}"',
                        '    style="dashed"',
                    ]
                )
            dot_lines.extend(
                rf'{indent}"{cycle}/{task}" [label="{task}\n{cycle}"]'
                for task in tasks
            )
            if opts.cycles:
                dot_lines.append('  }')
            dot_lines.append('')

    # write edges
    for left, right in edges:
        dot_lines.append(f'  "{left}" -> "{right}"')

    # close graph
    dot_lines.append('}')

    return dot_lines


def format_cylc_reference(
    opts,
    nodes: List[Node],
    edges: List[Edge],
) -> List[str]:
    """Write graph in cylc reference format."""
    lines = []
    # write edges
    for left, right in edges:
        lines.append(f'edge "{left}" "{right}"')

    # write separator
    lines.append('graph')

    # write nodes
    if opts.namespaces:
        for node in nodes:
            lines.append(f'node "{node}" "{node}"')
    else:
        for node in nodes:
            tokens = Tokens(node, relative=True)
            lines.append(
                f'node "{node}" "{tokens["task"]}\\n{tokens["cycle"]}"'
            )

    # write terminator
    lines.append('stop')

    return lines


def render_dot(dot_lines, filename, fmt):
    """Render graph using `dot`."""
    # check graphviz-dot is installed
    if not which('dot'):
        sys.exit('Graphviz must be installed to render graphs.')

    # render graph with graphviz
    proc = Popen(  # nosec
        ['dot', f'-T{fmt}', '-o', filename],
        stdin=PIPE,
        text=True
    )
    proc.communicate('\n'.join(dot_lines))
    proc.wait()
    if proc.returncode:
        raise CylcError('Graphing Failed')


def open_image(filename):
    """Open an image file."""
    print(f'Graph rendered to {filename}')
    try:
        from PIL import Image
    except ModuleNotFoundError:
        # dependencies required to display images not present
        pass
    else:
        img = Image.open(filename)
        img.show()


def graph_render(opts, workflow_id, start, stop, flow_file) -> int:
    """Render the workflow graph to the specified format.

    Graph is rendered to the specified format. The Graphviz "dot" format
    does not require Graphviz to be installed.

    All other formats require Graphviz. Supported formats depend on your
    Graphviz installation.
    """
    # get nodes and edges
    nodes, edges = get_nodes_and_edges(
        opts,
        workflow_id,
        start,
        stop,
        flow_file
    )

    # format the graph in graphviz-dot format
    dot_lines = format_graphviz(opts, nodes, edges)

    # set filename and output format
    if opts.output:
        filename = opts.output
        try:
            fmt = filename.rsplit('.', 1)[1]
        except IndexError:
            sys.exit('Output filename requires a format.')
    else:
        filename = NamedTemporaryFile().name
        fmt = 'png'

    if fmt == 'dot':
        # output in dot format (graphviz not needed for this)
        with open(filename, 'w+') as dot_file:
            dot_file.write('\n'.join(dot_lines) + '\n')
        return 0

    # render with graphviz
    render_dot(dot_lines, filename, fmt)

    # notify the user / open the graph
    if opts.output:
        print(f'Graph rendered to {opts.output}')
    else:
        open_image(filename)
    return 0


def graph_reference(
    opts, workflow_id, start, stop, flow_file, write=print,
) -> int:
    """Format the workflow graph using the cylc reference format."""
    # get nodes and edges
    nodes, edges = get_nodes_and_edges(
        opts,
        workflow_id,
        start,
        stop,
        flow_file
    )
    for line in format_cylc_reference(opts, nodes, edges):
        write(line)

    return 0


async def graph_diff(
    opts, workflow_a, workflow_b, start, stop, flow_file
) -> int:
    """Difference the workflow graphs using the cylc reference format."""

    workflow_b, _, flow_file_b = await parse_id_async(
        workflow_b,
        src=True,
        constraint='workflows',
    )

    # load graphs
    graph_a: List[str] = []
    graph_b: List[str] = []
    graph_reference(
        opts, workflow_a, start, stop, flow_file, write=graph_a.append),
    graph_reference(
        opts, workflow_b, start, stop, flow_file_b, write=graph_b.append),

    # compare graphs
    diff_lines = list(
        unified_diff(
            [f'{line}\n' for line in graph_a],
            [f'{line}\n' for line in graph_b],
            fromfile=workflow_a,
            tofile=workflow_b,
        )
    )

    # return results
    if diff_lines:
        sys.stdout.writelines(diff_lines)
        return 1
    return 0


def get_option_parser() -> COP:
    """CLI."""
    parser = COP(
        __doc__,
        jset=True,
        argdoc=[
            WORKFLOW_ID_OR_PATH_ARG_DOC,
            COP.optional(
                ('START', 'Graph start; defaults to initial cycle point')
            ),
            COP.optional((
                'STOP',
                'Graph stop point or interval; defaults to 3 points from START'
            ))
        ]
    )

    parser.add_option(
        '-g', '--group',
        help="task family to group. Can be used multiple times. "
        "Use '<all>' to specify all families above root.",
        action='append', default=[], dest='grouping')

    parser.add_option(
        '-c', '--cycles',
        help='Group tasks by cycle point.',
        action='store_true',
        default=False,
    )

    parser.add_option(
        '-t', '--transpose',
        help='Transpose graph.',
        action='store_true',
        default=False,
    )

    parser.add_option(
        '-o',
        help=(
            'Output the graph to a file. The file extension determines the'
            ' format. E.G. "graph.png", "graph.svg", "graph.dot".'
        ),
        action='store',
        dest='output'
    )

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

    parser.add_option(icp_option)

    parser.add_option(
        '--diff',
        help='Show the difference between two workflows (implies --reference)',
        action='store',
    )

    parser.add_option(
        *AGAINST_SOURCE_OPTION.args, **AGAINST_SOURCE_OPTION.kwargs)

    parser.add_cylc_rose_options()

    return parser


@cli_function(get_option_parser)
def main(
    parser: COP,
    opts: 'Values',
    workflow_id: str,
    start: Optional[str] = None,
    stop: Optional[str] = None
) -> None:
    result = asyncio.run(_main(parser, opts, workflow_id, start, stop))
    sys.exit(result)


async def _main(
    parser: COP,
    opts: 'Values',
    workflow_id: str,
    start: Optional[str] = None,
    stop: Optional[str] = None
) -> int:
    """Implement ``cylc graph``."""
    if opts.grouping and opts.namespaces:
        raise InputError('Cannot combine --group and --namespaces.')
    if opts.cycles and opts.namespaces:
        raise InputError('Cannot combine --cycles and --namespaces.')

    workflow_id, _, flow_file = await parse_id_async(
        workflow_id,
        src=True,
        constraint='workflows',
    )

    if opts.diff:
        return await graph_diff(
            opts, workflow_id, opts.diff, start, stop, flow_file)
    if opts.reference:
        return graph_reference(
            opts, workflow_id, start, stop, flow_file)

    return graph_render(opts, workflow_id, start, stop, flow_file)
