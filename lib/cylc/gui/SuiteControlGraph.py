#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
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
import os, re
import gobject
from GraphUpdater import GraphUpdater
from warning_dialog import warning_dialog, info_dialog
from cylc.cylc_xdot import xdot_widgets
from cylc.task_state import task_state
import cylc.TaskID
from gcapture import gcapture_tmpfile


class ControlGraph(object):
    """
Dependency graph suite control interface.
    """
    def __init__(self, cfg, updater, theme, dot_size, info_bar,
            get_right_click_menu, log_colors, insert_task_popup):
        # NOTE: this view has separate family Group and Ungroup buttons
        # instead of a single Group/Ungroup toggle button, unlike the
        # other views the graph view can display intermediate states
        # between fully grouped and fully ungrouped (well, so can the
        # tree view, but in that case the toggle button determines
        # whether it displays a flat list or a proper tree view).

        self.cfg = cfg
        self.updater = updater
        self.theme = theme
        self.info_bar = info_bar
        self.get_right_click_menu = get_right_click_menu
        self.log_colors = log_colors
        self.insert_task_popup = insert_task_popup

        self.gcapture_windows = []

        self.xdot = xdot_widgets()
        self.xdot.widget.connect( 'clicked', self.on_url_clicked )
        self.xdot.widget.connect_after( 'motion-notify-event', self.on_motion_notify )
        self.last_url = None

    def get_control_widgets( self ):
        self.t = GraphUpdater( self.cfg, self.updater, self.theme,
                               self.info_bar, self.xdot )
        self.t.start()
        return self.xdot.get()

    def toggle_graph_disconnect( self, w, update_button ):
        if w.get_active():
            self.t.graph_disconnect = True
            self._set_tooltip( w, "Click to reconnect" )
            update_button.set_sensitive(True)
        else:
            self.t.graph_disconnect = False
            self._set_tooltip( w, "Click to disconnect" )
            update_button.set_sensitive(False)
        return True

    def graph_update( self, w ):
        self.t.action_required = True

    def on_url_clicked( self, widget, url, event ):
        if event.button != 3:
            return False

        m = re.match( 'base:(.*)', url )
        if m:
            # base graph node
            task_id = m.groups()[0]
            self.right_click_menu( event, task_id, type='base graph task' )
            return

        self.right_click_menu( event, url, type='live task' )

    def on_motion_notify( self, widget, event ):
        """Add a new tooltip when the cursor moves in the graph."""
        url = self.xdot.widget.get_url( event.x, event.y )
        if url == self.last_url:
            return False
        self.last_url = url
        if not hasattr(self.xdot.widget, "set_tooltip_text"):
            # Unfortunately, the older gtk.Tooltips doesn't work well here.
            # gtk.Widget.set_tooltip_text was introduced at PyGTK 2.12
            return False
        if url is None:
            self.xdot.widget.set_tooltip_text(None)
            return False
        url = unicode(url.url)
        m = re.match( 'base:(.*)', url )
        if m:
            #print 'BASE GRAPH'
            task_id = m.groups()[0]
            #warning_dialog(
            #        task_id + "\n"
            #        "This task is part of the base graph, taken from the\n"
            #        "suite config file (suite.rc) dependencies section, \n"
            #        "but it does not currently exist in the running suite." ).warn()
            self.xdot.widget.set_tooltip_text(self.t.get_summary(task_id))
            return False

        # URL is task ID
        #print 'LIVE TASK'
        self.xdot.widget.set_tooltip_text(self.t.get_summary(url))
        return False

    def stop(self):
        self.t.quit = True

    def right_click_menu( self, event, task_id, type='live task' ):
        name, point_string = cylc.TaskID.split( task_id )

        menu = gtk.Menu()
        menu_root = gtk.MenuItem( task_id )
        menu_root.set_submenu( menu )

        timezoom_item_direct = gtk.MenuItem( 'Focus on ' + point_string )
        timezoom_item_direct.connect(
            'activate', self.focused_timezoom_direct, point_string)

        # TODO - pre cylc-6 could focus on a range of points (was hours-based).
        #timezoom_item = gtk.MenuItem( 'Focus on Range' )
        #timezoom_item.connect( 'activate', self.focused_timezoom_popup, task_id )

        timezoom_reset_item = gtk.MenuItem( 'Focus Reset' )
        timezoom_reset_item.connect( 'activate', self.focused_timezoom_direct, None )

        group_item = gtk.ImageMenuItem( 'Group' )
        img = gtk.image_new_from_stock( 'group', gtk.ICON_SIZE_MENU )
        group_item.set_image(img)
        group_item.set_sensitive( not self.t.have_leaves_and_feet or name not in self.t.feet )
        group_item.connect( 'activate', self.grouping, name, True )

        ungroup_item = gtk.ImageMenuItem( 'UnGroup' )
        img = gtk.image_new_from_stock( 'ungroup', gtk.ICON_SIZE_MENU )
        ungroup_item.set_image(img)
        ungroup_item.set_sensitive( not self.t.have_leaves_and_feet or name not in self.t.leaves )
        ungroup_item.connect( 'activate', self.grouping, name, False )

        ungroup_rec_item = gtk.ImageMenuItem( 'Recursive UnGroup' )
        img = gtk.image_new_from_stock( 'ungroup', gtk.ICON_SIZE_MENU )
        ungroup_rec_item.set_image(img)
        ungroup_rec_item.set_sensitive( not self.t.have_leaves_and_feet or name not in self.t.leaves )
        ungroup_rec_item.connect( 'activate', self.grouping, name, False, True )

        title_item = gtk.MenuItem( 'Task: ' + task_id.replace("_", "__") )
        title_item.set_sensitive(False)
        menu.append( title_item )

        menu.append( gtk.SeparatorMenuItem() )

        if type is not 'live task':
            insert_item = gtk.ImageMenuItem( 'Insert ...' )
            img = gtk.image_new_from_stock(  gtk.STOCK_DIALOG_INFO, gtk.ICON_SIZE_MENU )
            insert_item.set_image(img)
            menu.append( insert_item )
            insert_item.connect(
                'button-press-event',
                lambda *a: self.insert_task_popup(
                    is_fam=(name in self.t.descendants),
                    name=name, point_string=point_string
                )
            )
            menu.append( gtk.SeparatorMenuItem() )

        menu.append( timezoom_item_direct )
        #menu.append( timezoom_item )
        menu.append( timezoom_reset_item )

        menu.append( gtk.SeparatorMenuItem() )
        menu.append( group_item )
        menu.append( ungroup_item )
        menu.append( ungroup_rec_item )

        if type == 'live task':
            is_fam = (name in self.t.descendants)
            default_menu = self.get_right_click_menu( task_id, hide_task=True,
                                                      task_is_family=is_fam )
            for item in default_menu.get_children():
                default_menu.remove( item )
                menu.append( item )

        menu.show_all()
        menu.popup( None, None, None, event.button, event.time )

        # TODO - popup menus are not automatically destroyed and can be
        # reused if saved; however, we need to reconstruct or at least
        # alter ours dynamically => should destroy after each use to
        # prevent a memory leak? But I'm not sure how to do this as yet.)

        return True

    def grouping( self, w, name, group, rec=False ):
        self.t.ungroup_recursive = rec
        self.t.group_all = False
        self.t.ungroup_all = False
        if group:
            self.t.group = [name]
            self.t.ungroup = []
        else:
            self.t.ungroup = [name]
            self.t.group = []
        self.t.action_required = True
        self.t.best_fit = True

    def rearrange( self, col, n ):
        cols = self.ttreeview.get_columns()
        for i_n in range(len(cols)):
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

    def get_menuitems( self ):
        """Return the menu items specific to this view."""
        items = []
        graph_range_item = gtk.MenuItem( 'Time Range Focus ...' )
        items.append( graph_range_item )
        graph_range_item.connect( 'activate', self.graph_timezoom_popup )

        crop_item = gtk.CheckMenuItem( 'Toggle _Crop Base Graph' )
        items.append( crop_item )
        crop_item.set_active( self.t.crop )
        crop_item.connect( 'activate', self.toggle_crop )

        menu_filter_item = gtk.ImageMenuItem( 'Task _Filtering ...' )
        img = gtk.image_new_from_stock(  gtk.STOCK_CLEAR, gtk.ICON_SIZE_MENU )
        menu_filter_item.set_image(img)
        items.append( menu_filter_item )
        menu_filter_item.connect( 'activate', self.filter_popup )

        self.menu_group_item = gtk.ImageMenuItem( '_Group All Families' )
        img = gtk.image_new_from_stock(  'group', gtk.ICON_SIZE_MENU )
        self.menu_group_item.set_image(img)
        items.append( self.menu_group_item )
        self.menu_group_item.connect( 'activate', self.group_all, True )

        self.menu_ungroup_item = gtk.ImageMenuItem( '_UnGroup All Families' )
        img = gtk.image_new_from_stock(  'ungroup', gtk.ICON_SIZE_MENU )
        self.menu_ungroup_item.set_image(img)
        items.append( self.menu_ungroup_item )
        self.menu_ungroup_item.connect( 'activate', self.group_all, False )

        menu_left_to_right_item = gtk.CheckMenuItem(
            '_Left-to-right Graphing' )
        items.append( menu_left_to_right_item )
        menu_left_to_right_item.set_active( self.t.orientation == "LR" )
        menu_left_to_right_item.connect( 'activate',
                                         self.toggle_left_to_right_mode )

        self.menu_subgraphs_item = gtk.CheckMenuItem(
            '_Organise by Cycle Point' )
        items.append( self.menu_subgraphs_item )
        self.menu_subgraphs_item.set_active( self.t.subgraphs_on )
        self.menu_subgraphs_item.connect(
            'activate',
            self.toggle_cycle_point_subgraphs
        )

        igsui_item = gtk.CheckMenuItem( '_Ignore Suicide Triggers' )
        items.append( igsui_item )
        igsui_item.set_active( self.t.ignore_suicide )
        igsui_item.connect( 'activate', self.toggle_ignore_suicide_triggers )

        return items

    def _set_tooltip( self, widget, tip_text ):
        tip = gtk.Tooltips()
        tip.enable()
        tip.set_tip( widget, tip_text )

    def get_toolitems( self ):
        """Return the tool bar items specific to this view."""
        items = []
        for child in self.xdot.vbox.get_children():
            if isinstance(child, gtk.HButtonBox):
                self.xdot.vbox.remove(child)

        self.group_toolbutton = gtk.ToolButton()
        g_image = gtk.image_new_from_stock( 'group', gtk.ICON_SIZE_SMALL_TOOLBAR )
        self.group_toolbutton.set_icon_widget( g_image )
        self.group_toolbutton.set_label( "Group" )
        self.group_toolbutton.connect( 'clicked', self.group_all, True )
        self._set_tooltip( self.group_toolbutton, "Graph View - Click to group all task families" )
        items.append( self.group_toolbutton )

        self.ungroup_toolbutton = gtk.ToolButton()
        g_image = gtk.image_new_from_stock( 'ungroup', gtk.ICON_SIZE_SMALL_TOOLBAR )
        self.ungroup_toolbutton.set_icon_widget( g_image )
        self.ungroup_toolbutton.set_label( "Ungroup" )
        self.ungroup_toolbutton.connect( 'clicked', self.group_all, False )
        self._set_tooltip( self.ungroup_toolbutton, "Graph View - Click to ungroup all task families" )
        items.append( self.ungroup_toolbutton )

        self.subgraphs_button = gtk.ToggleToolButton()
        image = gtk.image_new_from_stock( gtk.STOCK_LEAVE_FULLSCREEN,
                                          gtk.ICON_SIZE_SMALL_TOOLBAR )
        self.subgraphs_button.set_icon_widget( image )
        self.subgraphs_button.connect(
            'clicked', self.toggle_cycle_point_subgraphs )
        self.subgraphs_button.set_label( None )
        self._set_tooltip(
            self.subgraphs_button,
            "Graph View - Click to organise by cycle point"
        )
        items.append( self.subgraphs_button )

        zoomin_button = gtk.ToolButton( gtk.STOCK_ZOOM_IN )
        zoomin_button.connect( 'clicked', self.xdot.widget.on_zoom_in )
        zoomin_button.set_label( None )
        self._set_tooltip( zoomin_button, "Graph View - Zoom In" )
        items.append( zoomin_button )

        zoomout_button = gtk.ToolButton( gtk.STOCK_ZOOM_OUT )
        zoomout_button.connect( 'clicked', self.xdot.widget.on_zoom_out )
        zoomout_button.set_label( None )
        self._set_tooltip( zoomout_button, "Graph View - Zoom Out" )
        items.append( zoomout_button )

        zoomfit_button = gtk.ToolButton( gtk.STOCK_ZOOM_FIT )
        zoomfit_button.connect('clicked', self.xdot.widget.on_zoom_fit)
        zoomfit_button.set_label( None )
        self._set_tooltip( zoomfit_button, "Graph View - Best Fit" )
        items.append( zoomfit_button )

        zoom100_button = gtk.ToolButton( gtk.STOCK_ZOOM_100 )
        zoom100_button.connect('clicked', self.xdot.widget.on_zoom_100)
        zoom100_button.set_label( None )
        self._set_tooltip( zoom100_button, "Graph View - Normal Size" )
        items.append( zoom100_button )

        connect_button = gtk.ToggleToolButton()
        image = gtk.image_new_from_stock( gtk.STOCK_DISCONNECT,
                                          gtk.ICON_SIZE_SMALL_TOOLBAR )
        connect_button.set_icon_widget( image )
        connect_button.set_label( "Disconnect" )
        self._set_tooltip( connect_button, "Graph View - Click to disconnect" )
        items.append( connect_button )

        update_button = gtk.ToolButton( gtk.STOCK_REFRESH )
        update_button.connect( 'clicked', self.graph_update )
        update_button.set_label( None )
        update_button.set_sensitive( False )
        self._set_tooltip( update_button, "Graph View - Update graph" )
        items.append( update_button )

        connect_button.connect( 'clicked', self.toggle_graph_disconnect, update_button )

        return items

    def group_all( self, w, group ):
        if group:
            self.t.group_all = True
            self.t.ungroup_all = False
            if "graph" in self.cfg.ungrouped_views:
                self.cfg.ungrouped_views.remove("graph")
        else:
            self.t.ungroup_all = True
            self.t.group_all = False
            if "graph" not in self.cfg.ungrouped_views:
                self.cfg.ungrouped_views.append("graph")
        self.t.action_required = True
        self.t.best_fit = True

    def toggle_crop( self, w ):
        self.t.crop = not self.t.crop
        self.t.action_required = True

    def toggle_cycle_point_subgraphs( self, toggle_item ):
        subgraphs_on = toggle_item.get_active()
        if subgraphs_on == self.t.subgraphs_on:
            return
        self.t.subgraphs_on = subgraphs_on
        if isinstance( toggle_item, gtk.ToggleToolButton ):
            self.menu_subgraphs_item.set_active( self.t.subgraphs_on )
        else:
            self.subgraphs_button.set_active( self.t.subgraphs_on )
        self.t.action_required = True

    def toggle_left_to_right_mode( self, w ):
        """Change the graph to left-to-right or top-to-bottom."""
        if self.t.orientation == "TB":  # Top -> bottom ordering
            self.t.orientation = "LR"  # Left -> right ordering
        elif self.t.orientation == "LR":
            self.t.orientation = "TB"
        self.t.action_required = True

    def toggle_ignore_suicide_triggers( self, w ):
        self.t.ignore_suicide = not self.t.ignore_suicide
        self.t.action_required = True

    def filter_popup( self, w ):
        window = gtk.Window()
        window.modify_bg( gtk.STATE_NORMAL,
                gtk.gdk.color_parse( self.log_colors.get_color()))
        window.set_border_width(5)
        window.set_title( "Task Filtering")
        parent_window = self.xdot.widget.get_toplevel()
        if isinstance(parent_window, gtk.Window):
            window.set_transient_for( parent_window )
            window.set_type_hint( gtk.gdk.WINDOW_TYPE_HINT_DIALOG )
        vbox = gtk.VBox()

        # TODO - error checking on date range given
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

        # to initially filter out 'succeeded' and 'waiting' tasks
        #filter_states = [ 'waiting', 'succeeded' ]
        for st in task_state.legal:
            b = gtk.CheckButton( task_state.labels[st] )
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

        hbox = gtk.HBox()
        hbox.pack_start( apply_button, False )
        hbox.pack_start( reset_button, False )
        hbox.pack_end( cancel_button, False )
        #hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def filter_reset( self, w):
        self.t.filter_include = None
        self.t.filter_exclude = None
        self.t.state_filter = None
        self.t.action_required = True

    def filter( self, w, excl_e, incl_e, fbox ):
        filters = {}
        filters["excl"] = excl_e.get_text()
        filters["incl"] = incl_e.get_text()
        for filt_name, filt in filters.items():
            if not filt:
                filters[filt_name] = None
                continue
            try:
                re.compile( filt )
            except re.error as exc:
                warning_dialog(
                    'Bad filter regex: %s: error: %s' % (filt, exc)).warn()
                filters[filt_name] = None

        self.t.filter_include = filters["incl"]
        self.t.filter_exclude = filters["excl"]

        fstates = []
        for b in fbox.get_children():
            if not b.get_active():
                # sub '_' from button label keyboard mnemonics
                fstates.append( re.sub('_', '', b.get_label()))
        if len(fstates) > 0:
            self.t.state_filter = fstates
        else:
            self.t.state_filter = None

        self.t.action_required = True

