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
        sw.add( treeview )

        main_box.pack_start( sw, expand=True, fill=True )
        
        self.t = lupdater( self.cfg, treeview, self.info_bar )
        self.t.start()

        return main_box

    def stop(self):
        self.t.quit = True

    def on_popup_quit( self, b, lv, w ):
        lv.quit()
        self.quitters.remove( lv )
        w.destroy()

    def get_menuitems( self ):
        """Return the menuitems specific to this view."""
        return []

    def get_toolitems( self ):
        """Return the tool bar items specific to this view."""
        return []
