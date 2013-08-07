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
from stateview import TreeUpdater
from gcapture import gcapture_tmpfile
from util import EntryTempText
from warning_dialog import warning_dialog, info_dialog
from cylc.task_state import task_state
from cylc.TaskID import TaskID

class ControlTree(object):
    """
Text Treeview suite control interface.
    """
    def __init__(self, cfg, updater, usercfg, info_bar, get_right_click_menu,
                 log_colors ):

        self.cfg = cfg
        self.updater = updater
        self.usercfg = usercfg
        self.info_bar = info_bar
        self.get_right_click_menu = get_right_click_menu
        self.log_colors = log_colors

        self.gcapture_windows = []

        self.ttree_paths = {}  # Cache dict of tree paths & states, names.

    def get_control_widgets( self ):
        main_box = gtk.VBox()
        main_box.pack_start( self.treeview_widgets(), expand=True, fill=True )
        
        self.tfilt = ''
        
        self.t = TreeUpdater( self.cfg, self.updater, self.ttreeview,
                              self.ttree_paths, self.info_bar, self.usercfg )
        self.t.start()
        return main_box

    def visible_cb(self, model, iter ):
        # visibility result determined by state matching active check
        # buttons: set visible if model value NOT in filter_states;
        # and matching name against current name filter setting.
        # (state result: sres; name result: nres)

        ctime = model.get_value(iter, 0 )
        name = model.get_value(iter, 1)
        if name is None or ctime is None:
            return True
        name = re.sub( r'<.*?>', '', name )

        if ctime == name:
            # Cycle-time line (not state etc.)
            return True

         # Task or family.
        state = model.get_value(iter, 2 ) 
        if state is not None:
            state = re.sub( r'<.*?>', '', state )
        sres = state not in self.tfilter_states

        try:
            if not self.tfilt:
                nres = True
            elif self.tfilt in name:
                # tfilt is any substring of name
                nres = True
            elif re.search( self.tfilt, name ):
                # full regex match
                nres = True
            else:
                nres = False
        except:
            warning_dialog( 'Bad filter regex? ' + self.tfilt ).warn()
            nres = False

        if model.iter_has_child( iter ):
            # Family.
            path = model.get_path( iter )

            sub_st = self.ttree_paths.get( path, {} ).get( 'states', [] )
            sres = sres or any([t not in self.tfilter_states for t in sub_st])

            if self.tfilt:
                sub_nm = self.ttree_paths.get( path, {} ).get( 'names', [] )
                nres = nres or any([self.tfilt in n for n in sub_nm])

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

    def toggle_grouping( self, toggle_item ):
        """Toggle grouping by visualisation families."""
        group_on = toggle_item.get_active()
        if group_on == self.t.should_group_families:
            return False
        self.t.should_group_families = group_on
        if isinstance( toggle_item, gtk.ToggleToolButton ):
            if group_on:
                tip_text = "Tree View - Click to ungroup families"
            else:
                tip_text = "Tree View - Click to group tasks by families"
            self._set_tooltip( toggle_item, tip_text )
            self.group_menu_item.set_active( group_on )
        else:
            if toggle_item != self.group_menu_item:
                self.group_menu_item.set_active( group_on )
            self.group_toolbutton.set_active( group_on )            
        self.t.update_gui()
        return False

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

        self.sort_col_num = 0

        self.ttreestore = gtk.TreeStore(str, str, str, str, str, str, str, str, gtk.gdk.Pixbuf )
        self.tmodelfilter = self.ttreestore.filter_new()
        self.tmodelfilter.set_visible_func(self.visible_cb)
        self.tmodelsort = gtk.TreeModelSort(self.tmodelfilter)
        self.ttreeview = gtk.TreeView()
        self.ttreeview.set_model(self.tmodelsort)

        ts = self.ttreeview.get_selection()
        ts.set_mode( gtk.SELECTION_SINGLE )

        self.ttreeview.connect( 'button_press_event', self.on_treeview_button_pressed )
        headings = [ None, 'task', 'state', 'message', 'Tsubmit', 'Tstart', 'mean dT', 'ETC' ]
        bkgcols  = [ None, None,  '#def',  '#fff',    '#def',    '#fff',   '#def',    '#fff']

        for n in range(1, len(headings)):
            # Skip first column (cycle time)
            cr = gtk.CellRendererText()
            tvc = gtk.TreeViewColumn( headings[n] )
            cr.set_property( 'cell-background', bkgcols[n] )
            if n == 2:
                crp = gtk.CellRendererPixbuf()
                tvc.pack_start( crp, False )
                tvc.set_attributes( crp, pixbuf=8 )
            tvc.pack_start( cr, True )
            tvc.set_attributes( cr, text=n )
            tvc.set_resizable(True)
            tvc.set_clickable(True)
         #   tvc.connect("clicked", self.change_sort_order, n - 1 )
            self.ttreeview.append_column(tvc)
            tvc.set_sort_column_id( n - 1 )
            self.tmodelsort.set_sort_func( n - 1, self.sort_column, n - 1 )
        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )
        sw.add( self.ttreeview )

        self.tfilterbox = gtk.VBox()
        subbox1 = gtk.HBox(homogeneous=True)
        subbox2 = gtk.HBox(homogeneous=True)
        self.tfilterbox.pack_start(subbox1)
        self.tfilterbox.pack_start(subbox2)

        self.tfilter_states = []

        cnt = 0
        for st in task_state.legal:
            b = gtk.CheckButton( task_state.labels[st] )
            cnt += 1
            if cnt > len(task_state.legal)/2:
                subbox2.pack_start(b)
            else:
                subbox1.pack_start(b)
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
        ctime = treemodel.get_value( iter, 0 )
        name = treemodel.get_value( iter, 1 )
        if ctime == name:
            # must have clicked on the top level ctime 
            return

        task_id = name + TaskID.DELIM + ctime

        is_fam = (name in self.t.descendants)

        menu = self.get_right_click_menu( task_id, task_is_family=is_fam )

        sep = gtk.SeparatorMenuItem()
        sep.show()
        menu.append( sep )

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

    def sort_column( self, model, iter1, iter2, col_num ):
        cols = self.ttreeview.get_columns()
        ctime1 = model.get_value( iter1 , 0 )
        ctime2 = model.get_value( iter2, 0 )
        if ctime1 != ctime2:
            if cols[col_num].get_sort_order() == gtk.SORT_DESCENDING:
                return cmp(ctime2, ctime1)
            return cmp(ctime1, ctime2)

        # Columns do not include the cycle time (0th col), so add 1.
        prop1 = model.get_value( iter1, col_num + 1 )
        prop2 = model.get_value( iter2, col_num + 1 )
        return cmp( prop1, prop2 )

    def change_sort_order( self, col, event=None, n=0 ):
        if hasattr(event, "button") and event.button != 1:
            return False
        cols = self.ttreeview.get_columns()
        self.sort_col_num = n
        if cols[n].get_sort_order() == gtk.SORT_ASCENDING:
            cols[n].set_sort_order( gtk.SORT_DESCENDING )
        else:
            cols[n].set_sort_order( gtk.SORT_ASCENDING )
        return False

    def on_popup_quit( self, b, lv, w ):
        lv.quit()
        self.quitters.remove( lv )
        w.destroy()

    def get_menuitems( self ):
        """Return the menu items specific to this view."""
        items = []
        autoex_item = gtk.CheckMenuItem( 'Toggle _Auto-Expand Tree' )
        autoex_item.set_active( self.t.autoexpand )
        items.append( autoex_item )
        autoex_item.connect( 'activate', self.toggle_autoexpand )

        self.group_menu_item = gtk.CheckMenuItem( 'Toggle _Family Grouping' )
        self.group_menu_item.set_active( self.t.should_group_families )
        items.append( self.group_menu_item )
        self.group_menu_item.connect( 'toggled', self.toggle_grouping )
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
        self._set_tooltip( expand_button, "Tree View - Expand all" )
        expand_button.connect( 'clicked', lambda x: self.ttreeview.expand_all() )
        items.append( expand_button )

        collapse_button = gtk.ToolButton()
        image = gtk.image_new_from_stock( gtk.STOCK_REMOVE, gtk.ICON_SIZE_SMALL_TOOLBAR )
        collapse_button.set_icon_widget( image )        
        collapse_button.connect( 'clicked', lambda x: self.ttreeview.collapse_all() )
        self._set_tooltip( collapse_button, "Tree View - Collapse all" )
        items.append( collapse_button )
     
        self.group_toolbutton = gtk.ToggleToolButton()
        self.group_toolbutton.set_active( self.t.should_group_families )
        g_image = gtk.image_new_from_stock( 'group', gtk.ICON_SIZE_SMALL_TOOLBAR )
        self.group_toolbutton.set_icon_widget( g_image )
        self.group_toolbutton.connect( 'toggled', self.toggle_grouping )
        self._set_tooltip( self.group_toolbutton, "Tree View - Click to group tasks by families" )
        items.append( self.group_toolbutton )

        self.filter_entry = EntryTempText()
        self.filter_entry.set_width_chars( 7 )  # Reduce width in toolbar
        self.filter_entry.connect( "activate", self.check_filter_entry )
        self.filter_entry.set_temp_text( "filter" )
        filter_toolitem = gtk.ToolItem()
        filter_toolitem.add(self.filter_entry)
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip(filter_toolitem, "Tree View - Filter tasks by name\n(enter a sub-string or regex)")
        items.append(filter_toolitem)

        return items

class StandaloneControlTreeApp( ControlTree ):
    def __init__(self, suite, owner, host, port ):
        gobject.threads_init()
        ControlTree.__init__(self, suite, owner, host, port )
 
    def quit_gcapture( self ):
        for gwindow in self.gcapture_windows:
            if not gwindow.quit_already:
                gwindow.quit( None, None )

    def delete_event(self, widget, event, data=None):
        self.quit_gcapture()
        ControlTree.delete_event( self, widget, event, data )
        gtk.main_quit()

    def click_exit( self, foo ):
        self.quit_gcapture()
        ControlTree.click_exit( self, foo )
        gtk.main_quit()
