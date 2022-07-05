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
"""

from difflib import unified_diff
import re
from shutil import which
from subprocess import Popen, PIPE
import sys
from tempfile import NamedTemporaryFile
from typing import List, Optional, TYPE_CHECKING, Tuple

from cylc.flow.config import WorkflowConfig
from cylc.flow.exceptions import InputError
from cylc.flow.id import Tokens
from cylc.flow.id_cli import parse_id
from cylc.flow.option_parsers import (
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
        tokens = Tokens(node, relative=True)
        write(
            f'node "{node}" "{tokens["task"]}\\n{tokens["cycle"]}"'
        )

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
        write('edge "%s" "%s"' % edge)

    write('graph')

    for node in sorted(nodes):
        write('node "%s" "%s"' % (node, node))

    write('stop')


def get_config(workflow_id: str, opts: 'Values') -> WorkflowConfig:
    """Return a WorkflowConfig object for the provided reg / path."""
    workflow_id, _, flow_file = parse_id(
        workflow_id,
        src=True,
        constraint='workflows',
    )
    template_vars = get_template_vars(opts)
    return WorkflowConfig(
        workflow_id, flow_file, opts, template_vars=template_vars
    )


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
            ' format.'
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

    parser.add_cylc_rose_options()

    return parser


def dot(opts, lines):
    """Render a graph using graphviz 'dot'.

    This crudely re-parses the output of the reference output for simplicity.

    This functionality will be replaced by the GUI.

    """
    if not which('dot'):
        sys.exit('Graphviz must be installed to render graphs.')

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

    # scrape nodes and edges from the reference output
    node = re.compile(r'node "(.*)" "(.*)"')
    edge = re.compile(r'edge "(.*)" "(.*)"')
    nodes = {}
    edges = []
    for line in lines:
        match = node.match(line)
        if match:
            if opts.namespaces:
                task = match.group(1)
                cycle = ''
            else:
                cycle, task = match.group(1).split('/')
                nodes.setdefault(cycle, []).append(task)
            continue
        match = edge.match(line)
        if match:
            edges.append(match.groups())

    # write graph header
    dot = [
        'digraph {',
        '  graph [fontname="sans" fontsize="25"]',
        '  node [fontname="sans"]',
    ]
    if opts.transpose:
        dot.append('  rankdir="LR"')
    if opts.namespaces:
        dot.append('  node [shape="rect"]')

    # write nodes
    for cycle, tasks in nodes.items():
        if opts.cycles:
            dot.extend(
                [
                    f'  subgraph "cluster_{cycle}" {{ ',
                    f'    label="{cycle}"',
                    '    style="dashed"',
                ]
            )
        dot.extend(
            rf'    "{cycle}/{task}" [label="{task}\n{cycle}"]'
            for task in tasks
        )
        dot.append('  }' if opts.cycles else '')

    # write edges
    for left, right in edges:
        dot.append(f'  "{left}" -> "{right}"')

    # close graph
    dot.append('}')

    # render graph
    proc = Popen(  # nosec
        ['dot', f'-T{fmt}', '-o', filename],
        stdin=PIPE,
        text=True
    )
    # * filename is generated in code above
    # * fmt is user specified and quoted (by subprocess)
    proc.communicate('\n'.join(dot))
    proc.wait()
    if proc.returncode:
        sys.exit('Graphing Failed')

    return filename


def gui(filename):
    """Open the rendered image file."""
    print(f'Graph rendered to {filename}')
    try:
        from PIL import Image
    except ModuleNotFoundError:
        # dependencies required to display images not present
        pass
    else:
        img = Image.open(filename)
        img.show()


@cli_function(get_option_parser)
def main(
    parser: COP,
    opts: 'Values',
    workflow_id: str,
    start: Optional[str] = None,
    stop: Optional[str] = None
) -> None:
    """Implement ``cylc graph``."""
    if opts.grouping and opts.namespaces:
        raise InputError('Cannot combine --group and --namespaces.')

    lines: List[str] = []
    if not (opts.reference or opts.diff):
        write = lines.append
    else:
        write = print

    flows: List[Tuple[str, List[str]]] = [(workflow_id, [])]
    if opts.diff:
        flows.append((opts.diff, []))

    for flow, graph in flows:
        if opts.diff:
            write = graph.append
        config = get_config(flow, opts)
        if opts.namespaces:
            graph_inheritance(config, write=write)
        else:
            graph_workflow(
                config,
                start,
                stop,
                grouping=opts.grouping,
                show_suicide=opts.show_suicide,
                write=write
            )

    if opts.diff:
        diff_lines = list(
            unified_diff(
                [f'{line}\n' for line in flows[0][1]],
                [f'{line}\n' for line in flows[1][1]],
                fromfile=flows[0][0],
                tofile=flows[1][0]
            )
        )

        if diff_lines:
            sys.stdout.writelines(diff_lines)
            sys.exit(1)

    if not (opts.reference or opts.diff):
        filename = dot(opts, lines)
        if opts.output:
            print(f'Graph rendered to {opts.output}')
        else:
            gui(filename)
