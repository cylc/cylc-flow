#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

import re
from TaskID import TaskID, AsyncTag

class GraphvizError( Exception ):
    """
    Attributes:
        message - what the problem is. 
        TO DO: element - config element causing the problem
    """
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)

# TO DO:
# 1/ Consolidate graph-disabling tests within cylc.
# 2/ Do we still need autoURL below?

try:
    import pygraphviz
except ImportError:
    # This allows us to carry on with graphing disabled if
    # pygraphviz is not installed.
    raise GraphvizError, 'graphviz and/or pygraphviz are not accessible.'

# Not needed as 'import pygraphviz' fails if graphviz is not installed.
#try:
#    testG = pygraphviz.AGraph(directed=True)
#    testG.layout()  # this invokes the pygraphviz 'dot' program
#except ValueError:
#    raise GraphvizError, 'graphviz is not installed or not accessible'

ddmmhh = TaskID.DELIM_RE
tformat = r'\\n'

class CGraphPlain( pygraphviz.AGraph ):
    """Directed Acyclic Graph class for cylc dependency graphs."""

    def __init__( self, title ):
        self.title = title
        pygraphviz.AGraph.__init__( self, directed=True )
        # graph attributes
        # - label (suite name)
        self.graph_attr['label'] = title

    def node_attr_by_taskname( self, n ):
        name = re.sub( TaskID.DELIM+'.*', '', n )
        if name in self.task_attr:
            return self.task_attr[name]
        else:
            return []

    def style_edge( self, l, r ):
        pass

    def style_node( self, n, autoURL, base=False ):
        node = self.get_node(n)
        label = re.sub( ddmmhh, tformat, n )
        node.attr[ 'label' ] = label
        if autoURL:
            if base:
                # To Do: This is only called from cylc_add_edge in this
                # base class ... should it also be called from add_node?
                node.attr[ 'URL' ] = 'base:' + n
            else:
                node.attr['URL'] = n

    def cylc_add_node( self, n, autoURL, **attr ):
        pygraphviz.AGraph.add_node( self, n, **attr )
        self.style_node( n, autoURL )

    def cylc_add_edge( self, l, r, autoURL, **attr ):
        if l == None and r == None:
            pass
        elif l == None:
            self.cylc_add_node( r, autoURL )
        elif r == None:
            self.cylc_add_node( l, autoURL )
        elif l == r:
            # pygraphviz 1.1 adds a node instead of a self-edge
            # which results in a KeyError in get_edge() below.
            self.cylc_add_node( l, autoURL )
        else:
            pygraphviz.AGraph.add_edge( self, l, r, **attr )
            self.style_node( l, autoURL, base=True )
            self.style_node( r, autoURL, base=True )
            self.style_edge( l, r )

class CGraph( CGraphPlain ):
    """Directed Acyclic Graph class for cylc dependency graphs.
    This class automatically adds node and edge attributes 
    according to the suite.rc file visualization config."""

    def __init__( self, title, vizconfig ):

        # suite.rc visualization config section
        self.vizconfig = vizconfig

        CGraphPlain.__init__( self, title )

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
        # TO DO: ERROR CHECKING FOR INVALID TASK NAME
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

    def style_node( self, n, autoURL, base=False ):
        super( self.__class__, self ).style_node( n, autoURL, False )
        node = self.get_node(n)
        for item in self.node_attr_by_taskname( n ):
            attr, value = re.split( '\s*=\s*', item )
            node.attr[ attr ] = value
        if self.vizconfig['use node color for labels']:
            node.attr['fontcolor'] = node.attr['color']

    def style_edge( self, l, r ):
        super( self.__class__, self ).style_edge( l, r )
        nl = self.get_node(l)
        nr = self.get_node(r)
        edge = self.get_edge(l,r)
        if self.vizconfig['use node color for edges']:
            if nl.attr['style'] == 'filled':
                edge.attr['color'] = nl.attr['fillcolor']
            else:
                edge.attr['color'] = nl.attr['color']


class edge( object):
    def __init__( self, l, r, cyclr, sasl=False, suicide=False, conditional=False ):
        """contains qualified node names, e.g. 'foo[T-6]:out1'"""
        self.left = l
        self.right = r
        self.cyclr = cyclr
        self.sasl = sasl
        self.suicide = suicide
        self.conditional = conditional

    def get_right( self, intag, not_first_cycle, raw, startup_only, exclude ):
        tag = str(intag)
        # (exclude was briefly used - April 2011 - to stop plotting temporary tasks)
        if self.right in exclude:
            return None
        if self.right == None:
            return None
        first_cycle = not not_first_cycle
        if self.right in startup_only:
            if not first_cycle or raw:
                return None

        # strip off special outputs
        self.right = re.sub( ':\w+', '', self.right )

        return TaskID( self.right, tag )

    def get_left( self, intag, not_first_cycle, raw, startup_only, exclude ):
        tag = str(intag)
        # (exclude was briefly used - April 2011 - to stop plotting temporary tasks)
        if self.left in exclude:
            return None

        first_cycle = not not_first_cycle

        # strip off special outputs
        left = re.sub( ':\w+', '', self.left )

        if re.search( '\[\s*T\s*-\d+\s*\]', left ) and first_cycle:
            # ignore intercycle deps in first cycle
            return None

        if left in startup_only:
            if not first_cycle or raw:
                return None

        if self.sasl:
            # left node is asynchronous, so override the cycler
            tag = '1'
        else:
            m = re.search( '(\w+)\s*\[\s*T\s*([+-])(\d+)\s*\]', left )
            if m: 
                left, sign, offset = m.groups()
                tag = self.cyclr.__class__.offset( tag, offset )
            else:
                tag = tag

        return TaskID( left, tag )


