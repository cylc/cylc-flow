#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
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
from cylc import cylc_pyro_client, dump
from cylc import graphing
import gtk
import pygtk
from cylc.cycle_time import ct
from cylc.mkdir_p import mkdir_p
import cylc.dump
####pygtk.require('2.0')

try:
    any
except NameError:
    # any() appeared in Python 2.5
    def any(iterable):
        for entry in iterable:
            if entry:
                return True
        return False

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
    def __init__(self, cfg, info_bar, xdot ):
        super(xupdater, self).__init__()

        self.quit = False
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

        self.cfg = cfg
        self.info_bar = info_bar
        self.stop_summary = None

        self.god = None
        self.mode = "waiting..."
        self.dt = "waiting..."
        self.block = "waiting ..."

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
 
        try:
            client = cylc_pyro_client.client( 
                    self.cfg.suite,
                    self.cfg.pphrase,
                    self.cfg.owner,
                    self.cfg.host,
                    self.cfg.pyro_timeout,
                    self.cfg.port )
            self.god = client.get_proxy( 'state_summary' )
            self.remote = client.get_proxy( 'remote' )
        except:
            if self.stop_summary is None:
                self.stop_summary = dump.get_stop_state_summary(
                                                            self.cfg.suite,
                                                            self.cfg.owner,
                                                            self.cfg.host)
                if any(self.stop_summary):
                    self.info_bar.set_stop_summary(self.stop_summary)
            return False
        else:
            self.stop_summary = None
            self.family_nodes = self.remote.get_family_nodes()
            self.graphed_family_nodes = self.remote.get_graphed_family_nodes()
            self.families = self.remote.get_families()
            self.live_graph_movie, self.live_graph_dir = self.remote.do_live_graph_movie()
            if self.live_graph_movie:
                try:
                    mkdir_p( self.live_graph_dir )
                except Exception, x:
                    print >> sys.stderr, x
                    raise SuiteConfigError, 'ERROR, illegal dir? ' + self.live_graph_dir 

            self.status = "connected"
            self.info_bar.set_status( self.status )
            return True

    def connection_lost( self ):
        self.status = "stopped"

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
        if task_id in self.state_summary:
            return task_id + " " + self.state_summary[task_id]['state']
        if task_id in self.fam_state_summary:
            name, ctime = task_id.split("%")
            text = task_id + " " + self.fam_state_summary[task_id]['state']
            for child in self.families[name]:
                child_id = child + "%" + ctime
                text += "\n    " + self.get_summary(child_id).replace("\n", "\n    ")
            return text
        return task_id

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

        if glbl[ 'blocked' ]:
            self.block = 'blocked'
        else:
            self.block = 'unblocked'

        dt = glbl[ 'last_updated' ]
        self.dt = dt.strftime( " %Y/%m/%d %H:%M:%S" ) 

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
        self.info_bar.set_block( self.block )
        return False
 
    def run(self):
        glbl = None
        while not self.quit:
            if self.update():
                self.update_graph()
                # DO NOT USE gobject.idle_add() HERE - IT DRASTICALLY
                # AFFECTS PERFORMANCE FOR LARGE SUITES? appears to
                # be unnecessary anyway (due to xdot internals?)
                ################ gobject.idle_add( self.update_xdot )
                self.update_xdot()
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
        self.graphw.cylc_add_node( 'waiting', True )
        self.graphw.cylc_add_node( 'retry_delayed', True )
        self.graphw.cylc_add_node( 'runahead', True )
        self.graphw.cylc_add_node( 'queued', True )
        self.graphw.cylc_add_node( 'submitted', True )
        self.graphw.cylc_add_node( 'running', True )
        self.graphw.cylc_add_node( 'succeeded', True )
        self.graphw.cylc_add_node( 'failed', True )
        self.graphw.cylc_add_node( 'held', True )
        self.graphw.cylc_add_node( 'base', True )
        self.graphw.cylc_add_node( 'runtime family', True )
        self.graphw.cylc_add_node( 'trigger family', True )

        waiting = self.graphw.get_node( 'waiting' )
        retry_delayed = self.graphw.get_node( 'retry_delayed' )
        runahead = self.graphw.get_node( 'runahead' )
        queued = self.graphw.get_node( 'queued' )
        submitted = self.graphw.get_node( 'submitted' )
        running = self.graphw.get_node( 'running' )
        succeeded = self.graphw.get_node( 'succeeded' )
        failed = self.graphw.get_node( 'failed' )
        held = self.graphw.get_node( 'held' )
        base = self.graphw.get_node( 'base' )
        family = self.graphw.get_node( 'runtime family' )
        grfamily = self.graphw.get_node( 'trigger family' )


        for node in [ waiting, retry_delayed, runahead, queued, submitted, running, succeeded, failed, held, base, family, grfamily ]:
            node.attr['style'] = 'filled'
            node.attr['shape'] = 'ellipse'
            node.attr['URL'] = 'KEY'

        family.attr['shape'] = 'doublecircle'
        grfamily.attr['shape'] = 'doubleoctagon'

        waiting.attr['fillcolor'] = 'cadetblue2'
        waiting.attr['color'] = 'cadetblue4'

        retry_delayed.attr['fillcolor'] = 'pink'
        retry_delayed.attr['color'] = 'red'

        runahead.attr['fillcolor'] = 'cadetblue'
        runahead.attr['color'] = 'cadetblue4'
        queued.attr['fillcolor'] = 'purple'
        queued.attr['color'] = 'purple'
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

        self.graphw.cylc_add_edge( waiting, submitted, False, style='invis')
        self.graphw.cylc_add_edge( submitted, running, False, style='invis')
        self.graphw.cylc_add_edge( running, runahead, False, style='invis')

        self.graphw.cylc_add_edge( succeeded, failed, False, style='invis')
        self.graphw.cylc_add_edge( failed, held, False, style='invis')
        self.graphw.cylc_add_edge( held, queued, False, style='invis')

        self.graphw.cylc_add_edge( retry_delayed, base, False, style='invis')
        self.graphw.cylc_add_edge( base, grfamily, False, style='invis')
        self.graphw.cylc_add_edge( grfamily, family, False, style='invis')

    def set_live_node_attr( self, node, id, shape=None ):
        # override base graph URL to distinguish live tasks
        node.attr['URL'] = id
        if id in self.state_summary:
            state = self.state_summary[id]['state']
        else:
            state = self.fam_state_summary[id]['state']
        if state == 'submitted':
            node.attr['style'] = 'filled'
            node.attr['fillcolor'] = 'orange'
        elif state == 'running':
            node.attr['style'] = 'filled'
            node.attr['fillcolor'] = 'green'
        elif state == 'waiting':
            node.attr['style'] = 'filled'
            node.attr['fillcolor'] = 'cadetblue2'
        elif state == 'retry_delayed':
            node.attr['style'] = 'filled'
            node.attr['fillcolor'] = 'pink'
        elif state == 'succeeded':
            node.attr['style'] = 'filled'
            node.attr['fillcolor'] = 'grey'
        elif state == 'failed':
            node.attr['style'] = 'filled'
            node.attr['fillcolor'] = 'red'
        elif state == 'held':
            node.attr['style'] = 'filled'
            node.attr['fillcolor'] = 'yellow'
        elif state == 'runahead':
            node.attr['style'] = 'filled'
            node.attr['fillcolor'] = 'cadetblue'
        elif state == 'queued':
            node.attr['style'] = 'filled'
            node.attr['fillcolor'] = 'purple'

        if shape:
            node.attr['shape'] = shape

    def update_graph(self):
        # To do: check edges against resolved ones
        # (adding new ones, and nodes, if necessary)
        self.oldest_ctime = self.global_summary['oldest cycle time']
        self.newest_ctime = self.global_summary['newest cycle time']

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
        gr_edges = self.remote.get_graph_raw( ct(oldest).get(), ct(newest).get(),
                raw=rawx, group_nodes=self.group, ungroup_nodes=self.ungroup,
                ungroup_recursive=self.ungroup_recursive, 
                group_all=self.group_all, ungroup_all=self.ungroup_all) 

        # Get a graph object
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

        for n in self.graphw.nodes():
            n.attr['style'] = 'filled'
            n.attr['fillcolor'] = 'cornsilk'

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

        if self.show_key:
            self.add_graph_key()

        # process extra nodes (important nodes outside of focus range,
        # and family members that aren't plotted in the main graph).
        for state in extra_node_ids:
            for id in extra_node_ids[state]:
                self.graphw.cylc_add_node( id, True )
                self.set_live_node_attr( self.graphw.get_node(id), id, shape='box')
            # add invisible edges to force vertical alignment
            for i in range( 0, len(extra_node_ids[state])):
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

