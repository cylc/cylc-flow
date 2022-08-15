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

from types import SimpleNamespace
import typing as t

import pytest

from cylc.flow.scripts.graph import (
    Edge,
    Node,
    format_cylc_reference,
    format_graphviz,
    get_nodes_and_edges,
)


@pytest.fixture
def example_graph():
    """Example workflow graph with inter-cycle dependencies."""
    nodes: t.List[Node] = [
        '1/a',
        '1/b',
        '1/c',
        '2/a',
        '2/b',
        '2/c',
    ]
    edges: t.List[Edge] = [
        ('1/a', '1/b'),
        ('1/b', '1/c'),
        ('2/a', '2/b'),
        ('2/b', '2/c'),
        ('1/b', '2/b'),
    ]
    return nodes, edges


@pytest.fixture
def example_namespace_graph():
    """Example namespace graph with inheritance."""
    nodes: t.List[Node] = [
        'A',
        'a1',
        'a2',
        'B',
        'B1',
        'b11',
        'B2',
        'b22',
    ]
    edges: t.List[Edge] = [
        ('A', 'a1'),
        ('A', 'a2'),
        ('B', 'B1'),
        ('B', 'B2'),
        ('B1', 'b11'),
        ('B2', 'b22'),
    ]
    return nodes, edges


@pytest.fixture
def null_config(monkeypatch):
    """Patch the config loader to return a workflow with no nodes or edges."""
    def _get_graph_raw(*args, **kwargs):
        return None

    def _get_parents_lists(*args, **kwargs):
        return {}

    config = SimpleNamespace(
        get_graph_raw=_get_graph_raw,
        get_parent_lists=_get_parents_lists,
    )

    monkeypatch.setattr(
        'cylc.flow.scripts.graph.get_config',
        lambda x, y: config
    )


def test_format_graphviz_normal(example_graph):
    """Test graphviz output for default options.

    Tests both orientations (--transpose).
    """
    nodes, edges = example_graph

    # format the graph in regular orientation
    opts = SimpleNamespace(transpose=False, namespaces=False, cycles=False)
    lines = format_graphviz(opts, nodes, edges)
    assert lines == [
        'digraph {',
        '  graph [fontname="sans" fontsize="25"]',
        '  node [fontname="sans"]',
        '',
        '  "1/a" [label="a\\n1"]',
        '  "1/b" [label="b\\n1"]',
        '  "1/c" [label="c\\n1"]',
        '',
        '  "2/a" [label="a\\n2"]',
        '  "2/b" [label="b\\n2"]',
        '  "2/c" [label="c\\n2"]',
        '',
        '  "1/a" -> "1/b"',
        '  "1/b" -> "1/c"',
        '  "2/a" -> "2/b"',
        '  "2/b" -> "2/c"',
        '  "1/b" -> "2/b"',
        '}',
    ]

    # format the graph in transposed orientation
    opts = SimpleNamespace(transpose=True, namespaces=False, cycles=False)
    transposed_lines = format_graphviz(opts, nodes, edges)

    # the transposed graph should be the same except for one line...
    assert [
        line
        for line in transposed_lines
        if line not in lines
    ] == [
        # ...the one which sets the orientation
        '  rankdir="LR"',
    ]


def test_format_graphviz_namespace(example_namespace_graph):
    """Test graphviz output for a namespace graph.

    Tests both orientations (--transpose).
    """
    nodes, edges = example_namespace_graph

    # format the graph in regular orientation
    opts = SimpleNamespace(transpose=False, namespaces=True, cycles=False)
    lines = format_graphviz(opts, nodes, edges)
    assert lines == [
        'digraph {',
        '  graph [fontname="sans" fontsize="25"]',
        '  node [fontname="sans"]',
        '  node [shape="rect"]',
        '',
        '  "A"',
        '  "a1"',
        '  "a2"',
        '  "B"',
        '  "B1"',
        '  "b11"',
        '  "B2"',
        '  "b22"',
        '',
        '  "A" -> "a1"',
        '  "A" -> "a2"',
        '  "B" -> "B1"',
        '  "B" -> "B2"',
        '  "B1" -> "b11"',
        '  "B2" -> "b22"',
        '}',
    ]

    # format the graph in transposed orientation
    opts = SimpleNamespace(transpose=True, namespaces=True, cycles=False)
    transposed_lines = format_graphviz(opts, nodes, edges)

    # the transposed graph should be the same except for one line...
    assert [
        line
        for line in transposed_lines
        if line not in lines
    ] == [
        # ...the one which sets the orientation
        '  rankdir="LR"',
    ]


