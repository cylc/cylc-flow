#!/usr/bin/env python

import subprocess
import pango
from stateview import updater
from combo_logviewer import combo_logviewer
from cylc_logviewer import cylc_logviewer
from warning_dialog import warning_dialog, info_dialog
from port_scan import SuiteIdentificationError
import Pyro.errors
import gobject
import pygtk
####pygtk.require('2.0')
import gtk
import time, os, re, sys
from CylcOptionParsers import NoPromptOptionParser_u
import cylc_pyro_client
from cycle_time import _rt_to_dt, is_valid
from execute import execute
from option_group import option_group, controlled_option_group
from config import config

class color_rotator(object):
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

class monitor(object):
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
        try:
            god = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port ).get_proxy( 'remote' )
            result = god.hold()
        except SuiteIdentificationError, x:
            warning_dialog( x.__str__() ).warn()
        else:
            if result.success:
                info_dialog( result.reason ).inform()
            else:
                warning_dialog( result.reason ).warn()

    def resume_suite( self, bt ):
        try:
            god = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port ).get_proxy( 'remote' )
            result = god.resume()
        except SuiteIdentificationError, x:
            warning_dialog( x.__str__() ).warn()
        else:
            if result.success:
                info_dialog( result.reason ).inform()
            else:
                warning_dialog( result.reason ).warn()

    def stopsuite( self, bt, window, stop_rb, stopat_rb, stopnow_rb, stoptime_entry ):
        stop = False
        stopat = False
        stopnow = False
        if stop_rb.get_active():
            stop = True
        elif stopat_rb.get_active():
            stopat = True
            stoptime = stoptime_entry.get_text()
            if stoptime == '':
                warning_dialog( "No stop time entered" ).warn()
                return
            if not is_valid( stoptime ):
                warning_dialog( "Invalid stop time: " + stoptime ).warn()
                return
        elif stopnow_rb.get_active():
            stopnow = True

        window.destroy()

        try:
            god = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port ).get_proxy( 'remote' )
            if stop:
                result = god.shutdown()
            elif stopat:
                result = god.set_stop_time( stoptime )
            elif stopnow:
                result = god.shutdown_now()
        except SuiteIdentificationError, x:
            warning_dialog( x.__str__() ).warn()
        else:
            if result.success:
                info_dialog( result.reason ).inform()
            else:
                warning_dialog( result.reason ).warn()

    def startsuite( self, bt, window, 
            coldstart_rb, warmstart_rb, rawstart_rb, restart_rb,
            entry_ctime, stoptime_entry, statedump_entry, optgroups ):

        if coldstart_rb.get_active():
            command = 'cylc coldstart'
        elif warmstart_rb.get_active():
            command = 'cylc warmstart'
        elif rawstart_rb.get_active():
            command = 'cylc rawstart'
        elif restart_rb.get_active():
            command = 'cylc restart'

        if stoptime_entry.get_text():
            command += ' --until=' + stoptime_entry.get_text()

        ctime = entry_ctime.get_text()

        for group in optgroups:
            command += group.get_options()

        print command

        window.destroy()

        command += ' ' + self.suite + ' ' + ctime

        if restart_rb.get_active():
            if statedump_entry.get_text():
                command += ' ' + statedump_entry.get_text()
        try:
            subprocess.Popen( [command], shell=True )
        except OSError, e:
            warning_dialog( 'Error: failed to start ' + self.suite ).warn()
            success = False

    def unblock_suite( self, bt ):
        try:
            god = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port ).get_proxy( 'remote' )
            god.unblock()
        except Pyro.errors.NamingError:
            warning_dialog( 'Error: suite ' + self.suite + ' is not running' ).warn()

    def block_suite( self, bt ):
        try:
            god = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port ).get_proxy( 'remote' )
            god.block()
        except Pyro.errors.NamingError:
            warning_dialog( 'Error: suite ' + self.suite + ' is not running' ).warn()

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
A real time suite control and monitoring tool for cylc.
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

    def toggle_headings( self, w ):
        if w.get_active():
            self.no_task_headings()
        else:
            self.full_task_headings()

    def no_task_headings( self ):
        self.led_headings = ['Cycle Time' ] + [''] * len( self.task_list )
        self.reset_led_headings()

    def full_task_headings( self ):
        self.led_headings = ['Cycle Time' ] + self.task_list
        self.reset_led_headings()

    def reset_led_headings( self ):
        tvcs = self.led_treeview.get_columns()
        for n in range( 1,1+len( self.task_list) ):
            heading = self.led_headings[n]
            # underscores treated as underlines markup?
            heading = re.sub( '_', '\_', heading )
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
            tvc = gtk.TreeViewColumn( ""  )
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
        eb.add( gtk.Label( "click headings to sort") )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#a7c339' ) ) 
        hbox.pack_start( eb, True )

        eb = gtk.EventBox()
        eb.add( gtk.Label( "click on tasks for options" ) )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#dbd40a' ) ) 
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

    def view_task_info( self, w, task_id ):
        self.show_log( task_id )

    def show_log( self, task_id ):
        [ glbl, states ] = self.get_pyro( 'state_summary').get_state_summary()
        view = True
        reasons = []
        try:
            logfiles = states[ task_id ][ 'logfiles' ]
        except KeyError:
            warning_dialog( task_id + 'is no longer live' ).warn()
            return False

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

        # HERE'S HOW TO DISPLAY MENU ONLY ON RIGHT CLICK
        # (and show task log viewer otherwise):
        #if event.button != 3:
        #    self.show_log( task_id )
        #    return False

        menu = gtk.Menu()

        menu_root = gtk.MenuItem( task_id )
        menu_root.set_submenu( menu )

        info_item = gtk.MenuItem( 'Live Output Feed' )
        menu.append( info_item )
        info_item.connect( 'activate', self.view_task_info, task_id )

        info_item = gtk.MenuItem( 'Prerequisites and Outputs' )
        menu.append( info_item )
        info_item.connect( 'activate', self.popup_requisites, task_id )

        reset_ready_item = gtk.MenuItem( 'Reset to Ready (i.e. trigger immediately)' )
        menu.append( reset_ready_item )
        reset_ready_item.connect( 'activate', self.reset_task_state, task_id, 'ready' )
        if self.readonly:
            reset_ready_item.set_sensitive(False)

        reset_waiting_item = gtk.MenuItem( 'Reset to Waiting (i.e. prerequisites unsatisfied)' )
        menu.append( reset_waiting_item )
        reset_waiting_item.connect( 'activate', self.reset_task_state, task_id, 'waiting' )
        if self.readonly:
            reset_waiting_item.set_sensitive(False)

        reset_finished_item = gtk.MenuItem( 'Reset to Finished (i.e. outputs completed)' )
        menu.append( reset_finished_item )
        reset_finished_item.connect( 'activate', self.reset_task_state, task_id, 'finished' )
        if self.readonly:
            reset_finished_item.set_sensitive(False)

        kill_item = gtk.MenuItem( 'Remove (after spawning)' )
        menu.append( kill_item )
        kill_item.connect( 'activate', self.kill_task, task_id )
        if self.readonly:
            kill_item.set_sensitive(False)

        kill_nospawn_item = gtk.MenuItem( 'Remove (without spawning)' )
        menu.append( kill_nospawn_item )
        kill_nospawn_item.connect( 'activate', self.kill_task_nospawn, task_id )
        if self.readonly:
            kill_nospawn_item.set_sensitive(False)

        purge_item = gtk.MenuItem( 'Recursive Purge' )
        menu.append( purge_item )
        purge_item.connect( 'activate', self.popup_purge, task_id )
        if self.readonly:
            purge_item.set_sensitive(False)

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
        eb.add( gtk.Label( "click headings to sort") )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#dbd40a' ) ) 
        hbox.pack_start( eb, True )

        eb = gtk.EventBox()
        eb.add( gtk.Label( "click on tasks for options" ) )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#a7c339' ) ) 
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

    def start_guide( self, w ):
        window = gtk.Window()
        #window.set_border_width( 10 )
        window.set_title( "Starting A Suite" )
        #window.modify_bg( gtk.STATE_NORMAL, 
        #       gtk.gdk.color_parse( self.log_colors.get_color()))
        window.set_size_request(600, 600)

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC )

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

        textview.set_wrap_mode( gtk.WRAP_WORD )

        blue = tb.create_tag( None, foreground = "blue" )
        red = tb.create_tag( None, foreground = "darkblue" )
        red2 = tb.create_tag( None, foreground = "darkgreen" )
        alert = tb.create_tag( None, foreground = "red" )
        bold = tb.create_tag( None, weight = pango.WEIGHT_BOLD )

        self.update_tb( tb, "Help: Starting A Suite", [bold, blue] )

        self.update_tb( tb, "\n\n o Start (YYYYMMDDHH)", [bold, red] )
        self.update_tb( tb, " - Cold, Warm, and Raw start.", [bold, red2])
        self.update_tb( tb, "\nInitial cycle time.")

        self.update_tb( tb, "\n\n o Stop (YYYYMMDDHH)", [bold, red] )
        self.update_tb( tb, " - OPTIONAL.", [bold,red2])
        self.update_tb( tb, "\nFinal cycle time.")

        self.update_tb( tb, "\n\n o Initial State (FILE)", [bold, red] )
        self.update_tb( tb, " - Restart only.\n", [bold,red2] )
        self.update_tb( tb, "The state dump file from which to load the initial suite state. " )
        self.update_tb( tb, "The default file, " )
        self.update_tb( tb, "<suite-state-dump-dir>/state", [bold] )
        self.update_tb( tb, ", records "
                "the most recent previous state. However, prior to "
                "actioning any intervention, cylc dumps a "
                "special state file and logs its name; to restart from "
                "one of these files just cut-and-paste the filename from the "
                "suite's cylc log. The suite's configured state dump directory "
                "is assumed, unless you specify an absolute path.")

        self.update_tb( tb, "\n\n o Dummy Mode", [bold, red] )
        self.update_tb( tb, " - OPTIONAL.", [bold,red2])
        self.update_tb( tb, "\nDummy mode simulates a suite by replacing "
                "each real task with a small program that simply reports the "
                "task's registered outputs completed and then returns success. "
                "You can configure aspects of dummy mode scheduling in your "
                "suite.rc file, for example the accelerated clock rate, and the "
                "initial clock offset from the initial cycle time (this allows "
                "you to simulate catch up to real time operation after a delay).")

        self.update_tb( tb, "\n    + Fail Task (NAME%YYYYMMDDHH)", [bold, red] )
        self.update_tb( tb, " - OPTIONAL, dummy mode only.", [bold,red2])
        self.update_tb( tb, "\n   Get a task to fail in order "
                "to test the effect on the suite." )

        window.show_all()
 
    def stop_guide( self, w ):
        window = gtk.Window()
        #window.set_border_width( 10 )
        window.set_title( "Stopping A Suite" )
        #window.modify_bg( gtk.STATE_NORMAL, 
        #       gtk.gdk.color_parse( self.log_colors.get_color()))
        window.set_size_request(600, 600)

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC )

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

        textview.set_wrap_mode( gtk.WRAP_WORD )

        blue = tb.create_tag( None, foreground = "blue" )
        red = tb.create_tag( None, foreground = "darkblue" )
        red2 = tb.create_tag( None, foreground = "darkgreen" )
        alert = tb.create_tag( None, foreground = "red" )
        bold = tb.create_tag( None, weight = pango.WEIGHT_BOLD )

        self.update_tb( tb, "Help: Stopping A Suite", [bold, blue] )

        self.update_tb( tb, "\n\n o Stop", [bold, red] )
        self.update_tb( tb, "\nThe suite will not submit any new tasks to run, and will "
                "shut down as soon as all currently submitted or running "
                "tasks have finished. The final state dump file will "
                "reflect what actually happened "
                "in the external world.")

        self.update_tb( tb, "\n\n o Stop At (YYYYMMDDHH)", [bold, red] )
        self.update_tb( tb, "\nStop the suite once all tasks have passed "
                "the specified cycle time and finished running.  The "
                "final state dump file will reflect what actually happened "
                "in the external world.")

        self.update_tb( tb, "\n\n o Stop NOW", [bold, red] )
        self.update_tb( tb, "\nStop the suite immediately. "
                "The final state dump will reflect the state of the "
                "suite at shut down; it will not know about any "
                "already-running tasks that run to completion after "
                "the suite shuts down.")

        window.show_all()


    def userguide( self, w ):
        window = gtk.Window()
        #window.set_border_width( 10 )
        if self.readonly:
            window.set_title( "Cylc View Quick Guide" )
        else:
            window.set_title( "Cylc Control Quick Guide" )
        #window.modify_bg( gtk.STATE_NORMAL, 
        #       gtk.gdk.color_parse( self.log_colors.get_color()))
        window.set_size_request(600, 600)

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC )

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

        textview.set_wrap_mode( gtk.WRAP_WORD )

        blue = tb.create_tag( None, foreground = "blue" )
        red = tb.create_tag( None, foreground = "darkgreen" )
        alert = tb.create_tag( None, foreground = "red" )
        bold = tb.create_tag( None, weight = pango.WEIGHT_BOLD )

        if self.readonly:
            self.update_tb( tb, "\n\nThis is 'cylc view', the read-only "
                "version of the 'cylc control' GUI: all of the suite control "
                "functionality documented below has been disabled.'\n\n", [bold, alert] )

        self.update_tb( tb, "Cylc Control Quick Guide", [bold, blue] )

        self.update_tb( tb, "\n\nCylc Control is a real time suite control and "
                "monitoring tool for cylc. Note that same functionality is "
                "available via the cylc command line; see 'cylc help').")

        self.update_tb( tb, "\n\nMenu: File > ", [bold, red] )
        self.update_tb( tb, "\n o Exit Suite GUI: ", [bold])
        self.update_tb( tb, "Exit the GUI (this does not shut the suite down).")

        self.update_tb( tb, "\n\nMenu: View > ", [bold, red] )
        self.update_tb( tb, "This affects only the top 'light panel'. "
                "You can change turn off task name headings in order to "
                "maximize screen real estate.")

        self.update_tb( tb, "\n\nMenu: Suite > ", [bold, red] )
        self.update_tb( tb, "\n o Start: ", [bold])
        self.update_tb( tb, "Cold Start, Warm Start, Raw Start, or Restart the suite.")
        self.update_tb( tb, "\n o Stop: ", [bold])
        self.update_tb( tb, "Shut down the suite now, or after a given cycle, or "
                "when all currently running tasks have finished." )
        self.update_tb( tb, "\n o Pause: ", [bold])
        self.update_tb( tb, "Refrain from submitting tasks that are ready to run.")
        self.update_tb( tb, "\n o Resume: ", [bold])
        self.update_tb( tb, "Resume submitting tasks that are ready to run.")
        self.update_tb( tb, "\n o Insert: ", [bold])
        self.update_tb( tb, "Insert a task or task group into a running suite." )
        self.update_tb( tb, "\n o Block (if suite is configured to use blocking): ", [bold])
        self.update_tb( tb, "Tell cylc not to comply with subsequent intervention commands." )
        self.update_tb( tb, "\n o Unblock (if suite is configured to use blocking): ", [bold])
        self.update_tb( tb, "Tell cylc to comply with subsequent intervention commands." )

        self.update_tb( tb, "\n\nTask View Panels: Mouse Menu > ", [bold, red] )

        self.update_tb( tb, "\n o Live Output Feed: ", [bold])
        self.update_tb( tb, "View stdout and stderr, "
                "and the job submission file, for a task." )
        self.update_tb( tb, "\n o Prerequisites and Outputs: ", [bold])
        self.update_tb( tb, "View the state of a task's prerequisites and outputs.")
        self.update_tb( tb, "\n o Reset To Ready: ", [bold])
        self.update_tb( tb, "Set all of a task's prerequisites satisfied. This will "
                "(re)trigger the task immediately (if the suite has not been paused)." )
        self.update_tb( tb, "\n o Reset To Waiting: ", [bold])
        self.update_tb( tb, "Set all of a task's prerequisites unsatisfied." )
        self.update_tb( tb, "\n o Reset To Finished: ", [bold])
        self.update_tb( tb, "Set all of a task's outputs completed." )
        self.update_tb( tb, "\n o Remove (after spawning): ", [bold])
        self.update_tb( tb, "Remove a task from the suite after ensuring that it has "
                "spawned a successor." )
        self.update_tb( tb, "\n o Remove (without spawning): ", [bold])
        self.update_tb( tb, "Remove a task from the suite even if it has not "
                "yet spawned a successor (in which case it will be removed "
                "permanently unless re-inserted)." )
        self.update_tb( tb, "\n o Recursive Purge: ", [bold])
        self.update_tb( tb, "Remove a task from the suite, then remove any task "
                "that would depend on it, then remove any tasks that would depend on "
                "those tasks, and so on, through to a given stop cycle." )

        window.show_all()
 
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

    def reset_task_state( self, b, task_id, state ):
        msg = "reset " + task_id + " to " + state +"?"
        prompt = gtk.MessageDialog( None, gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_OK_CANCEL, msg )
        response = prompt.run()
        prompt.destroy()
        if response != gtk.RESPONSE_OK:
            return
        try:
            proxy = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port).get_proxy( 'remote' )
        except SuiteIdentificationError, x:
            # the suite was probably shut down by another process
            warning_dialog( x.__str__() ).warn()
            return
        result = proxy.reset_task_state( task_id, state )
        if result.success:
            info_dialog( result.reason ).inform()
        else:
            warning_dialog( result.reason ).warn()

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


    def stopsuite_popup( self, b ):
        window = gtk.Window()
        window.modify_bg( gtk.STATE_NORMAL, 
                gtk.gdk.color_parse( self.log_colors.get_color()))
        window.set_border_width(5)
        window.set_title( "Stop Suite '" + self.suite + "'")

        vbox = gtk.VBox()

        box = gtk.HBox()
        stop_rb = gtk.RadioButton( None, "Stop" )
        box.pack_start (stop_rb, True)
        stopat_rb = gtk.RadioButton( stop_rb, "Stop At" )
        box.pack_start (stopat_rb, True)
        stopnow_rb = gtk.RadioButton( stop_rb, "Stop NOW" )
        box.pack_start (stopnow_rb, True)
        stop_rb.set_active(True)
        vbox.pack_start( box )

        box = gtk.HBox()
        label = gtk.Label( 'Stop At (YYYYMMDDHH)' )
        box.pack_start( label, True )
        stoptime_entry = gtk.Entry()
        stoptime_entry.set_max_length(10)
        stoptime_entry.set_sensitive(False)
        box.pack_start (stoptime_entry, True)
        vbox.pack_start( box )

        stop_rb.connect( "toggled", self.stop_method, "stop", stoptime_entry )
        stopat_rb.connect( "toggled", self.stop_method, "stopat", stoptime_entry )
        stopnow_rb.connect(   "toggled", self.stop_method, "stopnow", stoptime_entry )

        cancel_button = gtk.Button( "Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        stop_button = gtk.Button( "Stop" )
        stop_button.connect("clicked", self.stopsuite, 
                window, stop_rb, stopat_rb, stopnow_rb,
                stoptime_entry )

        help_button = gtk.Button( "Help" )
        help_button.connect("clicked", self.stop_guide )

        hbox = gtk.HBox()
        hbox.pack_start( cancel_button, False )
        hbox.pack_start( stop_button, False )
        hbox.pack_start( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def stop_method( self, b, meth, stoptime_entry ):
        if meth == 'stop' or meth == 'stopnow':
            stoptime_entry.set_sensitive( False )
        else:
            stoptime_entry.set_sensitive( True )

    def startup_method( self, b, meth, ctime_entry, statedump_entry ):
        if meth == 'cold' or meth == 'warm' or meth == 'raw':
            statedump_entry.set_sensitive( False )
            ctime_entry.set_sensitive( True )
        else:
            statedump_entry.set_sensitive( True )
            ctime_entry.set_sensitive( False )

    def startsuite_popup( self, b ):
        window = gtk.Window()
        window.modify_bg( gtk.STATE_NORMAL, 
                gtk.gdk.color_parse( self.log_colors.get_color()))
        window.set_border_width(5)
        window.set_title( "Start Suite '" + self.suite + "'")

        vbox = gtk.VBox()

        box = gtk.HBox()
        coldstart_rb = gtk.RadioButton( None, "Cold Start" )
        box.pack_start (coldstart_rb, True)
        warmstart_rb = gtk.RadioButton( coldstart_rb, "Warm Start" )
        box.pack_start (warmstart_rb, True)
        rawstart_rb = gtk.RadioButton( coldstart_rb, "Raw Start" )
        box.pack_start (rawstart_rb, True)
        restart_rb = gtk.RadioButton( coldstart_rb, "Restart" )
        box.pack_start (restart_rb, True)
        coldstart_rb.set_active(True)
        vbox.pack_start( box )

        box = gtk.HBox()
        label = gtk.Label( 'Start (YYYYMMDDHH)' )
        box.pack_start( label, True )
        ctime_entry = gtk.Entry()
        ctime_entry.set_max_length(10)
        #ctime_entry.set_width_chars(10)
        box.pack_start (ctime_entry, True)
        vbox.pack_start( box )

        box = gtk.HBox()
        label = gtk.Label( 'Stop (YYYYMMDDHH)' )
        box.pack_start( label, True )
        stoptime_entry = gtk.Entry()
        stoptime_entry.set_max_length(10)
        #stoptime_entry.set_width_chars(10)
        box.pack_start (stoptime_entry, True)
        vbox.pack_start( box )

        box = gtk.HBox()
        label = gtk.Label( 'Initial State (FILE)' )
        box.pack_start( label, True )
        statedump_entry = gtk.Entry()
        statedump_entry.set_text( 'state' )
        statedump_entry.set_sensitive( False )
        box.pack_start (statedump_entry, True)
        vbox.pack_start(box)

        coldstart_rb.connect( "toggled", self.startup_method, "cold", ctime_entry, statedump_entry )
        warmstart_rb.connect( "toggled", self.startup_method, "warm", ctime_entry, statedump_entry )
        rawstart_rb.connect ( "toggled", self.startup_method, "raw",  ctime_entry, statedump_entry )
        restart_rb.connect(   "toggled", self.startup_method, "re",   ctime_entry, statedump_entry )

        dmode_group = controlled_option_group( "Dummy Mode", "--dummy-mode" )
        dmode_group.add_entry( 
                'Fail Task (NAME%YYYYMMDDHH)',
                '--fail='
                )
        dmode_group.pack( vbox )
        
        dot_group = controlled_option_group( "Debug Mode", "--debug" )
        #dot_group.add_entry( 'filename (absolute path or relative to $HOME)', 
        #        '--graphfile=', max_chars=None, default=self.suite+'.dot' )
        dot_group.pack( vbox )
        optgroups = [ dmode_group, dot_group ]

        cancel_button = gtk.Button( "Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        start_button = gtk.Button( "Start" )
        start_button.connect("clicked", self.startsuite, 
                window, coldstart_rb, warmstart_rb, rawstart_rb, restart_rb,
                ctime_entry, stoptime_entry, 
                statedump_entry, optgroups )

        help_button = gtk.Button( "Help" )
        help_button.connect("clicked", self.start_guide )

        hbox = gtk.HBox()
        hbox.pack_start( start_button, False )
        hbox.pack_start( cancel_button, False )
        hbox.pack_start( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()


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

    def ctime_entry_popup( self, b, callback, title ):
        window = gtk.Window()
        window.modify_bg( gtk.STATE_NORMAL, 
                gtk.gdk.color_parse( self.log_colors.get_color()))
        window.set_border_width(5)
        window.set_title( title )
        #window.set_size_request(800, 300)

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )

        vbox = gtk.VBox()

        hbox = gtk.HBox()
        label = gtk.Label( 'Cycle Time' )
        hbox.pack_start( label, True )
        entry_ctime = gtk.Entry()
        entry_ctime.set_max_length(10)
        hbox.pack_start (entry_ctime, True)
        vbox.pack_start(hbox)

        go_button = gtk.Button( "Go" )
        go_button.connect("clicked", callback, window, entry_ctime )
        vbox.pack_start(go_button)
 
        window.add( vbox )
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
        label = gtk.Label( 'Task or Insertion Group name' )
        hbox.pack_start( label, True )
        entry_name = gtk.Entry()
        hbox.pack_start (entry_name, True)
        vbox.pack_start(hbox)

        hbox = gtk.HBox()
        label = gtk.Label( 'Cycle Time' )
        hbox.pack_start( label, True )
        entry_ctime = gtk.Entry()
        entry_ctime.set_max_length(10)
        hbox.pack_start (entry_ctime, True)
        vbox.pack_start(hbox)

        hbox = gtk.HBox()
        insert_button = gtk.Button( "Insert" )
        insert_button.connect("clicked", self.insert_task, window, entry_name, entry_ctime )
        cancel_button = gtk.Button( "Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )
        hbox.pack_start(cancel_button)
        hbox.pack_start(insert_button)
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def insert_task( self, w, window, entry_name, entry_ctime ):
        name = entry_name.get_text()
        ctime = entry_ctime.get_text()
        if not is_valid( ctime ):
            warning_dialog( "Cycle time not valid: " + ctime).warn()
            return
        if name == '':
            warning_dialog( "Enter task or group name" ).warn()
            return
        window.destroy()
        task_id = name + '%' + ctime
        proxy = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port ).get_proxy( 'remote' )
        try:
            result = proxy.insert( task_id )
        except SuiteIdentificationError, x:
            warning_dialog( x.__str__() ).warn()
        else:
            if result.success:
                info_dialog( result.reason ).inform()
            else:
                warning_dialog( result.reason ).warn()

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

        #state_button = gtk.Button( "Interrogate" )
        #state_button.connect("clicked", self.popup_requisites, task_id )
 
        quit_button = gtk.Button( "Close" )
        quit_button.connect("clicked", self.on_popup_quit, lv, window )
        
        lv.hbox.pack_start( quit_button )
        #lv.hbox.pack_start( state_button )

        window.connect("delete_event", lv.quit_w_e)
        window.show_all()


    def create_menu( self ):
        file_menu = gtk.Menu()

        file_menu_root = gtk.MenuItem( 'File' )
        file_menu_root.set_submenu( file_menu )

        exit_item = gtk.MenuItem( 'Exit ' + self.suite + ' GUI' )
        exit_item.connect( 'activate', self.click_exit )
        file_menu.append( exit_item )

        start_menu = gtk.Menu()
        start_menu_root = gtk.MenuItem( 'Suite' )
        start_menu_root.set_submenu( start_menu )

        start_item = gtk.MenuItem( 'Start' )
        start_menu.append( start_item )
        start_item.connect( 'activate', self.startsuite_popup )
        if self.readonly:
            start_item.set_sensitive(False)

        stop_item = gtk.MenuItem( 'Stop' )
        start_menu.append( stop_item )
        stop_item.connect( 'activate', self.stopsuite_popup )
        if self.readonly:
            stop_item.set_sensitive(False)

        pause_item = gtk.MenuItem( 'Pause' )
        start_menu.append( pause_item )
        pause_item.connect( 'activate', self.pause_suite )
        if self.readonly:
            pause_item.set_sensitive(False)

        resume_item = gtk.MenuItem( 'Resume' )
        start_menu.append( resume_item )
        resume_item.connect( 'activate', self.resume_suite )
        if self.readonly:
            resume_item.set_sensitive(False)

        insert_item = gtk.MenuItem( 'Insert' )
        start_menu.append( insert_item )
        insert_item.connect( 'activate', self.insert_task_popup )
        if self.readonly:
            insert_item.set_sensitive(False)

        block_item = gtk.MenuItem( 'Block' )
        start_menu.append( block_item )
        block_item.connect( 'activate', self.block_suite )
        if self.readonly or not self.use_block:
            block_item.set_sensitive(False)

        unblock_item = gtk.MenuItem( 'Unblock' )
        start_menu.append( unblock_item )
        unblock_item.connect( 'activate', self.unblock_suite )
        if self.readonly or not self.use_block:
            unblock_item.set_sensitive(False)

        help_menu = gtk.Menu()
        help_menu_root = gtk.MenuItem( 'Help' )
        help_menu_root.set_submenu( help_menu )

        guide_item = gtk.MenuItem( 'Quick Guide' )
        help_menu.append( guide_item )
        guide_item.connect( 'activate', self.userguide )
 
        about_item = gtk.MenuItem( 'About' )
        help_menu.append( about_item )
        about_item.connect( 'activate', self.about )
      
        self.menu_bar = gtk.MenuBar()
        self.menu_bar.append( file_menu_root )
        self.menu_bar.append( start_menu_root )
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
 
    def preload_task_list( self ):
        # Load task list from suite config.
        ### TO DO: For suites that are already running, or for dynamically
        ### updating the viewed task list, we can retrieve the task list
        ### (etc.) from the suite's remote state summary object.
        suiterc = config( self.suite )
        self.task_list = suiterc.get_task_name_list()
        self.use_block = suiterc['use suite blocking']

    def __init__(self, suite, owner, host, port, suite_dir, logging_dir, imagedir, readonly=False ):
        self.readonly = readonly
        self.logdir = logging_dir
        self.suite_dir = suite_dir

        self.suite = suite
        self.host = host
        self.port = port
        self.owner = owner
        self.imagedir = imagedir
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        #self.window.set_border_width( 5 )
        if self.readonly:
            self.window.set_title("cylc view <" + self.suite + "> (READONLY)" )
        else:
            self.window.set_title("cylc control <" + self.suite + ">" )
        self.window.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( "#ddd" ))
        self.window.set_size_request(600, 500)
        self.window.connect("delete_event", self.delete_event)

        self.log_colors = color_rotator()

        # Get list of tasks in the suite
        self.preload_task_list()
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

        view_button = gtk.ToggleButton( "Task Names" )
        view_button.connect( 'toggled', self.toggle_headings )
    
        self.led_headings = None 
        self.full_task_headings()

        bigbox = gtk.VBox()
        bigbox.pack_start( self.menu_bar, False )
        hbox = gtk.HBox()
        hbox.pack_start( self.create_info_bar(), True )
        hbox.pack_start( view_button, False )
        bigbox.pack_start( hbox, False )
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
    # For a monitor not launched by the chooser: 
    # 1/ call gobject.threads_init() on startup
    # 2/ call gtk.main_quit() on exit

    def __init__(self, suite, owner, host, port, suite_dir, logging_dir, imagedir, readonly=False ):
        gobject.threads_init()
        monitor.__init__(self, suite, owner, host, port, suite_dir, logging_dir, imagedir, readonly )
 
    def delete_event(self, widget, event, data=None):
        monitor.delete_event( self, widget, event, data )
        gtk.main_quit()

    def click_exit( self, foo ):
        monitor.click_exit( self, foo )
        gtk.main_quit()
