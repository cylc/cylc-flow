#!/usr/bin/env python

# example basictreeview.py
try:
    import subprocess
    # see documentation in bin/cylc
    use_subprocess = True
except:
    use_subprocess = False
 
import pango
from stateview import updater
from combo_logviewer import combo_logviewer
from cylc_logviewer import cylc_logviewer
from warning_dialog import warning_dialog
import Pyro.errors
import gobject
import pygtk
####pygtk.require('2.0')
import gtk
import time, os, re, sys
from CylcOptionParsers import NoPromptOptionParser_u
import cylc_pyro_client
from cycle_time import _rt_to_dt, is_valid

class color_rotator:
    def __init__( self ):
        self.colors = [ '#ed9638', '#dbd40a', '#a7c339', '#6ab7b4' ]
        self.current_color = 0
 
    def get_color( self ):
        index = self.current_color
        if index == len( self.colors ) - 1:
            index = 0
        else:
            index += 1

        self.current_color = index
        return self.colors[ index ]

class monitor:
    # visibility determined by state matching active toggle buttons
    def visible_cb(self, model, iter, col ):
        # set visible if model value NOT in filter_states
        # TO DO: WHY IS STATE SOMETIMES NONE?
        state = model.get_value(iter, col) 
        #print '-->', model.get_value( iter, 0 ), model.get_value( iter, 1 ), state, model.get_value( iter, 3 )
        if state:
            p = re.compile( r'<.*?>')
            state = re.sub( r'<.*?>', '', state )

        return state not in self.filter_states

    def check_filter_buttons(self, tb):
        del self.filter_states[:]
        for b in self.filter_buttonbox.get_children():
            if not b.get_active():
                self.filter_states.append(b.get_label())

        self.modelfilter.refilter()
        return

    # close the window and quit
    def delete_event(self, widget, event, data=None):
        self.lvp.quit()
        self.t.quit = True

        for q in self.quitters:
            #print "calling quit on ", q
            q.quit()

        #print "BYE from main thread"
        return False

    def pause_suite( self, bt ):
        god = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port ).get_proxy( 'remote' )
        god.hold( self.owner )

    def resume_suite( self, bt ):
        god = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port ).get_proxy( 'remote' )
        god.resume( self.owner )

    def stop_suite( self, bt ):
        god = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port ).get_proxy( 'remote' )
        god.shutdown( self.owner )

    def restart_suite( self, bt ):
        if use_subprocess:
            command = [ 'cylc restart ' + self.suite ]
            #command = [ 'cylc restart', self.suite ]
            try:
                print command
                res = subprocess.Popen( command, shell=True )
                #res = subprocess.Popen( command )
            except OSError, e:
                # THIS DOES NOT CATCH BACKGROUND EXECUTION FAILURE
                # because subprocess.call( 'foo &' ) returns immediately
                # and the failure occurs in the detached sub-shell.
                print "FAILED", e
                success = False
        else:
            command = 'cylc restart ' + self.suite + ' > /dev/null 2>&1 &'
            os.system( command )
            success = True

    def stop_suite_now( self, bt ):
        god = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port ).get_proxy( 'remote' )
        god.shutdown_now( self.owner )

    def unlock_suite( self, bt ):
        god = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port ).get_proxy( 'remote' )
        god.unlock( self.owner )

    def lock_suite( self, bt ):
        god = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port ).get_proxy( 'remote' )
        god.lock( self.owner )

    def about( self, bt ):
        about = gtk.AboutDialog()
        if gtk.gtk_version[0] ==2:
            if gtk.gtk_version[1] >= 12:
                # set_program_name() was added in PyGTK 2.12
                about.set_program_name( "cylc" )
        cylc_version = 'THIS IS NOT A VERSIONED RELEASE'
        about.set_version( cylc_version )
        about.set_copyright( "(c) Hilary Oliver, NIWA" )
        about.set_comments( 
"""
Cylc View is a real time suite monitor and controller for Cylc.
""" )
        about.set_website( "http://www.niwa.co.nz" )
        about.set_logo( gtk.gdk.pixbuf_new_from_file( self.imagedir + "/dew.jpg" ))
        about.run()
        about.destroy()

    def click_exit( self, foo ):
        self.lvp.quit()
        self.t.quit = True
        for q in self.quitters:
            #print "calling quit on ", q
            q.quit()

        #print "BYE from main thread"
        self.window.destroy()
        return False

    def expand_all( self, widget, view ):
        view.expand_all()
 
    def collapse_all( self, widget, view ):
        view.collapse_all()

    def no_task_headings( self, w ):
        #self.led_headings = ['Cycle Time' ] + ['-'] * len( self.task_list )
        self.led_headings = ['Cycle Time' ] + [''] * len( self.task_list )
        self.reset_led_headings()

    def short_task_headings( self, w ):
        self.led_headings = ['Cycle Time' ] + self.task_list_shortnames
        self.reset_led_headings()

    def full_task_headings( self, w ):
        self.led_headings = ['Cycle Time' ] + self.task_list
        self.reset_led_headings()

    def reset_led_headings( self ):
        tvcs = self.led_treeview.get_columns()
        for n in range( 1,1+len( self.task_list) ):
            heading = self.led_headings[n]
            # underscores treated as underlines markup?
            #heading = re.sub( '_', ' ', heading )
            tvcs[n].set_title( heading )

    def create_led_panel( self ):
        types = tuple( [gtk.gdk.Pixbuf]* (10 + len( self.task_list)))
        liststore = gtk.ListStore( *types )
        treeview = gtk.TreeView( liststore )
        treeview.get_selection().set_mode( gtk.SELECTION_NONE )

        # set background color of the entire treeview
        treeview.modify_base( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#000' ) ) 

        tvc = gtk.TreeViewColumn( 'Cycle Time' )
        for i in range(10):
            cr = gtk.CellRendererPixbuf()
            cr.set_property( 'cell-background', 'black' )
            tvc.pack_start( cr, False )
            tvc.set_attributes( cr, pixbuf=i )
        treeview.append_column( tvc )

        # hardwired 10px lamp image width!
        lamp_width = 10

        for n in range( 10, 10+len( self.task_list )):
            cr = gtk.CellRendererPixbuf()
            cr.set_property( 'cell_background', 'black' )
            cr.set_property( 'xalign', 0 )
            tvc = gtk.TreeViewColumn( "-"  )
            tvc.set_min_width( lamp_width )  # WIDTH OF LED PIXBUFS
            tvc.pack_end( cr, True )
            tvc.set_attributes( cr, pixbuf=n )
            treeview.append_column( tvc )

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )

        self.led_treeview = treeview
        sw.add( treeview )

        return sw
    
    def create_tree_panel( self ):
        self.ttreestore = gtk.TreeStore(str, str, str )
        tms = gtk.TreeModelSort( self.ttreestore )
        tms.set_sort_column_id(0, gtk.SORT_ASCENDING)
        treeview = gtk.TreeView()
        treeview.set_model(tms)
        ts = treeview.get_selection()
        ts.set_mode( gtk.SELECTION_SINGLE )

        treeview.connect( 'button_press_event', self.on_treeview_button_pressed, False )

        headings = ['task', 'state', 'latest message' ]
        for n in range(len(headings)):
            cr = gtk.CellRendererText()
            tvc = gtk.TreeViewColumn( headings[n], cr, markup=n )
            #tvc = gtk.TreeViewColumn( headings[n], cr, text=n )
            treeview.append_column(tvc)
            tvc.set_sort_column_id(n)
 
        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )
        sw.add( treeview )

        hbox = gtk.HBox()
        eb = gtk.EventBox()
        eb.add( gtk.Label( "sort on headings") )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#ed9638' ) ) 
        hbox.pack_start( eb, True )

        eb = gtk.EventBox()
        eb.add( gtk.Label( "left click: Info" ) )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#dbd40a' ) ) 
        hbox.pack_start( eb, True )

        eb = gtk.EventBox()
        eb.add( gtk.Label( "right click: Control" ) )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#a7c339' ) ) 
        hbox.pack_start( eb, True )

        bbox = gtk.HButtonBox()
        expand_button = gtk.Button( "Expand" )
        expand_button.connect( 'clicked', self.expand_all, treeview )
    
        collapse_button = gtk.Button( "Collapse" )
        collapse_button.connect( 'clicked', self.collapse_all, treeview )

        bbox.add( expand_button )
        bbox.add( collapse_button )
        bbox.set_layout( gtk.BUTTONBOX_END )

        vbox = gtk.VBox()
        vbox.pack_start( hbox, False )
        vbox.pack_start( sw, True )
        vbox.pack_start( bbox, False )

        return vbox

    def get_selected_task_from_tree( self, selection, treemodel ):
        if len( selection ) == 1:
            # top level, just ctime
            return False

        c_iter = treemodel.get_iter( selection )
        name = treemodel.get_value( c_iter, 0 )
 
        iter = treemodel.iter_parent( c_iter )
        ctime = treemodel.get_value( iter, 0 )
        task_id = name + '%' + ctime

        self.show_log( task_id )
        return False


    def show_log( self, task_id ):

        [ glbl, states ] = self.get_pyro( 'state_summary').get_state_summary()

        view = True
        reasons = []

        logfiles = states[ task_id ][ 'logfiles' ]

        if len(logfiles) == 0:
            view = False
            reasons.append( task_id + ' has no associated log files' )

        if states[ task_id ][ 'state' ] == 'waiting':
            view = False
            reasons.append( task_id + ' has not started' )

        if not view:
            warning_dialog( '\n'.join( reasons ) ).warn()
            self.popup_requisites( None, task_id )
        else:
            self.popup_logview( task_id, logfiles )

        return False

    def get_selected_task_from_list( self, selection, treemodel ):
        print selection

        iter = treemodel.get_iter( selection )
        ctime = treemodel.get_value( iter, 0 )
        name = treemodel.get_value( iter, 1 )
        task_id = name + '%' + ctime

        self.show_log( task_id )

        return False

    def on_treeview_button_pressed( self, treeview, event, flat=True ):
        # the following sets selection to the position at which the
        # right click was done (otherwise selection lags behind the
        # right click):
        x = int( event.x )
        y = int( event.y )
        time = event.time
        pth = treeview.get_path_at_pos(x,y)

        if pth is None:
            return False

        treeview.grab_focus()
        path, col, cellx, celly = pth
        treeview.set_cursor( path, col, 0 )

        selection = treeview.get_selection()
        treemodel, iter = selection.get_selected()
        if flat:
            # flat list view
            ctime = treemodel.get_value( iter, 0 )
            name = treemodel.get_value( iter, 1 )
        else:
            # expanding tree view
            name = treemodel.get_value( iter, 0 )
            iter2 = treemodel.iter_parent( iter )
            try:
                ctime = treemodel.get_value( iter2, 0 )
            except TypeError:
                # must have clicked on the top level ctime 
                return

        task_id = name + '%' + ctime

        if event.button != 3:
            self.show_log( task_id )
            return False

        menu = gtk.Menu()

        menu_root = gtk.MenuItem( task_id )
        menu_root.set_submenu( menu )

        reset_ready_item = gtk.MenuItem( 'Reset to ready (trigger immediately)' )
        menu.append( reset_ready_item )
        reset_ready_item.connect( 'activate', self.reset_task_to_ready, task_id )

        reset_waiting_item = gtk.MenuItem( 'Reset to waiting (prerequisites unsatisfied)' )
        menu.append( reset_waiting_item )
        reset_waiting_item.connect( 'activate', self.reset_task_to_waiting, task_id )

        reset_finished_item = gtk.MenuItem( 'Reset to finished (outputs completed)' )
        menu.append( reset_finished_item )
        reset_finished_item.connect( 'activate', self.reset_task_to_finished, task_id )

        kill_item = gtk.MenuItem( 'Remove (after spawning)' )
        menu.append( kill_item )
        kill_item.connect( 'activate', self.kill_task, task_id )

        kill_nospawn_item = gtk.MenuItem( 'Remove (without spawning)' )
        menu.append( kill_nospawn_item )
        kill_nospawn_item.connect( 'activate', self.kill_task_nospawn, task_id )

        purge_item = gtk.MenuItem( 'Purge (remove dependency tree)' )
        menu.append( purge_item )
        purge_item.connect( 'activate', self.popup_purge, task_id )

        menu.show_all()
        menu.popup( None, None, None, event.button, event.time )

        # TO DO: POPUP MENU MUST BE DESTROY()ED AFTER EVERY USE AS
        # POPPING DOWN DOES NOT DO THIS (=> MEMORY LEAK?)

        return True


    def create_flatlist_panel( self ):
        self.fl_liststore = gtk.ListStore(str, str, str, str)
        self.modelfilter = self.fl_liststore.filter_new()
        self.modelfilter.set_visible_func(self.visible_cb, 2)
        tms = gtk.TreeModelSort( self.modelfilter )
        tms.set_sort_column_id(0, gtk.SORT_ASCENDING)
        treeview = gtk.TreeView()
        treeview.set_model(tms)

        ts = treeview.get_selection()
        ts.set_mode( gtk.SELECTION_SINGLE )

        treeview.connect( 'button_press_event', self.on_treeview_button_pressed )

        headings = ['cycle', 'name', 'state', 'latest message' ]
        bkgcols = ['#def', '#fff', '#fff', '#fff' ]

        # create the TreeViewColumn to display the data
        for n in range(len(headings)):
            # add columns to treeview
            cr = gtk.CellRendererText()
            cr.set_property( 'cell-background', bkgcols[ n] )
            tvc = gtk.TreeViewColumn( headings[n], cr, markup=n )
            #tvc = gtk.TreeViewColumn( headings[n], cr, text=n )
            tvc.set_sort_column_id(n)
            treeview.append_column(tvc)

        treeview.set_search_column(1)

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )
        sw.add( treeview )

        self.filter_buttonbox = gtk.HButtonBox()

        # allow filtering out of 'finished' and 'waiting'
        all_states = [ 'waiting', 'submitted', 'running', 'finished', 'failed' ]
        # initially filter out 'finished' and 'waiting' tasks
        self.filter_states = [ 'waiting', 'finished' ]

        for st in all_states:
            b = gtk.ToggleButton( st )
            self.filter_buttonbox.pack_start(b)
            if st in self.filter_states:
                b.set_active(False)
            else:
                b.set_active(True)
            b.connect('toggled', self.check_filter_buttons)

        self.filter_buttonbox.set_layout( gtk.BUTTONBOX_END )

        hbox = gtk.HBox()
        eb = gtk.EventBox()
        eb.add( gtk.Label( "sort on headings") )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#dbd40a' ) ) 
        hbox.pack_start( eb, True )

        eb = gtk.EventBox()
        eb.add( gtk.Label( "left click: Info" ) )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#a7c339' ) ) 
        hbox.pack_start( eb, True )

        eb = gtk.EventBox()
        eb.add( gtk.Label( "right click: Control" ) )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#ed9638' ) ) 
        hbox.pack_start( eb, True )

        vbox = gtk.VBox()
        vbox.pack_start( hbox, False )
        vbox.pack_start( sw, True )
        vbox.pack_start( self.filter_buttonbox, False )

        return vbox

    def update_tb( self, tb, line, tags = None ):
        if tags:
            tb.insert_with_tags( tb.get_end_iter(), line, *tags )
        else:
            tb.insert( tb.get_end_iter(), line )

    def popup_requisites( self, w, task_id ):
        window = gtk.Window()
        #window.set_border_width( 10 )
        window.set_title( task_id + ": Prerequisites and Outputs" )
        #window.modify_bg( gtk.STATE_NORMAL, 
        #       gtk.gdk.color_parse( self.log_colors.get_color()))
        window.set_size_request(400, 300)

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )

        vbox = gtk.VBox()
        quit_button = gtk.Button( "Close" )
        quit_button.connect("clicked", lambda x: window.destroy() )
        vbox.pack_start( sw )
        vbox.pack_start( quit_button, False )

        textview = gtk.TextView()
        textview.set_border_width(5)
        textview.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( "#fff" ))
        textview.set_editable( False )
        sw.add( textview )
        window.add( vbox )
        tb = textview.get_buffer()

        blue = tb.create_tag( None, foreground = "blue" )
        red = tb.create_tag( None, foreground = "red" )
        bold = tb.create_tag( None, weight = pango.WEIGHT_BOLD )
 
        result = self.get_pyro( 'remote' ).get_task_requisites( [ task_id ] )

        if task_id not in result:
            warning_dialog( 
                    "Task proxy " + task_id + " not found in " + self.suite + \
                 ".\nTasks are removed once they are no longer needed.").warn()
            return
        
        #self.update_tb( tb, 'Task ' + task_id + ' in ' +  self.suite + '\n\n', [bold])
        self.update_tb( tb, 'TASK ', [bold] )
        self.update_tb( tb, task_id, [bold, blue])
        self.update_tb( tb, ' in SUITE ', [bold] )
        self.update_tb( tb, self.suite + '\n\n', [bold, blue])

        [ pre, out, extra_info ] = result[ task_id ]

        self.update_tb( tb, 'Prerequisites', [bold])
        #self.update_tb( tb, ' blue => satisfied,', [blue] )
        self.update_tb( tb, ' (' )
        self.update_tb( tb, 'red', [red] )
        self.update_tb( tb, '=> NOT satisfied)\n') 

        if len( pre ) == 0:
            self.update_tb( tb, ' - (None)\n' )
        for item in pre:
            [ msg, state ] = item
            if state:
                tags = None
            else:
                tags = [red]
            self.update_tb( tb, ' - ' + msg + '\n', tags )

        self.update_tb( tb, '\nOutputs', [bold] )
        self.update_tb( tb, ' (' )
        self.update_tb( tb, 'red', [red] )
        self.update_tb( tb, '=> NOT completed)\n') 


        if len( out ) == 0:
            self.update_tb( tb, ' - (None)\n')
        for item in out:
            [ msg, state ] = item
            if state:
                tags = []
            else:
                tags = [red]
            self.update_tb( tb, ' - ' + msg + '\n', tags )

        if len( extra_info.keys() ) > 0:
            self.update_tb( tb, '\nOther\n', [bold] )
            for item in extra_info:
                self.update_tb( tb, ' - ' + item + ': ' + str( extra_info[ item ] ) + '\n' )

        #window.connect("delete_event", lv.quit_w_e)
        window.show_all()

    def on_popup_quit( self, b, lv, w ):
        lv.quit()
        self.quitters.remove( lv )
        w.destroy()

    def reset_task_to_ready( self, b, task_id ):
        msg = "reset " + task_id + " to ready\n(i.e. trigger immediately)?"
        prompt = gtk.MessageDialog( None, gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_OK_CANCEL, msg )
        response = prompt.run()
        prompt.destroy()
        if response != gtk.RESPONSE_OK:
            return
        proxy = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port).get_proxy( 'remote' )
        actioned, explanation = proxy.reset_to_ready( task_id, self.owner )

    def reset_task_to_waiting( self, b, task_id ):
        msg = "reset " + task_id + " to waiting\n(i.e. prerequisites not satisfied)?"
        prompt = gtk.MessageDialog( None, gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_OK_CANCEL, msg )
        response = prompt.run()
        prompt.destroy()
        if response != gtk.RESPONSE_OK:
            return
        proxy = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port).get_proxy( 'remote' )
        actioned, explanation = proxy.reset_to_waiting( task_id, self.owner )

    def reset_task_to_finished( self, b, task_id ):
        msg = "reset " + task_id + " to finished\n (i.e. outputs completed)?"
        prompt = gtk.MessageDialog( None, gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_OK_CANCEL, msg )
        response = prompt.run()
        prompt.destroy()
        if response != gtk.RESPONSE_OK:
            return
        proxy = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port).get_proxy( 'remote' )
        actioned, explanation = proxy.reset_to_finished( task_id, self.owner )

    def kill_task( self, b, task_id ):
        msg = "remove " + task_id + " (after spawning)?"
        prompt = gtk.MessageDialog( None, gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_OK_CANCEL, msg )
        response = prompt.run()
        prompt.destroy()
        if response != gtk.RESPONSE_OK:
            return
        proxy = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port).get_proxy( 'remote' )
        actioned, explanation = proxy.spawn_and_die( task_id, self.owner )
 
    def kill_task_nospawn( self, b, task_id ):
        msg = "remove " + task_id + " (without spawning)?"
        prompt = gtk.MessageDialog( None, gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_OK_CANCEL, msg )
        response = prompt.run()
        prompt.destroy()
        if response != gtk.RESPONSE_OK:
            return
        proxy = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port).get_proxy( 'remote' )
        actioned, explanation = proxy.die( task_id, self.owner )

    def purge_cycle_from_entry_text( self, e, w, task_id ):
        stop = e.get_text()
        w.destroy()
        msg = "purge " + task_id + " through " + stop + " (inclusive)?"
        prompt = gtk.MessageDialog( None, gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_OK_CANCEL, msg )
        response = prompt.run()
        prompt.destroy()
        if response != gtk.RESPONSE_OK:
            return
        proxy = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port ).get_proxy( 'remote' )
        actioned, explanation = proxy.purge( task_id, stop, self.owner )

    def popup_purge( self, b, task_id ):
        window = gtk.Window()
        window.modify_bg( gtk.STATE_NORMAL, 
                gtk.gdk.color_parse( self.log_colors.get_color()))
        window.set_border_width(5)
        window.set_title( "Purge " + task_id )
        #window.set_size_request(800, 300)

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )

        box = gtk.VBox()
        label = gtk.Label( 'cycle at which to stop the purge (inclusive)' )
        box.pack_start( label, True )

        entry = gtk.Entry()
        entry.set_max_length(10)
        entry.connect( "activate", self.purge_cycle_from_entry_text, window, task_id )

        box.pack_start (entry, True)

        window.add( box )
        window.show_all()

    def insert_task_popup( self, b ):
        window = gtk.Window()
        window.modify_bg( gtk.STATE_NORMAL, 
                gtk.gdk.color_parse( self.log_colors.get_color()))
        window.set_border_width(5)
        window.set_title( "Insert a task or task group" )
        #window.set_size_request(800, 300)

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )

        vbox = gtk.VBox()

        hbox = gtk.HBox()
        label = gtk.Label( 'task name' )
        hbox.pack_start( label, True )
        entry_name = gtk.Entry()
        hbox.pack_start (entry_name, True)
        vbox.pack_start(hbox)

        hbox = gtk.HBox()
        label = gtk.Label( 'cycle time' )
        hbox.pack_start( label, True )
        entry_ctime = gtk.Entry()
        entry_ctime.set_max_length(10)
        hbox.pack_start (entry_ctime, True)
        vbox.pack_start(hbox)

        insert_button = gtk.Button( "Do it" )
        insert_button.connect("clicked", self.insert_task, window, entry_name, entry_ctime )
        vbox.pack_start(insert_button)
 
        window.add( vbox )
        window.show_all()

    def insert_task( self, w, window, entry_name, entry_ctime ):
        name = entry_name.get_text()
        ctime = entry_ctime.get_text()
        task_id = name + '%' + ctime
        window.destroy()
        msg = "insert " + task_id + "?"
        prompt = gtk.MessageDialog( None, gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_OK_CANCEL, msg )
        response = prompt.run()
        prompt.destroy()
        if response != gtk.RESPONSE_OK:
            return
        proxy = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port ).get_proxy( 'remote' )
        actioned, explanation = proxy.insert( task_id, self.owner )
 
    def popup_logview( self, task_id, logfiles ):
        window = gtk.Window()
        window.modify_bg( gtk.STATE_NORMAL, 
                gtk.gdk.color_parse( self.log_colors.get_color()))
        window.set_border_width(5)
        window.set_title( task_id + ": Task Information Viewer" )
        window.set_size_request(800, 300)

        lv = combo_logviewer( task_id, logfiles )
        #print "ADDING to quitters: ", lv
        self.quitters.append( lv )

        window.add( lv.get_widget() )

        state_button = gtk.Button( "Interrogate" )
        state_button.connect("clicked", self.popup_requisites, task_id )
 
        quit_button = gtk.Button( "Close" )
        quit_button.connect("clicked", self.on_popup_quit, lv, window )
        
        lv.hbox.pack_start( quit_button )
        lv.hbox.pack_start( state_button )

        window.connect("delete_event", lv.quit_w_e)
        window.show_all()


    def create_menu( self ):
        file_menu = gtk.Menu()

        file_menu_root = gtk.MenuItem( 'File' )
        file_menu_root.set_submenu( file_menu )

        exit_item = gtk.MenuItem( 'Exit' )
        exit_item.connect( 'activate', self.click_exit )
        file_menu.append( exit_item )

        view_menu = gtk.Menu()
        view_menu_root = gtk.MenuItem( 'View' )
        view_menu_root.set_submenu( view_menu )

        heading_none_item = gtk.MenuItem( 'No Task Names' )
        view_menu.append( heading_none_item )
        heading_none_item.connect( 'activate', self.no_task_headings )

        heading_short_item = gtk.MenuItem( 'Short Task Names' )
        view_menu.append( heading_short_item )
        heading_short_item.connect( 'activate', self.short_task_headings )

        heading_full_item = gtk.MenuItem( 'Full Task Names' )
        view_menu.append( heading_full_item )
        heading_full_item.connect( 'activate', self.full_task_headings )

        lock_menu = gtk.Menu()
        lock_menu_root = gtk.MenuItem( 'Locking' )
        lock_menu_root.set_submenu( lock_menu )

        lock_item = gtk.MenuItem( 'Lock Suite' )
        lock_menu.append( lock_item )
        lock_item.connect( 'activate', self.lock_suite )

        unlock_item = gtk.MenuItem( 'Unlock Suite' )
        lock_menu.append( unlock_item )
        unlock_item.connect( 'activate', self.unlock_suite )

        suite_menu = gtk.Menu()
        suite_menu_root = gtk.MenuItem( 'Suite' )
        suite_menu_root.set_submenu( suite_menu )

        pause_item = gtk.MenuItem( 'Pause' )
        suite_menu.append( pause_item )
        pause_item.connect( 'activate', self.pause_suite )

        resume_item = gtk.MenuItem( 'Resume' )
        suite_menu.append( resume_item )
        resume_item.connect( 'activate', self.resume_suite )

        stop_item = gtk.MenuItem( 'Stop' )
        suite_menu.append( stop_item )
        stop_item.connect( 'activate', self.stop_suite )

        stop_now_item = gtk.MenuItem( 'Stop NOW' )
        suite_menu.append( stop_now_item )
        stop_now_item.connect( 'activate', self.stop_suite_now )

        #restart_item = gtk.MenuItem( 'Restart' )
        #suite_menu.append( restart_item )
        #restart_item.connect( 'activate', self.restart_suite )

        insert_item = gtk.MenuItem( 'Insert' )
        suite_menu.append( insert_item )
        insert_item.connect( 'activate', self.insert_task_popup )

        help_menu = gtk.Menu()
        help_menu_root = gtk.MenuItem( 'Help' )
        help_menu_root.set_submenu( help_menu )
        about_item = gtk.MenuItem( 'About' )
        help_menu.append( about_item )
        about_item.connect( 'activate', self.about )
      
        self.menu_bar = gtk.MenuBar()
        self.menu_bar.append( file_menu_root )
        self.menu_bar.append( view_menu_root )
        self.menu_bar.append( suite_menu_root )
        self.menu_bar.append( lock_menu_root )
        self.menu_bar.append( help_menu_root )

    def create_info_bar( self ):
        self.label_status = gtk.Label( "status..." )
        self.label_mode = gtk.Label( "mode..." )
        self.label_time = gtk.Label( "time..." )
        self.label_suitename = gtk.Label( self.suite )

        hbox = gtk.HBox()

        eb = gtk.EventBox()
        eb.add( self.label_suitename )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#ed9638' ) )
        hbox.pack_start( eb, True )

        eb = gtk.EventBox()
        eb.add( self.label_mode )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#dbd40a' ) )
        hbox.pack_start( eb, True )

        eb = gtk.EventBox()
        eb.add( self.label_status )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#a7c339' ) )
        hbox.pack_start( eb, True )

        eb = gtk.EventBox()
        eb.add( self.label_time )
        #eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#6ab7b4' ) ) 
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#fa87a4' ) ) 
        hbox.pack_start( eb, True )

        return hbox

    def translate_task_names( self, shortnames ):
        temp = {}
        for t in range( len( self.task_list )):
            temp[ self.task_list[ t ] ] = shortnames[ t ]

        self.task_list.sort()
        self.task_list_shortnames = []
        for task in self.task_list:
            self.task_list_shortnames.append( temp[ task ] )
 
    def check_connection( self ):
        # called on a timeout in the gtk main loop, tell the log viewer
        # to reload if the connection has been lost and re-established,
        # which probably means the cylc suite was shutdown and
        # restarted.
        try:
            cylc_pyro_client.ping( self.host, self.port )
        except Pyro.errors.ProtocolError:
            print "NO CONNECTION"
            self.connection_lost = True
        else:
            print "CONNECTED"
            if self.connection_lost:
                #print "------>INITIAL RECON"
                self.connection_lost = False
                self.lvp.clear_and_reconnect()
        # always return True so that we keep getting called
        return True

    def get_pyro( self, object ):
        return cylc_pyro_client.client( self.suite, self.owner, self.host, self.port ).get_proxy( object)
 
    #def block_till_connected( self ):
    #    # NO LONGER NEEDED (non-task-list-preload startup has been disabled)
    #    warned = False
    #    while True:
    #        try:
    #            self.get_pyro( 'minimal' )
    #        except:
    #            if not warned:
    #                print "waiting for suite " + self.suite + ".",
    #                warned = True
    #            else:
    #                print '.',
    #                sys.stdout.flush()
    #        else:
    #            print '.'
    #            sys.stdout.flush()
    #            time.sleep(1) # wait for suite to start
    #            break
    #        time.sleep(1)

    def load_task_list( self ):
        #self.block_till_connected()
        ss = self.get_pyro( 'state_summary' )
        self.logdir = ss.get_config( 'logging_dir' ) 
        self.task_list = ss.get_config( 'task_list' )
        self.shortnames = ss.get_config( 'task_list_shortnames' )

    def __init__(self, suite, owner, host, port, imagedir ):
        self.suite = suite
        self.host = host
        self.port = port
        self.owner = owner
        self.imagedir = imagedir
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        #self.window.set_border_width( 5 )
        self.window.set_title("cylc view <" + self.suite + ">" )
        self.window.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( "#ddd" ))
        self.window.set_size_request(600, 500)
        self.window.connect("delete_event", self.delete_event)

        self.log_colors = color_rotator()

        # Get list of tasks in the suite
        self.load_task_list()

        self.translate_task_names( self.shortnames )

        notebook = gtk.Notebook()
        notebook.set_tab_pos(gtk.POS_TOP)
        notebook.append_page( self.create_flatlist_panel(), gtk.Label("Filtered List View") )
        notebook.append_page( self.create_tree_panel(), gtk.Label("Expanding Tree View") )

        main_panes = gtk.VPaned()
        main_panes.set_position(200)
        main_panes.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#d91212' ))
        main_panes.add1( self.create_led_panel())
        main_panes.add2( notebook )

        self.lvp = cylc_logviewer( 'log', self.logdir, self.task_list )
        notebook.append_page( self.lvp.get_widget(), gtk.Label("Cylc Log Viewer"))

        self.create_menu()

        self.led_headings = None 
        self.short_task_headings( None )

        bigbox = gtk.VBox()
        bigbox.pack_start( self.menu_bar, False )
        bigbox.pack_start( self.create_info_bar(), False )
        bigbox.pack_start( main_panes, True )
        self.window.add( bigbox )

        self.window.show_all()

        self.quitters = []

        self.connection_lost = False
        #gobject.timeout_add( 1000, self.check_connection )

        self.t = updater( self.suite, self.owner, self.host, self.port, self.imagedir, 
                self.led_treeview.get_model(),
                self.fl_liststore, self.ttreestore, self.task_list,
                self.label_mode, self.label_status, self.label_time )

        #print "Starting task state info thread"
        self.t.start()

class standalone_monitor( monitor ):
    def __init__(self, suite, owner, host, port, imagedir ):
        gobject.threads_init()
        monitor.__init__(self, suite, owner, host, port, imagedir )
 
    def delete_event(self, widget, event, data=None):
        monitor.delete_event( self, widget, event, data )
        gtk.main_quit()

    def click_exit( self, foo ):
        monitor.click_exit( self, foo )
        gtk.main_quit()

class standalone_monitor_preload( standalone_monitor ):
    def __init__(self, suite, owner, host, port, suite_dir, logging_dir, imagedir ):
        self.logdir = logging_dir
        self.suite_dir = suite_dir
        standalone_monitor.__init__(self, suite, owner, host, port, imagedir )
 
    def load_task_list( self ):
        sys.path.append( os.path.join( self.suite_dir, 'configured'))
        try:
            import task_list
        except ImportError:
            raise SystemExit( "Error: unable to load task list (suite not configured?)" )
        self.task_list = task_list.task_list
        self.shortnames = task_list.task_list_shortnames
