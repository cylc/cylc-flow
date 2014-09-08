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
from TreeUpdater import TreeUpdater
from gcapture import gcapture_tmpfile
from util import EntryTempText
from warning_dialog import warning_dialog, info_dialog
from cylc.task_state import task_state
from cylc.gui.DotMaker import DotMaker
import cylc.TaskID

class ControlTree(object):
    """
Text Treeview suite control interface.
    """
    def __init__(self, cfg, updater, theme, dot_size, info_bar, get_right_click_menu,
                 log_colors, insert_task_popup ):

        self.cfg = cfg
        self.updater = updater
        self.theme = theme
        self.dot_size = dot_size
        self.info_bar = info_bar
        self.get_right_click_menu = get_right_click_menu
        self.log_colors = log_colors
        self.insert_task_popup = insert_task_popup

        self.gcapture_windows = []

        self.ttree_paths = {}  # Cache dict of tree paths & states, names.

    def get_control_widgets( self ):
        main_box = gtk.VBox()
        main_box.pack_start( self.treeview_widgets(), expand=True, fill=True )

        self.tfilt = ''

        self.t = TreeUpdater(
                self.cfg, self.updater, self.ttreeview, self.ttree_paths,
                self.info_bar, self.theme, self.dot_size
        )
        self.t.start()
        return main_box

    def visible_cb(self, model, iter ):
        # visibility result determined by state matching active check
        # buttons: set visible if model value NOT in filter_states;
        # and matching name against current name filter setting.
        # (state result: sres; name result: nres)

        point_string = model.get_value(iter, 0 )
        name = model.get_value(iter, 1)
        if name is None or point_string is None:
            return True
        name = re.sub( r'<.*?>', '', name )

        if point_string == name:
            # Cycle-time line (not state etc.)
            return True

         # Task or family.
        state = model.get_value(iter, 2 )
        if state is not None:
            state = re.sub( r'<.*?>', '', state )
        sres = state not in self.tfilter_states

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
        for subbox in self.tfilterbox.get_children():
            for box in subbox.get_children():
                try:
                    icon, cb = box.get_children()
                except (ValueError, AttributeError):
                    # ValueError: a null entry to line things up.
                    # AttributeError: filter_entry box (handled below).
                    pass
                else:
                    if not cb.get_active():
                        # sub '_' from button label keyboard mnemonics
                        self.tfilter_states.append( re.sub('_', '', cb.get_label()))
        self.tmodelfilter.refilter()

    def check_filter_entry( self, e ):
        ftext = self.filter_entry.get_text()
        try:
            re.compile(ftext)
        except re.error as exc:
            warning_dialog(
                "Bad filter regex: '%s': error: %s" % (ftext, exc)).warn()
            self.tfilt = ""
        else:
            self.tfilt = ftext
        self.tmodelfilter.refilter()

    def toggle_grouping( self, toggle_item ):
        """Toggle grouping by visualisation families."""
        group_on = toggle_item.get_active()
        if group_on == self.t.should_group_families:
            return False
        if group_on:
            if "text" in self.cfg.ungrouped_views:
                self.cfg.ungrouped_views.remove("text")
        elif "text" not in self.cfg.ungrouped_views:
            self.cfg.ungrouped_views.append("text")
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

        self.ttreestore = gtk.TreeStore(str, str, str, str, str, str, str, str, str, str, gtk.gdk.Pixbuf)
        self.tmodelfilter = self.ttreestore.filter_new()
        self.tmodelfilter.set_visible_func(self.visible_cb)
        self.tmodelsort = gtk.TreeModelSort(self.tmodelfilter)
        self.ttreeview = gtk.TreeView()
        self.ttreeview.set_rules_hint(True)
        self.ttreeview.set_model(self.tmodelsort)

        ts = self.ttreeview.get_selection()
        ts.set_mode( gtk.SELECTION_SINGLE )

        self.ttreeview.connect('button_press_event', self.on_treeview_button_pressed)
        headings = [
                None, 'task', 'state', 'host', 'Job ID', 'T-submit', 'T-start',
                'T-finish', 'dT-mean', 'latest message'
        ]

        for n in range(1, len(headings)):
            # Skip first column (cycle point)
            tvc = gtk.TreeViewColumn(headings[n])
            if n == 1:
                crp = gtk.CellRendererPixbuf()
                tvc.pack_start(crp, False)
                tvc.set_attributes(crp, pixbuf=10)
            cr = gtk.CellRendererText()
            tvc.pack_start(cr, True)
            if n == 7:
                tvc.set_attributes(cr, markup=n)
            else:
                tvc.set_attributes(cr, text=n)
            tvc.set_resizable(True)
            tvc.set_clickable(True)
            self.ttreeview.append_column(tvc)
            tvc.set_sort_column_id(n - 1)
            self.tmodelsort.set_sort_func(n - 1, self.sort_column, n - 1)
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.add(self.ttreeview)

        self.tfilterbox = gtk.VBox()
        subbox1 = gtk.HBox(homogeneous=True)
        subbox2 = gtk.HBox(homogeneous=True)
        self.tfilterbox.pack_start(subbox1)
        self.tfilterbox.pack_start(subbox2)

        self.tfilter_states = []

        dotm = DotMaker(self.theme, size='small')
        cnt = 0
        for st in task_state.legal:
            box = gtk.HBox()
            icon = dotm.get_image(st)
            cb = gtk.CheckButton(task_state.labels[st])
            tooltip = gtk.Tooltips()
            tooltip.enable()
            tooltip.set_tip(cb, "Filter by task state = %s" % st)
 
            box.pack_start(icon, expand=False)
            box.pack_start(cb, expand=False)
            cnt += 1
            if cnt > (len(task_state.legal) + 1)//2:
                subbox2.pack_start(box, expand=False, fill=True)
            else:
                subbox1.pack_start(box, expand=False, fill=True)
            if st in self.tfilter_states:
                cb.set_active(False)
            else:
                cb.set_active(True)
            cb.connect('toggled', self.check_tfilter_buttons)
        
        self.filter_entry = EntryTempText()
        self.filter_entry.set_width_chars(7)
        self.filter_entry.connect( "activate", self.check_filter_entry )
        self.filter_entry.set_temp_text( "filter" )
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip(self.filter_entry,
                "Filter by task name.\n"
                "Enter a sub-string or regex and hit Enter\n"
                "(to reset, clear the entry and hit Enter)")
        subbox2.pack_start(self.filter_entry)
        cnt += 1

        if cnt % 2 != 0:
            # subbox2 needs another entry to line things up.
            subbox2.pack_start(gtk.HBox(), expand=False, fill=True)

        filter_hbox = gtk.HBox()
        filter_hbox.pack_start(self.tfilterbox, True, True, 10)
        vbox = gtk.VBox()
        vbox.pack_start(sw, True)
        vbox.pack_end(filter_hbox, False)


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
        point_string = treemodel.get_value( iter, 0 )
        name = treemodel.get_value( iter, 1 )
        if point_string == name:
            # must have clicked on the top level point_string
            return

        task_id = cylc.TaskID.get( name, point_string )

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
        point_string1 = model.get_value( iter1 , 0 )
        point_string2 = model.get_value( iter2, 0 )
        if point_string1 != point_string2:
            # TODO ISO: worth a proper comparison here?
            if cols[col_num].get_sort_order() == gtk.SORT_DESCENDING:
                return cmp(point_string2, point_string1)
            return cmp(point_string1, point_string2)

        # Columns do not include the cycle point (0th col), so add 1.
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
        expand_button.set_label( "Expand" )
        self._set_tooltip( expand_button, "Tree View - Expand all" )
        expand_button.connect( 'clicked', lambda x: self.ttreeview.expand_all() )
        items.append( expand_button )

        collapse_button = gtk.ToolButton()
        image = gtk.image_new_from_stock( gtk.STOCK_REMOVE, gtk.ICON_SIZE_SMALL_TOOLBAR )
        collapse_button.set_icon_widget( image )
        collapse_button.set_label( "Collapse" )
        collapse_button.connect( 'clicked', lambda x: self.ttreeview.collapse_all() )
        self._set_tooltip( collapse_button, "Tree View - Collapse all" )
        items.append( collapse_button )

        self.group_toolbutton = gtk.ToggleToolButton()
        self.group_toolbutton.set_active( self.t.should_group_families )
        g_image = gtk.image_new_from_stock( 'group', gtk.ICON_SIZE_SMALL_TOOLBAR )
        self.group_toolbutton.set_icon_widget( g_image )
        self.group_toolbutton.set_label( "Group" )
        self.group_toolbutton.connect( 'toggled', self.toggle_grouping )
        self._set_tooltip( self.group_toolbutton, "Tree View - Click to group tasks by families" )
        items.append( self.group_toolbutton )

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
