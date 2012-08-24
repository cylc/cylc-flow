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
import os, re
import gobject
import helpwindow
from stateview import lupdater
from gcapture import gcapture_tmpfile
from cylc.port_scan import SuiteIdentificationError
from cylc import cylc_pyro_client
from warning_dialog import warning_dialog, info_dialog

class ControlLED(object):
    """
LED suite control interface.
    """
    def __init__(self, cfg, info_bar, get_right_click_menu, log_colors):

        self.cfg = cfg
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
        
        self.t = lupdater( self.cfg, treeview, self.info_bar )
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

        task_id = name + '%' + ctime

        menu = self.get_right_click_menu( task_id )

        sep = gtk.SeparatorMenuItem()
        sep.show()
        menu.append( sep )

        group_item = gtk.CheckMenuItem( 'Toggle Hide Task Headings' )
        group_item.set_active( self.t.should_hide_headings )
        menu.append( group_item )
        group_item.connect( 'toggled', self.toggle_headings )
        group_item.show()

        menu.popup( None, None, None, event.button, event.time )

        # TO DO: popup menus are not automatically destroyed and can be
        # reused if saved; however, we need to reconstruct or at least
        # alter ours dynamically => should destroy after each use to
        # prevent a memory leak? But I'm not sure how to do this as yet.)

        return True

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

    def get_menuitems( self ):
        """Return the menuitems specific to this view."""
        items = []
        self.headings_menu_item = gtk.CheckMenuItem( 'Toggle _Hide Task Headings' )
        self.headings_menu_item.set_active( self.t.should_hide_headings )
        items.append( self.headings_menu_item )
        self.headings_menu_item.show()
        self.headings_menu_item.connect( 'toggled', self.toggle_headings )
        return items

    def get_toolitems( self ):
        """Return the tool bar items specific to this view."""
        return []
