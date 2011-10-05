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

from cylc.config import config
import sys, re, string
import gobject
import time
import threading
from cylc import cylc_pyro_client
import gtk
import pygtk
from string import zfill
####pygtk.require('2.0')

def compare_dict_of_dict( one, two ):
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

def markup( col, string ):
    #return string
    return '<span foreground="' + col + '">' + string + '</span>'

def get_col( state ):
    if state == 'waiting':
        return '#38a'
    elif state == 'submitted':
        return '#f83'
    elif state == 'running':
        return '#0a0'
    elif state == 'failed':
        return '#f00'
    elif state == 'held':
        return '#bb0'
    elif state == 'runahead':
        return '#216'
    else:
        return '#000'

def get_col_priority( priority ):
    if priority == 'NORMAL':
        return '#006'
    elif priority == 'WARNING':
        return '#e400ff'
    elif priority == 'CRITICAL':
        return '#ff0072'
    elif priority == 'DEBUG':
        return '#d2ff00'
    else:
        # not needed
        return '#f0f'

class updater(threading.Thread):

    def __init__(self, suite, owner, host, port, imagedir,
            led_liststore, ttreeview, task_list,
            label_mode, label_status, label_time, label_block ):

        super(updater, self).__init__()

        self.quit = False
        self.autoexpand = True

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

        self.ttreeview = ttreeview
        self.ttreestore = ttreeview.get_model().get_model()
        self.led_liststore = led_liststore
        self.task_list = task_list
        self.label_mode = label_mode
        self.label_status = label_status
        self.label_time = label_time
        self.label_block = label_block

        self.reconnect()

        self.waiting_led = gtk.gdk.pixbuf_new_from_file( imagedir + "/lamps/led-waiting-glow.xpm" )
        self.runahead_led = gtk.gdk.pixbuf_new_from_file( imagedir + "/lamps/led-runahead-glow.xpm" )
        self.submitted_led = gtk.gdk.pixbuf_new_from_file( imagedir + "/lamps/led-submitted-glow.xpm" )
        self.running_led = gtk.gdk.pixbuf_new_from_file( imagedir + "/lamps/led-running-glow.xpm" )
        self.failed_led = gtk.gdk.pixbuf_new_from_file( imagedir + "/lamps/led-failed-glow.xpm" )
        self.stopped_led = gtk.gdk.pixbuf_new_from_file( imagedir + "/lamps/led-stopped-glow.xpm" )
        self.succeeded_led = gtk.gdk.pixbuf_new_from_file( imagedir + "/lamps/led-finished.xpm" )

        self.empty_led = gtk.gdk.pixbuf_new_from_file( imagedir + "/lamps/led-empty.xpm" )

        self.led_digits_one = []
        self.led_digits_two = []
        self.led_digits_blank = gtk.gdk.pixbuf_new_from_file( imagedir + "/digits/one/digit-blank.xpm" )
        for i in range(10):
            self.led_digits_one.append( gtk.gdk.pixbuf_new_from_file( imagedir + "/digits/one/digit-" + str(i) + ".xpm" ))
            self.led_digits_two.append( gtk.gdk.pixbuf_new_from_file( imagedir + "/digits/two/digit-" + str(i) + ".xpm" ))

        #self.config = config( self.suite )

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
        # clear the ttreestore ...
        self.ttreestore.clear()
        # ... and the data structure used to populate it (otherwise 
        # we'll get a blank treeview after a shutdown and restart via
        # the same gui when nothing is changing (e.g. all tasks waiting
        # on a clock trigger - because we only update the tree after
        # changes in the state summary)
        self.state_summary = {}

        # Keep LED panel to show what state the suite was in at shutdown
        #self.led_liststore.clear()

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

        # only update states if a change occurred
        if compare_dict_of_dict( states, self.state_summary ):
            #print "STATE UNCHANGED"
            # only update if state changed
            return False
        else:
            #print "STATE CHANGED"
            self.state_summary = states
            return True

    def search_level( self, model, iter, func, data ):
        while iter:
            if func( model, iter, data):
                return iter
            iter = model.iter_next(iter)
        return None

    def search_treemodel( self, model, iter, func, data ):
        while iter:
            if func( model, iter, data):
                return iter
            result = self.search_treemodel( model, model.iter_children(iter), func, data)
            if result:
                return result
            iter = model.iter_next(iter)
        return None

    def match_func( self, model, iter, data ):
        column, key = data
        value = model.get_value( iter, column )
        return value == key

    def digitize( self, ct ):
        # Digitize cycle time for the LED panel display.
        # For asynchronous tasks blank-pad the task tag.
        led_ctime = []
        if len(ct) < 10:
            zct = string.rjust( ct, 10, ' ' )
        else:
            zct = ct
        for i in range( 10 ):
            digit = zct[i:i+1]
            if digit == ' ':
                led_ctime.append( self.led_digits_blank )  
            elif i in [0,1,2,3,6,7]:
                led_ctime.append( self.led_digits_one[ int(digit) ] )  
            else:
                led_ctime.append( self.led_digits_two[ int(digit) ] )  

        return led_ctime

    def update_gui( self ):
        #print "Updating GUI"
        expand_me = []
        new_data = {}
        for id in self.state_summary:
            name, ctime = id.split( '%' )
            if ctime not in new_data:
                new_data[ ctime ] = {}
            state = self.state_summary[ id ][ 'state' ]
            message = self.state_summary[ id ][ 'latest_message' ]
            tsub = self.state_summary[ id ][ 'submitted_time' ]
            tstt = self.state_summary[ id ][ 'started_time' ]
            meant = self.state_summary[ id ][ 'mean total elapsed time' ]
            tetc = self.state_summary[ id ][ 'Tetc' ]
            priority = self.state_summary[ id ][ 'latest_message_priority' ]
            message = markup( get_col_priority( priority ), message )
            state = markup( get_col(state), state )
            new_data[ ctime ][ name ] = [ state, message, tsub, tstt, meant, tetc ]

        # print existing tree:
        #print
        #iter = self.ttreestore.get_iter_first()
        #while iter:
        #    row = []
        #    for col in range( self.ttreestore.get_n_columns() ):
        #        row.append( self.ttreestore.get_value( iter, col ))
        #    print "==================", row
        #    iterch = self.ttreestore.iter_children( iter )
        #    while iterch:
        #        ch_row = []
        #        for col in range( self.ttreestore.get_n_columns() ):
        #            ch_row.append( self.ttreestore.get_value( iterch, col ))
        #        print "  ===========", ch_row
        #        iterch = self.ttreestore.iter_next( iterch )
        #    iter = self.ttreestore.iter_next( iter )
        #print

        tree_data = {}

        # The treestore.remove() method removes the row pointed to by
        # iter from the treestore. After being removed, iter is set to
        # the next valid row at that level, or invalidated if it
        # previously pointed to the last one. Returns : None in PyGTK
        # 2.0. Returns True in PyGTK 2.2 and above if iter is still
        # valid.

        iter = self.ttreestore.get_iter_first()
        while iter:
            # get parent ctime 
            row = []
            for col in range( self.ttreestore.get_n_columns() ):
                row.append( self.ttreestore.get_value( iter, col) )
            [ ctime, state, message, tsub, tstt, meant, tetc ] = row
            # note state etc. is empty string for parent row
            tree_data[ ctime ] = {}

            if ctime not in new_data:
                # parent ctime not in new data; remove it
                #print "REMOVING", ctime
                res = self.ttreestore.remove( iter )
                if not self.ttreestore.iter_is_valid( iter ):
                    iter = None
            else:
                # parent ctime IS in new data; check children
                iterch = self.ttreestore.iter_children( iter )
                while iterch:
                    ch_row = []
                    for col in range( self.ttreestore.get_n_columns() ):
                        ch_row.append( self.ttreestore.get_value( iterch, col) )
                    [ name, state, message, tsub, tstt, meant, tetc ] = ch_row
                    tree_data[ ctime ][name] = [ state, message, tsub, tstt, meant, tetc ]

                    if name not in new_data[ ctime ]:
                        #print "  removing", name, "from", ctime
                        res = self.ttreestore.remove( iterch )
                        if not self.ttreestore.iter_is_valid( iterch ):
                            iterch = None

                    elif tree_data[ctime][name] != new_data[ ctime ][name]:
                        #print "   changing", name, "at", ctime
                        self.ttreestore.append( iter, [ name ] + new_data[ctime][name] )
                        res = self.ttreestore.remove( iterch )
                        if not self.ttreestore.iter_is_valid( iterch ):
                            iterch = None

                        st = re.sub('<[^>]+>', '', state ) # remove tags
                        if st == 'submitted' or st == 'running' or st == 'failed' or st == 'held':
                            if iter not in expand_me:
                                expand_me.append( iter )
                    else:
                        # row unchanged
                        iterch = self.ttreestore.iter_next( iterch )
                        st = re.sub('<[^>]+>', '', state ) # remove tags
                        if st == 'submitted' or st == 'running' or st == 'failed' or st == 'held':
                            if iter not in expand_me:
                                expand_me.append( iter )

                # then increment parent ctime
                iter = self.ttreestore.iter_next( iter )

        for ctime in new_data:
            if ctime not in tree_data:
                # add new ctime tree
                #print "ADDING", ctime
                piter = self.ttreestore.append(None, [ctime, None, None, None, None, None, None ])
                for name in new_data[ ctime ]:
                    #print "  adding", name, "to", ctime
                    self.ttreestore.append( piter, [ name ] + new_data[ctime][name] )
                    state = new_data[ ctime ][ name ][0]
                    st = re.sub('<[^>]+>', '', state ) # remove tags
                    if st == 'submitted' or st == 'running' or st == 'failed' or st == 'held':
                        if iter not in expand_me:
                            expand_me.append( piter )
                continue

            # this ctime tree is already in model
            p_iter = self.search_level( self.ttreestore, 
                    self.ttreestore.get_iter_first(),
                    self.match_func, (0, ctime ))

            for name in new_data[ ctime ]:
                # look for a matching row in the model
                ch_iter = self.search_treemodel( self.ttreestore, 
                        self.ttreestore.iter_children( p_iter ),
                        self.match_func, (0, name ))
                if not ch_iter:
                    #print "  adding", name, "to", ctime
                    self.ttreestore.append( p_iter, [ name ] + new_data[ctime][name] )
                state = new_data[ ctime ][ name ][0]
                # expand whether new or old data
                st = re.sub('<[^>]+>', '', state ) # remove tags
                if st == 'submitted' or st == 'running' or st == 'failed' or st == 'held':
                    if iter not in expand_me:
                        expand_me.append( p_iter )

        if self.autoexpand:
            for iter in expand_me:
                self.ttreeview.expand_row(self.ttreestore.get_path(iter),False)

        # LED VIEW
        self.led_liststore.clear()

        tasks = {}
        for id in self.state_summary:
            name, ctime = id.split( '%' )
            if ctime not in tasks:
                tasks[ ctime ] = [ name ]
            else:
                tasks[ ctime ].append( name )
 
        # flat (a liststore would do)
        ctimes = tasks.keys()
        ctimes.sort()

        for ctime in ctimes:
            tasks_at_ctime = tasks[ ctime ]
            state_list = [ ]

            for name in self.task_list:
                if name in tasks_at_ctime:
                    state = self.state_summary[ name + '%' + ctime ][ 'state' ] 
                    if state == 'waiting':
                        state_list.append( self.waiting_led )
                    elif state == 'submitted':
                        state_list.append( self.submitted_led )
                    elif state == 'running':
                        state_list.append( self.running_led )
                    elif state == 'succeeded':
                        state_list.append( self.succeeded_led )
                    elif state == 'failed':
                        state_list.append( self.failed_led )
                    elif state == 'held':
                        state_list.append( self.stopped_led )
                    elif state == 'runahead':
                        state_list.append( self.runahead_led )
                else:
                    state_list.append( self.empty_led )

            self.led_liststore.append( self.digitize( ctime ) + state_list )

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
                gobject.idle_add( self.update_gui )
            # TO DO: only update globals if they change, as for tasks
            gobject.idle_add( self.update_globals )
            time.sleep(1)
        else:
            pass
            ####print "Disconnecting task state info thread"
