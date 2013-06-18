#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
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
from stateview import DotUpdater
from gcapture import gcapture_tmpfile
from cylc import cylc_pyro_client
from cylc.TaskID import TaskID
from util import EntryTempText

class ControlLED(object):
    """
LED suite control interface.
    """
    def __init__(self, cfg, updater, usercfg, info_bar, get_right_click_menu,
                 log_colors):

        self.cfg = cfg
        self.updater = updater
        self.usercfg = usercfg
        self.info_bar = info_bar
        self.get_right_click_menu = get_right_click_menu
        self.log_colors = log_colors

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
        
        self.t = DotUpdater( self.cfg, self.updater, treeview,
                             self.info_bar, self.usercfg )
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
        name = self.t.task_list[column_index - 1]
        ctime_column = treeview.get_model().get_n_columns() - 1
        ctime = treeview.get_model().get_value( r_iter, ctime_column )

        task_id = name + TaskID.DELIM + ctime

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
        
        menu.popup( None, None, None, event.button, event.time )

        # TODO - popup menus are not automatically destroyed and can be
        # reused if saved; however, we need to reconstruct or at least
        # alter ours dynamically => should destroy after each use to
        # prevent a memory leak? But I'm not sure how to do this as yet.)

        return True

    def check_filter_entry( self, e ):
        ftxt = self.filter_entry.get_text()
        self.t.filter = self.filter_entry.get_text()
        self.t.update()
        self.t.update_gui()

    def toggle_grouping( self, toggle_item ):
        """Toggle grouping by visualisation families."""
        group_on = toggle_item.get_active()
        if group_on == self.t.should_group_families:
            return False
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
        self.t.update()           
        self.t.update_gui()
        return False

    def toggle_headings(self, toggle_item):
        headings_off = toggle_item.get_active()
        if headings_off == self.t.should_hide_headings:
            return False
        self.t.should_hide_headings = headings_off
        if toggle_item != self.headings_menu_item:
            self.headings_menu_item.set_active( headings_off )
        self.t.set_led_headings()

    def stop(self):
        self.t.quit = True

    def on_popup_quit( self, b, lv, w ):
        lv.quit()
        self.quitters.remove( lv )
        w.destroy()

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
        return items

    def get_toolitems( self ):
        """Return the tool bar items specific to this view."""
        items = []

        self.group_toolbutton = gtk.ToggleToolButton()
        self.group_toolbutton.set_active( self.t.should_group_families )
        g_image = gtk.image_new_from_stock( 'group', gtk.ICON_SIZE_SMALL_TOOLBAR )
        self.group_toolbutton.set_icon_widget( g_image )
        self.group_toolbutton.connect( 'toggled', self.toggle_grouping )
        self._set_tooltip( self.group_toolbutton, "Dot View - Click to group tasks by families" )
        items.append( self.group_toolbutton )
        
        self.filter_entry = EntryTempText()
        self.filter_entry.set_width_chars( 7 )  # Reduce width in toolbar
        self.filter_entry.connect( "activate", self.check_filter_entry )
        self.filter_entry.set_temp_text( "filter" )
        filter_toolitem = gtk.ToolItem()
        filter_toolitem.add(self.filter_entry)
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip(filter_toolitem, "Dot View - Filter tasks by name\n(enter a sub-string or regex)")
        items.append(filter_toolitem)

        return items
