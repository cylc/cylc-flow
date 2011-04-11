#!/usr/bin/env python

from config import config
import sys
import gobject
import time
import threading
import cylc_pyro_client
import gtk
import pygtk
import cycle_time
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

    def __init__(self, suite, owner, host, port, 
            label_mode, label_status, label_time, xdot ):

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
        self.show_key = True
        self.best_fit = False

        self.suite = suite
        self.owner = owner
        self.host = host
        self.port = port

        self.state_summary = {}
        self.global_summary = {}
        self.god = None
        self.mode = "waiting..."
        self.dt = "waiting..."

        self.label_mode = label_mode
        self.label_status = label_status
        self.label_time = label_time

        self.reconnect()

        self.config = config( self.suite )
        self.graph_warned = {}

        self.collapse = []

    def reconnect( self ):
        try:
            self.god = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port ).get_proxy( 'state_summary' )
        except:
            return False
        else:
            self.label_status.get_parent().modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#19ae0a' ))
            self.status = "connected"
            self.label_status.set_text( self.status )
            return True

    def connection_lost( self ):
        self.status = "NO CONNECTION"
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
            self.status = 'STOPPING'

        elif glbl['paused']:
            self.status = 'PAUSED'
       
        elif glbl['will_pause_at']:
            self.status = 'PAUSE ' + glbl[ 'will_pause_at' ]

        elif glbl['will_stop_at']:
            self.status = 'STOP ' + glbl[ 'will_stop_at' ]

        else:
            self.status = 'running'

        if glbl[ 'dummy_mode' ]:
            #rate = glbl[ 'dummy_clock_rate' ]
            #self.mode = 'DUMMY (' + str( rate ) + 's/hr)'
            #self.mode = 'DUMMY'
            self.mode = 'simulation'
        else:
            self.mode = 'operation'

        dt = glbl[ 'last_updated' ]
        self.dt = dt.strftime( " %Y/%m/%d %H:%M:%S" ) 

        # only update states if a change occurred, or action required
        if self.action_required:
            self.state_summary = states
            return True
        if not compare_dict_of_dict( states, self.state_summary ):
            # state changed
            self.state_summary = states
            return True
        else:
            return False

    def update_gui( self ):
        if not self.graph_disconnect: 
            #print "Updating GRAPH"
            self.update_xdot()
        return False

    def update_globals( self ):
        self.label_mode.set_text( self.mode )
        self.label_status.set_text( self.status )
        self.label_time.set_text( self.dt )
        return False
 
    def run(self):
        glbl = None
        states = {}
        while not self.quit:
            if self.update():
                self.update_graph()
                # DO NOT USE gobject.idle_add() HERE - IT DRASTICALLY
                # AFFECTS PERFORMANCE FOR LARGE SUITES and appears to
                # be unnecessary (due to xdot internals?)
                ###### gobject.idle_add( self.update_gui )
                self.update_gui()
                 
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
            self.xdot.widget.zoom_to_fit()
            self.first_update = False
        elif self.best_fit:
            self.xdot.widget.zoom_to_fit()
            self.best_fit = False


    def add_graph_key(self):
        self.graphw.add_node( 'waiting%YYYYMMDDHH' )
        self.graphw.add_node( 'submitted%YYYYMMDDHH' )
        self.graphw.add_node( 'running%YYYYMMDDHH' )
        self.graphw.add_node( 'finished%YYYYMMDDHH' )
        self.graphw.add_node( 'failed%YYYYMMDDHH' )
        self.graphw.add_node( 'base%YYYYMMDDHH' )

        waiting = self.graphw.get_node( 'waiting%YYYYMMDDHH' )
        submitted = self.graphw.get_node( 'submitted%YYYYMMDDHH' )
        running = self.graphw.get_node( 'running%YYYYMMDDHH' )
        finished = self.graphw.get_node( 'finished%YYYYMMDDHH' )
        failed = self.graphw.get_node( 'failed%YYYYMMDDHH' )
        base = self.graphw.get_node( 'base%YYYYMMDDHH' )

        for node in [ waiting, submitted, running, finished, failed, base ]:
            node.attr['style'] = 'filled'
            node.attr['shape'] = 'box'
            node.attr['URL'] = 'KEY'

        waiting.attr['fillcolor'] = 'cadetblue2'
        waiting.attr['color'] = 'cadetblue4'
        submitted.attr['fillcolor'] = 'orange'
        submitted.attr['color'] = 'darkorange3'
        running.attr['fillcolor'] = 'green'
        running.attr['color'] = 'darkgreen'
        finished.attr['fillcolor'] = 'grey'
        finished.attr['color'] = 'black'
        failed.attr['fillcolor'] = 'red'
        failed.attr['color'] = 'firebrick3'
        base.attr['fillcolor'] = 'cornsilk'
        base.attr['color'] = 'black'

        self.graphw.add_edge( base, waiting, autoURL=False, style='invis')
        self.graphw.add_edge( waiting, submitted, autoURL=False, style='invis')
        self.graphw.add_edge( submitted, running, autoURL=False, style='invis')
        self.graphw.add_edge( running, finished, autoURL=False, style='invis')
        self.graphw.add_edge( finished, failed, autoURL=False, style='invis')

    def set_live_node_attr( self, node, id ):
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
        elif self.state_summary[id]['state'] == 'finished':
            node.attr['style'] = 'filled'
            node.attr['fillcolor'] = 'grey'
        elif self.state_summary[id]['state'] == 'failed':
            node.attr['style'] = 'filled'
            node.attr['fillcolor'] = 'red'

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
            # (show coldstart tasks) - TO DO: actual raw start
            raw = False

        extra_node_ids = {}

        diffhrs = cycle_time.diff_hours( newest, oldest ) + 1
        #if diffhrs < 25:
        #    diffhrs = 25
        self.graphw = self.config.get_graph( oldest, diffhrs, colored=False, raw=raw ) 

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
                if state == 'submitted' or state == 'running' or  state == 'failed':
                    if state not in extra_node_ids:
                        extra_node_ids[state] = [id] 
                    else:
                        extra_node_ids[state].append(id) 
                    continue
                else:
                    continue

            self.set_live_node_attr( node, id )

        # layout adds positions to nodes etc.; this is not required if
        # we're writing to the 'dot' format which must be processed later
        # by the dot layout engine anyway.
        # self.live_graph.layout(prog="dot")
        # TO DO:
        #if self.config["experimental"]["live graph movie"]:
        #    self.live_graph_frame_count += 1
        #    self.live_graph.write( self.config["visualization"]["run time graph directory"], 'live' + '-' + str( self.live_graph_frame_count ) + '.dot' )

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
                    if state == 'submitted' or state == 'running' or  state == 'failed':
                        if state not in extra_node_ids:
                            extra_node_ids[state] = [id] 
                        else:
                            extra_node_ids[state].append(id) 
                self.graphw.remove_node( n )

            self.graphw.remove_node( node )

        if self.show_key:
            self.add_graph_key()

        # process extra nodes (important nodes outside of focus range)
        for state in extra_node_ids:
            for id in extra_node_ids[state]:
                self.graphw.add_node( id )
                self.set_live_node_attr( self.graphw.get_node(id), id)
            # add invisible edges to force vertical alignment
            for i in range( 0, len(extra_node_ids[state])):
               if i == len(extra_node_ids[state]) -1:
                   break
               self.graphw.add_edge( extra_node_ids[state][i],
                       extra_node_ids[state][i+1], autoURL=False,
                       style='invis')

        self.action_required = False

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

