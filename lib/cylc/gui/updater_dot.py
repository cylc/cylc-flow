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

from copy import deepcopy
import gobject
import gtk
import threading
from time import sleep

import warnings
warnings.filterwarnings('ignore', '^.*was not found when attempting to ' +
                        'remove it', Warning)

from cylc.task_id import TaskID
from cylc.gui.dot_maker import DotMaker
from cylc.gui.util import get_id_summary


class DotUpdater(threading.Thread):

    RIGHT_ARROW = u'\u25b7'  # Unicode enpty triangle facing right.
    DOWN_ARROW = u'\u25bd'  # Unicode enpty triangle facing down.
    INDENT = 5  # Number of spaces to indent nested items in transpose view.

    def __init__(self, cfg, updater, treeview, info_bar, theme, dot_size):

        super(DotUpdater, self).__init__()

        self.quit = False
        self.cleared = True
        self.action_required = False
        self.autoexpand = True
        self.should_hide_headings = False
        self.should_group_families = ("dot" not in cfg.ungrouped_views)
        self.should_transpose_view = False
        self.is_transposed = False
        self.defn_order_on = True

        self.cfg = cfg
        self.updater = updater
        self.theme = theme
        self.info_bar = info_bar
        self.last_update_time = None
        self.state_summary = {}
        self.fam_state_summary = {}
        self.ancestors_pruned = {}
        self.descendants = []
        self.point_strings = []

        self.led_headings = []
        self.led_treeview = treeview
        self.led_treestore = treeview.get_model()
        self._prev_tooltip_task_id = None
        if hasattr(self.led_treeview, "set_has_tooltip"):
            self.led_treeview.set_has_tooltip(True)
            try:
                self.led_treeview.connect('query-tooltip',
                                          self.on_query_tooltip)
            except TypeError:
                # Lower PyGTK version.
                pass

        self.task_list = []
        self.family_tree = {}
        self.expanded_rows = []
        self.selected_rows = []

        # generate task state icons
        dotm = DotMaker(theme, size=dot_size)
        self.dots = dotm.get_dots()

    def _set_tooltip(self, widget, tip_text):
        tip = gtk.Tooltips()
        tip.enable()
        tip.set_tip(widget, tip_text)

    def clear_gui(self):
        """Clear the LED tree store."""
        self.led_treestore.clear()
        # gtk idle functions must return false or will be called multiple times
        return False

    def update(self):
        """Update data using data from self.updater."""
        if not self.updater.connected:
            if not self.cleared:
                gobject.idle_add(self.clear_gui)
                self.cleared = True
            return False
        self.cleared = False

        if not self.action_required and (
                self.last_update_time is not None and
                self.last_update_time >= self.updater.last_update_time):
            return False

        self.last_update_time = self.updater.last_update_time
        self.updater.no_update_event.set()

        self.state_summary = deepcopy(self.updater.state_summary)
        self.fam_state_summary = deepcopy(self.updater.fam_state_summary)
        self.ancestors_pruned = deepcopy(self.updater.ancestors_pruned)
        self.descendants = deepcopy(self.updater.descendants)

        self.updater.no_update_event.clear()

        self.point_strings = []
        for id_ in self.state_summary:
            point_string = TaskID.split(id_)[1]
            if point_string not in self.point_strings:
                self.point_strings.append(point_string)
        try:
            self.point_strings.sort(key=int)
        except (TypeError, ValueError):
            # iso cycle points
            self.point_strings.sort()

        use_def_order = (
            self.cfg.use_defn_order and self.updater.ns_defn_order and
            self.defn_order_on)

        if not self.should_group_families:
            # Display the full task list.
            self.task_list = deepcopy(self.updater.task_list)

            if use_def_order:
                self.task_list = [task for task in self.updater.ns_defn_order
                                  if task in self.task_list]
            else:
                self.task_list.sort()
        else:
            self.family_tree = {}
            self.task_list = deepcopy(self.updater.task_list)

            if use_def_order:
                self.task_list = [task for task in self.updater.ns_defn_order
                                  if task in self.task_list]
            else:
                self.task_list.sort()

            for task in self.task_list:
                # Generate dict of families and their associated tasks.
                item = self.ancestors_pruned[task][-2]
                if item not in self.task_list:
                    if item not in self.family_tree:
                        self.family_tree[item] = []
                    self.family_tree[item].append(task)

            for heading, tasks in self.family_tree.iteritems():
                # Place associated tasks after headers.
                ind = min(self.task_list.index(task) for task in tasks)
                for task in tasks:
                    if task in self.task_list:
                        self.task_list.remove(task)
                self.task_list = (self.task_list[0:ind] + [heading] + tasks +
                                  self.task_list[ind:])
        return True

    def set_led_headings(self):
        if not self.should_transpose_view:
            new_headings = ['Name'] + self.point_strings
        else:
            new_headings = ['Point'] + self.task_list
        if new_headings == self.led_headings:
            return False
        self.led_headings = new_headings

        # Get a list of tasks belonging to families.
        if self.family_tree:
            all_sub_tasks = reduce(
                lambda x, y: x + y,
                self.family_tree.values()
            )
        else:
            all_sub_tasks = []

        if self.should_transpose_view:
            self.led_treeview.set_headers_clickable(True)

        tvcs = self.led_treeview.get_columns()
        labels = []
        families = []
        for n in range(1, len(self.led_headings)):
            text = self.led_headings[n]
            tip = self.led_headings[n]
            if self.should_hide_headings:
                text = "..."
            label = gtk.Label(text)
            label.set_use_underline(False)
            label.set_angle(90)
            label.show()
            labels.append(label)
            label_box = gtk.VBox()

            # Functionality for collapsed families in transpose view.
            if self.should_transpose_view:
                self._set_heading_attributes(tvcs[n], label, text,
                                             all_sub_tasks)

            label_box.pack_start(label, expand=False, fill=False)
            label_box.show()
            self._set_tooltip(label_box, tip)
            tvcs[n].set_widget(label_box)

            if self.should_transpose_view and text in self.family_tree:
                families.append(n)

        max_pixel_length = -1
        for label in labels:
            x = (label.get_layout().get_size())[0]
            if x > max_pixel_length:
                max_pixel_length = x
        for label in labels:
            while label.get_layout().get_size()[0] < max_pixel_length:
                label.set_text(label.get_text() + ' ')

        # Pre-collapse all families.
        for family in families:
            self.transposed_label_click(None, family)

    def _set_heading_attributes(self, col, label, text, all_sub_tasks):
        """Sets the attributes required for folding columns."""
        # Clear previously set attributes.
        for attribute in ['gcylc_parent_to', 'gcylc_task', 'gcylc_folded',
                          'gcylc_heading_label', 'gcylc_represents_task']:
            if hasattr(col, attribute):
                delattr(col, attribute)
        col.set_visible(True)

        # Set new attributes.
        if self.should_group_families and (text in self.family_tree or
                                           text in all_sub_tasks):
            if text in self.family_tree:
                # Heading is a family.
                label.set_text(self.RIGHT_ARROW + " " + text)
                col.gcylc_parent_to = self.family_tree[text]
                col.gcylc_task = text
                col.gcylc_folded = text in self.expanded_rows
                col.gcylc_heading_label = label
            elif text in all_sub_tasks:
                # Heading is the child of a family.
                col.gcylc_represents_task = text
                label.set_text(' ' * self.INDENT + text)

    def transposed_label_click(self, widget, heading):
        """Click handler for column headings in transposed mode.
        Responsible for folding / unfolding family sections."""
        column = self.led_treeview.get_column(heading)
        if not hasattr(column, 'gcylc_folded'):
            # Column is not foldable.
            return False

        column.gcylc_folded = not column.gcylc_folded
        if hasattr(column, 'gcylc_parent_to'):
            # Column is for a family.
            for col in self.led_treeview.get_columns():
                if hasattr(col, 'gcylc_represents_task'):
                    if col.gcylc_represents_task in column.gcylc_parent_to:
                        col.set_visible(not column.gcylc_folded)

        # Toggle folding arrows.
        if column.gcylc_folded:
            if hasattr(column, 'gcylc_heading_label'):
                column.gcylc_heading_label.set_text(
                    self.RIGHT_ARROW +
                    column.gcylc_heading_label.get_text()[3:]
                )
        else:
            if hasattr(column, 'gcylc_heading_label'):
                column.gcylc_heading_label.set_text(
                    self.DOWN_ARROW +
                    column.gcylc_heading_label.get_text()[3:]
                )

    def _get_expanded_rows(self):
        """Updates list of currently expanded rows (or columns in transpose
        mode."""
        self.expanded_rows = []
        if self.is_transposed:
            for column in self.led_treeview.get_columns():
                if hasattr(column, 'gcylc_folded'):
                    if not column.gcylc_folded:
                        self.expanded_rows.append(column.gcylc_task)
        else:
            rows = []
            self.led_treeview.map_expanded_rows(
                lambda treeview, path, data: rows.append(path),
                None
            )
            for row in rows:
                self.expanded_rows.append(self.led_treestore.get_value(
                    self.led_treestore.get_iter(row), 0))

    def _get_selected_rows(self):
        """Make a note of currently selected rows.

        Populates self.selected_rows with the value of the first column of all
        selected rows.

        """
        self.selected_rows = []
        selection = self.led_treeview.get_selection()
        if selection:
            selected_paths = selection.get_selected_rows()[1]
            model = self.led_treeview.get_model()
            for path in selected_paths:
                self.selected_rows.append(
                    model.get_value(model.get_iter(path), 0))

    @staticmethod
    def _reselect_row(model, _, iter_, (selection, selected_rows,)):
        """Select rows if they are referenced by selected_rows.

        If the value of the first column of a row matches a value in
        `selected_rows` then `selection` will be updated to include this row.

        Warning: This method has not been tested with multiple selection.

        """
        if model.get_value(iter_, 0) in selected_rows:
            selection.select_iter(iter_)

    def _set_selected_rows(self):
        """Re-Selects previously selected rows where possible.

        Uses self.selected_rows to determine which rows to select.

        """
        selection = self.led_treeview.get_selection()
        if selection:
            selection.unselect_all()
            model = self.led_treeview.get_model()
            model.foreach(self._reselect_row, (selection, self.selected_rows,))

    def ledview_widgets(self):
        self._get_expanded_rows()  # Make a note of expanded rows.
        self._get_selected_rows()  # Make a note of selected rows.

        if not self.should_transpose_view:
            types = [str] + [gtk.gdk.Pixbuf] * len(self.point_strings)
            num_new_columns = len(types)
        else:
            types = [str] + [gtk.gdk.Pixbuf] * len(self.task_list) + [str]
            num_new_columns = 1 + len(self.task_list)
        new_led_treestore = gtk.TreeStore(*types)
        old_types = []
        for i in range(self.led_treestore.get_n_columns()):
            old_types.append(self.led_treestore.get_column_type(i))
        new_types = []
        for i in range(new_led_treestore.get_n_columns()):
            new_types.append(new_led_treestore.get_column_type(i))
        treeview_has_content = bool(len(self.led_treeview.get_columns()))

        if treeview_has_content and old_types == new_types:
            self.set_led_headings()
            self.led_treestore.clear()
            self.is_transposed = self.should_transpose_view
            return False

        self.led_treestore = new_led_treestore

        if (treeview_has_content and
                self.is_transposed == self.should_transpose_view):
            tvcs_for_removal = self.led_treeview.get_columns()[
                num_new_columns:]

            for tvc in tvcs_for_removal:
                self.led_treeview.remove_column(tvc)

            self.led_treeview.set_model(self.led_treestore)
            num_columns = len(self.led_treeview.get_columns())
            for model_col_num in range(num_columns, num_new_columns):
                # Add newly-needed columns.
                cr = gtk.CellRendererPixbuf()
                cr.set_property('xalign', 0)
                tvc = gtk.TreeViewColumn("")
                tvc.connect(
                    'clicked', self.transposed_label_click, model_col_num)
                tvc.pack_end(cr, True)
                tvc.set_attributes(cr, pixbuf=model_col_num)
                self.led_treeview.append_column(tvc)
            self.set_led_headings()
            return False

        tvcs = self.led_treeview.get_columns()
        for tvc in tvcs:
            self.led_treeview.remove_column(tvc)

        self.led_treeview.set_model(self.led_treestore)

        if not self.should_transpose_view:
            tvc = gtk.TreeViewColumn('Name')
        else:
            tvc = gtk.TreeViewColumn('Point')

        cr = gtk.CellRendererText()
        tvc.pack_start(cr, False)
        tvc.set_attributes(cr, text=0)

        self.led_treeview.append_column(tvc)

        if not self.should_transpose_view:
            data_range = range(1, len(self.point_strings) + 1)
        else:
            data_range = range(1, len(self.task_list) + 1)

        for n in data_range:
            cr = gtk.CellRendererPixbuf()
            cr.set_property('xalign', 0)
            tvc = gtk.TreeViewColumn("")
            tvc.pack_end(cr, True)
            tvc.set_attributes(cr, pixbuf=n)
            self.led_treeview.append_column(tvc)
            if self.should_transpose_view:
                tvc.connect('clicked', self.transposed_label_click, n)
        self.set_led_headings()
        self.is_transposed = self.should_transpose_view

    def on_query_tooltip(self, widget, x, y, kbd_ctx, tooltip):
        """Handle a tooltip creation request."""
        tip_context = self.led_treeview.get_tooltip_context(x, y, kbd_ctx)
        if tip_context is None:
            self._prev_tooltip_task_id = None
            return False
        x, y = self.led_treeview.convert_widget_to_bin_window_coords(x, y)
        path, column = self.led_treeview.get_path_at_pos(x, y)[0:2]
        col_index = self.led_treeview.get_columns().index(column)
        if not self.is_transposed:
            iter_ = self.led_treeview.get_model().get_iter(path)
            name = self.led_treeview.get_model().get_value(iter_, 0)
            try:
                point_string = self.led_headings[col_index]
            except IndexError:
                # This can occur for a tooltip while switching from transposed.
                return False
            if col_index == 0:
                task_id = name
            else:
                task_id = TaskID.get(name, point_string)
        else:
            try:
                point_string = self.point_strings[path[0]]
            except IndexError:
                return False
            if col_index == 0:
                task_id = point_string
            else:
                try:
                    name = self.led_headings[col_index]
                except IndexError:
                    return False
                task_id = TaskID.get(name, point_string)
        if task_id != self._prev_tooltip_task_id:
            self._prev_tooltip_task_id = task_id
            tooltip.set_text(None)
            return False
        if col_index == 0:
            tooltip.set_text(task_id)
            return True
        text = self.updater.get_id_summary(
            task_id, self.state_summary, self.fam_state_summary,
            self.descendants)
        if text == task_id:
            return False
        tooltip.set_text(text)
        return True

    def update_gui(self):
        self.action_required = False
        state_summary = {}
        state_summary.update(self.state_summary)
        state_summary.update(self.fam_state_summary)
        self.ledview_widgets()

        tasks_by_point_string = {}
        tasks_by_name = {}
        for id_ in state_summary:
            name, point_string = TaskID.split(id_)
            tasks_by_point_string.setdefault(point_string, [])
            tasks_by_point_string[point_string].append(name)
            tasks_by_name.setdefault(name, [])
            tasks_by_name[name].append(point_string)

        names = tasks_by_name.keys()
        names.sort()

        if not self.is_transposed:
            self._update_gui_regular(tasks_by_name, state_summary)
        else:
            self._update_gui_transpose(tasks_by_point_string, state_summary)

        self.led_treeview.columns_autosize()

        if self.is_transposed == self.should_transpose_view:
            # Only select rows if we have not changed view mode.
            self._set_selected_rows()

        return False

    def _update_gui_transpose(self, tasks_by_point_string, state_summary):
        """Logic for updating the gui in transpose mode."""
        for point_string in self.point_strings:
            tasks_at_point_string = tasks_by_point_string[point_string]
            state_list = []
            for name in self.task_list:
                task_id = TaskID.get(name, point_string)
                if task_id in self.fam_state_summary:
                    dot_type = 'family'
                else:
                    dot_type = 'task'
                if name in tasks_at_point_string:
                    state = state_summary[task_id]['state']
                    state_list.append(self.dots[dot_type][state])
                else:
                    state_list.append(self.dots[dot_type]['empty'])
            try:
                self.led_treestore.append(
                    None, row=[point_string] + state_list + [point_string])
            except ValueError:
                # A very laggy store can change the columns and raise this.
                return False

    def _update_gui_regular(self, tasks_by_name, state_summary):
        """Logic for updating the gui in regular mode."""
        children = []
        to_unfold = []
        parent_iter = None
        for name in self.task_list:
            point_strings_for_tasks = tasks_by_name.get(name, [])
            if not point_strings_for_tasks:
                continue
            state_list = []
            for point_string in self.point_strings:
                if point_string in point_strings_for_tasks:
                    task_id = TaskID.get(name, point_string)
                    state = state_summary[task_id]['state']
                    if task_id in self.fam_state_summary:
                        dot_type = 'family'
                    else:
                        dot_type = 'task'
                    state_list.append(self.dots[dot_type][state])
                else:
                    state_list.append(self.dots['task']['empty'])
            try:
                if name in self.family_tree:
                    # Task is a family.
                    self.led_treestore.append(
                        None, row=[name] + state_list)
                    children = self.family_tree[name]

                    # Get iter for this family's entry.
                    iter_ = self.led_treestore.get_iter_first()
                    temp = self.led_treestore.get_value(
                        iter_, 0)
                    while temp != name:
                        iter_ = self.led_treestore.iter_next(iter_)
                        temp = self.led_treestore.get_value(iter_, 0)
                    parent_iter = iter_

                    # Unfold if family was folded before update
                    if name in self.expanded_rows:
                        to_unfold.append(
                            self.led_treestore.get_path(iter_))

                elif name in children:
                    # Task belongs to a family.
                    self.led_treestore.append(
                        parent_iter, row=[name] + state_list)

                else:
                    # Task does not belong to a family.
                    self.led_treestore.append(
                        None, row=[name] + state_list)
            except ValueError:
                # A very laggy store can change the columns and raise this.
                return False

        # Unfold any rows that were unfolded before the update.
        for path in to_unfold:
            self.led_treeview.expand_row(path, True)

    def run(self):
        while not self.quit:
            if self.update() or self.action_required:
                gobject.idle_add(self.update_gui)
            sleep(0.2)
