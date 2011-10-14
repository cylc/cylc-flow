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
from cylc.port_scan import SuiteIdentificationError
from cylc import cylc_pyro_client
from cylc.cycle_time import ct, CycleTimeError
from cylc.taskid import id, TaskIDError
from option_group import controlled_option_group
from cylc.config import config
from color_rotator import rotator
from cylc_logviewer import cylc_logviewer
from textload import textload
from datetime import datetime
from gcapture import gcapture_tmpfile

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

        self.suiterc = config( self.suite, os.path.join( self.suite_dir, 'suite.rc' ) )

        self.sim_only=False
        if self.suiterc['cylc']['simulation mode only']:
            self.sim_only=True
 
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
        except SuiteIdentificationError, x:
            warning_dialog( x.__str__() ).warn()
            return
        result = god.resume()
        if result.success:
            info_dialog( result.reason ).inform()
        else:
            warning_dialog( result.reason ).warn()

    def stopsuite( self, bt, window,
            stop_rb, stopat_rb, stopct_rb, stoptt_rb, stopnow_rb,
            stoptag_entry, stopclock_entry, stoptask_entry ):
        stop = False
        stopat = False
        stopnow = False
        stopclock = False
        stoptask = False

        if stop_rb.get_active():
            stop = True

        elif stopat_rb.get_active():
            stopat = True
            stoptag = stoptag_entry.get_text()
            if stoptag == '':
                warning_dialog( "ERROR: No stop TAG entered" ).warn()
                return
            if re.match( '^a:', stoptag ):
                # async
                stoptag = stoptag[2:]
            else:
                try:
                    ct(stoptag)
                except CycleTimeError,x:
                    warning_dialog( str(x) ).warn()
                    return

        elif stopnow_rb.get_active():
            stopnow = True

        elif stopct_rb.get_active():
            stopclock = True
            stopclock_time = stopclock_entry.get_text()
            if stopclock_time == '':
                warning_dialog( "ERROR: No stop time entered" ).warn()
                return
            try:
                # YYYY/MM/DD-HH:mm
                date, time = stopclock_time.split('-')
                yyyy, mm, dd = date.split('/')
                HH,MM = time.split(':')
                stop_dtime = datetime( int(yyyy), int(mm), int(dd), int(HH), int(MM) )
            except:
                warning_dialog( "ERROR: Bad datetime (YYYY/MM/DD-HH:mm): " + stopclock_time ).warn()
                return

        elif stoptt_rb.get_active():
            stoptask = True
            stoptask_id = stoptask_entry.get_text()
            if stoptask_id == '':
                warning_dialog( "ERROR: No stop task ID entered" ).warn()
                return
            try:
                tid = id( stoptask_id )
            except TaskIDError,x:
                warning_dialog( "ERROR: Bad task ID (TASK%YYYYMMDDHH): " + stoptask_id ).warn()
                return
            else:
                stoptask_id = tid.id
        else:
            # SHOULD NOT BE REACHED
            warning_dialog( "ERROR: Bug in GUI?" ).warn()
            return

        window.destroy()

        try:
            god = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port ).get_proxy( 'remote' )
            if stop:
                result = god.shutdown()
            elif stopat:
                result = god.set_stop( stoptag, 'stop after TAG' )
            elif stopnow:
                result = god.shutdown_now()
            elif stopclock:
                result = god.set_stop( stopclock_time, 'stop after clock time' )
            elif stoptask:
                result = god.set_stop( stoptask_id, 'stop after task' )
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
            optgroups, hold_cb, holdtime_entry ):

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

        ste = stoptime_entry.get_text()
        if ste:
            try:
                ct(ste)
            except CycleTimeError,x:
                warning_dialog( str(x) ).warn()
                return
            command += ' --until=' + stoptime_entry.get_text()

        ctime = entry_ctime.get_text()
        if method != 'restart':
            if ctime != '':
                try:
                    ct(ctime)
                except CycleTimeError,x:
                    warning_dialog( str(x) ).warn()
                    return

        hetxt = holdtime_entry.get_text()
        if hold_cb.get_active():
            command += ' --hold'
        elif hetxt != '':
            command += ' --hold-after=' + hetxt

        for group in optgroups:
            command += group.get_options()
        window.destroy()

        command += ' ' + self.suite + ' ' + ctime
        if restart_rb.get_active():
            if statedump_entry.get_text():
                command += ' ' + statedump_entry.get_text()

        #info_dialog( "I'm about to run this command: \n" + command ).inform()

        try:
            subprocess.Popen( [command], shell=True )
        except OSError, e:
            warning_dialog( 'Error: failed to start ' + self.suite ).warn()
            success = False


    def unblock_suite( self, bt ):
        try:
            god = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port ).get_proxy( 'remote' )
            god.unblock()
        except SuiteIdentificationError, x:
            warning_dialog( 'ERROR: ' + str(x) ).warn()

    def block_suite( self, bt ):
        try:
            god = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port ).get_proxy( 'remote' )
            god.block()
        except SuiteIdentificationError, x:
            warning_dialog( 'ERROR: ' + str(x) ).warn()

    def about( self, bt ):
        about = gtk.AboutDialog()
        if gtk.gtk_version[0] ==2:
            if gtk.gtk_version[1] >= 12:
                # set_program_name() was added in PyGTK 2.12
                about.set_program_name( "cylc" )
        cylc_version = 'THIS IS NOT A VERSIONED RELEASE'
        about.set_version( cylc_version )
        about.set_copyright( "(c) Hilary Oliver, NIWA, 2008-2011" )
        about.set_comments( 
"""
The cylc forecast suite metascheduler.
""" )
        #about.set_website( "http://www.niwa.co.nz" )
        about.set_logo( gtk.gdk.pixbuf_new_from_file( self.imagedir + "/logo.png" ))
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

    def jobscript( self, w, suite, task ):
        command = "cylc jobscript " + suite + " " + task
        foo = gcapture_tmpfile( command, self.tmpdir, 800, 800 )
        self.gcapture_windows.append(foo)
        foo.run()

    def get_right_click_menu_items( self, task_id ):
        name, ctime = task_id.split('%')

        items = []

        js_item = gtk.MenuItem( 'View The Job Script' )
        items.append( js_item )
        js_item.connect( 'activate', self.view_task_info, task_id, True )

        js2_item = gtk.MenuItem( 'View New Job Script' )
        items.append( js2_item )
        js2_item.connect( 'activate', self.jobscript, self.suite, task_id )

        info_item = gtk.MenuItem( 'View Task Output' )
        items.append( info_item )
        info_item.connect( 'activate', self.view_task_info, task_id, False )

        info_item = gtk.MenuItem( 'View Task State' )
        items.append( info_item )
        info_item.connect( 'activate', self.popup_requisites, task_id )

        items.append( gtk.SeparatorMenuItem() )

        reset_ready_item = gtk.MenuItem( 'Trigger' )
        items.append( reset_ready_item )
        reset_ready_item.connect( 'activate', self.reset_task_state, task_id, 'ready' )
        if self.readonly:
            reset_ready_item.set_sensitive(False)

        reset_waiting_item = gtk.MenuItem( 'Reset to "waiting"' )
        items.append( reset_waiting_item )
        reset_waiting_item.connect( 'activate', self.reset_task_state, task_id, 'waiting' )
        if self.readonly:
            reset_waiting_item.set_sensitive(False)

        reset_succeeded_item = gtk.MenuItem( 'Reset to "succeeded"' )
        items.append( reset_succeeded_item )
        reset_succeeded_item.connect( 'activate', self.reset_task_state, task_id, 'succeeded' )
        if self.readonly:
            reset_succeeded_item.set_sensitive(False)

        reset_failed_item = gtk.MenuItem( 'Reset to "failed"' )
        items.append( reset_failed_item )
        reset_failed_item.connect( 'activate', self.reset_task_state, task_id, 'failed' )
        if self.readonly:
            reset_failed_item.set_sensitive(False)

        items.append( gtk.SeparatorMenuItem() )

        stoptask_item = gtk.MenuItem( 'Hold' )
        items.append( stoptask_item )
        stoptask_item.connect( 'activate', self.hold_task, task_id, True )
        if self.readonly:
            stoptask_item.set_sensitive(False)

        unstoptask_item = gtk.MenuItem( 'Release' )
        items.append( unstoptask_item )
        unstoptask_item.connect( 'activate', self.hold_task, task_id, False )
        if self.readonly:
            unstoptask_item.set_sensitive(False)

        items.append( gtk.SeparatorMenuItem() )
    
        kill_item = gtk.MenuItem( 'Remove after spawning' )
        items.append( kill_item )
        kill_item.connect( 'activate', self.kill_task, task_id )
        if self.readonly:
            kill_item.set_sensitive(False)

        kill_nospawn_item = gtk.MenuItem( 'Remove without spawning' )
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
    
        addprereq_item = gtk.MenuItem( 'Add A Prerequisite' )
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

        label = gtk.Label( 'SUITE: ' + self.suite )
        vbox.pack_start( label, True )
 
        entry = gtk.Entry()
        #entry.connect( "activate", self.change_runahead_entry, window, task_id )

        hbox = gtk.HBox()
        label = gtk.Label( 'HOURS' )
        hbox.pack_start( label, True )
        hbox.pack_start (entry, True)
        vbox.pack_start( hbox )

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        start_button = gtk.Button( "_Change" )
        start_button.connect("clicked", self.change_runahead, entry, window )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", self.command_help, "control", "maxrunahead" )

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
        try:
            proxy = cylc_pyro_client.client( self.suite, self.owner,
                self.host, self.port ).get_proxy( 'remote' )
        except SuiteIdentificationError, x:
            warning_dialog( x.__str__() ).warn()
            return
        result = proxy.set_runahead( limit )
        if result.success:
            info_dialog( result.reason ).inform()
        else:
            warning_dialog( result.reason ).warn()

    def add_prerequisite_popup( self, b, task_id ):
        window = gtk.Window()
        window.modify_bg( gtk.STATE_NORMAL, 
                gtk.gdk.color_parse( self.log_colors.get_color()))
        window.set_border_width(5)
        window.set_title( "Add A Prequisite" )
        #window.set_size_request(800, 300)

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )

        vbox = gtk.VBox()

        label = gtk.Label( 'SUITE: ' + self.suite )
        vbox.pack_start( label, True )

        label = gtk.Label( 'TASK: ' + task_id )
        vbox.pack_start( label, True )
         
        label = gtk.Label( 'DEP (NAME%TAG or message)' )

        entry = gtk.Entry()

        hbox = gtk.HBox()
        hbox.pack_start( label, True )
        hbox.pack_start (entry, True)
        vbox.pack_start( hbox )

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        start_button = gtk.Button( "_Add" )
        start_button.connect("clicked", self.add_prerequisite, entry, window, task_id )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", self.command_help, "control", "depend" )

        hbox = gtk.HBox()
        hbox.pack_start( start_button, True)
        hbox.pack_start( help_button, True )
        hbox.pack_start( cancel_button, True )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def add_prerequisite( self, w, entry, window, task_id ):
        dep = entry.get_text()
        m = re.match( '^(\w+)%(\w+)$', dep )
        if m:
            #name, ctime = m.groups()
            msg = dep + ' succeeded'
        else:
            msg = dep

        try:
            (name, cycle ) = task_id.split('%')
        except ValueError:
            warning_dialog( "ERROR, Task or Group ID must be NAME%YYYYMMDDHH").warn()
            return
        try:
            ct(cycle)
        except CycleTimeError,x:
            warning_dialog( str(x) ).warn()
            return

        window.destroy()
        try:
            proxy = cylc_pyro_client.client( self.suite, self.owner,
                self.host, self.port ).get_proxy( 'remote' )
        except SuiteIdentificationError, x:
            warning_dialog( x.__str__() ).warn()
            return
        result = proxy.add_prerequisite( task_id, msg )
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

    def hold_task( self, b, task_id, stop=True ):
        if stop:
            msg = "hold " + task_id + "?"
        else:
            msg = "release " + task_id + "?"

        prompt = gtk.MessageDialog( None, gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_OK_CANCEL, msg )

        prompt.add_button( gtk.STOCK_HELP, gtk.RESPONSE_HELP )
        response = prompt.run()

        while response == gtk.RESPONSE_HELP:
            if stop:
                self.command_help( "control", "hold" )
            else:
                self.command_help( "control", "release" )

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
        if stop:
            result = proxy.hold_task( task_id )
        else:
            result = proxy.release_task( task_id )

        if result.success:
            info_dialog( result.reason ).inform()
        else:
            warning_dialog( result.reason ).warn()

    def reset_task_state( self, b, task_id, state ):
        msg = "reset " + task_id + " to " + state +"?"
        prompt = gtk.MessageDialog( None, gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_OK_CANCEL, msg )

        prompt.add_button( gtk.STOCK_HELP, gtk.RESPONSE_HELP )
        response = prompt.run()

        while response == gtk.RESPONSE_HELP:
            self.command_help( "control", "reset" )
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

        prompt.add_button( gtk.STOCK_HELP, gtk.RESPONSE_HELP )
        response = prompt.run()

        while response == gtk.RESPONSE_HELP:
            self.command_help( "control", "remove" )
            response = prompt.run()

        prompt.destroy()
        if response != gtk.RESPONSE_OK:
            return
        try:
            proxy = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port).get_proxy( 'remote' )
        except SuiteIdentificationError, x:
            warning_dialog(str(x)).warn()
            return
        result = proxy.spawn_and_die( task_id )
        if result.success:
            info_dialog( result.reason ).inform()
        else:
            warning_dialog( result.reason ).warn()
 
    def kill_task_nospawn( self, b, task_id ):
        msg = "remove " + task_id + " (without spawning)?"
        prompt = gtk.MessageDialog( None, gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_OK_CANCEL, msg )

        prompt.add_button( gtk.STOCK_HELP, gtk.RESPONSE_HELP )
        response = prompt.run()

        while response == gtk.RESPONSE_HELP:
            self.command_help( "control", "remove" )
            response = prompt.run()

        prompt.destroy()
        if response != gtk.RESPONSE_OK:
            return
        try:
            proxy = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port).get_proxy( 'remote' )
        except SuiteIdentificationError, x:
            warning_dialog(str(x)).warn()
            return
        result = proxy.die( task_id )
        if result.success:
            info_dialog( result.reason ).inform()
        else:
            warning_dialog( result.reason ).warn()

    def purge_cycle_entry( self, e, w, task_id ):
        stop = e.get_text()
        w.destroy()
        try:
            proxy = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port ).get_proxy( 'remote' )
        except SuiteIdentificationError, x:
            warning_dialog(str(x)).warn()
            return
        result = proxy.purge( task_id, stop )
        if result.success:
            info_dialog( result.reason ).inform()
        else:
            warning_dialog( result.reason ).warn()

    def purge_cycle_button( self, b, e, w, task_id ):
        stop = e.get_text()
        w.destroy()
        try:
            proxy = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port ).get_proxy( 'remote' )
        except SuiteIdentificationError, x:
            warning_dialog(str(x)).warn()
            return
        result = proxy.purge( task_id, stop )
        if result.success:
            info_dialog( result.reason ).inform()
        else:
            warning_dialog( result.reason ).warn()

    def stopsuite_popup( self, b ):
        window = gtk.Window()
        window.modify_bg( gtk.STATE_NORMAL, 
                gtk.gdk.color_parse( self.log_colors.get_color()))
        window.set_border_width(5)
        window.set_title( "Stop Suite")

        vbox = gtk.VBox()

        flabel = gtk.Label( "SUITE: " + self.suite )
        vbox.pack_start (flabel, True)

        flabel = gtk.Label( "Stop the suite when?" )
        vbox.pack_start (flabel, True)


        stop_rb = gtk.RadioButton( None, "After running tasks have finished" )
        vbox.pack_start (stop_rb, True)
        stopnow_rb = gtk.RadioButton( stop_rb, "NOW (beware of orphaned tasks!)" )
        vbox.pack_start (stopnow_rb, True)
        stopat_rb = gtk.RadioButton( stop_rb, "After all tasks have passed a given TAG" )
        vbox.pack_start (stopat_rb, True)

        st_box = gtk.HBox()
        label = gtk.Label( "STOP (cycle or 'a:INT')" )
        st_box.pack_start( label, True )
        stoptime_entry = gtk.Entry()
        stoptime_entry.set_max_length(10)
        stoptime_entry.set_sensitive(False)
        label.set_sensitive(False)
        st_box.pack_start (stoptime_entry, True)
        vbox.pack_start( st_box )

        stopct_rb = gtk.RadioButton( stop_rb, "After a given wall clock time" )
        vbox.pack_start (stopct_rb, True)

        sc_box = gtk.HBox()
        label = gtk.Label( 'STOP (YYYY/MM/DD-HH:mm)' )
        sc_box.pack_start( label, True )
        stopclock_entry = gtk.Entry()
        stopclock_entry.set_max_length(16)
        stopclock_entry.set_sensitive(False)
        label.set_sensitive(False)
        sc_box.pack_start (stopclock_entry, True)
        vbox.pack_start( sc_box )

        stoptt_rb = gtk.RadioButton( stop_rb, "After a given task finishes" )
        vbox.pack_start (stoptt_rb, True)
  
        stop_rb.set_active(True)

        tt_box = gtk.HBox()
        label = gtk.Label( 'STOP (task NAME%TAG)' )
        tt_box.pack_start( label, True )
        stoptask_entry = gtk.Entry()
        stoptask_entry.set_sensitive(False)
        label.set_sensitive(False)
        tt_box.pack_start (stoptask_entry, True)
        vbox.pack_start( tt_box )

        stop_rb.connect( "toggled", self.stop_method, "stop", st_box, sc_box, tt_box )
        stopat_rb.connect( "toggled", self.stop_method, "stopat", st_box, sc_box, tt_box )
        stopnow_rb.connect( "toggled", self.stop_method, "stopnow", st_box, sc_box, tt_box )
        stopct_rb.connect( "toggled", self.stop_method, "stopclock", st_box, sc_box, tt_box )
        stoptt_rb.connect( "toggled", self.stop_method, "stoptask", st_box, sc_box, tt_box )

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        stop_button = gtk.Button( "_Stop" )
        stop_button.connect("clicked", self.stopsuite, window,
                stop_rb, stopat_rb, stopct_rb, stoptt_rb, stopnow_rb,
                stoptime_entry, stopclock_entry, stoptask_entry )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", self.command_help, "control", "stop" )

        hbox = gtk.HBox()
        hbox.pack_start( stop_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def stop_method( self, b, meth, st_box, sc_box, tt_box  ):
        for ch in st_box.get_children() + sc_box.get_children() + tt_box.get_children():
            ch.set_sensitive( False )
        if meth == 'stopat':
            for ch in st_box.get_children():
                ch.set_sensitive( True )
        elif meth == 'stopclock':
            for ch in sc_box.get_children():
                ch.set_sensitive( True )
        elif meth == 'stoptask':
            for ch in tt_box.get_children():
                ch.set_sensitive( True )

    def hold_cb_toggled( self, b, box ):
        if b.get_active():
            box.set_sensitive(False)
        else:
            box.set_sensitive(True)

    def startup_method( self, b, meth, ic_box, is_box, no_reset_cb ):
        if meth in ['cold', 'warm', 'raw']:
            for ch in ic_box.get_children():
                ch.set_sensitive( True )
            for ch in is_box.get_children():
                ch.set_sensitive( False )
            no_reset_cb.set_sensitive(False)
        else:
            # restart
            for ch in ic_box.get_children():
                ch.set_sensitive( False )
            for ch in is_box.get_children():
                ch.set_sensitive( True )
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

        ic_box = gtk.HBox()
        label = gtk.Label( 'START (cycle)' )
        ic_box.pack_start( label, True )
        ctime_entry = gtk.Entry()
        ctime_entry.set_max_length(10)
        if self.suiterc['scheduling']['initial cycle time']:
            ctime_entry.set_text( str(self.suiterc['scheduling']['initial cycle time']) )
        ic_box.pack_start (ctime_entry, True)
        vbox.pack_start( ic_box )

        fc_box = gtk.HBox()
        label = gtk.Label( 'STOP (cycle, optional)' )
        fc_box.pack_start( label, True )
        stoptime_entry = gtk.Entry()
        stoptime_entry.set_max_length(10)
        if self.suiterc['scheduling']['final cycle time']:
            stoptime_entry.set_text( str(self.suiterc['scheduling']['final cycle time']) )
        fc_box.pack_start (stoptime_entry, True)
        vbox.pack_start( fc_box )

        is_box = gtk.HBox()
        label = gtk.Label( 'FILE (state dump, optional)' )
        is_box.pack_start( label, True )
        statedump_entry = gtk.Entry()
        statedump_entry.set_text( 'state' )
        statedump_entry.set_sensitive( False )
        label.set_sensitive( False )
        is_box.pack_start (statedump_entry, True)
        vbox.pack_start(is_box)

        no_reset_cb = gtk.CheckButton( "Don't reset failed tasks to the 'ready' state" )
        no_reset_cb.set_active(False)
        no_reset_cb.set_sensitive(False)
        vbox.pack_start (no_reset_cb, True)

        coldstart_rb.connect( "toggled", self.startup_method, "cold", ic_box, is_box, no_reset_cb )
        warmstart_rb.connect( "toggled", self.startup_method, "warm", ic_box, is_box, no_reset_cb )
        rawstart_rb.connect ( "toggled", self.startup_method, "raw",  ic_box, is_box, no_reset_cb )
        restart_rb.connect(   "toggled", self.startup_method, "re",   ic_box, is_box, no_reset_cb )

        dmode_group = controlled_option_group( "Simulation Mode", option="--simulation-mode", reverse=self.sim_only )
        dmode_group.add_entry('Fail A Task (NAME%YYYYMMDDHH)', '--fail=')
        dmode_group.pack( vbox )
        
        hold_cb = gtk.CheckButton( "Hold on start-up" )
  
        hold_box = gtk.HBox()
        label = gtk.Label( 'Hold after (cycle)' )
        hold_box.pack_start( label, True )
        holdtime_entry = gtk.Entry()
        holdtime_entry.set_max_length(10)
        hold_box.pack_start (holdtime_entry, True)

        vbox.pack_start( hold_cb )
        vbox.pack_start( hold_box )

        hold_cb.connect( "toggled", self.hold_cb_toggled, hold_box )

        debug_group = controlled_option_group( "Debug", "--debug" )
        debug_group.pack( vbox )

        optgroups = [ dmode_group, debug_group ]

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        start_button = gtk.Button( "_Start" )
        start_button.connect("clicked", self.startsuite, window,
                coldstart_rb, warmstart_rb, rawstart_rb, restart_rb,
                ctime_entry, stoptime_entry, no_reset_cb,
                statedump_entry, optgroups, hold_cb, holdtime_entry )

        help_run_button = gtk.Button( "_Help Run" )
        help_run_button.connect("clicked", self.command_help, "control", "run" )

        help_restart_button = gtk.Button( "_Help Restart" )
        help_restart_button.connect("clicked", self.command_help, "control", "restart" )

        hbox = gtk.HBox()
        hbox.pack_start( start_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_run_button, False )
        hbox.pack_end( help_restart_button, False )
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

        start_button = gtk.Button( "_Purge" )
        start_button.connect("clicked", self.purge_cycle_button, entry, window, task_id )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", self.command_help, "control", "purge" )

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        hbox = gtk.HBox()
        hbox.pack_start( start_button, True)
        hbox.pack_start( help_button, True)
        hbox.pack_start( cancel_button, True )
        vbox.pack_start( hbox )

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
        window.set_title( "Insert Task" )
        #window.set_size_request(800, 300)

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )

        vbox = gtk.VBox()

        label = gtk.Label( 'SUITE: ' + self.suite )
        vbox.pack_start( label, True )
 
        hbox = gtk.HBox()
        label = gtk.Label( 'TASK (NAME%TAG)' )
        hbox.pack_start( label, True )
        entry_taskorgroup = gtk.Entry()
        hbox.pack_start (entry_taskorgroup, True)
        vbox.pack_start(hbox)

        hbox = gtk.HBox()
        label = gtk.Label( 'STOP (optional final tag, temporary tasks)' )
        hbox.pack_start( label, True )
        entry_stoptag = gtk.Entry()
        entry_stoptag.set_max_length(10)
        hbox.pack_start (entry_stoptag, True)
        vbox.pack_start(hbox)
 
        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", self.command_help, "control", "insert" )

        hbox = gtk.HBox()
        insert_button = gtk.Button( "_Insert" )
        insert_button.connect("clicked", self.insert_task, window, entry_taskorgroup, entry_stoptag )
        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )
        hbox.pack_start(insert_button, False)
        hbox.pack_end(cancel_button, False)
        hbox.pack_end(help_button, False)
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def insert_task( self, w, window, entry_taskorgroup, entry_stoptag ):
        torg = entry_taskorgroup.get_text()
        if torg == '':
            warning_dialog( "Enter task or group ID" ).warn()
            return
        else:
            try:
                tid = id( torg )
            except TaskIDError,x:
                warning_dialog( str(x) ).warn()
                return
            else:
                torg= tid.id

        stoptag = entry_stoptag.get_text()
        if stoptag != '':
            try:
                ct(stoptag)
            except CycleTimeError,x:
                warning_dialog( str(x) ).warn()
                return
        window.destroy()
        if stoptag == '':
            stop = None
        else:
            stop = stoptag
        try:
            proxy = cylc_pyro_client.client( self.suite, self.owner, self.host, self.port ).get_proxy( 'remote' )
        except SuiteIdentificationError, x:
            warning_dialog( x.__str__() ).warn()
            return
        result = proxy.insert( torg, stop )
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
        # TO DO: jsonly is dirty hack to separate the task Job script from
        # task log files; we should do this properly by storing them
        # separately in the task proxy, or at least separating them in
        # the suite state summary.
        window = gtk.Window()
        window.modify_bg( gtk.STATE_NORMAL, 
                gtk.gdk.color_parse( self.log_colors.get_color()))
        window.set_border_width(5)
        logs = []
        jsfound = False
        for f in logfiles:
            if f.endswith('.err') or f.endswith('.out'):
                logs.append(f)
            else:
                jsfound = True
                js = f

        window.set_size_request(800, 300)
        if jsonly:
            window.set_title( task_id + ": Task Job Submission Script" )
            if jsfound:
                lv = textload( task_id, js )
            else:
                # This should not happen anymore!
                pass

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

        log_item = gtk.MenuItem( 'View _Suite Log' )
        self.view_menu.append( log_item )
        log_item.connect( 'activate', self.view_log )

        nudge_item = gtk.MenuItem( "_Nudge Suite (update times)" )
        self.view_menu.append( nudge_item )
        nudge_item.connect( 'activate', self.nudge_suite  )

        start_menu = gtk.Menu()
        start_menu_root = gtk.MenuItem( '_Control' )
        start_menu_root.set_submenu( start_menu )

        start_item = gtk.MenuItem( '_Run Suite ... ' )
        start_menu.append( start_item )
        start_item.connect( 'activate', self.startsuite_popup )
        if self.readonly:
            start_item.set_sensitive(False)

        stop_item = gtk.MenuItem( '_Stop Suite ... ' )
        start_menu.append( stop_item )
        stop_item.connect( 'activate', self.stopsuite_popup )
        if self.readonly:
            stop_item.set_sensitive(False)

        pause_item = gtk.MenuItem( '_Hold Suite (pause)' )
        start_menu.append( pause_item )
        pause_item.connect( 'activate', self.pause_suite )
        if self.readonly:
            pause_item.set_sensitive(False)

        resume_item = gtk.MenuItem( '_Release Suite (unpause)' )
        start_menu.append( resume_item )
        resume_item.connect( 'activate', self.resume_suite )
        if self.readonly:
            resume_item.set_sensitive(False)

        insert_item = gtk.MenuItem( '_Insert Task(s) ...' )
        start_menu.append( insert_item )
        insert_item.connect( 'activate', self.insert_task_popup )
        if self.readonly:
            insert_item.set_sensitive(False)

        block_item = gtk.MenuItem( '_Block Access' )
        start_menu.append( block_item )
        block_item.connect( 'activate', self.block_suite )
        if self.readonly:
            block_item.set_sensitive(False)

        unblock_item = gtk.MenuItem( 'U_nblock Access' )
        start_menu.append( unblock_item )
        unblock_item.connect( 'activate', self.unblock_suite )
        if self.readonly:
            unblock_item.set_sensitive(False)

        runahead_item = gtk.MenuItem( '_Change Runahead Limit ...' )
        start_menu.append( runahead_item )
        runahead_item.connect( 'activate', self.change_runahead_popup )
        if self.readonly:
            runahead_item.set_sensitive(False)

        help_menu = gtk.Menu()
        help_menu_root = gtk.MenuItem( '_Help' )
        help_menu_root.set_submenu( help_menu )

        self.userguide_item = gtk.MenuItem( '_GUI Quick Guide' )
        help_menu.append( self.userguide_item )

        chelp_menu = gtk.MenuItem( 'Control Commands' )
        help_menu.append( chelp_menu )
        self.construct_command_menu( chelp_menu )

        cug_pdf_item = gtk.MenuItem( 'Cylc User Guide (_PDF)' )
        help_menu.append( cug_pdf_item )
        cug_pdf_item.connect( 'activate', self.launch_cug, True )
  
        cug_html_item = gtk.MenuItem( 'Cylc User Guide (_HTML)' )
        help_menu.append( cug_html_item )
        cug_html_item.connect( 'activate', self.launch_cug, False )

        self.todo_item = gtk.MenuItem( '_To Do' )
        help_menu.append( self.todo_item )
        self.todo_item.connect( 'activate', helpwindow.todo )
  
        about_item = gtk.MenuItem( '_About' )
        help_menu.append( about_item )
        about_item.connect( 'activate', self.about )
      
        self.menu_bar = gtk.MenuBar()
        self.menu_bar.append( file_menu_root )
        self.menu_bar.append( view_menu_root )
        self.menu_bar.append( start_menu_root )
        self.menu_bar.append( help_menu_root )

    def construct_command_menu( self, menu ):
        com_menu = gtk.Menu()
        menu.set_submenu( com_menu )
        cout = subprocess.Popen( ["cylc", "category=control" ], stdout=subprocess.PIPE ).communicate()[0]
        commands = cout.rstrip().split()
        for command in commands:
            if command == "gcylc":
                continue
            bar_item = gtk.MenuItem( command )
            com_menu.append( bar_item )
            bar_item.connect( 'activate', self.command_help, "control", command )

    def create_info_bar( self ):
        self.label_status = gtk.Label( "status..." )
        self.label_mode = gtk.Label( "mode..." )
        self.label_time = gtk.Label( "time..." )
        self.label_block = gtk.Label( "block..." )
        self.label_suitename = gtk.Label( self.suite )

        hbox = gtk.HBox()

        eb = gtk.EventBox()
        eb.add( self.label_suitename )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#8be' ) )
        hbox.pack_start( eb, True )

        eb = gtk.EventBox()
        eb.add( self.label_mode )
        #eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#fff' ) )
        hbox.pack_start( eb, True )

        eb = gtk.EventBox()
        eb.add( self.label_status )
        #eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#fff' ) )
        hbox.pack_start( eb, True )

        eb = gtk.EventBox()
        eb.add( self.label_time )
        #eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#fff' ) ) 
        hbox.pack_start( eb, True )

        eb = gtk.EventBox()
        eb.add( self.label_block )
        #eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#fff' ) ) 
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
        logdir = os.path.join( self.suiterc['cylc']['logging']['directory'] )
        foo = cylc_logviewer( 'log', logdir, self.suiterc.get_full_task_name_list() )
        self.quitters.append(foo)

    def launch_cug( self, b, pdf ):
        fail = []
        cdir = None

        try:
            tmpdir = os.environ['TMPDIR']
        except KeyError:
            fail.append( "$TMPDIR is not defined" )
 
        try:
            cdir = os.environ['CYLC_DIR']
        except KeyError:
            fail.append( "$CYLC_DIR is not defined" )
 
        if pdf:
            try:
                appl = os.environ['PDF_READER']
            except KeyError:
                fail.append( "$PDF_READER is not defined" )
        else:
            try:
                appl = os.environ['HTML_READER']
            except KeyError:
                fail.append( "$HTML_READER is not defined" )

        if cdir:
            if pdf:
                file = os.path.join( cdir, 'doc', 'CylcUserGuide.pdf' )
            else:
                file = os.path.join( cdir, 'doc', 'cug-html.html' )

            if not os.path.isfile( file ):
                fail.append( "File not found: " + file )

        if len(fail) > 0:
            warning_dialog( '\n'.join( fail ) ).warn()
            return

        command = appl + " " + file 
        foo = gcapture_tmpfile( command, tmpdir )
        foo.run()
 