def test_format_graphviz_cycles(example_graph):
    """Test graphviz format for the --cycles option (group by cycle).

    Note: There is no difference between iso8601 and integer cycle points here,
    the graph logic is cycle point format agnostic. Sorting is not performed
    in this funtion.
    """
    nodes, edges = example_graph

    opts = SimpleNamespace(transpose=False, namespaces=False, cycles=True)
    lines = format_graphviz(opts, nodes, edges)
    assert lines == [
        'digraph {',
        '  graph [fontname="sans" fontsize="25"]',
        '  node [fontname="sans"]',
        '',
        '  subgraph "cluster_1" { ',
        '    label="1"',
        '    style="dashed"',
        '    "1/a" [label="a\\n1"]',
        '    "1/b" [label="b\\n1"]',
        '    "1/c" [label="c\\n1"]',
        '  }',
        '',
        '  subgraph "cluster_2" { ',
        '    label="2"',
        '    style="dashed"',
        '    "2/a" [label="a\\n2"]',
        '    "2/b" [label="b\\n2"]',
        '    "2/c" [label="c\\n2"]',
        '  }',
        '',
        '  "1/a" -> "1/b"',
        '  "1/b" -> "1/c"',
        '  "2/a" -> "2/b"',
        '  "2/b" -> "2/c"',
        '  "1/b" -> "2/b"',
        '}',
    ]


def test_format_cylc_reference_normal(example_graph):
    """Test Cylc "reference" format (used by the test battery).

    Note: There is no difference between iso8601 and integer cycle points here,
    the graph logic is cycle point format agnostic. Sorting is not performed
    in this funtion.

    Note: There is no transpose mode for reference graphs.
    """
    nodes, edges = example_graph

    opts = SimpleNamespace(namespaces=False)
    lines = format_cylc_reference(opts, nodes, edges)
    assert lines == [
        'edge "1/a" "1/b"',
        'edge "1/b" "1/c"',
        'edge "2/a" "2/b"',
        'edge "2/b" "2/c"',
        'edge "1/b" "2/b"',
        'graph',
        'node "1/a" "a\\n1"',
        'node "1/b" "b\\n1"',
        'node "1/c" "c\\n1"',
        'node "2/a" "a\\n2"',
        'node "2/b" "b\\n2"',
        'node "2/c" "c\\n2"',
        'stop',
    ]


def test_format_cylc_reference_namespace(example_namespace_graph):
    """Test Cylc "reference" format for namespace graphs.

    Note: There is no transpose mode for reference graphs.
    """
    nodes, edges = example_namespace_graph

    opts = SimpleNamespace(namespaces=True)
    lines = format_cylc_reference(opts, nodes, edges)
    assert lines == [
        'edge "A" "a1"',
        'edge "A" "a2"',
        'edge "B" "B1"',
        'edge "B" "B2"',
        'edge "B1" "b11"',
        'edge "B2" "b22"',
        'graph',
        'node "A" "A"',
        'node "a1" "a1"',
        'node "a2" "a2"',
        'node "B" "B"',
        'node "B1" "B1"',
        'node "b11" "b11"',
        'node "B2" "B2"',
        'node "b22" "b22"',
        'stop',
    ]


def test_null(null_config):
    """Ensure that an empty graph is handled elegantly."""
    opts = SimpleNamespace(
        namespaces=False,
        grouping=False,
        show_suicide=False
    )
    assert get_nodes_and_edges(opts, None, 1, 2) == ([], [])

    opts = SimpleNamespace(
        namespaces=True,
        grouping=False,
        show_suicide=False
    )
    assert get_nodes_and_edges(opts, None, 1, 2) == ([], [])
