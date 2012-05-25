#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
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

import gtk
#import pygtk
#pygtk.require('2.0')
import gobject
import pango
import os, re
import Pyro.errors
import subprocess
import helpwindow
from combo_logviewer import combo_logviewer
from warning_dialog import warning_dialog, info_dialog
from cylc.gui.SuiteControlGraph import ControlGraph
from cylc.gui.SuiteControlLED import ControlLED
from cylc.gui.SuiteControlTree import ControlTree
from cylc.port_scan import SuiteIdentificationError
from cylc import cylc_pyro_client
from cylc.cycle_time import ct, CycleTimeError
from cylc.TaskID import TaskID, TaskIDError
from cylc.version import cylc_version
from option_group import controlled_option_group
from cylc.config import config
from color_rotator import rotator
from cylc_logviewer import cylc_logviewer
from textload import textload
from datetime import datetime
from gcapture import gcapture_tmpfile


class InitData(object):
    """
Class to hold initialisation data.
    """

    def __init__( self, suite, owner, host, port, suite_dir, logging_dir, imagedir, cylc_tmpdir,
        readonly=False ):
        
        self.readonly = readonly
        self.logdir = logging_dir
        self.suite_dir = suite_dir
        self.suite = suite
        self.host = host
        self.port = port
        self.owner = owner
        self.imagedir = imagedir
        self.cylc_tmpdir = cylc_tmpdir


class InfoBar(gtk.HBox):
    """
Class to create an information bar.
    """

    def __init__( self, suite, status_changed_hook=lambda s: False ):
        super(InfoBar, self).__init__()

        self._status = "status..."
        self.notify_status_changed = status_changed_hook
        self.label_status = gtk.Label()
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip( self.label_status, "status" )

        self._mode = "mode..."
        self.label_mode = gtk.Label()
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip( self.label_mode, "mode" )

        self._time = "time..."
        self.label_time = gtk.Label()
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip( self.label_time, "last update time" )

        self._block = "access..."
        self.label_block = gtk.image_new_from_stock( gtk.STOCK_DIALOG_QUESTION,
                                                     gtk.ICON_SIZE_SMALL_TOOLBAR )


        eb = gtk.EventBox()
        eb.add( self.label_mode )
        #eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#fff' ) )
        self.pack_start( eb, True )

        eb = gtk.EventBox()
        eb.add( self.label_status )
        #eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#fff' ) )
        self.pack_start( eb, True )

        eb = gtk.EventBox()
        eb.add( self.label_time )
        #eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#fff' ) ) 
        self.pack_start( eb, True )

        eb = gtk.EventBox()
        eb.add( self.label_block )
        #eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#fff' ) ) 
        self.pack_end( eb, False )

    def set_block( self, block ):
        if block == self._block:
            return False
        self._block = block
        if "unblocked" in block:
            self.label_block.set_from_stock( gtk.STOCK_DIALOG_AUTHENTICATION,
                                             gtk.ICON_SIZE_SMALL_TOOLBAR )
        elif "blocked" in block:
            self.label_block.set_from_stock( gtk.STOCK_DIALOG_ERROR,
                                             gtk.ICON_SIZE_SMALL_TOOLBAR )
        elif "waiting" in block:
            self.label_block.set_from_stock( gtk.STOCK_DIALOG_QUESTION,
                                             gtk.ICON_SIZE_SMALL_TOOLBAR )
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip(self.label_block, self._block)

    def set_mode(self, mode):
        text = mode.replace( "mode:", "" ).strip()
        if text == self._mode:
            return False
        self._mode = text
        self.label_mode.set_text( self._mode )

    def set_status(self, status):
        text = status.replace( "status:", "" ).strip()
        if text == self._status:
            return False
        self._status = text
        self.label_status.set_text( self._status )
        if re.search( 'STOPPED', status ):
            self.label_status.get_parent().modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#ff1a45' ))
        elif re.search( 'STOP', status ):  # stopping
            self.label_status.get_parent().modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#ff8c2a' ))
        elif re.search( 'HELD', status ):
            self.label_status.get_parent().modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#ffde00' ))
        else:
            self.label_status.get_parent().modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#19ae0a' ))
        self.notify_status_changed( self._status )

    def set_time(self, time):
        text = time.replace("state last updated at:", "").strip() 
        if text == self._time:
            return False
        self._time = text
        self.label_time.set_text( self._time )