#    def focused_timezoom_popup( self, w, id ):
#        window = gtk.Window()
#        window.modify_bg( gtk.STATE_NORMAL,
#                gtk.gdk.color_parse( self.log_colors.get_color()))
#        window.set_border_width(5)
#        window.set_title( "Cycle Point Zoom")
#        parent_window = self.xdot.widget.get_toplevel()
#        if isinstance(parent_window, gtk.Window):
#            window.set_transient_for( parent_window )
#            window.set_type_hint( gtk.gdk.WINDOW_TYPE_HINT_DIALOG )
#        vbox = gtk.VBox()
#
#        name, point_string = cylc.TaskID.split( id )
#        # TODO - do we need to check that oldest_point_string is defined yet?
#
#        #diff_pre = ctime - self.t.oldest_ctime.hours
#        #diff_post = self.t.newest_ctime - ctime.hours
#        # ...
#        #start_entry.set_text(str(diff_pre))
#        #stop_entry.set_text(str(diff_post))
#
#        # TODO - error checking on date range given
#        box = gtk.HBox()
#        label = gtk.Label( 'Pre (hours)' )
#        box.pack_start( label, True )
#        start_entry = gtk.Entry()
#        box.pack_start (start_entry, True)
#        vbox.pack_start( box )
#
#        box = gtk.HBox()
#        label = gtk.Label( 'Post (hours)' )
#        box.pack_start( label, True )
#        stop_entry = gtk.Entry()
#        box.pack_start (stop_entry, True)
#        vbox.pack_start( box )
#
#        cancel_button = gtk.Button( "_Close" )
#        cancel_button.connect("clicked", lambda x: window.destroy() )
#
#        reset_button = gtk.Button( "_Reset (No Zoom)" )
#        reset_button.connect("clicked", self.focused_timezoom_direct, None )
#
#        apply_button = gtk.Button( "_Apply" )
#        apply_button.connect("clicked", self.focused_timezoom,
#               point_string, start_entry, stop_entry )
#
#        hbox = gtk.HBox()
#        hbox.pack_start( apply_button, False )
#        hbox.pack_start( reset_button, False )
#        hbox.pack_end( cancel_button, False )
#        #hbox.pack_end( help_button, False )
#        vbox.pack_start( hbox )
#
#        window.add( vbox )
#        window.show_all()
 
    def focused_timezoom_direct( self, w, point_string ):
        self.t.focus_start_point_string = point_string
        self.t.focus_stop_point_string = point_string
        self.t.action_required = True
        self.t.best_fit = True

    def graph_timezoom_popup( self, w ):
        window = gtk.Window()
        window.modify_bg( gtk.STATE_NORMAL,
                gtk.gdk.color_parse( self.log_colors.get_color()))
        window.set_border_width(5)
        window.set_title( "Time Zoom")
        parent_window = self.xdot.widget.get_toplevel()
        if isinstance(parent_window, gtk.Window):
            window.set_transient_for( parent_window )
            window.set_type_hint( gtk.gdk.WINDOW_TYPE_HINT_DIALOG )
        vbox = gtk.VBox()

        # TODO - error checking on date range given
        box = gtk.HBox()
        label = gtk.Label( 'Start CYCLE' )
        box.pack_start( label, True )
        start_entry = gtk.Entry()
        start_entry.set_max_length(14)
        if self.t.oldest_point_string:
            start_entry.set_text(self.t.oldest_point_string)
        box.pack_start (start_entry, True)
        vbox.pack_start( box )

        box = gtk.HBox()
        label = gtk.Label( 'Stop CYCLE' )
        box.pack_start( label, True )
        stop_entry = gtk.Entry()
        stop_entry.set_max_length(14)
        if self.t.newest_point_string:
            stop_entry.set_text(self.t.newest_point_string)
        box.pack_start (stop_entry, True)
        vbox.pack_start( box )

        cancel_button = gtk.Button( "_Close" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        reset_button = gtk.Button( "_Reset (No Zoom)" )
        reset_button.connect("clicked", self.focused_timezoom_direct, None )

        apply_button = gtk.Button( "_Apply" )
        apply_button.connect("clicked", self.graph_timezoom,
                start_entry, stop_entry )

        hbox = gtk.HBox()
        hbox.pack_start( apply_button, False )
        hbox.pack_start( reset_button, False )
        hbox.pack_end( cancel_button, False )
        #hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def graph_timezoom(self, w, start_e, stop_e):
        self.t.focus_start_point_string = start_e.get_text()
        self.t.focus_stop_point_string = stop_e.get_text()
        self.t.best_fit = True
        self.t.action_required = True

#    def focused_timezoom(self, w, focus_point_string, start_e, stop_e):
#        pre_hours = start_e.get_text()
#        post_hours = stop_e.get_text()
#        self.t.focus_point_string = focus_point_string - pre_hours
#        self.t.focus_stop_point_string = focus_point_string + post_hours
#        return
#        self.t.best_fit = True
#        self.t.action_required = True

class StandaloneControlGraphApp( ControlGraph ):
    # For a ControlApp not launched by the gcylc main app:
    # 1/ call gobject.threads_init() on startup
    # 2/ call gtk.main_quit() on exit

    def __init__(self, suite, owner, host, port ):
        gobject.threads_init()
        ControlGraph.__init__(self, suite, owner, host, port )

    def quit_gcapture( self ):
        for gwindow in self.gcapture_windows:
            if not gwindow.quit_already:
                gwindow.quit( None, None )

    def delete_event(self, widget, event, data=None):
        self.quit_gcapture()
        ControlGraph.delete_event( self, widget, event, data )
        gtk.main_quit()

    def click_exit( self, foo ):
        self.quit_gcapture()
        ControlGraph.click_exit( self, foo )
        gtk.main_quit()
