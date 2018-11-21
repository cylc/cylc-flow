#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & Contributors.
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

"""Cylc suite graphing module. Modules relying on this should test for
ImportError due to pygraphviz/graphviz not being installed."""

import pygraphviz

from cylc.cycling.loader import get_point, get_point_relative
from cylc.task_id import TaskID


class CGraphPlain(pygraphviz.AGraph):
    """Directed Acyclic Graph class for cylc dependency graphs."""

    def __init__(self, title, suite_polling_tasks=None):
        self.title = title
        pygraphviz.AGraph.__init__(self, directed=True, strict=True)
        # graph attributes
        # - label (suite name)
        self.graph_attr['label'] = title
        if suite_polling_tasks is None:
            suite_polling_tasks = {}
        self.suite_polling_tasks = suite_polling_tasks

    def style_edge(self, left, right):
        pass

    def style_node(self, node_string):
        node = self.get_node(node_string)
        try:
            name, point_string = TaskID.split(node_string)
        except ValueError:
            # Special node?
            if node_string.startswith("__remove_"):
                node.attr['style'] = 'dashed'
                node.attr['label'] = u'\u2702'
                node.attr['shape'] = 'diamond'
                return
            raise
        label = name
        if name in self.suite_polling_tasks:
            label += "\\n" + self.suite_polling_tasks[name][3]
        if not label.startswith('@'):
            label += "\\n" + point_string
        node.attr['label'] = label
        node.attr['URL'] = node_string

    def cylc_remove_nodes_from(self, nodes):
        """Remove nodes, returning extra edge structure if possible.

        Each group of connected to-be-removed nodes is replaced by a
        single special node to preserve dependency info between the
        remaining nodes.

        """
        if not nodes:
            return
        existing_nodes = set(self.nodes())
        remove_nodes = set(nodes)
        remove_node_groups = {}
        groups = {}
        group_new_nodes = {}
        edges = self.edges()
        incoming_remove_edges = []
        outgoing_remove_edges = []
        internal_remove_edges = []
        for l_node, r_node in edges:
            if l_node in remove_nodes:
                if r_node in remove_nodes:
                    # This is an edge between connected nuke nodes.
                    internal_remove_edges.append((l_node, r_node))
                else:
                    # This is an edge between nuke and normal nodes.
                    outgoing_remove_edges.append((l_node, r_node))
            elif r_node in remove_nodes:
                incoming_remove_edges.append((l_node, r_node))

        if not outgoing_remove_edges:
            # Preserving edges doesn't matter - ditch this whole set.
            self.remove_nodes_from(nodes)
            return

        # Loop through all connected nuke nodes and group them up.
        group_num = -1
        for l_node, r_node in sorted(internal_remove_edges):
            l_group = remove_node_groups.get(l_node)
            r_group = remove_node_groups.get(r_node)
            if l_group is None:
                if r_group is None:
                    # Create a new group for l_node and r_node.
                    group_num += 1
                    groups[group_num] = set((l_node, r_node))
                    remove_node_groups[l_node] = group_num
                    remove_node_groups[r_node] = group_num
                else:
                    # r_node already in a group, l_node not - add l_node.
                    groups[r_group].add(l_node)
                    remove_node_groups[l_node] = r_group
            elif r_group is None:
                # l_node already in a group, r_node not - add r_node.
                groups[l_group].add(r_node)
                remove_node_groups[r_node] = l_group
            elif l_group != r_group:
                # They are members of different groups - combine them.
                for node in groups[r_group]:
                    remove_node_groups[node] = l_group
                groups[l_group] = groups[l_group].union(groups[r_group])
                groups.pop(r_group)
        # Some nodes are their own group and don't have connections.
        for node in nodes:
            if node not in remove_node_groups:
                # The node is its own group.
                group_num += 1
                groups[group_num] = set([node])
                remove_node_groups[node] = group_num

        # Consolidate all groups with the same in/out edges.
        group_edges = {}
        for l_node, r_node in incoming_remove_edges:
            r_group = remove_node_groups[r_node]
            group_edges.setdefault(r_group, [set(), set()])
            group_edges[r_group][0].add(l_node)

        for l_node, r_node in outgoing_remove_edges:
            l_group = remove_node_groups[l_node]
            group_edges.setdefault(l_group, [set(), set()])
            group_edges[l_group][1].add(r_node)

        for group1 in sorted(group_edges):
            if group1 not in group_edges:
                continue
            for group2 in sorted(group_edges):
                if (group1 != group2 and
                        group_edges[group1][0] == group_edges[group2][0] and
                        group_edges[group1][1] == group_edges[group2][1]):
                    # Both groups have the same incoming and outgoing edges.
                    for node in groups[group2]:
                        remove_node_groups[node] = group1
                    groups[group1] = groups[group1].union(groups[group2])
                    groups.pop(group2)
                    group_edges.pop(group2)

        # Create a new node name for the group.
        names = set()
        index = -1
        for group in sorted(groups):
            index += 1
            name = "__remove_%s__" % index
            while name in existing_nodes or name in names:
                index += 1
                name = "__remove_%s__" % index
            group_new_nodes[group] = name
            names.add(name)

        new_edges = set()
        groups_have_outgoing = set()
        for l_node, r_node in outgoing_remove_edges:
            new_l_group = remove_node_groups[l_node]
            new_l_node = group_new_nodes[new_l_group]
            new_edges.add((new_l_node, r_node, True, False, False))
            groups_have_outgoing.add(new_l_group)

        for l_node, r_node in incoming_remove_edges:
            new_r_group = remove_node_groups[r_node]
            new_r_node = group_new_nodes[new_r_group]
            if new_r_group not in groups_have_outgoing:
                # Skip any groups that don't have edges on to normal nodes.
                continue
            new_edges.add((l_node, new_r_node, True, False, False))

        self.remove_nodes_from(nodes)
        self.add_edges(sorted(new_edges))

    def add_edges(self, edges, ignore_suicide=False):
        """Add edges and nodes connected by the edges."""
        for edge in sorted(edges):
            left, right, skipped, suicide, conditional = edge
            if left is None and right is None or suicide and ignore_suicide:
                continue
            if left is None:
                pygraphviz.AGraph.add_node(self, right)
                self.style_node(right)
            elif right is None:
                pygraphviz.AGraph.add_node(self, left)
                self.style_node(left)
            else:
                attrs = {}
                if skipped:
                    attrs.update({'style': 'dotted', 'arrowhead': 'oinv'})
                elif conditional and suicide:
                    attrs.update({'style': 'dashed', 'arrowhead': 'odot'})
                elif conditional:
                    attrs.update({'style': 'solid', 'arrowhead': 'onormal'})
                elif suicide:
                    attrs.update({'style': 'dashed', 'arrowhead': 'dot'})
                else:
                    attrs.update({'arrowhead': 'normal'})
                pygraphviz.AGraph.add_edge(self, left, right, **attrs)
                self.style_node(left)
                self.style_node(right)
                self.style_edge(left, right)

    def add_cycle_point_subgraphs(self, edges, fgcolor):
        """Draw nodes within cycle point groups (subgraphs)."""
        point_string_id_map = {}
        for edge_entry in edges:
            for id_ in edge_entry[:2]:
                if id_ is None:
                    continue
                try:
                    point_string = TaskID.split(id_)[1]
                except IndexError:
                    # Probably a special node - ignore it.
                    continue
                point_string_id_map.setdefault(point_string, [])
                point_string_id_map[point_string].append(id_)
        for point_string, ids in point_string_id_map.items():
            self.add_subgraph(
                nbunch=ids, name="cluster_" + point_string,
                label=point_string, fontsize=28, rank="max", style="dashed",
                color=fgcolor
            )

    def add_subgraph(self, nbunch=None, name=None, **attr):
        """Return subgraph induced by nodes in nbunch.

        Overrides (but does the same thing as) pygraphviz's
        AGraph.add_subgraph method.

        """

        name = name.encode(self.encoding)

        handle = pygraphviz.graphviz.agsubg(
            self.handle, name, 1)

        subgraph = pygraphviz.AGraph(
            handle=handle, name=name,
            strict=self.strict, directed=self.directed,
            **attr
        )

        nodes = self.prepare_nbunch(nbunch)
        subgraph.add_nodes_from(nodes)

        return subgraph

    def set_def_style(self, fgcolor, bgcolor, def_node_attr=None):
        """Set default graph styles.

        Depending on light/dark desktop color theme.
        """

        if def_node_attr is None:
            def_node_attr = {}

        # Transparent graph bg - let the desktop theme bg shine through.
        self.graph_attr['bgcolor'] = '#ffffff00'

        fg, bg = str(fgcolor), str(bgcolor)
        # 3-digit hex color codes are not recognized.
        if len(fg) == 4:
            fg = '#' + fg[1:2]*2 + fg[2:3]*2 + fg[3:4]*2
        if len(bg) == 4:
            bg = '#' + bg[1:2]*2 + bg[2:3]*2 + bg[3:4]*2

        # graph and cluster labels:
        self.graph_attr['fontcolor'] = fg
        # node outlines, or node fill if fillcolor is not defined:
        self.node_attr['color'] = fg
        # edges:
        self.edge_attr['color'] = fg  # edges
        # node labels:
        if def_node_attr.get('style', '') == "filled":
            self.node_attr['fontcolor'] = bg  # node labels
        else:
            self.node_attr['fontcolor'] = fg  # node labels