class ControlApp(object):
    """
Base class for suite control GUI functionality.
Derived classes must provide:
  self.get_control_widgets()
and associated methods for their control widgets.
    """

    DEFAULT_VIEW = "graph"
    VIEWS = {"graph": ControlGraph,
             "led": ControlLED,
             "tree": ControlTree}
    VIEW_ICON_PATHS = {"graph": "/icons/tab-graph.xpm",
                       "led": "/icons/tab-led.xpm",
                       "tree": "/icons/tab-tree.xpm"}
                       

    def __init__( self, suite, owner, host, port, suite_dir, logging_dir, imagedir, cylc_tmpdir,
        readonly=False ):
        gobject.threads_init()
        
        self.cfg = InitData( suite, owner, host, port, suite_dir, logging_dir, imagedir,
                             cylc_tmpdir, readonly )
        
        self.suiterc = config( self.cfg.suite, os.path.join( self.cfg.suite_dir, 'suite.rc' ) )

        self.sim_only=False
        if self.suiterc['cylc']['simulation mode only']:
            self.sim_only=True

        self.view_layout_horizontal = False

        self.connection_lost = False # (not used)
        self.quitters = []
        self.gcapture_windows = []

        self.log_colors = rotator()

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        if self.cfg.readonly:
            self.window.set_title("gcylc <" + self.cfg.suite + "> (READONLY)" )
        else:
            self.window.set_title("gcylc <" + self.cfg.suite + ">" )
        self.window.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( "#ddd" ))
        self.window.set_size_request(800, 500)
        self.window.connect("delete_event", self.delete_event)

        self.generate_main_menu()

        bigbox = gtk.VBox()
        bigbox.pack_start( self.menu_bar, False )

        self.generate_tool_bar()
        bigbox.pack_start( self.tool_bar, False )
        self.create_info_bar()

        self.views_parent = gtk.VBox()
        bigbox.pack_start( self.views_parent, True )
        self.setup_views()

        hbox = gtk.HBox()
        hbox.pack_start( self.info_bar, True )
        bigbox.pack_start( hbox, False )

        self.window.add( bigbox )
        self.window.show_all()

    def _sort_views( self, v1, v2 ):
        return ( v2 == self.DEFAULT_VIEW ) - ( v1 == self.DEFAULT_VIEW )

    def setup_views( self ):
        num_views = 2
        self.view_containers = []
        self.current_views = []
        self.current_view_menuitems = []
        self.current_view_toolitems = []
        for i in range(num_views):
            self.view_containers.append(gtk.HBox())
            self.current_views.append(None)
            self.current_view_menuitems.append([])
            self.current_view_toolitems.append([])
        self.views_parent.pack_start( self.view_containers[0],
                                      expand=True, fill=True )
        self.create_view()

    def change_view_layout( self, horizontal=False ):
        self.view_layout_horizontal = horizontal
        old_pane = self.view_containers[0].get_parent()
        if not isinstance(old_pane, gtk.Paned):
            return False
        old_pane.remove( self.view_containers[0] )
        old_pane.remove( self.view_containers[1] )
        top_parent = old_pane.get_parent()
        top_parent.remove( old_pane )
        if self.view_layout_horizontal:
           new_pane = gtk.HPaned()
           extent = top_parent.get_allocation().width
        else:
           new_pane = gtk.VPaned()
           extent = top_parent.get_allocation().height
        new_pane.pack1( self.view_containers[0] )
        new_pane.pack2( self.view_containers[1] )
        new_pane.set_position( extent / 2 )
        top_parent.pack_start( new_pane, expand=True, fill=True )
        self.window.show_all()

    def _cb_change_view0( self, item ):
        if isinstance( item, gtk.ToolItem ):
            # item.set_sensitive(False)
            # for alt_item in self.tool_view_buttons:
            #    if alt_item != item:
            #        alt_item.set_sensitive(True)
            pass
        elif isinstance( item, gtk.RadioMenuItem ):
            if not item.get_active():
                return False
        self.switch_view( item._viewname )
        return False

    def _cb_change_view1( self, widget ):
        if isinstance( widget, gtk.ComboBox ):
            viewname = widget.get_model().get_value(widget.get_active_iter(), 1)
        elif isinstance( widget, gtk.RadioMenuItem ):
            if not widget.get_active():
                return False
            viewname = widget._viewname
        self.switch_view( viewname, view_num=1 )
        return False

    def _cb_change_view_align( self, widget ):
        if isinstance( widget, gtk.CheckMenuItem ):
            self.change_view_layout( widget.get_active() )

    def switch_view( self, new_viewname, view_num=0 ):
        if new_viewname not in self.VIEWS:
            self.remove_view( view_num )
            return False
        old_position = -1
        if self.current_views[view_num] is not None:
            if self.current_views[view_num].name == new_viewname:
                return False
            if view_num == 1:
                old_position = self.views_parent.get_children()[0].get_position()
            self.remove_view( view_num )
        self.create_view( new_viewname, view_num, pane_position=old_position )
        return False

    def create_view( self, viewname=None, view_num=0, pane_position=-1 ):
        if viewname is None:
            viewname = self.DEFAULT_VIEW
        container = self.view_containers[view_num]
        self.current_views[view_num] = self.VIEWS[viewname]( 
                                                   self.cfg,
                                                   self.suiterc,
                                                   self.info_bar,
                                                   self.get_right_click_menu )
        view = self.current_views[view_num]
        view.name = viewname
        if view_num == 1:
            viewbox0 = self.view_containers[0]
            zero_parent = viewbox0.get_parent()
            zero_parent.remove( viewbox0 )
            if self.view_layout_horizontal:
                pane = gtk.HPaned()
                extent = zero_parent.get_allocation().width
            else:
                pane = gtk.VPaned()
                extent = zero_parent.get_allocation().height
            pane.pack1( viewbox0, resize=True, shrink=True )
            pane.pack2( container, resize=True, shrink=True )
            if pane_position == -1:
                pane_position =  extent / 2
            pane.set_position( pane_position )
            zero_parent.pack_start(pane, expand=True, fill=True)          
        container.pack_start( view.get_control_widgets(),
                              expand=True, fill=True )

        for view_menuitems in self.current_view_menuitems:
            for item in view_menuitems:
                self.view_menu.remove( item )
        new_menuitems = view.get_menuitems()
        if new_menuitems:
            new_menuitems.insert( 0, gtk.SeparatorMenuItem() )
        self.current_view_menuitems[view_num] = new_menuitems
        for menuitems in self.current_view_menuitems:
            for item in menuitems:
                self.view_menu.append( item )

        for view_toolitems in self.current_view_toolitems:
            for item in view_toolitems:
                self.tool_bar.remove( item )
        new_toolitems = view.get_toolitems()
        if new_toolitems:
            new_toolitems.insert( 0, gtk.SeparatorToolItem() ) 
        self.current_view_toolitems[view_num] = new_toolitems
        for toolitems in self.current_view_toolitems:
            for item in toolitems:
                self.tool_bar.insert( item, -1 )
        self.window.show_all()

    def remove_view( self, view_num ):
        self.current_views[view_num].stop()
        self.current_views[view_num] = None
        while len(self.current_view_menuitems[view_num]):
            self.view_menu.remove( self.current_view_menuitems[view_num].pop() )
        while len(self.current_view_toolitems[view_num]):
            self.tool_bar.remove( self.current_view_toolitems[view_num].pop() )    
        if view_num == 1:
            parent = self.view_containers[0].get_parent()
            parent.remove( self.view_containers[0] )
            parent.remove( self.view_containers[1] )
            top_parent = parent.get_parent()
            top_parent.remove( parent )
            top_parent.pack_start( self.view_containers[0],
                                   expand=True, fill=True )
        for child in self.view_containers[view_num].get_children():
            child.destroy()

    def quit_gcapture( self ):
        for gwindow in self.gcapture_windows:
            if not gwindow.quit_already:
                gwindow.quit( None, None )

    def delete_event(self, widget, event, data=None):
        self.quit_gcapture()
        for q in self.quitters:
            q.quit()
        for view in self.current_views:
            if view is not None:
                view.stop()
        gtk.main_quit()

    def click_exit( self, foo ):
        self.quit_gcapture()
        if self.current_view is not None:
            self.current_view.stop()
        gtk.main_quit()

    def pause_suite( self, bt ):
        try:
            god = cylc_pyro_client.client( self.cfg.suite, self.cfg.owner, self.cfg.host, self.cfg.port ).get_proxy( 'remote' )
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
            god = cylc_pyro_client.client( self.cfg.suite, self.cfg.owner, self.cfg.host, self.cfg.port ).get_proxy( 'remote' )
        except SuiteIdentificationError, x:
            warning_dialog( x.__str__() ).warn()
            return
        result = god.resume()
        if result.success:
            info_dialog( result.reason ).inform()
        else:
            warning_dialog( result.reason ).warn()

    def stopsuite_default( self, *args ):
        try:
            god = cylc_pyro_client.client( self.cfg.suite, self.cfg.owner, self.cfg.host, self.cfg.port ).get_proxy( 'remote' )
            result = god.shutdown()
        except SuiteIdentificationError, x:
            warning_dialog( x.__str__() ).warn()
        else:
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
                tid = TaskID( stoptask_id )
            except TaskIDError,x:
                warning_dialog( "ERROR: Bad task ID (TASK%YYYYMMDDHH): " + stoptask_id ).warn()
                return
            else:
                stoptask_id = tid.getstr()
        else:
            # SHOULD NOT BE REACHED
            warning_dialog( "ERROR: Bug in GUI?" ).warn()
            return

        window.destroy()

        try:
            god = cylc_pyro_client.client( self.cfg.suite, self.cfg.owner, self.cfg.host, self.cfg.port ).get_proxy( 'remote' )
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

        ctime = ''
        if method != 'restart':
            # start time
            ctime = entry_ctime.get_text()
            if ctime != '':
                try:
                    ct(ctime)
                except CycleTimeError,x:
                    warning_dialog( str(x) ).warn()
                    return

        ste = stoptime_entry.get_text()
        if ste:
            try:
                ct(ste)
            except CycleTimeError,x:
                warning_dialog( str(x) ).warn()
                return
            options += ' --until=' + ste
 
        hetxt = holdtime_entry.get_text()
        if hold_cb.get_active():
            options += ' --hold'
        elif hetxt != '':
            options += ' --hold-after=' + hetxt

        for group in optgroups:
            options += group.get_options()
        window.destroy()

        command += ' ' + options + ' ' + self.cfg.suite + ' ' + ctime
        if method == 'restart':
            if statedump_entry.get_text():
                command += ' ' + statedump_entry.get_text()

        # DEBUGGING:
        #info_dialog( "I'm about to run this command: \n" + command ).inform()
        #return

        try:
            subprocess.Popen( [command], shell=True )
        except OSError, e:
            warning_dialog( 'Error: failed to start ' + self.cfg.suite ).warn()
            success = False

    def unblock_suite( self, bt ):
        try:
            god = cylc_pyro_client.client( self.cfg.suite, self.cfg.owner, self.cfg.host, self.cfg.port ).get_proxy( 'remote' )
            god.unblock()
        except SuiteIdentificationError, x:
            warning_dialog( 'ERROR: ' + str(x) ).warn()

    def block_suite( self, bt ):
        try:
            god = cylc_pyro_client.client( self.cfg.suite, self.cfg.owner, self.cfg.host, self.cfg.port ).get_proxy( 'remote' )
            god.block()
        except SuiteIdentificationError, x:
            warning_dialog( 'ERROR: ' + str(x) ).warn()

    def about( self, bt ):
        about = gtk.AboutDialog()
        if gtk.gtk_version[0] ==2:
            if gtk.gtk_version[1] >= 12:
                # set_program_name() was added in PyGTK 2.12
                about.set_program_name( "cylc" )
        about.set_version( cylc_version )
        about.set_copyright( "Copyright (C) 2008-2012 Hilary Oliver, NIWA" )

        about.set_comments( 
"""
The cylc forecast suite metascheduler.
""" )
        #about.set_website( "http://www.niwa.co.nz" )
        about.set_logo( gtk.gdk.pixbuf_new_from_file( self.imagedir + "/logo.png" ))
        about.run()
        about.destroy()

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

        if states[ task_id ][ 'state' ] == 'waiting' or states[ task_id ][ 'state' ] == 'queued':
            view = False
            reasons.append( task_id + ' has not started running yet' )

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

    def get_right_click_menu( self, task_id, hide_task=False ):
        menu = gtk.Menu()
        if not hide_task:
            menu_root = gtk.MenuItem( task_id )
            menu_root.set_submenu( menu )

            title_item = gtk.MenuItem( 'Task: ' + task_id )
            title_item.set_sensitive(False)
            menu.append( title_item )
            menu.append( gtk.SeparatorMenuItem() )

        menu_items = self._get_right_click_menu_items( task_id )
        for item in menu_items:
            menu.append( item )

        menu.show_all()
        return menu


    def _get_right_click_menu_items( self, task_id ):
        name, ctime = task_id.split('%')

        items = []

        js_item = gtk.MenuItem( 'View The Job Script' )
        items.append( js_item )
        js_item.connect( 'activate', self.view_task_info, task_id, True )

        js2_item = gtk.MenuItem( 'View New Job Script' )
        items.append( js2_item )
        js2_item.connect( 'activate', self.jobscript, self.cfg.suite, task_id )

        info_item = gtk.MenuItem( 'View Task Output' )
        items.append( info_item )
        info_item.connect( 'activate', self.view_task_info, task_id, False )

        info_item = gtk.MenuItem( 'View Task State' )
        items.append( info_item )
        info_item.connect( 'activate', self.popup_requisites, task_id )

        items.append( gtk.SeparatorMenuItem() )

        trigger_now_item = gtk.MenuItem( 'Trigger' )
        items.append( trigger_now_item )
        trigger_now_item.connect( 'activate', self.trigger_task_now, task_id )
        if self.cfg.readonly:
            trigger_now_item.set_sensitive(False)

        reset_ready_item = gtk.MenuItem( 'Reset to "ready"' )
        items.append( reset_ready_item )
        reset_ready_item.connect( 'activate', self.reset_task_state, task_id, 'ready' )
        if self.cfg.readonly:
            reset_ready_item.set_sensitive(False)

        reset_waiting_item = gtk.MenuItem( 'Reset to "waiting"' )
        items.append( reset_waiting_item )
        reset_waiting_item.connect( 'activate', self.reset_task_state, task_id, 'waiting' )
        if self.cfg.readonly:
            reset_waiting_item.set_sensitive(False)

        reset_succeeded_item = gtk.MenuItem( 'Reset to "succeeded"' )
        items.append( reset_succeeded_item )
        reset_succeeded_item.connect( 'activate', self.reset_task_state, task_id, 'succeeded' )
        if self.cfg.readonly:
            reset_succeeded_item.set_sensitive(False)

        reset_failed_item = gtk.MenuItem( 'Reset to "failed"' )
        items.append( reset_failed_item )
        reset_failed_item.connect( 'activate', self.reset_task_state, task_id, 'failed' )
        if self.cfg.readonly:
            reset_failed_item.set_sensitive(False)

        spawn_item = gtk.MenuItem( 'Force spawn' )
        items.append( spawn_item )
        spawn_item.connect( 'activate', self.reset_task_state, task_id, 'spawn' )
        if self.cfg.readonly:
            spawn_item.set_sensitive(False)

        items.append( gtk.SeparatorMenuItem() )

        stoptask_item = gtk.MenuItem( 'Hold' )
        items.append( stoptask_item )
        stoptask_item.connect( 'activate', self.hold_task, task_id, True )
        if self.cfg.readonly:
            stoptask_item.set_sensitive(False)

        unstoptask_item = gtk.MenuItem( 'Release' )
        items.append( unstoptask_item )
        unstoptask_item.connect( 'activate', self.hold_task, task_id, False )
        if self.cfg.readonly:
            unstoptask_item.set_sensitive(False)

        items.append( gtk.SeparatorMenuItem() )
    
        kill_item = gtk.MenuItem( 'Remove after spawning' )
        items.append( kill_item )
        kill_item.connect( 'activate', self.kill_task, task_id )
        if self.cfg.readonly:
            kill_item.set_sensitive(False)

        kill_nospawn_item = gtk.MenuItem( 'Remove without spawning' )
        items.append( kill_nospawn_item )
        kill_nospawn_item.connect( 'activate', self.kill_task_nospawn, task_id )
        if self.cfg.readonly:
            kill_nospawn_item.set_sensitive(False)

        purge_item = gtk.MenuItem( 'Remove Tree (Recursive Purge)' )
        items.append( purge_item )
        purge_item.connect( 'activate', self.popup_purge, task_id )
        if self.cfg.readonly:
            purge_item.set_sensitive(False)

        items.append( gtk.SeparatorMenuItem() )
    
        addprereq_item = gtk.MenuItem( 'Add A Prerequisite' )
        items.append( addprereq_item )
        addprereq_item.connect( 'activate', self.add_prerequisite_popup, task_id )
        if self.cfg.readonly:
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

        label = gtk.Label( 'SUITE: ' + self.cfg.suite )
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
            proxy = cylc_pyro_client.client( self.cfg.suite, self.cfg.owner,
                self.cfg.host, self.cfg.port ).get_proxy( 'remote' )
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

        label = gtk.Label( 'SUITE: ' + self.cfg.suite )
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
            proxy = cylc_pyro_client.client( self.cfg.suite, self.cfg.owner,
                self.cfg.host, self.cfg.port ).get_proxy( 'remote' )
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
                    "Task proxy " + task_id + " not found in " + self.cfg.suite + \
                 ".\nTasks are removed once they are no longer needed.").warn()
                return

        window = gtk.Window()
        window.set_title( task_id + " State" )
        #window.modify_bg( gtk.STATE_NORMAL, 
        #       gtk.gdk.color_parse( self.log_colors.get_color()))
        window.set_size_request(600, 400)

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
        
        self.update_tb( tb, 'TASK ', [bold] )
        self.update_tb( tb, task_id, [bold, blue])
        self.update_tb( tb, ' in SUITE ', [bold] )
        self.update_tb( tb, self.cfg.suite + '\n\n', [bold, blue])

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

        self.update_tb( tb, '\nNOTE: ', [bold] )
        self.update_tb( tb, ''' for tasks that have triggered already, prerequisites are 
shown here in the state they were in at the time of triggering.''' )

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
            proxy = cylc_pyro_client.client( self.cfg.suite, self.cfg.owner, self.cfg.host, self.cfg.port).get_proxy( 'remote' )
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

    def trigger_task_now( self, b, task_id ):
        msg = "trigger " + task_id + " now?"
        prompt = gtk.MessageDialog( None, gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_OK_CANCEL, msg )

        prompt.add_button( gtk.STOCK_HELP, gtk.RESPONSE_HELP )
        response = prompt.run()

        while response == gtk.RESPONSE_HELP:
            self.command_help( "control", "trigger" )
            response = prompt.run()

        prompt.destroy()
        if response != gtk.RESPONSE_OK:
            return
        try:
            proxy = cylc_pyro_client.client( self.cfg.suite, self.cfg.owner, self.cfg.host, self.cfg.port).get_proxy( 'remote' )
        except SuiteIdentificationError, x:
            # the suite was probably shut down by another process
            warning_dialog( x.__str__() ).warn()
            return
        result = proxy.trigger_task( task_id )
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
            proxy = cylc_pyro_client.client( self.cfg.suite, self.cfg.owner, self.cfg.host, self.cfg.port).get_proxy( 'remote' )
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
            proxy = cylc_pyro_client.client( self.cfg.suite, self.cfg.owner, self.cfg.host, self.cfg.port).get_proxy( 'remote' )
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
            proxy = cylc_pyro_client.client( self.cfg.suite, self.cfg.owner, self.cfg.host, self.cfg.port).get_proxy( 'remote' )
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
            proxy = cylc_pyro_client.client( self.cfg.suite, self.cfg.owner, self.cfg.host, self.cfg.port ).get_proxy( 'remote' )
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
            proxy = cylc_pyro_client.client( self.cfg.suite, self.cfg.owner, self.cfg.host, self.cfg.port ).get_proxy( 'remote' )
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

        flabel = gtk.Label( "SUITE: " + self.cfg.suite )
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
        stoptime_entry.set_max_length(14)
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
        window.set_title( "Start Suite '" + self.cfg.suite + "'")

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
        ctime_entry.set_max_length(14)
        if self.suiterc['scheduling']['initial cycle time']:
            ctime_entry.set_text( str(self.suiterc['scheduling']['initial cycle time']) )
        ic_box.pack_start (ctime_entry, True)
        vbox.pack_start( ic_box )

        fc_box = gtk.HBox()
        label = gtk.Label( 'STOP (cycle, optional)' )
        fc_box.pack_start( label, True )
        stoptime_entry = gtk.Entry()
        stoptime_entry.set_max_length(14)
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
        holdtime_entry.set_max_length(14)
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
        entry.set_max_length(14)
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
        entry_ctime.set_max_length(14)
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

        label = gtk.Label( 'SUITE: ' + self.cfg.suite )
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
        entry_stoptag.set_max_length(14)
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
                tid = TaskID( torg )
            except TaskIDError,x:
                warning_dialog( str(x) ).warn()
                return
            else:
                torg= tid.getstr()

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
            proxy = cylc_pyro_client.client( self.cfg.suite, self.cfg.owner, self.cfg.host, self.cfg.port ).get_proxy( 'remote' )
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
            proxy = cylc_pyro_client.client( self.cfg.suite ).get_proxy( 'remote' )
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


    def generate_main_menu( self ):
        if hasattr(self, "menu_bar"):
            for child in self.menu_bar.get_children():
                self.menu_bar.remove(child)
        else:
            self.menu_bar = gtk.MenuBar()
        
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

        self.view_menu.append( gtk.SeparatorMenuItem() )

        graph_view_item = gtk.RadioMenuItem( label="View _Graph" )
        self.view_menu.append( graph_view_item )
        graph_view_item._viewname = "graph"
        graph_view_item.set_active( True )
        graph_view_item.connect( 'toggled', self._cb_change_view0 )

        led_view_item = gtk.RadioMenuItem( group=graph_view_item, label="View _LED" )
        self.view_menu.append( led_view_item )
        led_view_item._viewname = "led"
        led_view_item.connect( 'toggled', self._cb_change_view0 )

        tree_view_item = gtk.RadioMenuItem( group=graph_view_item, label="View _Tree" )
        self.view_menu.append( tree_view_item )
        tree_view_item._viewname = "tree"
        tree_view_item.connect( 'toggled', self._cb_change_view0 )

        self.view_menu.append( gtk.SeparatorMenuItem() )
        
        second_view_menu = gtk.Menu()
        second_view_menu_root = gtk.MenuItem( '_Secondary ...' )
        self.view_menu.append( second_view_menu_root )
        second_view_menu_root.set_submenu( second_view_menu )

        second_no_view_item = gtk.RadioMenuItem( label="None" )
        second_no_view_item.set_active( True )
        second_view_menu.append( second_no_view_item )
        second_no_view_item._viewname = "None"
        second_no_view_item.connect( 'toggled', self._cb_change_view1 )

        second_graph_view_item = gtk.RadioMenuItem( group=second_no_view_item,
                                                    label="View _Graph" )
        second_view_menu.append( second_graph_view_item )
        second_graph_view_item._viewname = "graph"
        second_graph_view_item.connect( 'toggled', self._cb_change_view1 )

        second_led_view_item = gtk.RadioMenuItem( group=second_no_view_item,
                                                  label="View _LED" )
        second_view_menu.append( second_led_view_item )
        second_led_view_item._viewname = "led"
        second_led_view_item.connect( 'toggled', self._cb_change_view1 )

        second_tree_view_item = gtk.RadioMenuItem( group=second_no_view_item,
                                                   label="View _Tree" )
        second_view_menu.append( second_tree_view_item )
        second_tree_view_item._viewname = "tree"
        second_tree_view_item.connect( 'toggled', self._cb_change_view1 )

        second_view_align_item = gtk.CheckMenuItem( label="View side-by-side" )
        second_view_align_item.connect( 'toggled', self._cb_change_view_align )
        second_view_menu.append( second_view_align_item )

        start_menu = gtk.Menu()
        start_menu_root = gtk.MenuItem( '_Control' )
        start_menu_root.set_submenu( start_menu )

        start_item = gtk.MenuItem( '_Run Suite ... ' )
        start_menu.append( start_item )
        start_item.connect( 'activate', self.startsuite_popup )
        if self.cfg.readonly:
            start_item.set_sensitive(False)

        stop_item = gtk.MenuItem( '_Stop Suite ... ' )
        start_menu.append( stop_item )
        stop_item.connect( 'activate', self.stopsuite_popup )
        if self.cfg.readonly:
            stop_item.set_sensitive(False)

        pause_item = gtk.MenuItem( '_Hold Suite (pause)' )
        start_menu.append( pause_item )
        pause_item.connect( 'activate', self.pause_suite )
        if self.cfg.readonly:
            pause_item.set_sensitive(False)

        resume_item = gtk.MenuItem( '_Release Suite (unpause)' )
        start_menu.append( resume_item )
        resume_item.connect( 'activate', self.resume_suite )
        if self.cfg.readonly:
            resume_item.set_sensitive(False)

        insert_item = gtk.MenuItem( '_Insert Task(s) ...' )
        start_menu.append( insert_item )
        insert_item.connect( 'activate', self.insert_task_popup )
        if self.cfg.readonly:
            insert_item.set_sensitive(False)

        block_item = gtk.MenuItem( '_Block Access' )
        start_menu.append( block_item )
        block_item.connect( 'activate', self.block_suite )
        if self.cfg.readonly:
            block_item.set_sensitive(False)

        unblock_item = gtk.MenuItem( 'U_nblock Access' )
        start_menu.append( unblock_item )
        unblock_item.connect( 'activate', self.unblock_suite )
        if self.cfg.readonly:
            unblock_item.set_sensitive(False)

        runahead_item = gtk.MenuItem( '_Change Runahead Limit ...' )
        start_menu.append( runahead_item )
        runahead_item.connect( 'activate', self.change_runahead_popup )
        if self.cfg.readonly:
            runahead_item.set_sensitive(False)

        help_menu = gtk.Menu()
        help_menu_root = gtk.MenuItem( '_Help' )
        help_menu_root.set_submenu( help_menu )

        self.userguide_item = gtk.MenuItem( '_GUI Quick Guide' )
        help_menu.append( self.userguide_item )

        chelp_menu = gtk.MenuItem( 'Command Help' )
        help_menu.append( chelp_menu )
        self.construct_command_menu( chelp_menu )

        cug_pdf_item = gtk.MenuItem( 'Cylc User Guide (_PDF)' )
        help_menu.append( cug_pdf_item )
        cug_pdf_item.connect( 'activate', self.launch_cug, True )
  
        cug_html_item = gtk.MenuItem( 'Cylc User Guide (_HTML)' )
        help_menu.append( cug_html_item )
        cug_html_item.connect( 'activate', self.launch_cug, False )

        #self.todo_item = gtk.MenuItem( '_To Do' )
        #help_menu.append( self.todo_item )
        #self.todo_item.connect( 'activate', helpwindow.todo )
  
        about_item = gtk.MenuItem( '_About' )
        help_menu.append( about_item )
        about_item.connect( 'activate', self.about )

        self.menu_bar.append( file_menu_root )
        self.menu_bar.append( view_menu_root )
        self.menu_bar.append( start_menu_root )
        self.menu_bar.append( help_menu_root )

    def construct_command_menu( self, menu ):
        ## # JUST CONTROL COMMANDS:
        ## com_menu = gtk.Menu()
        ## menu.set_submenu( com_menu )
        ## cout = subprocess.Popen( ["cylc", "category=control" ], stdout=subprocess.PIPE ).communicate()[0]
        ## commands = cout.rstrip().split()
        ## for command in commands:
        ##     if command == "gcylc":
        ##         continue
        ##     bar_item = gtk.MenuItem( command )
        ##     com_menu.append( bar_item )
        ##     bar_item.connect( 'activate', self.command_help, "control", command )
        # ALL COMMANDS
        # ALL COMMANDS
        cat_menu = gtk.Menu()
        menu.set_submenu( cat_menu )

        cylc_help_item = gtk.MenuItem( 'cylc' )
        cat_menu.append( cylc_help_item )
        cylc_help_item.connect( 'activate', self.command_help )

        cout = subprocess.Popen( ["cylc", "categories"], stdout=subprocess.PIPE ).communicate()[0]
        categories = cout.rstrip().split()
        for category in categories: 
            foo_item = gtk.MenuItem( category )
            cat_menu.append( foo_item )
            com_menu = gtk.Menu()
            foo_item.set_submenu( com_menu )
            cout = subprocess.Popen( ["cylc", "category="+category ], stdout=subprocess.PIPE ).communicate()[0]
            commands = cout.rstrip().split()
            for command in commands:
                bar_item = gtk.MenuItem( command )
                com_menu.append( bar_item )
                bar_item.connect( 'activate', self.command_help, category, command )

    def generate_tool_bar( self ):
        if hasattr(self, "tool_bar"):
            for child in self.tool_bar.get_children():
                self.tool_bar.remove( child )
        else:
            self.tool_bar = gtk.Toolbar()
        views = self.VIEWS.keys()
        views.sort()
        views.sort( self._sort_views )

        items = [( "Run suite", gtk.STOCK_MEDIA_PLAY, True, self.startsuite_popup ),
                 ( "Stop suite", gtk.STOCK_MEDIA_STOP, True, self.pause_suite )]
        view2_combo_box = gtk.ComboBox()
        pixlist = gtk.ListStore( gtk.gdk.Pixbuf, str, bool, bool )
        view_items = []
        for v in views:
             image = gtk.image_new_from_file( self.cfg.imagedir + self.VIEW_ICON_PATHS[v] )
             pixbuf = gtk.gdk.pixbuf_new_from_file( self.cfg.imagedir + self.VIEW_ICON_PATHS[v] )
             view_items.append( ( v, image) )
             pixlist.append( ( pixbuf, v, True, False ) )
        pixlist.insert( 0, ( pixbuf, "None", False, True ) )
        view2_combo_box.set_model( pixlist )
        cell_pix = gtk.CellRendererPixbuf()
        cell_text = gtk.CellRendererText()
        view2_combo_box.pack_start( cell_pix )
        view2_combo_box.pack_start( cell_text )
        view2_combo_box.add_attribute( cell_pix, "pixbuf", 0 )
        view2_combo_box.add_attribute( cell_text, "text", 1 )
        view2_combo_box.add_attribute( cell_pix, "visible", 2 )
        view2_combo_box.add_attribute( cell_text, "visible", 3 )
        view2_combo_box.set_active(0)
        view2_combo_box.connect( "changed", self._cb_change_view1 )
        view2_toolitem = gtk.ToolItem()
        view2_toolitem.add( view2_combo_box )
        self.tool_bar.insert( view2_toolitem, 0 )
        self.tool_bar.insert( gtk.SeparatorToolItem(), 0 )
        self.tool_view_buttons = []
        for viewname, image in reversed(view_items):
            toolbutton = gtk.ToolButton( icon_widget=image )
            tooltip = gtk.Tooltips()
            tooltip.enable()
            tooltip.set_tip( toolbutton, viewname )
            toolbutton._viewname = viewname
            toolbutton.connect( "clicked", self._cb_change_view0 )
            self.tool_view_buttons.append( toolbutton )
            self.tool_bar.insert( toolbutton, 0 )
        sep = gtk.SeparatorToolItem()
        self.tool_bar.insert( sep, 0 )

        stop_icon = gtk.image_new_from_stock( gtk.STOCK_MEDIA_STOP,
                                              gtk.ICON_SIZE_SMALL_TOOLBAR )
        self.stop_toolbutton = gtk.ToolButton( icon_widget=stop_icon )
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip( self.stop_toolbutton, "Stop Suite" )
        if self.cfg.readonly:
            self.stop_toolbutton.set_sensitive( False )
        self.stop_toolbutton.connect( "clicked", self.stopsuite_default )
        self.tool_bar.insert(self.stop_toolbutton, 0)

        run_icon = gtk.image_new_from_stock( gtk.STOCK_MEDIA_PLAY,
                                             gtk.ICON_SIZE_SMALL_TOOLBAR )
        self.run_pause_toolbutton = gtk.ToolButton( icon_widget=run_icon )
        if self.cfg.readonly:
            self.run_pause_toolbutton.set_sensitive( False )
        click_func = self.startsuite_popup
        self.run_pause_toolbutton.connect( "clicked", lambda w: w.click_func( w ) )
        self.tool_bar.insert(self.run_pause_toolbutton, 0)

    def _alter_status_tool_bar( self, new_status ):
        self.stop_toolbutton.set_sensitive( "STOP" not in new_status )
        if "running" in new_status:
            icon = gtk.STOCK_MEDIA_PAUSE
            tip_text = "Hold Suite (pause)"
            click_func = self.pause_suite
            print icon, tip_text
        elif "STOPPED" in new_status:
            icon = gtk.STOCK_MEDIA_PLAY
            tip_text = "Run Suite"
            click_func = self.startsuite_popup
        elif "HELD" in new_status or "STOPPING" in new_status:
            icon = gtk.STOCK_MEDIA_PLAY
            tip_text = "Release Suite (unpause)"
            print icon, tip_text
            click_func = self.resume_suite
        else:
            self.run_pause_toolbutton.set_sensitive( False )
            return False
        if not self.cfg.readonly:
            self.run_pause_toolbutton.set_sensitive( True )
        icon_widget = gtk.image_new_from_stock( icon,
                                                gtk.ICON_SIZE_SMALL_TOOLBAR )
        icon_widget.show()
        self.run_pause_toolbutton.set_icon_widget( icon_widget )
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip( self.run_pause_toolbutton, tip_text )
        self.run_pause_toolbutton.click_func = click_func

    def create_info_bar( self ):
        self.info_bar = InfoBar( self.cfg.suite, self._alter_status_tool_bar )

    #def check_connection( self ):
    #    # called on a timeout in the gtk main loop, tell the log viewer
    #    # to reload if the connection has been lost and re-established,
    #    # which probably means the cylc suite was shutdown and
    #    # restarted.
    #    try:
    #        cylc_pyro_client.ping( self.cfg.host, self.cfg.port )
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
        return cylc_pyro_client.client( self.cfg.suite, self.cfg.owner, self.cfg.host, self.cfg.port ).get_proxy( object )
 
    def view_log( self, w ):
        logdir = os.path.join( self.suiterc['cylc']['logging']['directory'] )
        foo = cylc_logviewer( 'log', logdir, self.suiterc.get_task_name_list() )
        self.quitters.append(foo)

    def launch_cug( self, b, pdf ):
        fail = []
        cdir = None

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
        foo = gcapture_tmpfile( command, self.tmpdir )
        foo.run()
 
    def command_help( self, w, cat='', com='' ):
        command = "cylc " + cat + " " + com + " help"
        foo = gcapture_tmpfile( command, self.tmpdir, 700, 600 )
        self.gcapture_windows.append(foo)
        foo.run()
