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

from SuiteControl import ControlAppBase
import gtk
import os, re
import gobject
import helpwindow
from xstateview import xupdater
#from warning_dialog import warning_dialog, info_dialog
import cycle_time
from cylc_xdot import xdot_widgets

class ControlGraph(ControlAppBase):
    """
Dependency graph based GUI suite control interface.
    """
    def __init__(self, suite, owner, host, port, suite_dir, logging_dir,
            imagedir, readonly=False ):

        ControlAppBase.__init__(self, suite, owner, host, port,
                suite_dir, logging_dir, imagedir, readonly=False )

        self.userguide_item.connect( 'activate', helpwindow.userguide, True )

        self.x = xupdater( self.suite, self.suiterc, self.owner, self.host, self.port,
                self.label_mode, self.label_status, self.label_time, self.label_block, self.xdot )
        self.x.start()

    def get_control_widgets(self ):
        self.xdot = xdot_widgets()
        self.xdot.widget.connect( 'clicked', self.on_url_clicked )
        self.xdot.graph_disconnect_button.connect( 'toggled', self.toggle_graph_disconnect )
        self.xdot.graph_update_button.connect( 'clicked', self.graph_update )
        return self.xdot.get()

    def toggle_graph_disconnect( self, w ):
        if w.get_active():
            self.x.graph_disconnect = True
            w.set_label( '_REconnect' )
            self.xdot.graph_update_button.set_sensitive(True)
        else:
            self.x.graph_disconnect = False
            w.set_label( '_DISconnect' )
            self.xdot.graph_update_button.set_sensitive(False)
        return True

    def graph_update( self, w ):
        self.x.action_required = True
 
    def on_url_clicked( self, widget, url, event ):
        if event.button != 3:
            return False
        if url == 'KEY':
            # graph key node
            return

        m = re.match( 'SUBTREE:(.*)', url )
        if m:
            #print 'SUBTREE'
            task_id = m.groups()[0]
            self.right_click_menu( event, task_id, type='collapsed subtree' )
            return

        m = re.match( 'base:(.*)', url )
        if m:
            #print 'BASE GRAPH'
            task_id = m.groups()[0]
            #warning_dialog( 
            #        task_id + "\n"
            #        "This task is part of the base graph, taken from the\n"
            #        "suite config file (suite.rc) dependencies section, \n" 
            #        "but it does not currently exist in the running suite." ).warn()
            self.right_click_menu( event, task_id, type='base graph task' )
            return

        # URL is task ID
        #print 'LIVE TASK'
        self.right_click_menu( event, url, type='live task' )

    def delete_event(self, widget, event, data=None):
        self.x.quit = True
        return ControlAppBase.delete_event(self, widget, event, data )

    def click_exit( self, foo ):
        self.x.quit = True
        return ControlAppBase.click_exit(self, foo )

    def right_click_menu( self, event, task_id, type='live task' ):
        name, ctime = task_id.split('%')

        menu = gtk.Menu()
        menu_root = gtk.MenuItem( task_id )
        menu_root.set_submenu( menu )

        timezoom_item_direct = gtk.MenuItem( 'Focus on ' + ctime )
        timezoom_item_direct.connect( 'activate', self.focused_timezoom_direct, ctime )

        timezoom_item = gtk.MenuItem( 'Focus on Range' )
        timezoom_item.connect( 'activate', self.focused_timezoom_popup, task_id )

        timezoom_reset_item = gtk.MenuItem( 'Focus Reset' )
        timezoom_reset_item.connect( 'activate', self.focused_timezoom_direct, None )

        if type == 'collapsed subtree':
            title_item = gtk.MenuItem( 'Subtree: ' + task_id )
            title_item.set_sensitive(False)
            menu.append( title_item )
            menu.append( gtk.SeparatorMenuItem() )

            expand_item = gtk.MenuItem( 'Expand Subtree' )
            menu.append( expand_item )
            expand_item.connect( 'activate', self.expand_subtree, task_id )
    
            menu.append( timezoom_item_direct )
            menu.append( timezoom_item )
            menu.append( timezoom_reset_item )

        else:

            title_item = gtk.MenuItem( 'Task: ' + task_id )
            title_item.set_sensitive(False)
            menu.append( title_item )

            menu.append( gtk.SeparatorMenuItem() )

            menu.append( timezoom_item_direct )
            menu.append( timezoom_item )
            menu.append( timezoom_reset_item )

            menu.append( gtk.SeparatorMenuItem() )
            collapse_item = gtk.MenuItem( 'Collapse Subtree' )
            menu.append( collapse_item )
            collapse_item.connect( 'activate', self.collapse_subtree, task_id )

        if type == 'live task':
            menu.append( gtk.SeparatorMenuItem() )

            menu_items = self.get_right_click_menu_items( task_id )
            for item in menu_items:
                menu.append( item )

        menu.show_all()
        menu.popup( None, None, None, event.button, event.time )

        # TO DO: popup menus are not automatically destroyed and can be
        # reused if saved; however, we need to reconstruct or at least
        # alter ours dynamically => should destroy after each use to
        # prevent a memory leak? But I'm not sure how to do this as yet.)

        return True

    def collapse_subtree( self, w, id ):
        self.x.collapse.append(id)
        self.x.action_required = True
        self.x.best_fit = True

    def expand_subtree( self, w, id ):
        self.x.collapse.remove(id)
        self.x.action_required = True
        self.x.best_fit = True

    def expand_all_subtrees( self, w ):
        del self.x.collapse[:]
        self.x.action_required = True
        self.x.best_fit = True

    def rearrange( self, col, n ):
        cols = self.ttreeview.get_columns()
        for i_n in range(0,len(cols)):
            if i_n == n: 
                cols[i_n].set_sort_indicator(True)
            else:
                cols[i_n].set_sort_indicator(False)
        # col is cols[n]
        if col.get_sort_order() == gtk.SORT_ASCENDING:
            col.set_sort_order(gtk.SORT_DESCENDING)
        else:
            col.set_sort_order(gtk.SORT_ASCENDING)
        self.ttreestore.set_sort_column_id(n, col.get_sort_order()) 

    def create_main_menu( self ):
        ControlAppBase.create_main_menu(self)

        graph_range_item = gtk.MenuItem( 'Time Range Focus ...' )
        self.view_menu.append( graph_range_item )
        graph_range_item.connect( 'activate', self.graph_timezoom_popup )

        crop_item = gtk.MenuItem( 'Toggle _Crop Base Graph' )
        self.view_menu.append( crop_item )
        crop_item.connect( 'activate', self.toggle_crop )

        filter_item = gtk.MenuItem( 'Task _Filtering ...' )
        self.view_menu.append( filter_item )
        filter_item.connect( 'activate', self.filter_popup )

        expand_item = gtk.MenuItem( '_Expand All Subtrees' )
        self.view_menu.append( expand_item )
        expand_item.connect( 'activate', self.expand_all_subtrees )

        key_item = gtk.MenuItem( 'Toggle Graph _Key' )
        self.view_menu.append( key_item )
        key_item.connect( 'activate', self.toggle_key )

    def toggle_crop( self, w ):
        self.x.crop = not self.x.crop
        self.x.action_required = True
        
    def toggle_key( self, w ):
        self.x.show_key = not self.x.show_key
        self.x.action_required = True

    def filter_popup( self, w ):
        window = gtk.Window()
        window.modify_bg( gtk.STATE_NORMAL, 
                gtk.gdk.color_parse( self.log_colors.get_color()))
        window.set_border_width(5)
        window.set_title( "Task Filtering")

        vbox = gtk.VBox()

        # TO DO: error checking on date range given
        box = gtk.HBox()
        label = gtk.Label( 'Exclude (regex)' )
        box.pack_start( label, True )
        exclude_entry = gtk.Entry()
        box.pack_start (exclude_entry, True)
        vbox.pack_start( box )

        box = gtk.HBox()
        label = gtk.Label( 'Include (regex)' )
        box.pack_start( label, True )
        include_entry = gtk.Entry()
        box.pack_start (include_entry, True)
        vbox.pack_start( box )

        filterbox = gtk.HBox()
        # allow filtering out of 'succeeded' and 'waiting'
        all_states = [ 'waiting', 'submitted', 'running', 'succeeded', 'failed', 'held' ]
        labels = {}
        labels[ 'waiting'   ] = '_waiting'
        labels[ 'submitted' ] = 's_ubmitted'
        labels[ 'running'   ] = '_running'
        labels[ 'succeeded'  ] = 'su_cceeded'
        labels[ 'failed'    ] = 'f_ailed'
        labels[ 'held'   ] = 'h_eld'
        # initially filter out 'succeeded' and 'waiting' tasks
        #filter_states = [ 'waiting', 'succeeded' ]
        for st in all_states:
            b = gtk.CheckButton( labels[st] )
            filterbox.pack_start(b)
            #if st in filter_states:
            #    b.set_active(False)
            #else:
            b.set_active(True)

        vbox.pack_start( filterbox )

        cancel_button = gtk.Button( "_Close" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        reset_button = gtk.Button( "_Reset (No Filtering)" )
        reset_button.connect("clicked", self.filter_reset )

        apply_button = gtk.Button( "_Apply" )
        apply_button.connect("clicked", self.filter,
                exclude_entry, include_entry, filterbox)

        #help_button = gtk.Button( "_Help" )
        #help_button.connect("clicked", helpwindow.stop_guide )

        hbox = gtk.HBox()
        hbox.pack_start( apply_button, False )
        hbox.pack_start( reset_button, False )
        hbox.pack_end( cancel_button, False )
        #hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def filter_reset( self, w):
        self.x.filter_include = None
        self.x.filter_exclude = None
        self.x.state_filter = None
        self.x.action_required = True

    def filter( self, w, excl_e, incl_e, fbox ):
        excl = excl_e.get_text()
        incl = incl_e.get_text()
        if excl == '':
            excl = None
        if incl == '':
            incl == None
        for filt in excl, incl:
            if not filt:
                continue
            try:
                re.compile( filt )
            except:
                warning_dialog( "Bad Expression: " + filt ).warn()
        self.x.filter_include = incl
        self.x.filter_exclude = excl

        fstates = []
        for b in fbox.get_children():
            if not b.get_active():
                # sub '_' from button label keyboard mnemonics
                fstates.append( re.sub('_', '', b.get_label()))
        if len(fstates) > 0:
            self.x.state_filter = fstates
        else:
            self.x.state_filter = None
        
        self.x.action_required = True

    def focused_timezoom_popup( self, w, id ):
        window = gtk.Window()
        window.modify_bg( gtk.STATE_NORMAL, 
                gtk.gdk.color_parse( self.log_colors.get_color()))
        window.set_border_width(5)
        window.set_title( "Cycle-Time Zoom")

        vbox = gtk.VBox()

        name, ctime = id.split('%')
        # TO DO: do we need to check that oldeset_ctime is defined yet?
        diff_pre = cycle_time.diff_hours( ctime, self.x.oldest_ctime )
        diff_post = cycle_time.diff_hours( self.x.newest_ctime, ctime )

        # TO DO: error checking on date range given
        box = gtk.HBox()
        label = gtk.Label( 'Pre (hours)' )
        box.pack_start( label, True )
        start_entry = gtk.Entry()
        start_entry.set_text(str(diff_pre))
        box.pack_start (start_entry, True)
        vbox.pack_start( box )

        box = gtk.HBox()
        label = gtk.Label( 'Post (hours)' )
        box.pack_start( label, True )
        stop_entry = gtk.Entry()
        stop_entry.set_text(str(diff_post))
        box.pack_start (stop_entry, True)
        vbox.pack_start( box )

        cancel_button = gtk.Button( "_Close" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        reset_button = gtk.Button( "_Reset (No Zoom)" )
        reset_button.connect("clicked", self.focused_timezoom_direct, None )

        apply_button = gtk.Button( "_Apply" )
        apply_button.connect("clicked", self.focused_timezoom, 
               ctime, start_entry, stop_entry )

        #help_button = gtk.Button( "_Help" )
        #help_button.connect("clicked", helpwindow.stop_guide )

        hbox = gtk.HBox()
        hbox.pack_start( apply_button, False )
        hbox.pack_start( reset_button, False )
        hbox.pack_end( cancel_button, False )
        #hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def focused_timezoom_direct( self, w, ctime ):
        self.x.start_ctime = ctime
        self.x.stop_ctime = ctime
        self.x.action_required = True
        self.x.best_fit = True

    def graph_timezoom_popup( self, w ):
        window = gtk.Window()
        window.modify_bg( gtk.STATE_NORMAL, 
                gtk.gdk.color_parse( self.log_colors.get_color()))
        window.set_border_width(5)
        window.set_title( "Time Zoom")

        vbox = gtk.VBox()

        # TO DO: error checking on date range given
        box = gtk.HBox()
        label = gtk.Label( 'Start (YYYYMMDDHH)' )
        box.pack_start( label, True )
        start_entry = gtk.Entry()
        start_entry.set_max_length(10)
        if self.x.oldest_ctime:
            start_entry.set_text(self.x.oldest_ctime)
        box.pack_start (start_entry, True)
        vbox.pack_start( box )

        box = gtk.HBox()
        label = gtk.Label( 'Stop (YYYYMMDDHH)' )
        box.pack_start( label, True )
        stop_entry = gtk.Entry()
        stop_entry.set_max_length(10)
        if self.x.newest_ctime:
            stop_entry.set_text(self.x.newest_ctime)
        box.pack_start (stop_entry, True)
        vbox.pack_start( box )

        cancel_button = gtk.Button( "_Close" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        reset_button = gtk.Button( "_Reset (No Zoom)" )
        reset_button.connect("clicked", self.focused_timezoom_direct, None )

        apply_button = gtk.Button( "_Apply" )
        apply_button.connect("clicked", self.graph_timezoom, 
                start_entry, stop_entry )

        #help_button = gtk.Button( "_Help" )
        #help_button.connect("clicked", helpwindow.stop_guide )

        hbox = gtk.HBox()
        hbox.pack_start( apply_button, False )
        hbox.pack_start( reset_button, False )
        hbox.pack_end( cancel_button, False )
        #hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def graph_timezoom(self, w, start_e, stop_e):
        self.x.start_ctime = start_e.get_text()
        self.x.stop_ctime = stop_e.get_text()
        self.x.best_fit = True
        self.x.action_required = True

    def focused_timezoom(self, w, focus_ctime, start_e, stop_e):
        pre_hours = start_e.get_text()
        post_hours = stop_e.get_text()
        self.x.start_ctime = cycle_time.decrement( focus_ctime, pre_hours )
        self.x.stop_ctime = cycle_time.increment( focus_ctime, post_hours )
        self.x.best_fit = True
        self.x.action_required = True

class StandaloneControlGraphApp( ControlGraph ):
    # For a ControlApp not launched by the gcylc main app: 
    # 1/ call gobject.threads_init() on startup
    # 2/ call gtk.main_quit() on exit

    def __init__(self, suite, owner, host, port, suite_dir, logging_dir, imagedir, readonly=False ):
        gobject.threads_init()
        ControlGraph.__init__(self, suite, owner, host, port, suite_dir, logging_dir, imagedir, readonly )
 
    def delete_event(self, widget, event, data=None):
        ControlGraph.delete_event( self, widget, event, data )
        gtk.main_quit()

    def click_exit( self, foo ):
        ControlGraph.click_exit( self, foo )
        gtk.main_quit()
