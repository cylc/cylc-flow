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
from stateview import tupdater
from gcapture import gcapture_tmpfile

class ControlTree(object):
    """
Text Treeview suite control interface.
    """
    def __init__(self, cfg, suiterc, info_bar, get_right_click_menu, log_colors):

        self.cfg = cfg
        self.suiterc = suiterc
        self.info_bar = info_bar
        self.get_right_click_menu = get_right_click_menu
        self.log_colors = log_colors

        self.gcapture_windows = []

    def get_control_widgets( self ):
        # Load task list from suite config.
        ### TO DO: For suites that are already running, or for dynamically
        ### updating the viewed task list, we can retrieve the task list
        ### (etc.) from the suite's remote state summary object.
        self.task_list = self.suiterc.get_task_name_list()

        main_box = gtk.VBox()
        main_box.pack_start( self.treeview_widgets(), expand=True, fill=True )
        
        self.tfilt = ''
        
        self.t = tupdater( self.cfg, self.ttreeview,
                           self.task_list, self.info_bar )
        self.t.start()
        return main_box

    def visible_cb(self, model, iter ):
        # visibility determined by state matching active toggle buttons
        # set visible if model value NOT in filter_states
        state = model.get_value(iter, 1 ) 
        # strip formatting tags
        if state:
            state = re.sub( r'<.*?>', '', state )
            sres = state not in self.tfilter_states
            # AND if taskname matches filter entry text
            if self.tfilt == '':
                nres = True
            else:
                tname = model.get_value(iter, 0)
                tname = re.sub( r'<.*?>', '', tname )
                if re.search( self.tfilt, tname ):
                    nres = True
                else:
                    nres = False
        else:
            # this must be a cycle-time line (not state etc.)
            sres = True
            nres = True
        return sres and nres

    def check_tfilter_buttons(self, tb):
        del self.tfilter_states[:]
        for b in self.tfilterbox.get_children():
            if not b.get_active():
                # sub '_' from button label keyboard mnemonics
                self.tfilter_states.append( re.sub('_', '', b.get_label()))
        self.tmodelfilter.refilter()

    def check_filter_entry( self, e ):
        ftxt = self.filter_entry.get_text()
        self.tfilt = self.filter_entry.get_text()
        self.tmodelfilter.refilter()

    def stop(self):
        self.t.quit = True

    def toggle_autoexpand( self, w ):
        self.t.autoexpand = not self.t.autoexpand

    def treeview_widgets( self ):
        # Treeview of current suite state, with filtering and sorting.
        # sorting is handled somewhat manually because the simple method 
        # of interposing a TreeModelSort at the top:
        #   treestore = gtk.TreeStore(str, ...)
        #   tms = gtk.TreeModelSort( treestore )   #\ 
        #   tmf = tms.filter_new()                 #-- or other way round?
        #   tv = gtk.TreeView()
        #   tv.set_model(tms)
        # failed to produce correct results (the data displayed was not 
        # consistently what should have been displayed given the
        # filtering in use) although the exact same code worked for a
        # liststore.

        self.ttreestore = gtk.TreeStore(str, str, str, str, str, str, str )
        self.tmodelfilter = self.ttreestore.filter_new()
        self.tmodelfilter.set_visible_func(self.visible_cb)
        self.ttreeview = gtk.TreeView()
        self.ttreeview.set_model(self.tmodelfilter)

        ts = self.ttreeview.get_selection()
        ts.set_mode( gtk.SELECTION_SINGLE )

        self.ttreeview.connect( 'button_press_event', self.on_treeview_button_pressed )

        headings = ['task', 'state', 'message', 'Tsubmit', 'Tstart', 'mean dT', 'ETC' ]
        bkgcols  = [ None,  '#def',  '#fff',    '#def',    '#fff',   '#def',    '#fff']
        for n in range(len(headings)):
            cr = gtk.CellRendererText()
            cr.set_property( 'cell-background', bkgcols[n] )
            #tvc = gtk.TreeViewColumn( headings[n], cr, text=n )
            tvc = gtk.TreeViewColumn( headings[n], cr, markup=n )
            tvc.set_resizable(True)
            if n == 0:
                # allow click sorting only on first column (cycle time
                # and task name) as I don't understand the effect of
                # sorting on other columns in a treeview (it doesn't
                # seem to work as expected).
                tvc.set_clickable(True)
                tvc.connect("clicked", self.rearrange, n )
                tvc.set_sort_order(gtk.SORT_ASCENDING)
                tvc.set_sort_indicator(True)
                self.ttreestore.set_sort_column_id(n, gtk.SORT_ASCENDING ) 
            self.ttreeview.append_column(tvc)
 
        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )
        sw.add( self.ttreeview )

        self.tfilterbox = gtk.HBox()

        # allow filtering out of 'succeeded' and 'waiting'
        all_states = [ 'waiting', 'submitted', 'running', 'succeeded', 'failed', 'held', 'runahead', 'queued' ]
        labels = {}
        labels[ 'waiting'   ] = '_waiting'
        labels[ 'submitted' ] = 's_ubmitted'
        labels[ 'running'   ] = '_running'
        labels[ 'succeeded' ] = 'su_cceeded'
        labels[ 'failed'    ] = 'f_ailed'
        labels[ 'held'      ] = '_held'
        labels[ 'runahead'  ] = '_runahead'
        labels[ 'queued'   ] = '_queued'
  
        # initially filter out 'succeeded' and 'waiting' tasks
        self.tfilter_states = [ 'waiting', 'succeeded' ]

        for st in all_states:
            b = gtk.CheckButton( labels[st] )
            self.tfilterbox.pack_start(b)
            if st in self.tfilter_states:
                b.set_active(False)
            else:
                b.set_active(True)
            b.connect('toggled', self.check_tfilter_buttons)

        ahbox = gtk.HBox()
        ahbox.pack_start( self.tfilterbox, True)

        vbox = gtk.VBox()
        vbox.pack_start( sw, True )
        vbox.pack_end( ahbox, False )

        return vbox

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

        menu = self.get_right_click_menu( task_id )
        menu.popup( None, None, None, event.button, event.time )

        # TO DO: popup menus are not automatically destroyed and can be
        # reused if saved; however, we need to reconstruct or at least
        # alter ours dynamically => should destroy after each use to
        # prevent a memory leak? But I'm not sure how to do this as yet.)

        return True

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
        """Return the menu items specific to this view."""
        items = []
        autoex_item = gtk.MenuItem( 'Toggle _Auto-Expand Tree' )
        items.append( autoex_item )
        autoex_item.connect( 'activate', self.toggle_autoexpand )
        return items

    def _set_tooltip( self, widget, tip_text ):
        # Convenience function to add hover over text to a widget.
        tip = gtk.Tooltips()
        tip.enable()
        tip.set_tip( widget, tip_text )

    def get_toolitems( self ):
        """Return the tool bar items specific to this view."""
        items = []

        expand_button = gtk.ToolButton()
        image = gtk.image_new_from_stock( gtk.STOCK_ADD, gtk.ICON_SIZE_SMALL_TOOLBAR )
        expand_button.set_icon_widget( image )
        self._set_tooltip( expand_button, "Expand all" )
        expand_button.connect( 'clicked', lambda x: self.ttreeview.expand_all() )
        items.append( expand_button )

        collapse_button = gtk.ToolButton()
        image = gtk.image_new_from_stock( gtk.STOCK_REMOVE, gtk.ICON_SIZE_SMALL_TOOLBAR )
        collapse_button.set_icon_widget( image )        
        collapse_button.connect( 'clicked', lambda x: self.ttreeview.collapse_all() )
        self._set_tooltip( collapse_button, "Collapse all" )
        items.append( collapse_button )
     
        self.filter_entry = gtk.Entry()
        self.filter_entry.set_width_chars( 10 )  # Reduce width in toolbar
        self.filter_entry.connect( "activate", self.check_filter_entry )
        filter_toolitem = gtk.ToolItem()
        filter_toolitem.add(self.filter_entry)
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip(filter_toolitem, "Filter tasks by name")
        items.append(filter_toolitem)
        
        return items
