#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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

import re
import pygraphviz
from cylc.task_id import TaskID
from cycling.loader import get_point, get_point_relative, get_interval
from graphnode import graphnode

# TODO: Do we still need autoURL below?

class CGraphPlain( pygraphviz.AGraph ):
    """Directed Acyclic Graph class for cylc dependency graphs."""

    def __init__( self, title, suite_polling_tasks={} ):
        self.title = title
        pygraphviz.AGraph.__init__( self, directed=True, strict=False )
        # graph attributes
        # - label (suite name)
        self.graph_attr['label'] = title
        self.suite_polling_tasks = suite_polling_tasks

    def node_attr_by_taskname( self, node_string ):
        try:
            name, point_string = TaskID.split(node_string)
        except ValueError:
            # Special node?
            if node_string.startswith("__remove_"):
                return []
            raise
        if name in self.task_attr:
            return self.task_attr[name]
        else:
            return []

    def style_edge( self, left, right ):
        pass

    def style_node( self, node_string, autoURL, base=False ):
        node = self.get_node( node_string )
        try:
            name, point_string = TaskID.split(node_string)
        except ValueError:
            # Special node?
            if node_string.startswith("__remove_"):
                node.attr['style'] = 'dashed'
                node.attr['label'] = u'\u2702'
                return
            raise
        label = name
        if name in self.suite_polling_tasks:
            label += "\\n" + self.suite_polling_tasks[name][3]
        label += "\\n" + point_string
        node.attr[ 'label' ] = label
        if autoURL:
            if base:
                # TODO - This is only called from cylc_add_edge in this
                # base class ... should it also be called from add_node?
                node.attr[ 'URL' ] = 'base:' + node_string
            else:
                node.attr['URL'] = node_string

    def cylc_add_node( self, node_string, autoURL, **attr ):
        pygraphviz.AGraph.add_node( self, node_string, **attr )
        self.style_node( node_string, autoURL )

    def cylc_add_edge( self, left, right, autoURL, **attr ):
        if left == None and right == None:
            pass
        elif left == None:
            self.cylc_add_node( right, autoURL )
        elif right == None:
            self.cylc_add_node( left, autoURL )
        else:
            pygraphviz.AGraph.add_edge( self, left, right, **attr )
            self.style_node( left, autoURL, base=True )
            self.style_node( right, autoURL, base=True )
            self.style_edge( left, right )

    def cylc_remove_nodes_from(self, nodes):
        """Remove nodes, returning extra edge structure if possible.

        Each group of connected to-be-removed nodes is replaced by a
        single special node to preserve dependency info between the
        remaining nodes.

        """
        if not nodes:
            return
        existing_nodes = set(self.nodes())
        add_edges = set()
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
        for group, group_nodes in sorted(groups.items()):
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
        self.add_edges(list(new_edges))

    def add_edges( self, edges, ignore_suicide=False ):
        edges.sort() # TODO: does sorting help layout stability?
        for edge in edges:
            left, right, skipped, suicide, conditional = edge
            if suicide and ignore_suicide:
                continue
            attrs = {}
            if conditional:
                if suicide:
                    attrs['style'] = 'dashed'
                    attrs['arrowhead'] = 'odot'
                else:
                    attrs['style'] = 'solid'
                    attrs['arrowhead'] = 'onormal'
            else:
                if suicide:
                    attrs['style'] = 'dashed'
                    attrs['arrowhead'] = 'dot'
                else:
                    attrs['style'] = 'solid'
                    attrs['arrowhead'] = 'normal'
            if skipped:
                # override
                attrs['style'] = 'dotted'
                attrs['arrowhead'] = 'oinv'

            attrs['penwidth'] = 2

            self.cylc_add_edge(
                left, right, True, **attrs
            )

    def add_cycle_point_subgraphs( self, edges ):
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
                label=point_string, fontsize=28, rank="max", style="dashed"
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

        for left, right in self.edges():
            if left in subgraph and right in subgraph: 
                subgraph.add_edge(left, right)

        return subgraph


class CGraph( CGraphPlain ):
    """Directed Acyclic Graph class for cylc dependency graphs.
    This class automatically adds node and edge attributes
    according to the suite.rc file visualization config."""

    def __init__( self, title, suite_polling_tasks={}, vizconfig={} ):

        # suite.rc visualization config section
        self.vizconfig = vizconfig
        CGraphPlain.__init__( self, title, suite_polling_tasks )

        # graph attributes
        # - default node attributes
        for item in vizconfig['default node attributes']:
            attr, value = re.split( '\s*=\s*', item )
            self.node_attr[ attr ] = value
        # - default edge attributes
        for item in vizconfig['default edge attributes']:
            attr, value = re.split( '\s*=\s*', item )
            self.edge_attr[ attr ] = value

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
                        self.task_attr[task].append( attr )
            else:
                # item must be a task name
                for attr in self.vizconfig['node attributes'][item]:
                    if item not in self.task_attr:
                        self.task_attr[item] = []
                    self.task_attr[item].append( attr )

    def style_node( self, node_string, autoURL, base=False ):
        super( self.__class__, self ).style_node(
            node_string, autoURL, False)
        node = self.get_node(node_string)
        for item in self.node_attr_by_taskname( node_string ):
            attr, value = re.split( '\s*=\s*', item )
            node.attr[ attr ] = value
        if self.vizconfig['use node color for labels']:
            node.attr['fontcolor'] = node.attr['color']

    def style_edge( self, left, right ):
        super( self.__class__, self ).style_edge( left, right )
        left_node = self.get_node(left)
        edge = self.get_edge(left, right)
        if self.vizconfig['use node color for edges']:
            if left_node.attr['style'] == 'filled':
                edge.attr['color'] = left_node.attr['fillcolor']
            else:
                edge.attr['color'] = left_node.attr['color']


class edge( object):
    def __init__( self, left, right, sequence, suicide=False,
                  conditional=False ):
        """contains qualified node names, e.g. 'foo[T-6]:out1'"""
        self.left = left
        if suicide:
            # Change name of suicide nodes to avoid cyclic dep check.
            # (this is removed in config.get_graph() for normal use).
            self.right = "!" + right
        else:
            self.right = right
        self.suicide = suicide
        self.sequence = sequence
        self.conditional = conditional

    def get_right( self, inpoint, start_point):
        inpoint_string = str(inpoint)
        if self.right == None:
            return None

        # strip off special outputs
        self.right = re.sub( ':\w+', '', self.right )

        return TaskID.get(self.right, inpoint_string)

    def get_left( self, inpoint, start_point, base_interval ):
        # strip off special outputs
        left = re.sub( ':[\w-]+', '', self.left )

        left_graphnode = graphnode(left, base_interval=base_interval)
        if left_graphnode.offset_is_from_ict:
            point = get_point_relative(left_graphnode.offset_string,
                                       start_point)
        elif left_graphnode.offset_string:
            point = get_point_relative(left_graphnode.offset_string, inpoint)
        else:
            point = inpoint
        name = left_graphnode.name

        return TaskID.get(name, point)
