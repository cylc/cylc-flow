#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import gtk
import os, re
import gobject
from updater_dot import DotUpdater
from gcapture import gcapture_tmpfile
from cylc import cylc_pyro_client
from cylc.task_id import TaskID
from util import EntryTempText
from warning_dialog import warning_dialog

class ControlLED(object):
    """
LED suite control interface.
    """
    def __init__(self, cfg, updater, theme, dot_size, info_bar, get_right_click_menu,
                 log_colors, insert_task_popup):

        self.cfg = cfg
        self.updater = updater
        self.theme = theme
        self.dot_size = dot_size
        self.info_bar = info_bar
        self.get_right_click_menu = get_right_click_menu
        self.log_colors = log_colors
        self.insert_task_popup = insert_task_popup

        self.gcapture_windows = []

    def get_control_widgets( self ):

        main_box = gtk.VBox()

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )

        types = tuple( [gtk.gdk.Pixbuf]* (10 ))
        liststore = gtk.ListStore(*types)
        treeview = gtk.TreeView( liststore )
        treeview.connect( 'button_press_event', self.on_treeview_button_pressed )
        sw.add( treeview )

        main_box.pack_start( sw, expand=True, fill=True )

        self.t = DotUpdater(
                self.cfg, self.updater, treeview, self.info_bar, self.theme,
                self.dot_size
        )
        self.t.start()

        return main_box

    def on_treeview_button_pressed( self, treeview, event ):
        # DISPLAY MENU ONLY ON RIGHT CLICK ONLY
        if event.button != 3:
            return False
        # the following sets selection to the position at which the
        # right click was done (otherwise selection lags behind the
        # right click):
        x = int( event.x )
        y = int( event.y )
        time = event.time
        pth = treeview.get_path_at_pos(x,y)

        if pth is None:
            return False

        path, col, cellx, celly = pth
        r_iter = treeview.get_model().get_iter( path )

        column_index = treeview.get_columns().index(col)
        if column_index == 0:
            return False

        if not self.t.is_transposed:
            point_string = self.t.led_headings[column_index]
            name = treeview.get_model().get_value( r_iter, 0 )
        else:
            name = self.t.led_headings[column_index]
            point_string_column = treeview.get_model().get_n_columns() - 1
            point_string = treeview.get_model().get_value(
                r_iter, point_string_column )

        task_id = TaskID.get(name, point_string)

        is_fam = (name in self.t.descendants)

        menu = self.get_right_click_menu( task_id, task_is_family=is_fam )

        sep = gtk.SeparatorMenuItem()
        sep.show()
        menu.append( sep )

        toggle_item = gtk.CheckMenuItem( 'Toggle Hide Task Headings' )
        toggle_item.set_active( self.t.should_hide_headings )
        menu.append( toggle_item )
        toggle_item.connect( 'toggled', self.toggle_headings )
        toggle_item.show()

        group_item = gtk.CheckMenuItem( 'Toggle Family Grouping' )
        group_item.set_active( self.t.should_group_families )
        menu.append( group_item )
        group_item.connect( 'toggled', self.toggle_grouping )
        group_item.show()

        transpose_menu_item = gtk.CheckMenuItem('Toggle _Transpose View')
        transpose_menu_item.set_active(self.t.should_transpose_view)
        menu.append(transpose_menu_item)
        transpose_menu_item.connect('toggled', self.toggle_transpose)
        transpose_menu_item.show()

        if self.cfg.use_defn_order:
            defn_order_menu_item = gtk.CheckMenuItem( 'Toggle _Definition Order' )
            defn_order_menu_item.set_active( self.t.defn_order_on )
            menu.append( defn_order_menu_item )
            defn_order_menu_item.connect( 'toggled', self.toggle_defn_order )
            defn_order_menu_item.show()

        menu.popup( None, None, None, event.button, event.time )

        # TODO - popup menus are not automatically destroyed and can be
        # reused if saved; however, we need to reconstruct or at least
        # alter ours dynamically => should destroy after each use to
        # prevent a memory leak? But I'm not sure how to do this as yet.)

        return True

    def toggle_grouping( self, toggle_item ):
        """Toggle grouping by visualisation families."""
        group_on = toggle_item.get_active()
        if group_on == self.t.should_group_families:
            return False
        if group_on:
            if "dot" in self.cfg.ungrouped_views:
                self.cfg.ungrouped_views.remove("dot")
        elif "dot" not in self.cfg.ungrouped_views:
            self.cfg.ungrouped_views.append("dot")
        self.t.should_group_families = group_on
        if isinstance( toggle_item, gtk.ToggleToolButton ):
            if group_on:
                tip_text = "Dot View - Click to ungroup families"
            else:
                tip_text = "Dot View - Click to group tasks by families"
            self._set_tooltip( toggle_item, tip_text )
            self.group_menu_item.set_active( group_on )
        else:
            if toggle_item != self.group_menu_item:
                self.group_menu_item.set_active( group_on )
            self.group_toolbutton.set_active( group_on )
        self.t.action_required = True
        return False

    def toggle_headings(self, toggle_item):
        headings_off = toggle_item.get_active()
        if headings_off == self.t.should_hide_headings:
            return False
        self.t.should_hide_headings = headings_off
        if toggle_item != self.headings_menu_item:
            self.headings_menu_item.set_active( headings_off )
        self.t.action_required = True

    def toggle_transpose(self, toggle_item):
        """Toggle transpose (rows-as-columns, etc) table view."""
        transpose_on = toggle_item.get_active()
        if transpose_on == self.t.should_transpose_view:
            return False
        self.t.should_transpose_view = transpose_on
        if toggle_item != self.transpose_menu_item:
            self.transpose_menu_item.set_active(transpose_on)
        self.t.action_required = True
        return False

    def toggle_defn_order( self, toggle_item ):
        """Toggle definition vs alphabetic ordering of namespaces"""
        defn_order_on = toggle_item.get_active()
        if defn_order_on == self.t.defn_order_on:
            return False
        self.t.defn_order_on = defn_order_on
        if toggle_item != self.defn_order_menu_item:
            self.defn_order_menu_item.set_active( defn_order_on )
        self.t.action_required = True
        return False

    def stop(self):
        self.t.quit = True

    def on_popup_quit( self, b, lv, w ):
        lv.quit()
        self.quitters.remove( lv )
        w.destroy()

    def refresh(self):
        self.t.update()
        self.t.action_required = True

    def _set_tooltip( self, widget, tip_text ):
        # Convenience function to add hover over text to a widget.
        tip = gtk.Tooltips()
        tip.enable()
        tip.set_tip( widget, tip_text )

    def get_menuitems( self ):
        """Return the menuitems specific to this view."""
        items = []
        self.headings_menu_item = gtk.CheckMenuItem( 'Toggle _Hide Task Headings' )
        self.headings_menu_item.set_active( self.t.should_hide_headings )
        items.append( self.headings_menu_item )
        self.headings_menu_item.show()
        self.headings_menu_item.connect( 'toggled', self.toggle_headings )

        self.group_menu_item = gtk.CheckMenuItem( 'Toggle _Family Grouping' )
        self.group_menu_item.set_active( self.t.should_group_families )
        items.append( self.group_menu_item )
        self.group_menu_item.connect( 'toggled', self.toggle_grouping )

        self.transpose_menu_item = gtk.CheckMenuItem('Toggle _Transpose View')
        self.transpose_menu_item.set_active(self.t.should_transpose_view)
        items.append(self.transpose_menu_item)
        self.transpose_menu_item.connect('toggled', self.toggle_transpose)

        if self.cfg.use_defn_order:
            self.defn_order_menu_item = gtk.CheckMenuItem( 'Toggle _Definition Order' )
            self.defn_order_menu_item.set_active( self.t.defn_order_on )
            items.append( self.defn_order_menu_item )
            self.defn_order_menu_item.connect( 'toggled', self.toggle_defn_order )
 
        return items

    def get_toolitems( self ):
        """Return the tool bar items specific to this view."""
        items = []

        self.group_toolbutton = gtk.ToggleToolButton()
        self.group_toolbutton.set_active( self.t.should_group_families )
        g_image = gtk.image_new_from_stock( 'group', gtk.ICON_SIZE_SMALL_TOOLBAR )
        self.group_toolbutton.set_icon_widget( g_image )
        self.group_toolbutton.set_label( "Group" )
        self.group_toolbutton.connect( 'toggled', self.toggle_grouping )
        items.append( self.group_toolbutton )
        self._set_tooltip( self.group_toolbutton, "Dot View - Click to group tasks by families" )

        self.transpose_toolbutton = gtk.ToggleToolButton()
        self.transpose_toolbutton.set_active(False)
        g_image = gtk.image_new_from_stock('transpose', gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.transpose_toolbutton.set_icon_widget(g_image)
        self.transpose_toolbutton.set_label("Transpose")
        self.transpose_toolbutton.connect('toggled', self.toggle_transpose)
        items.append(self.transpose_toolbutton)
        self._set_tooltip(self.transpose_toolbutton, "Dot View - Click to transpose view")

        return items
