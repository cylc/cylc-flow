#!/usr/bin/env python

import gobject
import time
import threading
import gtk
import pygtk
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
    else:
        return '#000'

class updater(threading.Thread):

    def __init__(self, god, imagedir, led_liststore,
            fl_liststore, ttreestore, task_list,
            label_mode, label_status, label_time ):

        super(updater, self).__init__()

        self.state_summary = {}
        self.god = god

        self.fl_liststore = fl_liststore
        self.ttreestore = ttreestore
        self.led_liststore = led_liststore
        self.task_list = task_list
        self.label_mode = label_mode
        self.label_status = label_status
        self.label_time = label_time

        self.quit = False

        self.waiting_led = gtk.gdk.pixbuf_new_from_file( imagedir + "/led-waiting-glow.xpm" )
        self.submitted_led = gtk.gdk.pixbuf_new_from_file( imagedir + "/led-submitted-glow.xpm" )
        self.running_led = gtk.gdk.pixbuf_new_from_file( imagedir + "/led-running-glow.xpm" )
        self.failed_led = gtk.gdk.pixbuf_new_from_file( imagedir + "/led-failed-glow.xpm" )
        self.finished_led = gtk.gdk.pixbuf_new_from_file( imagedir + "/led-finished.xpm" )

        self.empty_led = gtk.gdk.pixbuf_new_from_file( imagedir + "/led-empty.xpm" )

        self.led_digits_one = []
        self.led_digits_two = []
        for i in range(10):
            self.led_digits_one.append( gtk.gdk.pixbuf_new_from_file( imagedir + "/digits/one/digit-" + str(i) + ".xpm" ))
            self.led_digits_two.append( gtk.gdk.pixbuf_new_from_file( imagedir + "/digits/two/digit-" + str(i) + ".xpm" ))

    def connection_lost( self ):
        self.status = "CONNECTION LOST"
        self.label_status.get_parent().modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#ff0' ))
        # GTK IDLE FUNCTIONS MUST RETURN FALSE OR WILL BE CALLED 
        # MULTIPLE TIMES???????????????///
        return False

    def update(self):
        #print "Updating"
        try:
            [glbl, states] = self.god.get_state_summary()
        except Exception,x:
            self.led_liststore.clear()
            self.ttreestore.clear()
            self.fl_liststore.clear()
            gobject.idle_add( self.connection_lost )
 
            return False

        # always update global info

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
            self.mode = 'DUMMY'
        else:
            self.mode = 'REAL'

        dt = glbl[ 'last_updated' ]
        self.dt = dt.strftime( " %Y/%m/%d %H:%M:%S" ) 

        # only update states if a change occurred
        if compare_dict_of_dict( states, self.state_summary ):
            #print "STATE UNCHANGED"
            return False
        else:
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
        led_ctime = []
        for i in range( 10 ):
            digit = int( ct[i:i+1] )
            if i in [0,1,2,3,6,7]:
                led_ctime.append( self.led_digits_one[ digit ] )  
            else:
                led_ctime.append( self.led_digits_two[ digit ] )  

        return led_ctime

    def update_gui( self ):
        #print "Updating GUI"

        new_data = {}
        for id in self.state_summary:
            state = self.state_summary[ id ][ 'state' ]
            message = self.state_summary[ id ][ 'latest_message' ]
            message = markup( get_col(state), message )
            state = markup( get_col(state), state )
            new_data[id] = [ state, message ]

        list_data = {}
        iter = self.fl_liststore.get_iter_first()
        while iter:
            row = []
            for col in range( self.fl_liststore.get_n_columns() ):
                row.append( self.fl_liststore.get_value( iter, col) )

            [ctime, name, state, message] = row
            id = name + '%' + ctime 
            list_data[ id ] = [ state, message ]

            if id not in new_data:
                # id no longer in system, remove from view
                #print "REMOVING", id
                result = self.fl_liststore.remove( iter )
                if not result:
                    iter = None

            elif new_data[ id ] != list_data[ id ]:
                #print "CHANGING", id
                # id still in system but data changed, so replace it
                self.fl_liststore.append( [ ctime, name ] + new_data[ id ] )
                result = self.fl_liststore.remove( iter )
                if not result:
                    iter = None

            else:
                # id still exists and data has not changed
                #print "UNCHANGED", id
                iter = self.fl_liststore.iter_next( iter )
            
        # add any new data    
        for id in new_data:
            name, ctime = id.split( '%' )
            if id not in list_data:
                #print "ADDING", id
                self.fl_liststore.append( [ ctime, name ] + new_data[ id ] )

        # EXPANDING TREE VIEW

        new_data = {}
        for id in self.state_summary:
            name, ctime = id.split( '%' )
            if ctime not in new_data:
                new_data[ ctime ] = {}
            state = self.state_summary[ id ][ 'state' ]
            message = self.state_summary[ id ][ 'latest_message' ]
            message = markup( get_col( state ), message )
            state = markup( get_col(state), state )
            new_data[ ctime ][ name ] = [ state, message ]

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

        # NOTE: BELOW I'M ADDING SOME ITEMS TO TREE_DATA DICT
        # IMMEDIATELY BEFORE REMOVING THEM FROM THE TREE ITSELF; CHECK
        # THAT THIS HAS NO ADVERSE AFFECT LATER.

        tree_data = {}
        iter = self.ttreestore.get_iter_first()
        while iter:
            # get parent ctime 
            row = []
            for col in range( self.ttreestore.get_n_columns() ):
                row.append( self.ttreestore.get_value( iter, col) )
            [ ctime, state, message ] = row
            # state is empty string for parent row

            tree_data[ ctime ] = {}

            if ctime not in new_data:
                # parent ctime not in new data; remove it
                #print "REMOVING", ctime
                result = self.ttreestore.remove( iter )
                if not result:
                    iter = None

            else:
                # parent ctime IS in new data; check children
                iterch = self.ttreestore.iter_children( iter )
                while iterch:
                    ch_row = []
                    for col in range( self.ttreestore.get_n_columns() ):
                        ch_row.append( self.ttreestore.get_value( iterch, col) )
                    [ name, state, message ] = ch_row
                    tree_data[ ctime ][name] = [ state, message ]

                    if name not in new_data[ ctime ]:
                        #print "  removing", name, "from", ctime
                        result = self.ttreestore.remove( iterch )
                        if not result:
                            # This indicates we removed the last 
                            # child, i.e. there is no next iterch.
                            # Remove leaves iterch at the old value,
                            # which has just become invalid.
                            iterch = None
                    elif tree_data[ctime][name] != new_data[ ctime ][name]:
                        #print "   changing", name, "at", ctime
                        self.ttreestore.append( iter, [ name ] + new_data[ctime][name] )
                        result = self.ttreestore.remove( iterch )
                        if not result:
                            # see above
                            iterch = None
                    else:
                        iterch = self.ttreestore.iter_next( iterch )

                # then increment parent ctime
                iter = self.ttreestore.iter_next( iter )

        for ctime in new_data:
            if ctime not in tree_data:
                # add new ctime tree
                #print "ADDING", ctime
                piter = self.ttreestore.append(None, [ctime, None, None ])
                for name in new_data[ ctime ]:
                    #print "  adding", name, "to", ctime
                    self.ttreestore.append( piter, [ name ] + new_data[ctime][name] )
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
                    elif state == 'finished':
                        state_list.append( self.finished_led )
                    elif state == 'failed':
                        state_list.append( self.failed_led )
                else:
                    state_list.append( self.empty_led )

            self.led_liststore.append( self.digitize( ctime ) + state_list )

        return False

    def run(self):
        glbl = None
        states = {}
        while not self.quit:
            if self.update():
                gobject.idle_add( self.update_gui )
            # TO DO: only update globals if they change, as for tasks
            gobject.idle_add( self.label_mode.set_text, self.mode )
            gobject.idle_add( self.label_status.set_text, self.status )
            gobject.idle_add( self.label_time.set_text, self.dt )
            time.sleep(1)
        else:
            pass
            #print "Disconnecting task state info thread"
