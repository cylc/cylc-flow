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

class ControlLED(object):
    """
LED GUI suite control interface.
    """
    def __init__(self, cfg, suiterc, info_bar, right_click_menu):

        self.cfg = cfg
        self.suiterc = suiterc
        self.info_bar = info_bar
        self.right_click_menu = right_click_menu

        self.gcapture_windows = []

    def get_control_widgets( self ):
        # Load task list from suite config.
        ### TO DO: For suites that are already running, or for dynamically
        ### updating the viewed task list, we can retrieve the task list
        ### (etc.) from the suite's remote state summary object.
        self.task_list = self.suiterc.get_task_name_list()

        main_box = gtk.VBox()
        main_box.pack_start( self.ledview_widgets(), expand=True, fill=True )
        
        self.tfilt = ''
        self.full_task_headings()
        
        self.t = lupdater( self.cfg, self.led_treeview.get_model(),
                           self.task_list, self.info_bar )
        self.t.start()
        return main_box

    def stop(self):
        self.t.quit = True

    def toggle_autoexpand( self, w ):
        self.t.autoexpand = not self.t.autoexpand

    def toggle_headings( self, w ):
        if self.task_headings_on:
            self.no_task_headings()
        else:
            self.full_task_headings()

    def no_task_headings( self ):
        self.task_headings_on = False
        self.led_headings = ['Task Tag' ] + [''] * len( self.task_list )
        self.reset_led_headings()

    def full_task_headings( self ):
        self.task_headings_on = True
        self.led_headings = ['Task Tag' ] + self.task_list
        self.reset_led_headings()

    def reset_led_headings( self ):
        tvcs = self.led_treeview.get_columns()
        labels = []
        for n in range( 1,1+len( self.task_list) ):
            labels.append(gtk.Label(self.led_headings[n]))
            labels[-1].set_use_underline(False)
            labels[-1].set_angle(90)
            labels[-1].show()
            label_box = gtk.VBox()
            label_box.pack_start(labels[-1], expand=False, fill=False)
            label_box.show()
            tvcs[n].set_widget( label_box )
        max_pixel_length = -1
        for label in labels:
            x, y = label.get_layout().get_size()
            if x > max_pixel_length:
                max_pixel_length = x
        for label in labels:
            while label.get_layout().get_size()[0] < max_pixel_length:
                label.set_text(label.get_text() + ' ')

    def ledview_widgets( self ):
        types = tuple( [gtk.gdk.Pixbuf]* (10 + len( self.task_list)))
        liststore = gtk.ListStore( *types )
        treeview = gtk.TreeView( liststore )
        treeview.get_selection().set_mode( gtk.SELECTION_NONE )

        # this is how to set background color of the entire treeview to black:
        #treeview.modify_base( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#000' ) ) 

        tvc = gtk.TreeViewColumn( 'Task Tag' )
        for i in range(10):
            cr = gtk.CellRendererPixbuf()
            #cr.set_property( 'cell-background', 'black' )
            tvc.pack_start( cr, False )
            tvc.set_attributes( cr, pixbuf=i )
        treeview.append_column( tvc )

        # hardwired 10px lamp image width!
        lamp_width = 10

        for n in range( 10, 10+len( self.task_list )):
            cr = gtk.CellRendererPixbuf()
            #cr.set_property( 'cell_background', 'black' )
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

        treeview.grab_focus()
        path, col, cellx, celly = pth
        treeview.set_cursor( path, col, 0 )

        selection = treeview.get_selection()
        treemodel, iter = selection.get_selected()
        name = treemodel.get_value( iter, 0 )
        iter2 = treemodel.iter_parent( iter )
        try:
            ctime = treemodel.get_value( iter2, 0 )
        except TypeError:
            # must have clicked on the top level ctime 
            return

        task_id = name + '%' + ctime

        self.right_click_menu( event, task_id )

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

    def on_popup_quit( self, b, lv, w ):
        lv.quit()
        self.quitters.remove( lv )
        w.destroy()

    def get_menuitems( self ):
        items = []
        names_item = gtk.MenuItem( '_Toggle Task Names (light panel)' )
        items.append( names_item )
        names_item.connect( 'activate', self.toggle_headings )
        return items

    def get_toolitems( self ):
        return []
