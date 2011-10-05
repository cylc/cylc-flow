#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2011 Hilary Oliver, NIWA
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

import sys, os, re
import gobject
import time
import threading
from cylc import cylc_pyro_client
import gtk
import pygtk
from cylc.cycle_time import ct
####pygtk.require('2.0')

def compare_dict_of_dict( one, two ):
    # return True if one == two, else return False.
    for key in one:
        if key not in two:
            return False
        for subkey in one[ key ]:
            if subkey not in two[ key ]:
                return False
            if one[key][subkey] != two[key][subkey]:
                return False
    for key in two:
        if key not in one:
            return False
        for subkey in two[ key ]:
            if subkey not in one[ key ]:
                return False
            if two[key][subkey] != one[key][subkey]:
                return False
    return True

class xupdater(threading.Thread):

    def __init__(self, suite, suiterc, owner, host, port, 
            label_mode, label_status, label_time, label_block, xdot ):

        super(xupdater, self).__init__()

        self.quit = False
        self.start_ctime = None
        self.stop_ctime = None
        self.xdot = xdot
        self.first_update = True
        self.graph_disconnect = False
        self.action_required = True
        self.oldest_ctime = None
        self.newest_ctime = None
        self.show_key = False # graph key visibility default
        self.best_fit = False
        self.crop = False
        self.filter_include = None
        self.filter_exclude = None
        self.state_filter = None

        self.suite = suite
        self.owner = owner
        self.host = host
        self.port = port

        self.state_summary = {}
        self.global_summary = {}
        self.god = None
        self.mode = "mode:\nwaiting..."
        self.dt = "state last updated at:\nwaiting..."
        self.block = "access:\nwaiting ..."

        self.label_mode = label_mode
        self.label_status = label_status
        self.label_time = label_time
        self.label_block = label_block

        self.reconnect()

        self.suiterc = suiterc
        self.family_nodes = suiterc.members.keys()
        self.graphed_family_nodes = suiterc.families_used_in_graph

        self.graph_warned = {}

        self.collapse = []

        self.group = []
        self.ungroup = []
        self.ungroup_recursive = False
        self.group_all = False
        self.ungroup_all = False

        self.graph_frame_count = 0

    def reconnect( self ):
        try:
            self.god = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port ).get_proxy( 'state_summary' )
        except:
            return False
        else:
            self.label_status.get_parent().modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#19ae0a' ))
            self.status = "status:\nconnected"
            self.label_status.set_text( self.status )
            return True

    def connection_lost( self ):
        self.status = "status:\nSTOPPED"
        self.label_status.get_parent().modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#ff1a45' ))
        self.label_status.set_text( self.status )
        # GTK IDLE FUNCTIONS MUST RETURN FALSE OR WILL BE CALLED MULTIPLE TIMES
        self.reconnect()
        return False

    def update(self):
        #print "Updating"
        try:
            [glbl, states] = self.god.get_state_summary()
        except:
            gobject.idle_add( self.connection_lost )
            return False

        # always update global info
        self.global_summary = glbl

        if glbl['stopping']:
            self.status = 'status:\nSTOPPING'

        elif glbl['paused']:
            self.status = 'status:\nHELD'
       
        elif glbl['will_pause_at']:
            self.status = 'status:\nHOLD ' + glbl[ 'will_pause_at' ]

        elif glbl['will_stop_at']:
            self.status = 'status:\nSTOP ' + glbl[ 'will_stop_at' ]

        else:
            self.status = 'status:\nrunning'

        if glbl[ 'simulation_mode' ]:
            #rate = glbl[ 'simulation_clock_rate' ]
            #self.mode = 'SIMULATION (' + str( rate ) + 's/hr)'
            #self.mode = 'SIMULATION'
            self.mode = 'mode:\nsimulation'
        else:
            self.mode = 'mode:\nlive'

        if glbl[ 'blocked' ]:
            self.block = 'access:\nblocked'
        else:
            self.block = 'access:\nunblocked'

        dt = glbl[ 'last_updated' ]
        self.dt = 'state last updated at:\n' + dt.strftime( " %Y/%m/%d %H:%M:%S" ) 

        # only update states if a change occurred, or action required
        if self.action_required:
            self.state_summary = states
            return True
        elif self.graph_disconnect:
            return False
        elif not compare_dict_of_dict( states, self.state_summary ):
            # state changed
            self.state_summary = states
            return True
        else:
            return False

    def update_globals( self ):
        self.label_mode.set_text( self.mode )
        self.label_time.set_text( self.dt )

        self.label_block.set_text( self.block )
        if self.block == 'access:\nblocked':
            self.label_block.get_parent().modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#ff1a45' ))
        else:
            self.label_block.get_parent().modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#19ae0a' ))

        self.label_status.set_text( self.status )
        if re.search( 'STOPPED', self.status ):
            self.label_status.get_parent().modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#ff1a45' ))
        elif re.search( 'STOP', self.status ):  # stopping
            self.label_status.get_parent().modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#ff8c2a' ))
        elif re.search( 'HELD', self.status ):
            self.label_status.get_parent().modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#ffde00' ))
        else:
            self.label_status.get_parent().modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#19ae0a' ))
 
        return False
 
    def run(self):
        glbl = None
        states = {}
        while not self.quit:
            if self.update():
                self.update_graph()
                # DO NOT USE gobject.idle_add() HERE - IT DRASTICALLY
                # AFFECTS PERFORMANCE FOR LARGE SUITES? appears to
                # be unnecessary anyway (due to xdot internals?)
                ################ gobject.idle_add( self.update_xdot )
                self.update_xdot()
                 
            # TO DO: only update globals if they change, as for tasks
            gobject.idle_add( self.update_globals )
            time.sleep(1)
        else:
            pass
            ####print "Disconnecting task state info thread"

    def update_xdot(self):
        #print 'Updating xdot'
        self.xdot.set_dotcode( self.graphw.to_string())
        if self.first_update:
            #self.xdot.widget.zoom_to_fit()
            self.first_update = False
        elif self.best_fit:
            self.xdot.widget.zoom_to_fit()
            self.best_fit = False

    def add_graph_key(self):
        self.graphw.add_node( 'waiting' )
        self.graphw.add_node( 'runahead' )
        self.graphw.add_node( 'submitted' )
        self.graphw.add_node( 'running' )
        self.graphw.add_node( 'succeeded' )
        self.graphw.add_node( 'failed' )
        self.graphw.add_node( 'held' )
        self.graphw.add_node( 'base' )
        self.graphw.add_node( 'runtime family' )
        self.graphw.add_node( 'trigger family' )

        waiting = self.graphw.get_node( 'waiting' )
        runahead = self.graphw.get_node( 'runahead' )
        submitted = self.graphw.get_node( 'submitted' )
        running = self.graphw.get_node( 'running' )
        succeeded = self.graphw.get_node( 'succeeded' )
        failed = self.graphw.get_node( 'failed' )
        held = self.graphw.get_node( 'held' )
        base = self.graphw.get_node( 'base' )
        family = self.graphw.get_node( 'runtime family' )
        grfamily = self.graphw.get_node( 'trigger family' )


        for node in [ waiting, runahead, submitted, running, succeeded, failed, held, base, family, grfamily ]:
            node.attr['style'] = 'filled'
            node.attr['shape'] = 'ellipse'
            node.attr['URL'] = 'KEY'

        family.attr['shape'] = 'doublecircle'
        grfamily.attr['shape'] = 'doubleoctagon'

        waiting.attr['fillcolor'] = 'cadetblue2'
        waiting.attr['color'] = 'cadetblue4'
        runahead.attr['fillcolor'] = 'cadetblue'
        runahead.attr['color'] = 'cadetblue4'
        submitted.attr['fillcolor'] = 'orange'
        submitted.attr['color'] = 'darkorange3'
        running.attr['fillcolor'] = 'green'
        running.attr['color'] = 'darkgreen'
        succeeded.attr['fillcolor'] = 'grey'
        succeeded.attr['color'] = 'black'
        failed.attr['fillcolor'] = 'red'
        failed.attr['color'] = 'firebrick3'
        base.attr['fillcolor'] = 'cornsilk'
        base.attr['color'] = 'black'
        family.attr['fillcolor'] = 'cornsilk'
        family.attr['color'] = 'black'
        grfamily.attr['fillcolor'] = 'cornsilk'
        grfamily.attr['color'] = 'black'
        held.attr['fillcolor'] = 'yellow'
        held.attr['color'] = 'black'

        self.graphw.add_edge( waiting, submitted, autoURL=False, style='invis')
        self.graphw.add_edge( submitted, running, autoURL=False, style='invis')
        self.graphw.add_edge( running, runahead, autoURL=False, style='invis')

        self.graphw.add_edge( succeeded, failed, autoURL=False, style='invis')
        self.graphw.add_edge( failed, held, autoURL=False, style='invis')

        self.graphw.add_edge( base, grfamily, autoURL=False, style='invis')
        self.graphw.add_edge( grfamily, family, autoURL=False, style='invis')

    def set_live_node_attr( self, node, id, shape=None ):
        # override base graph URL to distinguish live tasks
        node.attr['URL'] = id
        if self.state_summary[id]['state'] == 'submitted':
            node.attr['style'] = 'filled'
            node.attr['fillcolor'] = 'orange'
        elif self.state_summary[id]['state'] == 'running':
            node.attr['style'] = 'filled'
            node.attr['fillcolor'] = 'green'
        elif self.state_summary[id]['state'] == 'waiting':
            node.attr['style'] = 'filled'
            node.attr['fillcolor'] = 'cadetblue2'
        elif self.state_summary[id]['state'] == 'succeeded':
            node.attr['style'] = 'filled'
            node.attr['fillcolor'] = 'grey'
        elif self.state_summary[id]['state'] == 'failed':
            node.attr['style'] = 'filled'
            node.attr['fillcolor'] = 'red'
        elif self.state_summary[id]['state'] == 'held':
            node.attr['style'] = 'filled'
            node.attr['fillcolor'] = 'yellow'
        elif self.state_summary[id]['state'] == 'runahead':
            node.attr['style'] = 'filled'
            node.attr['fillcolor'] = 'cadetblue'

        if shape:
            node.attr['shape'] = shape

    def update_graph(self):
        # To do: check edges against resolved ones
        # (adding new ones, and nodes, if necessary)
        self.oldest_ctime = self.global_summary['oldest cycle time']
        self.newest_ctime = self.global_summary['newest cycle time']

        if self.start_ctime:
            oldest = self.start_ctime
            newest = self.stop_ctime
        else:
            oldest = self.oldest_ctime
            newest = self.newest_ctime

        start_time = self.global_summary['start time']

        if start_time == None or oldest > start_time:
            raw = True
        else:
            # (show cold start tasks) - TO DO: actual raw start
            raw = False

        extra_node_ids = {}

        nct = ct(newest)
        oct = ct(oldest)
        diffhrs = nct.subtract_hrs( oct ) + 1

        #if diffhrs < 25:
        #    diffhrs = 25
        self.graphw = self.suiterc.get_graph( oldest, diffhrs,
                colored=False, raw=raw, group_nodes=self.group,
                ungroup_nodes=self.ungroup,
                ungroup_recursive=self.ungroup_recursive, 
                group_all=self.group_all, ungroup_all=self.ungroup_all) 
        self.group = []
        self.ungroup = []
        self.group_all = False
        self.ungroup_all = False
        self.ungroup_recursive = False

        self.rem_nodes = []

        # FAMILIES
        for node in self.graphw.nodes():
            name, tag = node.get_name().split('%')
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
            name, ctime = id.split('%')
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

        for id in self.state_summary:
            try:
                node = self.graphw.get_node( id )
            except KeyError:
                # this task is not present in the live graph
                # TO DO: FAMILY MEMBERS NEED TO SELF-IDENTIFY IN STATE DUMP
                #if hasattr( task, 'member_of' ):
                    # OK: member of a family
                    #continue
                #else:
                if id not in self.graph_warned or \
                        not self.graph_warned[id]:
                    print >> sys.stderr, 'WARNING: SUITE TASK NOT GRAPHED: ' + id
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

        for id in self.collapse:
            try:
                node = self.graphw.get_node( id )
            except:
                # node no longer in graph
                self.collapse.remove(id)
                continue

            self.feedins = []
            self.collapsems = []
            for n in self.graphw.successors( id ):
                self.remove_tree( id )

            # replace collapsed node with a stand-in
            new_node_label = 'SUBTREE:' + id
            self.graphw.add_node( new_node_label )
            new_node = self.graphw.get_node( new_node_label )
            #new_node.attr['shape'] = 'doublecircle'
            new_node.attr['shape'] = 'tripleoctagon'
            new_node.attr['style'] = 'filled'
            new_node.attr['color'] = 'magenta'
            new_node.attr['fillcolor'] = 'yellow'
            new_node.attr['URL'] = new_node_label

            for n in self.graphw.predecessors( node ):
                self.graphw.add_edge( n, new_node, autoURL=False )

            name, topctime = id.split('%')
            for n in self.feedins:
                #self.feedintops = []
                #self.follow_up(n,topctime)
                #if n not in self.collapsems and n not in self.feedintops:
                if n not in self.collapsems:
                    self.graphw.add_edge( n, new_node, autoURL=False )
                #for m in self.feedintops:
                #    self.graphw.remove_node( m )

            for n in self.collapsems:
                id = n.get_name()
                if id in self.state_summary:
                    # (else is part of the base graph)
                    state = self.state_summary[id]['state']
                    if state == 'submitted' or state == 'running' or  state == 'failed' or state == 'held':
                        if state not in extra_node_ids:
                            extra_node_ids[state] = [id] 
                        else:
                            extra_node_ids[state].append(id) 
                self.graphw.remove_node( n )

            self.graphw.remove_node( node )

        # TO DO: ?optional transitive reduction:
        # self.graphw.tred()

        if self.show_key:
            self.add_graph_key()

        # process extra nodes (important nodes outside of focus range,
        # and family members that aren't plotted in the main graph).
        for state in extra_node_ids:
            for id in extra_node_ids[state]:
                self.graphw.add_node( id )
                self.set_live_node_attr( self.graphw.get_node(id), id, shape='box')
            # add invisible edges to force vertical alignment
            for i in range( 0, len(extra_node_ids[state])):
               if i == len(extra_node_ids[state]) -1:
                   break
               self.graphw.add_edge( extra_node_ids[state][i],
                       extra_node_ids[state][i+1], autoURL=False,
                       style='invis')

        self.action_required = False

        if self.suiterc["development"]["live graph movie"]:
            self.graph_frame_count += 1
            self.graphw.write( os.path.join( self.suiterc["visualization"]["run time graph directory"], 'live' + '-' + str( self.graph_frame_count ) + '.dot' ))

    #def follow_up( self, id, topctime ):
    #    name, ctime = id.split('%')
    #    if int(ctime) < int(topctime):
    #        return
    #    pred = self.graphw.predecessors( id )
    #    if len(pred) == 0:
    #        # id has no predecessors
    #        self.feedintops.append(id)
    #        return
    #    for m in pred:
    #        self.follow_up(m,topctime)

    def remove_empty_nodes( self, node ):
        # recursively remove base graph nodes whose predecessors are
        # also not live nodes. ABANDONED - this doesn't have the desired
        # effect as we need to trace all branches encountered! 
        empty = True
        for n in self.graphw.predecessors( node ):
            if n in self.rem_nodes:
                continue
            if n.get_name() in self.state_summary.keys():
                empty = False
            else:
                self.remove_empty_nodes( n )
        if empty:
            self.rem_nodes.append(node)

    def remove_tree(self, id ):
        node = self.graphw.get_node(id)
        for n in self.graphw.successors( id ):
            for m in self.graphw.predecessors( n ):
                if m != node:
                    self.feedins.append(m)
                #else:
                #    print 'EQUAL'
            self.remove_tree( n )
            if n not in self.collapsems:
                self.collapsems.append(n)

    def get_leaves( self ):
        od = self.graphw.out_degree(with_labels=True)
        leaves = []
        for id in od:
            if od[id] == 0:
                leaves.append(id)
        return leaves

