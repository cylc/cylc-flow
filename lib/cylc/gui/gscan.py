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
"""Implement "cylc gscan"."""

import re
import threading
import time

import gtk
import gobject

from isodatetime.data import (
    get_timepoint_from_seconds_since_unix_epoch as timepoint_from_epoch)

from cylc.cfgspec.gcylc import gcfg
from cylc.cfgspec.globalcfg import GLOBAL_CFG
from cylc.cfgspec.gscan import gsfg
from cylc.gui.dot_maker import DotMaker
from cylc.gui.scanutil import (
    KEY_PORT, get_scan_menu, launch_gcylc, update_suites_info)
from cylc.gui.util import get_icon, setup_icons, set_exception_hook_dialog
from cylc.network import (
    KEY_GROUP, KEY_STATES, KEY_TASKS_BY_STATE, KEY_TITLE, KEY_UPDATE_TIME)
from cylc.owner import USER
from cylc.task_state import (
    TASK_STATUSES_ORDERED, TASK_STATUS_RUNAHEAD, TASK_STATUS_FAILED,
    TASK_STATUS_SUBMIT_FAILED)


class ScanApp(object):

    """Summarize running suite statuses for a given set of hosts."""

    WARNINGS_COLUMN = 9
    STATUS_COLUMN = 8
    CYCLE_COLUMN = 7
    UPDATE_TIME_COLUMN = 6
    TITLE_COLUMN = 5
    STOPPED_COLUMN = 4
    SUITE_COLUMN = 3
    OWNER_COLUMN = 2
    HOST_COLUMN = 1
    GROUP_COLUMN = 0

    ICON_SIZE = 17

    def __init__(
            self, hosts=None, patterns_name=None, patterns_owner=None,
            comms_timeout=None, poll_interval=None):
        gobject.threads_init()
        set_exception_hook_dialog("cylc gscan")
        setup_icons()
        if not hosts:
            hosts = GLOBAL_CFG.get(["suite host scanning", "hosts"])
        self.hosts = hosts

        self.window = gtk.Window()
        title = "cylc gscan"
        for opt, items, skip in [
                ("-n", patterns_name, None), ("-o", patterns_owner, USER)]:
            if items:
                for pattern in items:
                    if pattern != skip:
                        title += " %s %s" % (opt, pattern)
        self.window.set_title(title)
        self.window.set_icon(get_icon())
        self.vbox = gtk.VBox()
        self.vbox.show()

        self.warnings = {}

        self.theme_name = gcfg.get(['use theme'])
        self.theme = gcfg.get(['themes', self.theme_name])

        self.dots = DotMaker(self.theme)
        suite_treemodel = gtk.TreeStore(
            str,  # group
            str,  # host
            str,  # owner
            str,  # suite
            bool,  # is_stopped
            str,  # title
            int,  # update_time
            str,  # states
            str,  # states_text
            str)  # warning_text
        self._prev_tooltip_location_id = None
        self.suite_treeview = gtk.TreeView(suite_treemodel)

        # Visibility of columns
        vis_cols = gsfg.get(["columns"])
        # Doesn't make any sense without suite name column
        if gsfg.COL_SUITE not in vis_cols:
            vis_cols.append(gsfg.COL_SUITE.lower())
        # In multiple host environment, add host column by default
        if hosts:
            vis_cols.append(gsfg.COL_HOST.lower())
        # In multiple owner environment, add owner column by default
        if patterns_owner != [USER]:
            vis_cols.append(gsfg.COL_OWNER.lower())
        # Construct the group, host, owner, suite, title, update time column.
        for col_title, col_id, col_cell_text_setter in [
                (gsfg.COL_GROUP, self.GROUP_COLUMN, self._set_cell_text_group),
                (gsfg.COL_HOST, self.HOST_COLUMN, self._set_cell_text_host),
                (gsfg.COL_OWNER, self.OWNER_COLUMN, self._set_cell_text_owner),
                (gsfg.COL_SUITE, self.SUITE_COLUMN, self._set_cell_text_name),
                (gsfg.COL_TITLE, self.TITLE_COLUMN, self._set_cell_text_title),
                (gsfg.COL_UPDATED, self.UPDATE_TIME_COLUMN,
                 self._set_cell_text_time),
        ]:
            column = gtk.TreeViewColumn(col_title)
            cell_text = gtk.CellRendererText()
            column.pack_start(cell_text, expand=False)
            column.set_cell_data_func(cell_text, col_cell_text_setter)
            column.set_sort_column_id(col_id)
            column.set_visible(col_title.lower() in vis_cols)
            column.set_resizable(True)
            self.suite_treeview.append_column(column)

        # Construct the status column.
        status_column = gtk.TreeViewColumn(gsfg.COL_STATUS)
        status_column.set_sort_column_id(self.STATUS_COLUMN)
        status_column.set_visible(gsfg.COL_STATUS.lower() in vis_cols)
        status_column.set_resizable(True)
        cell_text_cycle = gtk.CellRendererText()
        status_column.pack_start(cell_text_cycle, expand=False)
        status_column.set_cell_data_func(
            cell_text_cycle, self._set_cell_text_cycle, self.CYCLE_COLUMN)
        self.suite_treeview.append_column(status_column)

        # Warning icon.
        warn_icon = gtk.CellRendererPixbuf()
        image = gtk.Image()
        pixbuf = image.render_icon(
            gtk.STOCK_DIALOG_WARNING, gtk.ICON_SIZE_LARGE_TOOLBAR)
        self.warn_icon_colour = pixbuf.scale_simple(  # colour warn icon pixbuf
            self.ICON_SIZE, self.ICON_SIZE, gtk.gdk.INTERP_HYPER)
        self.warn_icon_grey = pixbuf.scale_simple(
            self.ICON_SIZE, self.ICON_SIZE, gtk.gdk.INTERP_HYPER)
        self.warn_icon_colour.saturate_and_pixelate(
            self.warn_icon_grey, 0, False)  # b&w warn icon pixbuf
        status_column.pack_start(warn_icon, expand=False)
        status_column.set_cell_data_func(warn_icon, self._set_error_icon_state)
        self.warn_icon_blank = gtk.gdk.Pixbuf(  # Transparent pixbuff.
            gtk.gdk.COLORSPACE_RGB, True, 8, self.ICON_SIZE, self.ICON_SIZE
        ).fill(0x00000000)
        # Task status icons.
        for i in range(len(TASK_STATUSES_ORDERED)):
            cell_pixbuf_state = gtk.CellRendererPixbuf()
            status_column.pack_start(cell_pixbuf_state, expand=False)
            status_column.set_cell_data_func(
                cell_pixbuf_state, self._set_cell_pixbuf_state, i)

        self.suite_treeview.show()
        if hasattr(self.suite_treeview, "set_has_tooltip"):
            self.suite_treeview.set_has_tooltip(True)
            try:
                self.suite_treeview.connect('query-tooltip',
                                            self._on_query_tooltip)
            except TypeError:
                # Lower PyGTK version.
                pass
        self.suite_treeview.connect("button-press-event",
                                    self._on_button_press_event)
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,
                                   gtk.POLICY_AUTOMATIC)
        scrolled_window.add(self.suite_treeview)
        scrolled_window.show()
        self.vbox.pack_start(scrolled_window, expand=True, fill=True)

        patterns = {"name": None, "owner": None}
        for label, items in [
                ("owner", patterns_owner), ("name", patterns_name)]:
            if items:
                patterns[label] = r"\A(?:" + r")|(?:".join(items) + r")\Z"
                try:
                    patterns[label] = re.compile(patterns[label])
                except re.error:
                    raise ValueError("Invalid %s pattern: %s" % (label, items))

        self.updater = ScanAppUpdater(
            self.window, self.hosts, suite_treemodel, self.suite_treeview,
            comms_timeout=comms_timeout, poll_interval=poll_interval,
            group_column_id=self.GROUP_COLUMN,
            name_pattern=patterns["name"], owner_pattern=patterns["owner"])
        self.updater.start()
        self.window.add(self.vbox)
        self.window.connect("destroy", self._on_destroy_event)
        self.window.set_default_size(300, 150)
        self.suite_treeview.grab_focus()
        self.window.show()

        self.warning_icon_shown = []

    def _on_button_press_event(self, treeview, event):
        """Tree view button press callback."""
        x = int(event.x)
        y = int(event.y)
        pth = treeview.get_path_at_pos(x, y)
        treemodel = treeview.get_model()

        # Dismiss warnings by clicking on a warning icon.
        if event.button == 1:
            if not pth:
                return False
            path, column, cell_x, _ = pth
            if column.get_title() == gsfg.COL_STATUS:
                dot_offset, dot_width = tuple(column.cell_get_position(
                    column.get_cell_renderers()[1]))
                if not dot_width:
                    return False
                try:
                    cell_index = (cell_x - dot_offset) // dot_width
                except ZeroDivisionError:
                    return False
                if cell_index == 0:

                    iter_ = treemodel.get_iter(path)
                    host, owner, suite = treemodel.get(
                        iter_,
                        self.HOST_COLUMN, self.OWNER_COLUMN, self.SUITE_COLUMN)

                    self.updater.clear_warnings(host, owner, suite)
                    treemodel.set(iter_, self.WARNINGS_COLUMN, '')
                    return True

        # Display menu on right click.
        if event.type != gtk.gdk._2BUTTON_PRESS and event.button != 3:
            return False

        suite_keys = []

        if pth is not None:
            # Add a gcylc launcher item.
            path = pth[0]

            iter_ = treemodel.get_iter(path)
            host, owner, suite = treemodel.get(
                iter_, self.HOST_COLUMN, self.OWNER_COLUMN, self.SUITE_COLUMN)
            if suite is None:
                # On an expanded cycle point row, so get from parent.
                host, owner, suite = treemodel.get(
                    treemodel.iter_parent(iter_),
                    self.HOST_COLUMN, self.OWNER_COLUMN, self.SUITE_COLUMN)
            suite_keys.append((host, owner, suite))

        if event.type == gtk.gdk._2BUTTON_PRESS:
            if suite_keys:
                launch_gcylc(suite_keys[0])
            return False

        view_item = gtk.ImageMenuItem("View Column...")
        img = gtk.image_new_from_stock(gtk.STOCK_INDEX, gtk.ICON_SIZE_MENU)
        view_item.set_image(img)
        view_item.show()
        view_menu = gtk.Menu()
        view_item.set_submenu(view_menu)
        for column_index, column in enumerate(treeview.get_columns()):
            name = column.get_title()
            is_visible = column.get_visible()
            column_item = gtk.CheckMenuItem(name.replace("_", "__"))
            column_item._connect_args = (column_index, is_visible)
            column_item.set_active(is_visible)
            column_item.connect("toggled", self._on_toggle_column_visible)
            column_item.show()
            view_menu.append(column_item)

        menu = get_scan_menu(
            suite_keys,
            self.theme_name,
            self._set_theme,
            self.updater.has_stopped_suites(),
            self.updater.clear_stopped_suites,
            self.hosts,
            self.updater.set_hosts,
            self.updater.update_now,
            self.updater.start,
            program_name="cylc gscan",
            extra_items=[view_item],
        )
        menu.popup(None, None, None, event.button, event.time)
        return False

    def _on_destroy_event(self, _):
        """Callback on destroy of main window."""
        self.updater.quit = True
        gtk.main_quit()
        return False

    def _on_query_tooltip(self, _, x, y, kbd_ctx, tooltip):
        """Handle a tooltip creation request."""
        tip_context = self.suite_treeview.get_tooltip_context(x, y, kbd_ctx)
        if tip_context is None:
            self._prev_tooltip_location_id = None
            return False
        x, y = self.suite_treeview.convert_widget_to_bin_window_coords(x, y)
        path, column, cell_x, _ = (
            self.suite_treeview.get_path_at_pos(x, y))
        model = self.suite_treeview.get_model()
        iter_ = model.get_iter(path)
        parent_iter = model.iter_parent(iter_)
        if parent_iter is None or parent_iter and model.iter_has_child(iter_):
            host, owner, suite = model.get(
                iter_, self.HOST_COLUMN, self.OWNER_COLUMN, self.SUITE_COLUMN)
            child_row_number = None
        else:
            host, owner, suite = model.get(
                parent_iter,
                self.HOST_COLUMN, self.OWNER_COLUMN, self.SUITE_COLUMN)
            child_row_number = path[-1]
        suite_update_time = model.get_value(iter_, self.UPDATE_TIME_COLUMN)
        location_id = (
            host, owner, suite, suite_update_time, column.get_title(),
            child_row_number)

        if location_id != self._prev_tooltip_location_id:
            self._prev_tooltip_location_id = location_id
            tooltip.set_text(None)
            return False
        if column.get_title() in [
                gsfg.COL_HOST, gsfg.COL_OWNER, gsfg.COL_SUITE]:
            tooltip.set_text("%s - %s:%s" % (suite, owner, host))
            return True
        if column.get_title() == gsfg.COL_UPDATED:
            suite_update_point = timepoint_from_epoch(suite_update_time)
            if (self.updater.last_update_time is not None and
                    suite_update_time != int(self.updater.last_update_time)):
                retrieval_point = timepoint_from_epoch(
                    int(self.updater.last_update_time))
                text = "Last changed at %s\n" % suite_update_point
                text += "Last scanned at %s" % retrieval_point
            else:
                # An older suite (or before any updates are made?)
                text = "Last scanned at %s" % suite_update_point
            tooltip.set_text(text)
            return True

        if column.get_title() != gsfg.COL_STATUS:
            tooltip.set_text(None)
            return False

        # Generate text for the number of tasks in each state
        state_texts = []
        state_text = model.get_value(iter_, self.STATUS_COLUMN)
        if state_text is None:
            tooltip.set_text(None)
            return False
        info = re.findall(r'\D+\d+', state_text)
        for status_number in info:
            status, number = status_number.rsplit(" ", 1)
            state_texts.append(number + " " + status.strip())
        tooltip_prefix = (
            "<span foreground=\"#777777\">Tasks: " + ", ".join(state_texts) +
            "</span>"
        )

        # If hovering over a status indicator set tooltip to show most recent
        # tasks.
        dot_offset, dot_width = tuple(column.cell_get_position(
            column.get_cell_renderers()[2]))
        try:
            cell_index = ((cell_x - dot_offset) // dot_width) + 1
        except ZeroDivisionError:
            return False
        if cell_index >= 0:
            # NOTE: TreeViewColumn.get_cell_renderers() does not always return
            # cell renderers for the correct row.
            if cell_index == 0:
                # Hovering over the error symbol.
                point_string = model.get(iter_, self.CYCLE_COLUMN)[0]
                if point_string:
                    return False
                if not self.warnings.get((host, owner, suite)):
                    return False
                tooltip.set_markup(
                    tooltip_prefix +
                    '\n<b>New failures</b> (<i>last 5</i>) <i><span ' +
                    'foreground="#2222BB">click to dismiss</span></i>\n' +
                    self.warnings[(host, owner, suite)])
                return True
            else:
                # Hovering over a status indicator.
                info = re.findall(r'\D+\d+', model.get(iter_,
                                                       self.STATUS_COLUMN)[0])
                if cell_index > len(info):
                    return False
                state = info[cell_index - 1].strip().split(' ')[0]
                point_string = model.get(iter_, self.CYCLE_COLUMN)[0]

                tooltip_text = tooltip_prefix

                if suite:
                    tasks = self.updater.get_last_n_tasks(
                        host, owner, suite, state, point_string)
                    tooltip_text += (
                        '\n<b>Recent {state} tasks</b>\n{tasks}').format(
                        state=state, tasks='\n'.join(tasks))
                tooltip.set_markup(tooltip_text)
                return True

        # Set the tooltip to a generic status for this suite.
        tooltip.set_markup(tooltip_prefix)
        return True

    def _on_toggle_column_visible(self, menu_item):
        """Toggle column visibility callback."""
        column_index, is_visible = menu_item._connect_args
        column = self.suite_treeview.get_columns()[column_index]
        column.set_visible(not is_visible)
        self.updater.update()
        return False

    def _set_cell_pixbuf_state(self, _, cell, model, iter_, index):
        """State info pixbuf."""
        state_info = model.get_value(iter_, self.STATUS_COLUMN)
        if state_info is not None:
            is_stopped = model.get_value(iter_, self.STOPPED_COLUMN)
            info = re.findall(r'\D+\d+', state_info)
            if index < len(info):
                state = info[index].strip().rsplit(
                    " ", self.SUITE_COLUMN)[0].strip()
                icon = self.dots.get_icon(state, is_stopped=is_stopped)
                cell.set_property("visible", True)
            else:
                icon = None
                cell.set_property("visible", False)
        else:
            icon = None
            cell.set_property("visible", False)
        cell.set_property("pixbuf", icon)

    def _set_error_icon_state(self, _, cell, model, iter_):
        """Update the state of the warning icon."""
        host, owner, suite, warnings, point_string = model.get(
            iter_, self.HOST_COLUMN, self.OWNER_COLUMN, self.SUITE_COLUMN,
            self.WARNINGS_COLUMN, self.CYCLE_COLUMN)
        key = (host, owner, suite)
        if point_string:
            # Error icon only for first row.
            cell.set_property('pixbuf', self.warn_icon_blank)
        elif warnings:
            cell.set_property('pixbuf', self.warn_icon_colour)
            self.warning_icon_shown.append(key)
            self.warnings[key] = warnings
        else:
            cell.set_property('pixbuf', self.warn_icon_grey)
            self.warnings[key] = None
            if key not in self.warning_icon_shown:
                cell.set_property('pixbuf', self.warn_icon_blank)

    def _set_cell_text_group(self, _, cell, model, iter_):
        """Set cell text for "group" column."""
        group = model.get_value(iter_, self.GROUP_COLUMN)
        is_stopped = model.get_value(iter_, self.STOPPED_COLUMN)
        cell.set_property("sensitive", not is_stopped)
        cell.set_property("text", group)

    def _set_cell_text_host(self, _, cell, model, iter_):
        """Set cell text for "host" column."""
        host = model.get_value(iter_, self.HOST_COLUMN)
        is_stopped = model.get_value(iter_, self.STOPPED_COLUMN)
        cell.set_property("sensitive", not is_stopped)
        cell.set_property("text", host)

    def _set_cell_text_owner(self, _, cell, model, iter_):
        """Set cell text for "owner" column."""
        value = model.get_value(iter_, self.OWNER_COLUMN)
        is_stopped = model.get_value(iter_, self.STOPPED_COLUMN)
        cell.set_property("sensitive", not is_stopped)
        cell.set_property("text", value)

    def _set_cell_text_name(self, _, cell, model, iter_):
        """Set cell text for (suite name) "name" column."""
        name = model.get_value(iter_, self.SUITE_COLUMN)
        is_stopped = model.get_value(iter_, self.STOPPED_COLUMN)
        cell.set_property("sensitive", not is_stopped)
        cell.set_property("text", name)

    def _set_cell_text_title(self, _, cell, model, iter_):
        """Set cell text for "title" column."""
        title = model.get_value(iter_, self.TITLE_COLUMN)
        is_stopped = model.get_value(iter_, self.STOPPED_COLUMN)
        cell.set_property("sensitive", not is_stopped)
        cell.set_property("text", title)

    def _set_cell_text_time(self, _, cell, model, iter_):
        """Set cell text for "update-time" column."""
        suite_update_time = model.get_value(iter_, self.UPDATE_TIME_COLUMN)
        time_point = timepoint_from_epoch(suite_update_time)
        time_point.set_time_zone_to_local()
        current_time = time.time()
        current_point = timepoint_from_epoch(current_time)
        if str(time_point).split("T")[0] == str(current_point).split("T")[0]:
            time_string = str(time_point).split("T")[1]
        else:
            time_string = str(time_point)
        is_stopped = model.get_value(iter_, self.STOPPED_COLUMN)
        cell.set_property("sensitive", not is_stopped)
        cell.set_property("text", time_string)

    def _set_cell_text_cycle(self, _, cell, model, iter_, active_cycle):
        """Set cell text for "cycle" column."""
        cycle = model.get_value(iter_, active_cycle)
        is_stopped = model.get_value(iter_, self.STOPPED_COLUMN)
        cell.set_property("sensitive", not is_stopped)
        cell.set_property("text", cycle)

    def _set_theme(self, new_theme_name):
        """Set GUI theme."""
        self.theme_name = new_theme_name
        self.theme = gcfg.get(['themes', self.theme_name])
        self.dots = DotMaker(self.theme)

    @staticmethod
    def _set_tooltip(widget, text):
        """Set tooltip for a widget."""
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip(widget, text)


class ScanAppUpdater(threading.Thread):

    """Update the scan app."""

    POLL_INTERVAL = 60

    def __init__(self, window, hosts, suite_treemodel, suite_treeview,
                 comms_timeout=None, poll_interval=None, group_column_id=0,
                 name_pattern=None, owner_pattern=None):
        self.window = window
        self.hosts = hosts
        self.comms_timeout = comms_timeout
        if poll_interval is None:
            poll_interval = self.POLL_INTERVAL
        self.poll_interval = poll_interval
        self.suite_info_map = {}
        self.last_update_time = None
        self._should_force_update = False
        self.quit = False
        self.suite_treemodel = suite_treemodel
        self.suite_treeview = suite_treeview
        self.group_column_id = group_column_id
        self.tasks_by_state = {}
        self.warning_times = {}
        self.name_pattern = name_pattern
        self.owner_pattern = owner_pattern
        super(ScanAppUpdater, self).__init__()

    @staticmethod
    def _add_expanded_row(view, rpath, row_ids):
        """Add user-expanded rows to a list of suite and hosts to be
        expanded."""
        model = view.get_model()
        row_iter = model.get_iter(rpath)
        row_id = model.get(row_iter, 0, 1)
        row_ids.append(row_id)
        return False

    def _expand_row(self, model, rpath, row_iter, row_ids):
        """Expand a row if it matches rose_ids suite and host."""
        point_string_name_tuple = model.get(row_iter, 0, 1)
        if point_string_name_tuple in row_ids:
            self.suite_treeview.expand_to_path(rpath)
        return False

    def _get_user_expanded_row_ids(self):
        """Return a list of user-expanded row point_strings and names."""
        names = []
        model = self.suite_treeview.get_model()
        if model is None or model.get_iter_first() is None:
            return names
        self.suite_treeview.map_expanded_rows(self._add_expanded_row, names)
        return names

    def _get_warnings(self, key):
        """Updates the list of tasks to issue warning for. To be called
        on update only."""
        if key not in self.tasks_by_state:
            return []
        warn_time = 0
        if key in self.warning_times:
            warn_time = self.warning_times[key]
        failed_tasks = []
        for state in (TASK_STATUS_FAILED, TASK_STATUS_SUBMIT_FAILED):
            failed_tasks += self.tasks_by_state[key].get(state, [])
        warnings = [warn for warn in failed_tasks if warn[0] > warn_time]
        warnings.sort()
        return warnings[-5:]

    def clear_stopped_suites(self):
        """Clear stopped suite information that may have built up."""
        for key, result in self.suite_info_map.copy().items():
            if KEY_PORT not in result:
                del self.suite_info_map[key]
        gobject.idle_add(self.update)

    def clear_warnings(self, host, owner, suite):
        """Marks all presently issued warnings for a suite as read."""
        self.warning_times[(host, owner, suite)] = time.time()

    def get_last_n_tasks(self, host, owner, suite, task_state, point_string):
        """Returns a list of the last 'n' tasks with the provided state for
        the provided suite."""
        # Get list of tasks for the provided state or return an error msg.
        key = (host, owner, suite)
        if (key not in self.tasks_by_state or
                task_state not in self.tasks_by_state[key]):
            return []
        tasks = list(self.tasks_by_state[key][task_state])

        # Append "And x more" to list if required.
        temp = [[dt, tn, ps] for (dt, tn, ps) in tasks if dt is None]
        suffix = []
        if temp:
            tasks.remove(temp[0])
            if not point_string:
                suffix.append(('<span foreground="#777777">'
                               '<i>And %s more</i></span>') % (temp[0][1],))

        # Filter by point string if provided.
        if point_string:
            ret = [task_name + '.' + p_string for
                   (_, task_name, p_string) in tasks if
                   p_string == point_string]
        else:
            ret = [task[1] + '.' + task[2] for task in tasks]

        if not ret:
            return ['<span foreground="#777777"><i>None</i></span>']

        return ret + suffix

    def has_stopped_suites(self):
        """Return True if we have any stopped suite information."""
        for result in self.suite_info_map.copy().values():
            if KEY_PORT not in result:
                return True
        return False

    def run(self):
        """Execute the main loop of the thread."""
        while not self.quit:
            time_for_update = (
                self.last_update_time is None or
                time.time() >= self.last_update_time + self.poll_interval
            )
            if not self._should_force_update and not time_for_update:
                time.sleep(1)
                continue
            if self._should_force_update:
                self._should_force_update = False
            title = self.window.get_title()
            gobject.idle_add(self.window.set_title, title + " (updating)")
            self.suite_info_map = update_suites_info(
                self.hosts, self.comms_timeout, self.owner_pattern,
                self.name_pattern, self.suite_info_map)
            self.last_update_time = time.time()
            gobject.idle_add(self.window.set_title, title)
            gobject.idle_add(self.update)
            time.sleep(1)

    def set_hosts(self, new_hosts):
        """Set new hosts."""
        del self.hosts[:]
        self.hosts.extend(new_hosts)
        self.update_now()

    def update(self):
        """Update the Applet."""
        # Get expanded row IDs here, so the same expansion can be applied again
        # after the update.
        row_ids = self._get_user_expanded_row_ids()
        group_counts = self._update_group_counts()
        self.suite_treemodel.clear()
        group_iters = {}
        for key, suite_info in sorted(self.suite_info_map.items()):
            host, owner, suite = key
            suite_updated_time = suite_info.get(
                KEY_UPDATE_TIME, int(time.time()))
            title = suite_info.get(KEY_TITLE)
            group = suite_info.get(KEY_GROUP)

            try:
                self.tasks_by_state[key] = suite_info[KEY_TASKS_BY_STATE]
            except KeyError:
                pass

            # Build up and assign group iters across the various suites
            if (group_iters.get(group) is None and
                    self.suite_treeview.get_column(
                        self.group_column_id).get_visible()):
                states_text = ""
                for state, number in sorted(group_counts[group].items()):
                    if state != TASK_STATUS_RUNAHEAD and state != 'total':
                        # 'runahead' states are usually hidden.
                        states_text += '%s %d ' % (state, number)
                summary_text = "%s - %d" % (
                    group, group_counts[group]['total'])
                group_iters[group] = self.suite_treemodel.append(None, [
                    summary_text, None, None, None, False, None,
                    suite_updated_time, None, states_text, None])

            tasks = sorted(self._get_warnings(key), reverse=True)
            warning_text = '\n'.join(
                [warn[1] + '.' + warn[2] for warn in tasks[0:6]])

            is_stopped = KEY_PORT not in suite_info
            if KEY_STATES in suite_info:
                # Add the state count column (e.g. 'failed 1 succeeded 2').
                # Total count of each state
                parent_iter = self.suite_treemodel.append(
                    group_iters.get(group), [
                        None, host, owner, suite, is_stopped, title,
                        suite_updated_time, None,
                        self._states_to_text(suite_info[KEY_STATES][0]),
                        warning_text])
                # Count of each state by cycle points
                for point, states in sorted(suite_info[KEY_STATES][1].items()):
                    states_text = self._states_to_text(states)
                    if not states_text:
                        # Purely runahead cycle point.
                        continue
                    self.suite_treemodel.append(
                        parent_iter, [
                            None, None, None, None, is_stopped, title,
                            suite_updated_time, str(point),
                            states_text, warning_text])
            else:
                # No states in suite_info
                self.suite_treemodel.append(group_iters.get(group), [
                    None, host, owner, suite, is_stopped, title,
                    suite_updated_time, None, None, warning_text])

        self.suite_treemodel.foreach(self._expand_row, row_ids)
        return False

    def _update_group_counts(self):
        """Helper for self.update."""
        group_counts = {"": {'total': 0}}
        for suite_info in self.suite_info_map.values():
            group_id = suite_info.get(KEY_GROUP)

            if group_id in group_counts:
                group_counts[group_id]['total'] += 1
            else:
                group_counts[group_id] = {'total': 1}

            if KEY_STATES in suite_info:
                for state, number in sorted(
                        suite_info[KEY_STATES][0].items(), key=lambda _: _[1]):
                    group_counts[group_id].setdefault(state, 0)
                    group_counts[group_id][state] += number
        return group_counts

    @staticmethod
    def _states_to_text(states):
        """Helper for self.update. Build states text from states."""
        states_text = ""
        for state, number in sorted(states.items(), key=lambda _: _[1]):
            if state != TASK_STATUS_RUNAHEAD:
                # 'runahead' states are usually hidden.
                states_text += '%s %d ' % (state, number)
        return states_text.rstrip()

    def update_now(self):
        """Force an update as soon as possible."""
        self._should_force_update = True