class CGraph(CGraphPlain):
    """Directed Acyclic Graph class for cylc dependency graphs.

    For "cylc graph" - add node and edge attributes according to the
    suite.rc file visualization config.
    """

    def __init__(self, title, suite_polling_tasks=None, vizconfig=None):

        # suite.rc visualization config section
        CGraphPlain.__init__(self, title, suite_polling_tasks)
        if vizconfig is None:
            vizconfig = {}
        self.vizconfig = vizconfig

        # graph attributes
        # - default node attributes
        for item in vizconfig['default node attributes']:
            attr, value = [val.strip() for val in item.split('=', 1)]
            self.node_attr[attr] = value
        # - default edge attributes
        for item in vizconfig['default edge attributes']:
            attr, value = [val.strip() for val in item.split('=', 1)]
            self.edge_attr[attr] = value

        # non-default node attributes by task name
        # TODO - ERROR CHECKING FOR INVALID TASK NAME
        self.task_attr = {}

        for item in self.vizconfig['node attributes']:
            if item in self.vizconfig['node groups']:
                # item is a group of tasks
                for task in self.vizconfig['node groups'][item]:
                    # for each task in the group
                    for attr in self.vizconfig['node attributes'][item]:
                        if task not in self.task_attr:
                            self.task_attr[task] = []
                        self.task_attr[task].append(attr)
            else:
                # item must be a task name
                for attr in self.vizconfig['node attributes'][item]:
                    if item not in self.task_attr:
                        self.task_attr[item] = []
                    self.task_attr[item].append(attr)

    def node_attr_by_taskname(self, node_string):
        try:
            name = TaskID.split(node_string)[0]
        except ValueError:
            # Special node?
            if node_string.startswith("__remove_"):
                return []
            raise
        if name in self.task_attr:
            return self.task_attr[name]
        else:
            return []

    def style_node(self, node_string):
        CGraphPlain.style_node(self, node_string)
        node = self.get_node(node_string)
        attrs = {}
        for item in self.node_attr_by_taskname(node_string):
            attr, value = [val.strip() for val in item.split('=', 1)]
            attrs[attr] = value
            node.attr[attr] = value
        if node.attr['style'] != 'filled' and (
                'color' in attrs and 'fontcolor' not in attrs):
            node.attr['fontcolor'] = node.attr['color']
        if self.vizconfig['use node color for labels']:
            node.attr['fontcolor'] = node.attr['color']
        node.attr['penwidth'] = self.vizconfig['node penwidth']

    def style_edge(self, left, right):
        CGraphPlain.style_edge(self, left, right)
        left_node = self.get_node(left)
        edge = self.get_edge(left, right)
        if self.vizconfig['use node color for edges']:
            edge.attr['color'] = left_node.attr['color']
        elif self.vizconfig['use node fillcolor for edges']:
            if left_node.attr['style'] == 'filled':
                edge.attr['color'] = left_node.attr['fillcolor']
        edge.attr['penwidth'] = self.vizconfig['edge penwidth']

    @classmethod
    def get_graph(
            cls, suiterc, group_nodes=None, ungroup_nodes=None,
            ungroup_recursive=False, group_all=False, ungroup_all=False,
            ignore_suicide=False, subgraphs_on=False, bgcolor=None,
            fgcolor=None):
        """Return dependency graph."""
        # Use visualization settings.
        start_point_string = (
            suiterc.cfg['visualization']['initial cycle point'])

        # Use visualization settings in absence of final cycle point definition
        # when not validating (stops slowdown of validation due to vis
        # settings)
        stop_point = None
        vfcp = suiterc.cfg['visualization']['final cycle point']
        if vfcp:
            try:
                stop_point = get_point_relative(
                    vfcp, get_point(start_point_string)).standardise()
            except ValueError:
                stop_point = get_point(vfcp).standardise()

        if stop_point is not None:
            if stop_point < get_point(start_point_string):
                # Avoid a null graph.
                stop_point_string = start_point_string
            else:
                stop_point_string = str(stop_point)
        else:
            stop_point_string = None

        graph = cls(
            suiterc.suite,
            suiterc.suite_polling_tasks,
            suiterc.cfg['visualization'])

        graph.set_def_style(fgcolor, bgcolor, graph.node_attr)

        gr_edges = suiterc.get_graph_raw(
            start_point_string, stop_point_string,
            group_nodes, ungroup_nodes, ungroup_recursive,
            group_all, ungroup_all)
        graph.add_edges(gr_edges, ignore_suicide)
        if subgraphs_on:
            graph.add_cycle_point_subgraphs(gr_edges, fgcolor)
        return graph
