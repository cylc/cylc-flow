#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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
import gobject
from updater_tree import TreeUpdater
from cylc.task_id import TaskID
from isodatetime.parsers import DurationParser


class ControlTree(object):
    """Text Treeview suite control interface."""
    headings = [
        None, 'task', 'state', 'host', 'job system', 'job ID', 'T-submit',
        'T-start', 'T-finish', 'dT-mean', 'latest message',
    ]

    def __init__(self, cfg, updater, theme, dot_size, info_bar,
                 get_right_click_menu, log_colors, insert_task_popup):

        self.cfg = cfg
        self.updater = updater
        self.theme = theme
        self.dot_size = dot_size
        self.info_bar = info_bar
        self.get_right_click_menu = get_right_click_menu
        self.log_colors = log_colors
        self.insert_task_popup = insert_task_popup
        self.interval_parser = DurationParser()

        self.gcapture_windows = []

        self.ttree_paths = {}  # Cache dict of tree paths & states, names.

    def get_control_widgets(self):
        main_box = gtk.VBox()
        main_box.pack_start(self.treeview_widgets(), expand=True, fill=True)

        self.t = TreeUpdater(
            self.cfg, self.updater, self.ttreeview, self.ttree_paths,
            self.info_bar, self.theme, self.dot_size
        )
        self.t.start()
        return main_box

    def toggle_grouping(self, toggle_item):
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
        if isinstance(toggle_item, gtk.ToggleToolButton):
            if group_on:
                tip_text = "Tree View - Click to ungroup families"
            else:
                tip_text = "Tree View - Click to group tasks by families"
            self._set_tooltip(toggle_item, tip_text)
            self.group_menu_item.set_active(group_on)
        else:
            if toggle_item != self.group_menu_item:
                self.group_menu_item.set_active(group_on)
            self.group_toolbutton.set_active(group_on)
        self.t.update_gui()
        return False

    def stop(self):
        self.t.quit = True

    def toggle_autoexpand(self, w):
        self.t.autoexpand = not self.t.autoexpand

    def treeview_widgets(self):
        self.sort_col_num = 0
        self.ttreestore = gtk.TreeStore(
            str, str, str, str, str, str, str, str, str, str, str,
            gtk.gdk.Pixbuf, int)
        self.ttreeview = gtk.TreeView()
        self.ttreeview.set_rules_hint(True)
        # TODO - REMOVE FILTER HERE?
        self.tmodelfilter = self.ttreestore.filter_new()
        self.tmodelsort = gtk.TreeModelSort(self.tmodelfilter)
        self.ttreeview.set_model(self.tmodelsort)

        # multiple selection
        ts = self.ttreeview.get_selection()
        self.ttreeview.set_rubber_banding(True)
        if ts:
            ts.set_mode(gtk.SELECTION_MULTIPLE)

        self.ttreeview.connect(
            'button_press_event', self.on_treeview_button_pressed)

        for n in range(1, len(ControlTree.headings)):
            # Skip first column (cycle point)
            tvc = gtk.TreeViewColumn(ControlTree.headings[n])
            if n == 1:
                crp = gtk.CellRendererPixbuf()
                tvc.pack_start(crp, False)
                tvc.set_attributes(crp, pixbuf=11)
            if n == 8:
                # Pack in progress and text cell renderers.
                prog_cr = gtk.CellRendererProgress()
                tvc.pack_start(prog_cr, True)
                tvc.set_cell_data_func(prog_cr, self._set_cell_text_time, n)
            cr = gtk.CellRendererText()
            tvc.pack_start(cr, True)
            if n == 6 or n == 7 or n == 8:
                tvc.set_cell_data_func(cr, self._set_cell_text_time, n)
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

        vbox = gtk.VBox()
        vbox.pack_start(sw, True)

        return vbox

    def on_treeview_button_pressed(self, treeview, event):
        # DISPLAY MENU ONLY ON RIGHT CLICK ONLY
        if event.button != 3:
            return False

        # If clicking on a task that is not selected, set the selection to be
        # that task.
        x = int(event.x)
        y = int(event.y)
        pth = treeview.get_path_at_pos(x, y)

        if pth is None:
            return False

        treeview.grab_focus()
        path, col = pth[:2]
        tvte = TreeViewTaskExtractor(treeview)

        if path not in (row[0] for row in tvte.get_selected_rows()):
            treeview.set_cursor(path, col, 0)

        # Populate lists of task info from the selected tasks.
        task_ids = []
        t_states = []
        task_is_family = []  # List of boolean values.
        for task in tvte.get_selected_tasks():
            # get_selected_tasks() does not return tasks if their parent node
            # is also returned, i.e. no duplicates.
            point_string, name = task

            if point_string == name:
                name = 'root'

            task_id = TaskID.get(name, point_string)
            task_ids.append(task_id)
            is_fam = (name in self.t.descendants)
            task_is_family.append(is_fam)
            if is_fam:
                if task_id not in self.t.fam_state_summary:
                    return False
                t_states.append(self.t.fam_state_summary[task_id]['state'])
            else:
                if task_id not in self.t.state_summary:
                    return False
                t_states.append(self.t.state_summary[task_id]['state'])

        menu = self.get_right_click_menu(task_ids, t_states,
                                         task_is_family=task_is_family)

        sep = gtk.SeparatorMenuItem()
        sep.show()
        menu.append(sep)

        group_item = gtk.CheckMenuItem('Toggle Family Grouping')
        group_item.set_active(self.t.should_group_families)
        menu.append(group_item)
        group_item.connect('toggled', self.toggle_grouping)
        group_item.show()

        menu.popup(None, None, None, event.button, event.time)

        # TODO - popup menus are not automatically destroyed and can be
        # reused if saved; however, we need to reconstruct or at least
        # alter ours dynamically => should destroy after each use to
        # prevent a memory leak? But I'm not sure how to do this as yet.)

        return True

    def sort_by_column(self, col_name=None, col_no=None, ascending=True):
        """Sort this ControlTree by the column selected by the string
        col_name OR by the index col_no."""
        if col_name is not None and col_name in ControlTree.headings:
            col_no = ControlTree.headings.index(col_name)
        if col_no is not None:
            self.sort_col_num = col_no
            cols = self.ttreeview.get_columns()
            order = gtk.SORT_ASCENDING if ascending else gtk.SORT_DESCENDING
            cols[col_no].set_sort_order(order)
            self.tmodelsort.set_sort_column_id(col_no - 1, order)

    def sort_column(self, model, iter1, iter2, col_num):
        cols = self.ttreeview.get_columns()
        point_string1 = model.get_value(iter1, 0)
        point_string2 = model.get_value(iter2, 0)
        if point_string1 != point_string2:
            # TODO ISO: worth a proper comparison here?
            if cols[col_num].get_sort_order() == gtk.SORT_DESCENDING:
                return cmp(point_string2, point_string1)
            return cmp(point_string1, point_string2)

        # Columns do not include the cycle point (0th col), so add 1.
        if (col_num + 1) == 9:
            prop1 = (model.get_value(iter1, col_num + 1))
            prop2 = (model.get_value(iter2, col_num + 1))
            prop1 = self._get_interval_in_seconds(prop1)
            prop2 = self._get_interval_in_seconds(prop2)
        else:
            prop1 = model.get_value(iter1, col_num + 1)
            prop2 = model.get_value(iter2, col_num + 1)
        return cmp(prop1, prop2)

    def _get_interval_in_seconds(self, val):
        """Convert the IOS 8601 date/time to seconds."""
        if val == "*" or val == "":
            secsout = val
        else:
            interval = self.interval_parser.parse(val)
            seconds = interval.get_seconds()
            secsout = seconds
        return secsout

    def change_sort_order(self, col, event=None, n=0):
        if hasattr(event, "button") and event.button != 1:
            return False
        cols = self.ttreeview.get_columns()
        self.sort_col_num = n
        if cols[n].get_sort_order() == gtk.SORT_ASCENDING:
            cols[n].set_sort_order(gtk.SORT_DESCENDING)
        else:
            cols[n].set_sort_order(gtk.SORT_ASCENDING)
        return False

    def on_popup_quit(self, b, lv, w):
        lv.quit()
        self.quitters.remove(lv)
        w.destroy()

    def refresh(self):
        self.t.update_gui()
        self.t.action_required = True

    def get_menuitems(self):
        """Return the menu items specific to this view."""
        items = []
        autoex_item = gtk.CheckMenuItem('Toggle _Auto-Expand Tree')
        autoex_item.set_active(self.t.autoexpand)
        items.append(autoex_item)
        autoex_item.connect('activate', self.toggle_autoexpand)

        self.group_menu_item = gtk.CheckMenuItem('Toggle _Family Grouping')
        self.group_menu_item.set_active(self.t.should_group_families)
        items.append(self.group_menu_item)
        self.group_menu_item.connect('toggled', self.toggle_grouping)
        return items

    def _set_tooltip(self, widget, tip_text):
        """Convenience function to add hover over text to a widget."""
        tip = gtk.Tooltips()
        tip.enable()
        tip.set_tip(widget, tip_text)

    def _set_cell_text_time(self, column, cell, model, iter_, n):
        """Remove the date part if it matches the last update date."""
        date_time_string = model.get_value(iter_, n)
        if "T" in self.updater.update_time_str:
            last_update_date = self.updater.update_time_str.split("T")[0]
            date_time_string = date_time_string.replace(
                last_update_date + "T", "", 1)
        if n == 8:
            # Progress bar for estimated completion time.
            if isinstance(cell, gtk.CellRendererText):
                if date_time_string.endswith("?"):
                    # Task running -show progress bar instead.
                    cell.set_property('visible', False)
                else:
                    # Task not running - just show text
                    cell.set_property('visible', True)
                    cell.set_property('text', date_time_string)
            if isinstance(cell, gtk.CellRendererProgress):
                if date_time_string.endswith("?"):
                    # Task running -show progress bar to estimated finish time.
                    cell.set_property('visible', True)
                    percent = model.get_value(iter_, 12)
                    cell.set_property('value', percent)
                else:
                    # Task not running - show text cell instead.
                    cell.set_property('visible', False)
                    cell.set_property('value', 0)
        cell.set_property("text", date_time_string)

    def get_toolitems(self):
        """Return the tool bar items specific to this view."""
        items = []

        expand_button = gtk.ToolButton()
        image = gtk.image_new_from_stock(
            gtk.STOCK_ADD, gtk.ICON_SIZE_SMALL_TOOLBAR)
        expand_button.set_icon_widget(image)
        expand_button.set_label("Expand")
        self._set_tooltip(expand_button, "Tree View - Expand all")
        expand_button.connect('clicked', lambda x: self.ttreeview.expand_all())
        items.append(expand_button)

        collapse_button = gtk.ToolButton()
        image = gtk.image_new_from_stock(
            gtk.STOCK_REMOVE, gtk.ICON_SIZE_SMALL_TOOLBAR)
        collapse_button.set_icon_widget(image)
        collapse_button.set_label("Collapse")
        collapse_button.connect(
            'clicked', lambda x: self.ttreeview.collapse_all())
        self._set_tooltip(collapse_button, "Tree View - Collapse all")
        items.append(collapse_button)

        self.group_toolbutton = gtk.ToggleToolButton()
        self.group_toolbutton.set_active(self.t.should_group_families)
        g_image = gtk.image_new_from_stock(
            'group', gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.group_toolbutton.set_icon_widget(g_image)
        self.group_toolbutton.set_label("Group")
        self.group_toolbutton.connect('toggled', self.toggle_grouping)
        self._set_tooltip(
            self.group_toolbutton,
            "Tree View - Click to group tasks by families")
        items.append(self.group_toolbutton)

        return items


class StandaloneControlTreeApp(ControlTree):
    def __init__(self, suite, owner, host, port):
        gobject.threads_init()
        ControlTree.__init__(self, suite, owner, host, port)

    def quit_gcapture(self):
        for gwindow in self.gcapture_windows:
            if not gwindow.quit_already:
                gwindow.quit(None, None)

    def delete_event(self, widget, event, data=None):
        self.quit_gcapture()
        ControlTree.delete_event(self, widget, event, data)
        gtk.main_quit()

    def click_exit(self, foo):
        self.quit_gcapture()
        ControlTree.click_exit(self, foo)
        gtk.main_quit()


class TreeViewTaskExtractor(object):
    """Extracts information from the rows currently selected in the provided
    treeview."""

    def __init__(self, treeview):
        self.treeview = treeview

    def get_selected_tasks(self):
        rows = self.get_selected_rows()
        tree = self._make_tree_from_rows(rows)
        tree = self._prune_tree(tree)
        return self._flatten_list(tree)

    def get_selected_rows(self):
        """Returns a list of rows that are currently selected in the provided
        treeview. Rows are returned in the form (path, col1, col2)"""
        ret = []
        selection = self.treeview.get_selection()
        if selection:
            model, rows = selection.get_selected_rows()
            rows.sort()
            for row in rows:
                _iter = model.get_iter(row)
                path = model.get_path(_iter)
                ret.append((
                    path, model.get_value(_iter, 0),
                    model.get_value(_iter, 1)))
        return ret

    def _make_tree_from_rows(self, rows):
        """Convert list of rows to a tree.
        Rows are denoted with the entry 'node' which holds the value
        (row1, row2)."""
        tree = {}
        for task in rows:
            path, row1, row2 = task
            temp = tree
            for index, key in enumerate(path):
                if index == len(path) - 1:
                    temp[key] = {'node': (row1, row2)}
                if key not in temp:
                    temp[key] = {}
                temp = temp[key]
        return tree

    def _prune_tree(self, tree_dict):
        """Returns a list of nodes which have no parent node above them."""
        if 'node' in tree_dict:
            return tree_dict['node']
        else:
            ret = []
            for key in tree_dict:
                ret.append(self._prune_tree(tree_dict[key]))
            return ret

    def _flatten_list(self, tree_list):
        """Reduces irregular, multi-dimensional lists to a list containing all
        its items."""
        ret = []
        for item in tree_list:
            if type(item) is list:
                ret.extend(self._flatten_list(item))
            else:
                ret.append(item)
        return ret
