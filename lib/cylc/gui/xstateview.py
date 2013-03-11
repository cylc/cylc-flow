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

from cylc import cylc_pyro_client, dump, graphing
from cylc.cycle_time import ct
from cylc.gui.stateview import compare_dict_of_dict, PollSchd
from cylc.mkdir_p import mkdir_p
from cylc.state_summary import get_id_summary
from cylc.strftime import strftime
from cylc.TaskID import TaskID
import gobject
import os
import re
import sys
import threading
from time import sleep


try:
    any
except NameError:
    # any() appeared in Python 2.5
    def any(iterable):
        for entry in iterable:
            if entry:
                return True
        return False


class xupdater(threading.Thread):
    def __init__(self, cfg, theme, info_bar, xdot ):
        super(xupdater, self).__init__()

        self.quit = False
        self.focus_start_ctime = None
        self.focus_stop_ctime = None
        self.xdot = xdot
        self.first_update = False
        self.graph_disconnect = False
        self.action_required = True
        self.oldest_ctime = None
        self.newest_ctime = None
        self.orientation = "TB"  # Top to Bottom ordering of nodes, by default.
        self.best_fit = False # If True, xdot will zoom to page size
        self.normal_fit = False # if True, xdot will zoom to 1.0 scale
        self.crop = False
        self.filter_include = None
        self.filter_exclude = None
        self.state_filter = None

        self.families = []
        self.family_nodes = []
        self.graphed_family_nodes = []
        self.live_graph_movie = False

        self.prev_graph_id = ()

        self.cfg = cfg
        self.theme = theme
        self.info_bar = info_bar
        self.stop_summary = None

        self.god = None
        self.mode = "waiting..."
        self.dt = "waiting..."
        self.status = None
        self.poll_schd = PollSchd()

        # empty graphw object:
        self.graphw = graphing.CGraphPlain( self.cfg.suite )
 
        self.reconnect()
        # TO DO: handle failure to get a remote proxy in reconnect()

        self.graph_warned = {}

        self.group = []
        self.ungroup = []
        self.ungroup_recursive = False
        self.group_all = False
        self.ungroup_all = False

        self.graph_frame_count = 0

    def reconnect( self ):

        self.prev_graph_id = ()
        try:
            client = cylc_pyro_client.client( 
                    self.cfg.suite,
                    self.cfg.pphrase,
                    self.cfg.owner,
                    self.cfg.host,
                    self.cfg.pyro_timeout,
                    self.cfg.port )
            self.god = client.get_proxy( 'state_summary' )
            self.sinfo = client.get_proxy( 'suite-info' )

            # on reconnection retrieve static info
            self.family_nodes = self.sinfo.get( 'family nodes' )
            self.graphed_family_nodes = self.sinfo.get( 'graphed family nodes' )
            self.families = self.sinfo.get( 'first-parent descendants' )
            self.live_graph_movie, self.live_graph_dir = self.sinfo.get( 'do live graph movie' )
        except:
            # connection lost
            if self.stop_summary is None:
                self.stop_summary = dump.get_stop_state_summary(
                                                            self.cfg.suite,
                                                            self.cfg.owner,
                                                            self.cfg.host)
                if self.stop_summary is not None and any(self.stop_summary):
                    self.info_bar.set_stop_summary(self.stop_summary)
            return False
        else: 
            self.stop_summary = None
            self.status = "connected"
            self.first_update = True
            self.info_bar.set_status( self.status )
            if self.live_graph_movie:
                try:
                    mkdir_p( self.live_graph_dir )
                except Exception, x:
                    print >> sys.stderr, x
                    print >> sys.stderr, "Disabling live graph movie"
                    self.live_graph_movie = False
            self.first_update = True
            self.status = "connected"
            self.poll_schd.stop()
            self.info_bar.set_status( self.status )
            return True

    def connection_lost( self ):
        self.status = "stopped"
        self.poll_schd.start()
        self.prev_graph_id = ()
        self.normal_fit = True
        # Get an *empty* graph object
        # (comment out to show the last suite state before shutdown)
        self.graphw = graphing.CGraphPlain( self.cfg.suite )
        # TO DO: if connection is lost we should just set the state
        # summary arrays to empty and update to clear only once.
        self.update_xdot()

        if not self.quit:
            self.info_bar.set_state( [] )
            self.info_bar.set_status( self.status )
            if self.stop_summary is not None and any(self.stop_summary):
                self.info_bar.set_stop_summary(self.stop_summary)
        # GTK IDLE FUNCTIONS MUST RETURN FALSE OR WILL BE CALLED MULTIPLE TIMES
        self.reconnect()
        return False

    def get_summary( self, task_id ):
        return get_id_summary( task_id, self.state_summary,
                               self.fam_state_summary, self.families )

    def update(self):
        #print "Updating"
        try:
            [glbl, states_full, fam_states_full] = self.god.get_state_summary()
        except:
            gobject.idle_add( self.connection_lost )
            return False

        # The graph layout is not stable even when (py)graphviz is  
        # presented with the same graph (may be a node ordering issue
        # due to use of dicts?). For this reason we only plot node name 
        # and color (state) and only replot when node content or states 
        # change.  The full state summary contains task timing
        # information that changes continually, so we have to disregard
        # this when checking for changes. So: just extract the critical
        # info here:
        states = {}
        for id in states_full:
            if id not in states:
                states[id] = {}
            states[id]['name' ] = states_full[id]['name' ]
            states[id]['label'] = states_full[id]['label']
            states[id]['state'] = states_full[id]['state']

        f_states = {}
        for id in fam_states_full:
            if id not in states:
                f_states[id] = {}
            f_states[id]['name' ] = fam_states_full[id]['name' ]
            f_states[id]['label'] = fam_states_full[id]['label']
            f_states[id]['state'] = fam_states_full[id]['state'] 
        # always update global info
        self.global_summary = glbl

        if glbl['stopping']:
            self.status = 'stopping'

        elif glbl['paused']:
            self.status = 'held'
       
        elif glbl['will_pause_at']:
            self.status = 'hold at ' + glbl[ 'will_pause_at' ]

        elif glbl['will_stop_at']:
            self.status = 'running to ' + glbl[ 'will_stop_at' ]

        else:
            self.status = 'running'

        self.info_bar.set_status( self.status )

        self.mode = glbl['run_mode']

        dt = glbl[ 'last_updated' ]
        self.dt = strftime( dt, " %Y/%m/%d %H:%M:%S" ) 

        # only update states if a change occurred, or action required
        if self.action_required:
            self.state_summary = states
            self.fam_state_summary = f_states
            return True
        elif self.graph_disconnect:
            return False
        elif not compare_dict_of_dict( states, self.state_summary ):
            # state changed - implicitly includes family state change.
            #print 'STATE CHANGED'
            self.state_summary = states
            self.fam_state_summary = f_states
            return True
        else:
            return False

    def update_globals( self ):
        self.info_bar.set_state( self.global_summary.get( "states", [] ) )
        self.info_bar.set_mode( self.mode )
        self.info_bar.set_time( self.dt )
        return False
 
    def run(self):
        glbl = None
        while not self.quit:
            if self.poll_schd.ready() and self.update():
                needed_no_redraw = self.update_graph()
                # DO NOT USE gobject.idle_add() HERE - IT DRASTICALLY
                # AFFECTS PERFORMANCE FOR LARGE SUITES? appears to
                # be unnecessary anyway (due to xdot internals?)
                ################ gobject.idle_add( self.update_xdot )
                self.update_xdot( no_zoom=needed_no_redraw )
                gobject.idle_add( self.update_globals )
            sleep(1)
        else:
            pass
            ####print "Disconnecting task state info thread"

    def update_xdot(self, no_zoom=False):
        #print 'Updating xdot'
        self.xdot.set_dotcode( self.graphw.to_string(),
                               no_zoom=True )
        if self.first_update:
            self.xdot.widget.zoom_to_fit()
            self.first_update = False
        elif self.best_fit:
            self.xdot.widget.zoom_to_fit()
            self.best_fit = False
        elif self.normal_fit:
            self.xdot.widget.zoom_image( 1.0, center=True )
            self.normal_fit = False

    def set_live_node_attr( self, node, id, shape=None ):
        # override base graph URL to distinguish live tasks
        node.attr['URL'] = id
        if id in self.state_summary:
            state = self.state_summary[id]['state']
        else:
            state = self.fam_state_summary[id]['state']

        node.attr['style'    ] = 'bold,' + self.theme[state]['style']
        node.attr['fillcolor'] = self.theme[state]['color']
        node.attr['color'    ] = self.theme[state]['color' ]
        node.attr['fontcolor'] = self.theme[state]['fontcolor']

        if shape:
            node.attr['shape'] = shape

    def update_graph(self):
        # To do: check edges against resolved ones
        # (adding new ones, and nodes, if necessary)
        self.oldest_ctime = self.global_summary['oldest cycle time']
        self.newest_ctime = self.global_summary['newest cycle time']

        if self.focus_start_ctime:
            oldest = self.focus_start_ctime
            newest = self.focus_stop_ctime
        else:
            oldest = self.oldest_ctime
            newest = self.newest_ctime

        start_time = self.global_summary['start time']

        rawx = None
        if start_time == None or oldest > start_time:
            rawx = True
        else:
            # (show cold start tasks) - TO DO: actual raw start
            rawx = False

        extra_node_ids = {}

        # TO DO: mv ct().get() out of this call (for error checking):
        # TO DO: remote connection exception handling?
        try:
            gr_edges = self.sinfo.get( 'graph raw', ct(oldest).get(), ct(newest).get(),
                    rawx, self.group, self.ungroup, self.ungroup_recursive, 
                    self.group_all, self.ungroup_all) 
        except Exception:  # PyroError
            return False

        extra_ids = []

        for id in self.state_summary:
            try:
                node = self.graphw.get_node( id )
            except AttributeError:
                # No graphw yet.
                break
            except KeyError:
                name, tag = id.split(TaskID.DELIM)
                if any( [name in self.families[fam] for
                         fam in self.graphed_family_nodes] ):
                    # if task name is a member of a family omit it
                    #print 'Not graphing family-collapsed node', id
                    continue

                state = self.state_summary[id]['state']
                if state == 'submitted' or state == 'running' or  state == 'failed' or state == 'held':
                    if id not in extra_ids:
                        extra_ids.append( id )

        current_id = self.get_graph_id( gr_edges, extra_ids )
        needs_redraw = current_id != self.prev_graph_id

        if needs_redraw:
            #Get a graph object
            self.graphw = graphing.CGraphPlain( self.cfg.suite )

            # sort and then add edges in the hope that edges added in the
            # same order each time will result in the graph layout not
            # jumping around (does this help? -if not discard)
            gr_edges.sort()
            for e in gr_edges:
                l, r, dashed, suicide, conditional = e
                style=None
                arrowhead='normal'
                if dashed:
                    style='dashed'
                if suicide:
                    style='dashed'
                    arrowhead='dot'
                if conditional:
                    arrowhead='onormal'
                self.graphw.cylc_add_edge( l, r, True, style=style, arrowhead=arrowhead )

        for n in self.graphw.nodes(): # base node defaults
            n.attr['style'] = 'filled'
            n.attr['color'] = '#888888'
            n.attr['fillcolor'] = 'white'
            n.attr['fontcolor'] = '#888888'

        self.group = []
        self.ungroup = []
        self.group_all = False
        self.ungroup_all = False
        self.ungroup_recursive = False

        self.rem_nodes = []

        # FAMILIES
        if needs_redraw:
            for node in self.graphw.nodes():
                name, tag = node.get_name().split(TaskID.DELIM)
                if name in self.family_nodes:
                    if name in self.graphed_family_nodes:
                        node.attr['shape'] = 'doubleoctagon'
                    else:
                        node.attr['shape'] = 'doublecircle'

            # CROPPING
            if self.crop:
                for node in self.graphw.nodes():
                    #if node in self.rem_nodes:
                    #    continue
                    #if node.get_name() not in self.state_summary and \
                        # len( self.graphw.successors( node )) == 0:
                        # self.remove_empty_nodes( node )
                    if node.get_name() not in self.state_summary:
                        self.rem_nodes.append(node)
                        continue

            # FILTERING:
            for node in self.graphw.nodes():
                id = node.get_name()
                name, ctime = id.split(TaskID.DELIM)
                if self.filter_exclude:
                    if re.match( self.filter_exclude, name ):
                        if node not in self.rem_nodes:
                            self.rem_nodes.append(node)
                if self.filter_include:
                    if not re.match( self.filter_include, name ):
                        if node not in self.rem_nodes:
                            self.rem_nodes.append(node)
                if self.state_filter:
                    if id in self.state_summary:
                        state = self.state_summary[id]['state']
                        if state in self.state_filter:
                            if node not in self.rem_nodes:
                                self.rem_nodes.append(node)

            # remove_nodes_from( nbunch ) - nbunch is any iterable container.
            self.graphw.remove_nodes_from( self.rem_nodes )

        #print '____'
        #print self.families
        #print
        #print self.family_nodes
        #print 
        #print self.graphed_family_nodes
        #print '____'

        for id in self.state_summary:

            try:
                node = self.graphw.get_node( id )
            except KeyError:
                # This live task proxy is not represented in the graph.
                # But it is live so if its state is deemed interesting
                # plot it off to the right of the main graph.

                # Tasks in this category include: members of collapsed
                # families; tasks outside of the current focus range (if
                # one is set), inserted tasks that are defined under
                # [runtime] but not used in the suite graph.

                # Now that we have family state coloring with family
                # member states listed in tool-tips, don't draw
                # off-graph family members:
                name, tag = id.split(TaskID.DELIM)
                if any( [name in self.families[fam] for
                         fam in self.graphed_family_nodes] ):
                    # if task name is a member of a family omit it
                    #print 'Not graphing family-collapsed node', id
                    continue

                if id not in self.graph_warned or not self.graph_warned[id]:
                    print >> sys.stderr, 'WARNING: ' + id + ' is outside of the main graph.'
                    self.graph_warned[id] = True

                state = self.state_summary[id]['state']
                if state == 'submitted' or state == 'running' or  state == 'failed' or state == 'held':
                    if state not in extra_node_ids:
                        extra_node_ids[state] = [id] 
                    else:
                        extra_node_ids[state].append(id)
                    continue
                else:
                    continue

            self.set_live_node_attr( node, id )

        for id in self.fam_state_summary:
            try:
                node = self.graphw.get_node( id )
            except:
                continue
            self.set_live_node_attr( node, id )

        # TO DO: ?optional transitive reduction:
        # self.graphw.tred()

        self.graphw.graph_attr['rankdir'] = self.orientation

        # process extra nodes (important nodes outside of focus range,
        # and family members that aren't plotted in the main graph).
        
        if needs_redraw:
            for state in extra_node_ids:
                for id in extra_node_ids[state]:
                    self.graphw.cylc_add_node( id, True )
                    node = self.graphw.get_node(id)
                    self.set_live_node_attr( node, id, shape='box')

                # add invisible edges to force vertical alignment
                for i in range( len(extra_node_ids[state])):
                   if i == len(extra_node_ids[state]) -1:
                       break
                   self.graphw.cylc_add_edge( extra_node_ids[state][i],
                           extra_node_ids[state][i+1], True, style='invis')

        self.action_required = False

        if self.live_graph_movie:
            self.graph_frame_count += 1
            arg = os.path.join( self.live_graph_dir, 'live' + '-' + \
                    str( self.graph_frame_count ) + '.dot' )
            self.graphw.write( arg )

        self.prev_graph_id = current_id
        return not needs_redraw

    def get_graph_id( self, edges, extra_ids ):
        """If any of these quantities change, the graph should be redrawn."""
        states = self.state_filter
        if self.state_filter:
            states = set(self.state_filter)
        return ( set( edges ), set( extra_ids ), self.crop,
                 self.filter_exclude, self.filter_include, states,
                 self.orientation )
