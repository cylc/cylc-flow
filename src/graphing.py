#!/usr/bin/env python

import re

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

try:
    import pygraphviz
except ImportError:
    # This allows us to carry on with graphing disabled if
    # pygraphviz is not installed.
    raise GraphvizError, 'pygraphviz not available.'

try:
    import xdot
except ImportError:
    raise GraphvizError, 'xdot not available.'

class CGraph( pygraphviz.AGraph ):
    """automatically add cylc's configured graph visualization
    attributes to pygraphviz graphs."""

    def __init__( self, title, vizconfig ):

        # suite.rc visualization config section
        self.vizconfig = vizconfig

        pygraphviz.AGraph.__init__( self, directed=True )

        # graph attributes
        # - label (suite name)
        self.graph_attr['label'] = title
        # - default node attributes
        for item in vizconfig['list of default node attributes']:
            attr, value = re.split( '\s*=\s*', item )
            self.node_attr[ attr ] = value
        # - default edge attributes
        for item in vizconfig['list of default edge attributes']:
            attr, value = re.split( '\s*=\s*', item )
            self.edge_attr[ attr ] = value

        # non-default node attributes by task name
        self.task_attr = {}
        for group in self.vizconfig['task groups']:
            for task in self.vizconfig['task groups'][group]:
                self.task_attr[task] = self.vizconfig['node attributes'][group]

    def node_attr_by_taskname( self, n ):
        name = re.sub( '%.*', '', n )
        if name in self.task_attr:
            return self.task_attr[name]
        else:
            return []

    def add_edge( self, l, r ):
        # l and r are cylc task IDs 
        pygraphviz.AGraph.add_edge( self, l, r )

        nl = self.get_node( l )
        nr = self.get_node( r )

        llabel = re.sub( '%\d{8}(\d\d)', r'(\1)', l )
        rlabel = re.sub( '%\d{8}(\d\d)', r'(\1)', r )
        nl.attr[ 'label' ] = llabel
        nr.attr[ 'label' ] = rlabel

        for item in self.node_attr_by_taskname( l ):
            attr, value = re.split( '\s*=\s*', item )
            nl.attr[ attr ] = value

        for item in self.node_attr_by_taskname( r ):
            attr, value = re.split( '\s*=\s*', item )
            nr.attr[ attr ] = value

        if self.vizconfig['use node fillcolor for edges']:
            edge = self.get_edge( l, r )
            edge.attr['color'] = nl.attr['fillcolor']
