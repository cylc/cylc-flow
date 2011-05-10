#!/usr/bin/env python

import gtk
#import pygtk
#pygtk.require('2.0')
import pango
import os, re
import Pyro.errors
import subprocess
import helpwindow
from combo_logviewer import combo_logviewer
from warning_dialog import warning_dialog, info_dialog
from port_scan import SuiteIdentificationError
import cylc_pyro_client
import cycle_time
from option_group import controlled_option_group
from config import config
from color_rotator import rotator
from cylc_logviewer import cylc_logviewer
from textload import textload

class ControlAppBase(object):
    """
Base class for suite control GUI functionality.
Derived classes must provide:
  self.get_control_widgets()
and associated methods for their control widgets.
    """
    def __init__(self, suite, owner, host, port, suite_dir, logging_dir, imagedir, readonly=False ):
        self.readonly = readonly
        self.logdir = logging_dir
        self.suite_dir = suite_dir
        self.suite = suite
        self.host = host
        self.port = port
        self.owner = owner
        self.imagedir = imagedir

        self.suiterc = config( self.suite )
        self.use_block = self.suiterc['use blocking']

        self.connection_lost = False # (not used)
        self.quitters = []

        self.log_colors = rotator()

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        if self.readonly:
            self.window.set_title("gcylc <" + self.suite + "> (READONLY)" )
        else:
            self.window.set_title("gcylc <" + self.suite + ">" )
        self.window.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( "#ddd" ))
        self.window.set_size_request(800, 500)
        self.window.connect("delete_event", self.delete_event)

        self.create_main_menu()

        bigbox = gtk.VBox()
        bigbox.pack_start( self.menu_bar, False )
        hbox = gtk.HBox()

        hbox.pack_start( self.create_info_bar(), True )
        bigbox.pack_start( hbox, False )

        bigbox.pack_start( self.get_control_widgets(), True )

        self.window.add( bigbox )
        self.window.show_all()

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
            if not cycle_time.is_valid( stoptime ):
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
            entry_ctime, stoptime_entry, no_reset_cb, statedump_entry,
            optgroups ):

        command = 'cylc control run --gcylc'
        options = ''
        method = ''
        if coldstart_rb.get_active():
            method = 'coldstart'
            pass
        elif warmstart_rb.get_active():
            method = 'warmstart'
            options += ' -w'
        elif rawstart_rb.get_active():
            method = 'rawstart'
            options += ' -r'
        elif restart_rb.get_active():
            method = 'restart'
            command = 'cylc control restart --gcylc'
            if no_reset_cb.get_active():
                options += ' --no-reset'

        command += ' ' + options + ' '

        if stoptime_entry.get_text():
            command += ' --until=' + stoptime_entry.get_text()

        ctime = entry_ctime.get_text()

        if method != 'restart':
            if ctime == '':
                warning_dialog( 'Error: an initial cycle time is required' ).warn()
                return False

        for group in optgroups:
            command += group.get_options()
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
        about.set_copyright( "(c) Hilary Oliver, NIWA, 2008-2010" )
        about.set_comments( 
"""
The cylc forecast suite metascheduler.
""" )
        about.set_website( "http://www.niwa.co.nz" )
        about.set_logo( gtk.gdk.pixbuf_new_from_file( self.imagedir + "/dew.jpg" ))
        about.run()
        about.destroy()

    def delete_event(self, widget, event, data=None):
        for q in self.quitters:
            q.quit()
        return False

    def click_exit( self, foo ):
        for q in self.quitters:
            q.quit()
        self.window.destroy()
        return False

    def view_task_info( self, w, task_id, jsonly ):
        try:
            [ glbl, states ] = self.get_pyro( 'state_summary').get_state_summary()
        except SuiteIdentificationError, x:
            warning_dialog( str(x) ).warn()
            return
        view = True
        reasons = []
        try:
            logfiles = states[ task_id ][ 'logfiles' ]
        except KeyError:
            warning_dialog( task_id + ' is no longer live' ).warn()
            return False

        if len(logfiles) == 0:
            view = False
            reasons.append( task_id + ' has no associated log files' )

        if states[ task_id ][ 'state' ] == 'waiting':
            view = False
            reasons.append( task_id + ' has not started yet' )

        if not view:
            warning_dialog( '\n'.join( reasons ) ).warn()
        else:
            self.popup_logview( task_id, logfiles, jsonly )

        return False

    def get_right_click_menu_items( self, task_id ):
        name, ctime = task_id.split('%')

        items = []

        js_item = gtk.MenuItem( 'View Job Script' )
        items.append( js_item )
        js_item.connect( 'activate', self.view_task_info, task_id, True )

        info_item = gtk.MenuItem( 'View Job Stdout & Stderr' )
        items.append( info_item )
        info_item.connect( 'activate', self.view_task_info, task_id, False )

        info_item = gtk.MenuItem( 'View Task Prerequisites & Outputs' )
        items.append( info_item )
        info_item.connect( 'activate', self.popup_requisites, task_id )

        items.append( gtk.SeparatorMenuItem() )

        reset_ready_item = gtk.MenuItem( 'Trigger Now (if suite not paused)' )
        items.append( reset_ready_item )
        reset_ready_item.connect( 'activate', self.reset_task_state, task_id, 'ready' )
        if self.readonly:
            reset_ready_item.set_sensitive(False)

        reset_waiting_item = gtk.MenuItem( 'Reset State to "waiting"' )
        items.append( reset_waiting_item )
        reset_waiting_item.connect( 'activate', self.reset_task_state, task_id, 'waiting' )
        if self.readonly:
            reset_waiting_item.set_sensitive(False)

        reset_finished_item = gtk.MenuItem( 'Reset State to "finished"' )
        items.append( reset_finished_item )
        reset_finished_item.connect( 'activate', self.reset_task_state, task_id, 'finished' )
        if self.readonly:
            reset_finished_item.set_sensitive(False)

        reset_failed_item = gtk.MenuItem( 'Reset State to "failed"' )
        items.append( reset_failed_item )
        reset_failed_item.connect( 'activate', self.reset_task_state, task_id, 'failed' )
        if self.readonly:
            reset_failed_item.set_sensitive(False)

        items.append( gtk.SeparatorMenuItem() )
    
        kill_item = gtk.MenuItem( 'Remove Task (after spawning)' )
        items.append( kill_item )
        kill_item.connect( 'activate', self.kill_task, task_id )
        if self.readonly:
            kill_item.set_sensitive(False)

        kill_nospawn_item = gtk.MenuItem( 'Remove Task (without spawning)' )
        items.append( kill_nospawn_item )
        kill_nospawn_item.connect( 'activate', self.kill_task_nospawn, task_id )
        if self.readonly:
            kill_nospawn_item.set_sensitive(False)

        purge_item = gtk.MenuItem( 'Remove Tree (Recursive Purge)' )
        items.append( purge_item )
        purge_item.connect( 'activate', self.popup_purge, task_id )
        if self.readonly:
            purge_item.set_sensitive(False)

        items.append( gtk.SeparatorMenuItem() )
    
        addprereq_item = gtk.MenuItem( 'Add a Prerequisite' )
        items.append( addprereq_item )
        addprereq_item.connect( 'activate', self.add_prerequisite_popup, task_id )
        if self.readonly:
            addprereq_item.set_sensitive(False)

        return items

    def change_runahead_popup( self, b ):
        window = gtk.Window()
        window.modify_bg( gtk.STATE_NORMAL, 
                gtk.gdk.color_parse( self.log_colors.get_color()))
        window.set_border_width(5)
        window.set_title( "Change Suite Runahead Limit" )
        #window.set_size_request(800, 300)

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )

        vbox = gtk.VBox()
        label = gtk.Label( 'Limit in HOURS (omit for no limit)' )

        entry = gtk.Entry()
        #entry.connect( "activate", self.change_runahead_entry, window, task_id )

        hbox = gtk.HBox()
        hbox.pack_start( label, True )
        hbox.pack_start (entry, True)
        vbox.pack_start( hbox )

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        start_button = gtk.Button( "_Change" )
        start_button.connect("clicked", self.change_runahead, entry, window )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.change_runahead )

        hbox = gtk.HBox()
        hbox.pack_start( cancel_button, True )
        hbox.pack_start( start_button, True)
        hbox.pack_start( help_button, True)
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def change_runahead( self, w, entry, window ):
        ent = entry.get_text()
        if ent == '':
            limit = None
        else:
            try:
                int( ent )
            except ValueError:
                warning_dialog( 'Hours value must be integer!' ).warn()
                return
            else:
                limit = ent
        window.destroy()
        proxy = cylc_pyro_client.client( self.suite, self.owner,
                self.host, self.port ).get_proxy( 'remote' )
        try:
            result = proxy.set_runahead( limit )
        except SuiteIdentificationError, x:
            warning_dialog( x.__str__() ).warn()
        else:
            if result.success:
                info_dialog( result.reason ).inform()
            else:
                warning_dialog( result.reason ).warn()

    def add_prerequisite_popup( self, b, task_id ):
        window = gtk.Window()
        window.modify_bg( gtk.STATE_NORMAL, 
                gtk.gdk.color_parse( self.log_colors.get_color()))
        window.set_border_width(5)
        window.set_title( "Add A Prequisite To " + task_id )
        #window.set_size_request(800, 300)

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )

        vbox = gtk.VBox()
        label = gtk.Label( 'Task (NAME%YYYYMMDDHH) or prerequisite message' )

        entry = gtk.Entry()
        #entry.connect( "activate", self.add_prerequisite_entry, window, task_id )

        hbox = gtk.HBox()
        hbox.pack_start( label, True )
        hbox.pack_start (entry, True)
        vbox.pack_start( hbox )

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        start_button = gtk.Button( "_Add" )
        start_button.connect("clicked", self.add_prerequisite, entry, window, task_id )

        hbox = gtk.HBox()
        hbox.pack_start( cancel_button, True )
        hbox.pack_start(start_button, True)
        vbox.pack_start( hbox )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.add_prerequisite )

        window.add( vbox )
        window.show_all()

    def add_prerequisite( self, w, entry, window, task_id ):
        dep = entry.get_text()
        m = re.match( '^(\w+)%(\w+)$', dep )
        if m:
            #name, ctime = m.groups()
            msg = dep + ' finished'
        else:
            msg = dep

        try:
            (name, cycle ) = task_id.split('%')
        except ValueError:
            warning_dialog( "Task or Group ID must be NAME%YYYYMMDDHH").warn()
            return
        if not cycle_time.is_valid( cycle ):
            warning_dialog( "invalid cycle time: " + cycle ).warn()
            return

        window.destroy()
        proxy = cylc_pyro_client.client( self.suite, self.owner,
                self.host, self.port ).get_proxy( 'remote' )
        try:
            result = proxy.add_prerequisite( task_id, msg )
        except SuiteIdentificationError, x:
            warning_dialog( x.__str__() ).warn()
        else:
            if result.success:
                info_dialog( result.reason ).inform()
            else:
                warning_dialog( result.reason ).warn()

    def update_tb( self, tb, line, tags = None ):
        if tags:
            tb.insert_with_tags( tb.get_end_iter(), line, *tags )
        else:
            tb.insert( tb.get_end_iter(), line )

    def popup_requisites( self, w, task_id ):
        try:
            result = self.get_pyro( 'remote' ).get_task_requisites( [ task_id ] )
        except SuiteIdentificationError,x:
            warning_dialog(str(x)).warn()
            return

        if result:
            # (else no tasks were found at all -suite shutting down)
            if task_id not in result:
                warning_dialog( 
                    "Task proxy " + task_id + " not found in " + self.suite + \
                 ".\nTasks are removed once they are no longer needed.").warn()
                return

        window = gtk.Window()
        #window.set_border_width( 10 )
        window.set_title( task_id + ": Prerequisites and Outputs" )
        #window.modify_bg( gtk.STATE_NORMAL, 
        #       gtk.gdk.color_parse( self.log_colors.get_color()))
        window.set_size_request(400, 300)

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )

        vbox = gtk.VBox()
        quit_button = gtk.Button( "_Close" )
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
        try:
            proxy = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port).get_proxy( 'remote' )
        except SuiteIdentificationError, x:
            warning_dialog(str(x)).warn()
            return
        actioned, explanation = proxy.spawn_and_die( task_id )
 
    def kill_task_nospawn( self, b, task_id ):
        msg = "remove " + task_id + " (without spawning)?"
        prompt = gtk.MessageDialog( None, gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_OK_CANCEL, msg )
        response = prompt.run()
        prompt.destroy()
        if response != gtk.RESPONSE_OK:
            return
        try:
            proxy = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port).get_proxy( 'remote' )
        except SuiteIdentificationError, x:
            warning_dialog(str(x)).warn()
            return
        actioned, explanation = proxy.die( task_id )

    def purge_cycle_entry( self, e, w, task_id ):
        stop = e.get_text()
        w.destroy()
        try:
            proxy = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port ).get_proxy( 'remote' )
        except SuiteIdentificationError, x:
            warning_dialog(str(x)).warn()
            return
        actioned, explanation = proxy.purge( task_id, stop )

    def purge_cycle_button( self, b, e, w, task_id ):
        stop = e.get_text()
        w.destroy()
        try:
            proxy = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port ).get_proxy( 'remote' )
        except SuiteIdentificationError, x:
            warning_dialog(str(x)).warn()
            return
        actioned, explanation = proxy.purge( task_id, stop )

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

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        stop_button = gtk.Button( "_Stop" )
        stop_button.connect("clicked", self.stopsuite, 
                window, stop_rb, stopat_rb, stopnow_rb,
                stoptime_entry )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.stop_guide )

        hbox = gtk.HBox()
        hbox.pack_start( stop_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def stop_method( self, b, meth, stoptime_entry ):
        if meth == 'stop' or meth == 'stopnow':
            stoptime_entry.set_sensitive( False )
        else:
            stoptime_entry.set_sensitive( True )

    def startup_method( self, b, meth, ctime_entry, statedump_entry, no_reset_cb ):
        if meth == 'cold' or meth == 'warm' or meth == 'raw':
            statedump_entry.set_sensitive( False )
            ctime_entry.set_sensitive( True )
            no_reset_cb.set_sensitive(False)
        else:
            # restart
            statedump_entry.set_sensitive( True )
            ctime_entry.set_sensitive( False )
            no_reset_cb.set_sensitive(True)

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

        no_reset_cb = gtk.CheckButton( "Don't reset failed tasks" )
        no_reset_cb.set_active(False)
        no_reset_cb.set_sensitive(False)
        vbox.pack_start (no_reset_cb, True)

        coldstart_rb.connect( "toggled", self.startup_method, "cold", ctime_entry, statedump_entry, no_reset_cb )
        warmstart_rb.connect( "toggled", self.startup_method, "warm", ctime_entry, statedump_entry, no_reset_cb )
        rawstart_rb.connect ( "toggled", self.startup_method, "raw",  ctime_entry, statedump_entry, no_reset_cb )
        restart_rb.connect(   "toggled", self.startup_method, "re",   ctime_entry, statedump_entry, no_reset_cb )

        dmode_group = controlled_option_group( "Dummy Mode", "--dummy-mode" )
        dmode_group.add_entry( 
                'Fail Task (NAME%YYYYMMDDHH)',
                '--fail='
                )
        dmode_group.pack( vbox )
        
        stpaused_group = controlled_option_group( "Pause Immediately", "--paused" )
        stpaused_group.pack( vbox )

        debug_group = controlled_option_group( "Debug", "--debug" )
        debug_group.pack( vbox )

        optgroups = [ dmode_group, debug_group, stpaused_group ]

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        start_button = gtk.Button( "_Start" )
        start_button.connect("clicked", self.startsuite, 
                window, coldstart_rb, warmstart_rb, rawstart_rb, restart_rb,
                ctime_entry, stoptime_entry, no_reset_cb, 
                statedump_entry, optgroups )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.start_guide )

        hbox = gtk.HBox()
        hbox.pack_start( start_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
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

        vbox = gtk.VBox()
        label = gtk.Label( 'stop cycle (inclusive)' )

        entry = gtk.Entry()
        entry.set_max_length(10)
        entry.connect( "activate", self.purge_cycle_entry, window, task_id )

        hbox = gtk.HBox()
        hbox.pack_start( label, True )
        hbox.pack_start (entry, True)
        vbox.pack_start( hbox )

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        start_button = gtk.Button( "_Purge" )
        start_button.connect("clicked", self.purge_cycle_button, entry, window, task_id )

        hbox = gtk.HBox()
        hbox.pack_start( cancel_button, True )
        hbox.pack_start(start_button, True)
        vbox.pack_start( hbox )

        # TO DO:
        #help_button = gtk.Button( "Help" )
        #help_button.connect("clicked", self.purge_guide )

        window.add( vbox )
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
        window.set_title( "Insert a Task or Group" )
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
        label = gtk.Label( 'Optional Final Cycle Time' )
        hbox.pack_start( label, True )
        entry_stopctime = gtk.Entry()
        entry_stopctime.set_max_length(10)
        hbox.pack_start (entry_stopctime, True)
        vbox.pack_start(hbox)
 
        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.insertion )

        hbox = gtk.HBox()
        insert_button = gtk.Button( "_Insert" )
        insert_button.connect("clicked", self.insert_task, window, entry_name, entry_ctime, entry_stopctime )
        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )
        hbox.pack_start(insert_button, False)
        hbox.pack_end(cancel_button, False)
        hbox.pack_end(help_button, False)
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def insert_task( self, w, window, entry_name, entry_ctime, entry_stopctime ):
        name = entry_name.get_text()
        ctime = entry_ctime.get_text()
        if not cycle_time.is_valid( ctime ):
            warning_dialog( "Cycle time not valid: " + ctime ).warn()
            return
        if name == '':
            warning_dialog( "Enter task or group name" ).warn()
            return
        stopctime = entry_stopctime.get_text()
        if stopctime != '':
            if not cycle_time.is_valid( stopctime ):
                warning_dialog( "Cycle time not valid: " + stopctime ).warn()
                return
        window.destroy()
        if stopctime == '':
            stop = None
        else:
            stop = stopctime
        proxy = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port ).get_proxy( 'remote' )
        try:
            result = proxy.insert( name + '%' + ctime, stop )
        except SuiteIdentificationError, x:
            warning_dialog( x.__str__() ).warn()
        else:
            if result.success:
                info_dialog( result.reason ).inform()
            else:
                warning_dialog( result.reason ).warn()

    def nudge_suite( self, w ):
        try:
            proxy = cylc_pyro_client.client( self.suite ).get_proxy( 'remote' )
        except SuiteIdentificationError, x:
            warning_dialog( str(x) ).warn()
            return False
        result = proxy.nudge()
        if not result:
            warning_dialog( 'Failed to nudge the suite' ).warn()

    def popup_logview( self, task_id, logfiles, jsonly ):
        # TO DO: jsonly is dirty hack to separate the job script from
        # task log files; we should do this properly by storing them
        # separately in the task proxy, or at least separating them in
        # the suite state summary.
        window = gtk.Window()
        window.modify_bg( gtk.STATE_NORMAL, 
                gtk.gdk.color_parse( self.log_colors.get_color()))
        window.set_border_width(5)
        logs = []
        for f in logfiles:
            if re.search( 'cylc-', f ):
                js = f
            else:
                logs.append(f)

        window.set_size_request(800, 300)
        if jsonly:
            window.set_title( task_id + ": Task Job Submission Script" )
            lv = textload( task_id, js )
        else:
            # put '.out' before '.err'
            logs.sort( reverse=True )
            window.set_title( task_id + ": Task Logs" )
            lv = combo_logviewer( task_id, logs )
        #print "ADDING to quitters: ", lv
        self.quitters.append( lv )

        window.add( lv.get_widget() )

        #state_button = gtk.Button( "Interrogate" )
        #state_button.connect("clicked", self.popup_requisites, task_id )
 
        quit_button = gtk.Button( "_Close" )
        quit_button.connect("clicked", self.on_popup_quit, lv, window )
        
        lv.hbox.pack_start( quit_button, False )
        #lv.hbox.pack_start( state_button )

        window.connect("delete_event", lv.quit_w_e)
        window.show_all()


    def create_main_menu( self ):
        file_menu = gtk.Menu()

        file_menu_root = gtk.MenuItem( '_File' )
        file_menu_root.set_submenu( file_menu )

        exit_item = gtk.MenuItem( 'E_xit (Disconnect From Suite)' )
        exit_item.connect( 'activate', self.click_exit )
        file_menu.append( exit_item )

        self.view_menu = gtk.Menu()
        view_menu_root = gtk.MenuItem( '_View' )
        view_menu_root.set_submenu( self.view_menu )

        nudge_item = gtk.MenuItem( "_Nudge Suite (update times)" )
        self.view_menu.append( nudge_item )
        nudge_item.connect( 'activate', self.nudge_suite  )

        log_item = gtk.MenuItem( 'View _Suite Log' )
        self.view_menu.append( log_item )
        log_item.connect( 'activate', self.view_log )

        start_menu = gtk.Menu()
        start_menu_root = gtk.MenuItem( '_Control' )
        start_menu_root.set_submenu( start_menu )

        start_item = gtk.MenuItem( '_Run (cold-, warm-, raw-, re-start)' )
        start_menu.append( start_item )
        start_item.connect( 'activate', self.startsuite_popup )
        if self.readonly:
            start_item.set_sensitive(False)

        stop_item = gtk.MenuItem( '_Stop (soon, now, or later)' )
        start_menu.append( stop_item )
        stop_item.connect( 'activate', self.stopsuite_popup )
        if self.readonly:
            stop_item.set_sensitive(False)

        pause_item = gtk.MenuItem( '_Pause (stop submitting tasks)' )
        start_menu.append( pause_item )
        pause_item.connect( 'activate', self.pause_suite )
        if self.readonly:
            pause_item.set_sensitive(False)

        resume_item = gtk.MenuItem( '_Unpause (resume submitting tasks)' )
        start_menu.append( resume_item )
        resume_item.connect( 'activate', self.resume_suite )
        if self.readonly:
            resume_item.set_sensitive(False)

        insert_item = gtk.MenuItem( '_Insert a Task or Group' )
        start_menu.append( insert_item )
        insert_item.connect( 'activate', self.insert_task_popup )
        if self.readonly:
            insert_item.set_sensitive(False)

        runahead_item = gtk.MenuItem( '_Change Runahead Limit' )
        start_menu.append( runahead_item )
        runahead_item.connect( 'activate', self.change_runahead_popup )
        if self.readonly:
            runahead_item.set_sensitive(False)

        block_item = gtk.MenuItem( '_Block (ignore intervention requests)' )
        start_menu.append( block_item )
        block_item.connect( 'activate', self.block_suite )
        if self.readonly or not self.use_block:
            block_item.set_sensitive(False)

        unblock_item = gtk.MenuItem( 'U_nblock (comply with intervention requests)' )
        start_menu.append( unblock_item )
        unblock_item.connect( 'activate', self.unblock_suite )
        if self.readonly or not self.use_block:
            unblock_item.set_sensitive(False)

        help_menu = gtk.Menu()
        help_menu_root = gtk.MenuItem( '_Help' )
        help_menu_root.set_submenu( help_menu )

        self.userguide_item = gtk.MenuItem( '_Quick Guide' )
        help_menu.append( self.userguide_item )
 
        about_item = gtk.MenuItem( '_About' )
        help_menu.append( about_item )
        about_item.connect( 'activate', self.about )
      
        self.menu_bar = gtk.MenuBar()
        self.menu_bar.append( file_menu_root )
        self.menu_bar.append( view_menu_root )
        self.menu_bar.append( start_menu_root )
        self.menu_bar.append( help_menu_root )

    def create_info_bar( self ):
        self.label_status = gtk.Label( "status..." )
        self.label_mode = gtk.Label( "mode..." )
        self.label_time = gtk.Label( "time..." )
        self.label_block = gtk.Label( "block..." )
        self.label_suitename = gtk.Label( self.suite )

        hbox = gtk.HBox()

        eb = gtk.EventBox()
        eb.add( self.label_suitename )
        #eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#ed9638' ) )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#88bbee' ) )
        hbox.pack_start( eb, True )

        eb = gtk.EventBox()
        eb.add( self.label_mode )
        #eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#dbd40a' ) )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#bbddff' ) )
        hbox.pack_start( eb, True )

        eb = gtk.EventBox()
        eb.add( self.label_status )
        #eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#a7c339' ) )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#88bbee' ) )
        hbox.pack_start( eb, True )

        eb = gtk.EventBox()
        eb.add( self.label_time )
        #eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#6ab7b4' ) ) 
        #eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#fa87a4' ) ) 
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#bbddff' ) ) 
        hbox.pack_start( eb, True )

        eb = gtk.EventBox()
        eb.add( self.label_block )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#dddddd' ) ) 
        hbox.pack_start( eb, True )

        return hbox

    #def check_connection( self ):
    #    # called on a timeout in the gtk main loop, tell the log viewer
    #    # to reload if the connection has been lost and re-established,
    #    # which probably means the cylc suite was shutdown and
    #    # restarted.
    #    try:
    #        cylc_pyro_client.ping( self.host, self.port )
    #    except Pyro.errors.ProtocolError:
    #        print "NO CONNECTION"
    #        self.connection_lost = True
    #    else:
    #        print "CONNECTED"
    #        if self.connection_lost:
    #            #print "------>INITIAL RECON"
    #            self.connection_lost = False
    #    # always return True so that we keep getting called
    #    return True

    def get_pyro( self, object ):
        return cylc_pyro_client.client( self.suite, self.owner, self.host, self.port ).get_proxy( object )
 
    def view_log( self, w ):
        logdir = os.path.join( self.suiterc['top level logging directory'], self.suite )
        foo = cylc_logviewer( 'log', logdir, self.suiterc.get_full_task_name_list() )
        self.quitters.append(foo)
