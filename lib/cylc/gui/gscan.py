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
from time import sleep, time

import gtk
import gobject

from isodatetime.data import (
    get_timepoint_from_seconds_since_unix_epoch as timepoint_from_epoch)

from cylc.cfgspec.gcylc import gcfg
from cylc.cfgspec.globalcfg import GLOBAL_CFG
from cylc.cfgspec.gscan import gsfg
from cylc.gui.legend import ThemeLegendWindow
from cylc.gui.dot_maker import DotMaker
from cylc.gui.scanutil import (
    KEY_PORT, get_scan_menu, launch_gcylc, update_suites_info,
    launch_hosts_dialog, launch_about_dialog)
from cylc.gui.util import get_icon, setup_icons, set_exception_hook_dialog
from cylc.suite_status import (
    KEY_GROUP, KEY_META, KEY_STATES, KEY_TASKS_BY_STATE, KEY_TITLE,
    KEY_UPDATE_TIME)
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
            comms_timeout=None, interval=None):
        gobject.threads_init()
        set_exception_hook_dialog("cylc gscan")
        setup_icons()

        self.window = gtk.Window()
        title = "cylc gscan"
        for opt, items in [("-n", patterns_name), ("-o", patterns_owner)]:
            if items:
                for pattern in items:
                    if pattern is not None:
                        title += " %s %s" % (opt, pattern)
        self.window.set_title(title)
        self.window.set_icon(get_icon())
        self.vbox = gtk.VBox()
        self.vbox.show()

        self.warnings = {}

        self.theme_name = gcfg.get(['use theme'])
        self.theme = gcfg.get(['themes', self.theme_name])

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
        self.treeview = gtk.TreeView(suite_treemodel)

        # Visibility of columns
        vis_cols = gsfg.get(["columns"])
        # Doesn't make any sense without suite name column
        if gsfg.COL_SUITE not in vis_cols:
            vis_cols.append(gsfg.COL_SUITE.lower())
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
            self.treeview.append_column(column)

        # Construct the status column.
        status_column = gtk.TreeViewColumn(gsfg.COL_STATUS)
        status_column.set_sort_column_id(self.STATUS_COLUMN)
        status_column.set_visible(gsfg.COL_STATUS.lower() in vis_cols)
        status_column.set_resizable(True)
        cell_text_cycle = gtk.CellRendererText()
        status_column.pack_start(cell_text_cycle, expand=False)
        status_column.set_cell_data_func(
            cell_text_cycle, self._set_cell_text_cycle, self.CYCLE_COLUMN)
        self.treeview.append_column(status_column)

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

        self.treeview.show()
        if hasattr(self.treeview, "set_has_tooltip"):
            self.treeview.set_has_tooltip(True)
            try:
                self.treeview.connect('query-tooltip',
                                      self._on_query_tooltip)
            except TypeError:
                # Lower PyGTK version.
                pass
        self.treeview.connect("button-press-event",
                              self._on_button_press_event)

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
            self.window, hosts, suite_treemodel, self.treeview,
            comms_timeout=comms_timeout, interval=interval,
            group_column_id=self.GROUP_COLUMN,
            name_pattern=patterns["name"], owner_pattern=patterns["owner"])

        self.updater.start()

        self.dot_size = gcfg.get(['dot icon size'])
        self._set_dots()

        self.create_menubar()

        accelgroup = gtk.AccelGroup()
        self.window.add_accel_group(accelgroup)
        key, modifier = gtk.accelerator_parse('<Alt>m')
        accelgroup.connect_group(
            key, modifier, gtk.ACCEL_VISIBLE, self._toggle_hide_menu_bar)

        self.create_tool_bar()

        self.menu_hbox = gtk.HBox()
        self.menu_hbox.pack_start(self.menu_bar, expand=True, fill=True)
        self.menu_hbox.pack_start(self.tool_bar, expand=True, fill=True)
        self.menu_hbox.show_all()
        self.menu_hbox.hide_all()

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,
                                   gtk.POLICY_AUTOMATIC)
        scrolled_window.add(self.treeview)
        scrolled_window.show()

        self.vbox.pack_start(self.menu_hbox, expand=False)
        self.vbox.pack_start(scrolled_window, expand=True, fill=True)

        self.window.add(self.vbox)
        self.window.connect("destroy", self._on_destroy_event)
        wsize = gsfg.get(['window size'])
        self.window.set_default_size(*wsize)
        self.treeview.grab_focus()
        self.window.show()

        self.theme_legend_window = None
        self.warning_icon_shown = []

    def popup_theme_legend(self, widget=None):
        """Popup a theme legend window."""
        if self.theme_legend_window is None:
            self.theme_legend_window = ThemeLegendWindow(
                self.window, self.theme)
            self.theme_legend_window.connect(
                "destroy", self.destroy_theme_legend)
        else:
            self.theme_legend_window.present()

    def update_theme_legend(self):
        """Update the theme legend window, if it exists."""
        if self.theme_legend_window is not None:
            self.theme_legend_window.update(self.theme)

    def destroy_theme_legend(self, widget):
        """Handle a destroy of the theme legend window."""
        self.theme_legend_window = None

    def create_menubar(self):
        """Create the main menu."""
        self.menu_bar = gtk.MenuBar()

        file_menu = gtk.Menu()
        file_menu_root = gtk.MenuItem('_File')
        file_menu_root.set_submenu(file_menu)

        exit_item = gtk.ImageMenuItem('E_xit')
        img = gtk.image_new_from_stock(gtk.STOCK_QUIT, gtk.ICON_SIZE_MENU)
        exit_item.set_image(img)
        exit_item.show()
        exit_item.connect("activate", self._on_destroy_event)
        file_menu.append(exit_item)

        view_menu = gtk.Menu()
        view_menu_root = gtk.MenuItem('_View')
        view_menu_root.set_submenu(view_menu)

        col_item = gtk.ImageMenuItem("_Columns...")
        img = gtk.image_new_from_stock(gtk.STOCK_INDEX, gtk.ICON_SIZE_MENU)
        col_item.set_image(img)
        col_item.show()
        col_menu = gtk.Menu()
        for column_index, column in enumerate(self.treeview.get_columns()):
            name = column.get_title()
            is_visible = column.get_visible()
            column_item = gtk.CheckMenuItem(name.replace("_", "__"))
            column_item._connect_args = column_index
            column_item.set_active(is_visible)
            column_item.connect("toggled", self._on_toggle_column_visible)
            column_item.show()
            col_menu.append(column_item)

        col_item.set_submenu(col_menu)
        col_item.show_all()
        view_menu.append(col_item)

        view_menu.append(gtk.SeparatorMenuItem())

        # Construct theme chooser items (same as cylc.gui.app_main).
        theme_item = gtk.ImageMenuItem('Theme...')
        img = gtk.image_new_from_stock(
            gtk.STOCK_SELECT_COLOR, gtk.ICON_SIZE_MENU)
        theme_item.set_image(img)
        thememenu = gtk.Menu()
        theme_item.set_submenu(thememenu)
        theme_item.show()

        theme_items = {}
        theme = "default"
        theme_items[theme] = gtk.RadioMenuItem(label=theme)
        thememenu.append(theme_items[theme])
        theme_items[theme].theme_name = theme
        for theme in gcfg.get(['themes']):
            if theme == "default":
                continue
            theme_items[theme] = gtk.RadioMenuItem(
                group=theme_items['default'], label=theme)
            thememenu.append(theme_items[theme])
            theme_items[theme].theme_name = theme

        # set_active then connect, to avoid causing an unnecessary toggle now.
        theme_items[self.theme_name].set_active(True)
        for theme in gcfg.get(['themes']):
            theme_items[theme].show()
            theme_items[theme].connect(
                'toggled',
                lambda i: (i.get_active() and self._set_theme(i.theme_name)))

        view_menu.append(theme_item)

        theme_legend_item = gtk.ImageMenuItem("Show task state key")
        img = gtk.image_new_from_stock(
            gtk.STOCK_SELECT_COLOR, gtk.ICON_SIZE_MENU)
        theme_legend_item.set_image(img)
        theme_legend_item.show()
        theme_legend_item.connect("activate", self.popup_theme_legend)
        view_menu.append(theme_legend_item)

        view_menu.append(gtk.SeparatorMenuItem())

        # Construct a configure scanned hosts item.
        hosts_item = gtk.ImageMenuItem("Configure Hosts")
        img = gtk.image_new_from_stock(
            gtk.STOCK_PREFERENCES, gtk.ICON_SIZE_MENU)
        hosts_item.set_image(img)
        hosts_item.show()
        hosts_item.connect(
            "activate",
            lambda w: launch_hosts_dialog(
                self.updater.hosts, self.updater.set_hosts))
        view_menu.append(hosts_item)

        sep_item = gtk.SeparatorMenuItem()
        sep_item.show()

        help_menu = gtk.Menu()
        help_menu_root = gtk.MenuItem('_Help')
        help_menu_root.set_submenu(help_menu)

        self.menu_bar.append(file_menu_root)
        self.menu_bar.append(view_menu_root)
        self.menu_bar.append(help_menu_root)

        # Construct an about dialog item.
        info_item = gtk.ImageMenuItem("About")
        img = gtk.image_new_from_stock(gtk.STOCK_ABOUT, gtk.ICON_SIZE_MENU)
        info_item.set_image(img)
        info_item.show()
        info_item.connect(
            "activate",
            lambda w: launch_about_dialog("cylc gscan", self.updater.hosts)
        )
        help_menu.append(info_item)

        self.menu_bar.show_all()

    def _set_dots(self):
        self.dots = DotMaker(self.theme, size=self.dot_size)

    def create_tool_bar(self):
        """Create the tool bar for the GUI."""
        self.tool_bar = gtk.Toolbar()

        update_now_button = gtk.ToolButton(
            icon_widget=gtk.image_new_from_stock(
                gtk.STOCK_REFRESH, gtk.ICON_SIZE_SMALL_TOOLBAR))
        update_now_button.set_label("Update Listing")
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip(update_now_button, "Update Suite Listing Now")
        update_now_button.connect("clicked", self.updater.set_update_listing)

        clear_stopped_button = gtk.ToolButton(
            icon_widget=gtk.image_new_from_stock(
                gtk.STOCK_CLEAR, gtk.ICON_SIZE_SMALL_TOOLBAR))
        clear_stopped_button.set_label("Clear")
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip(clear_stopped_button, "Clear stopped suites")
        clear_stopped_button.connect("clicked",
                                     self.updater.clear_stopped_suites)

        expand_button = gtk.ToolButton(
            icon_widget=gtk.image_new_from_stock(
                gtk.STOCK_ADD, gtk.ICON_SIZE_SMALL_TOOLBAR))
        expand_button.set_label("Expand all")
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip(expand_button, "Expand all rows")
        expand_button.connect("clicked", lambda e: self.treeview.expand_all())

        collapse_button = gtk.ToolButton(
            icon_widget=gtk.image_new_from_stock(
                gtk.STOCK_REMOVE, gtk.ICON_SIZE_SMALL_TOOLBAR))
        collapse_button.set_label("Expand all")
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip(collapse_button, "Collapse all rows")
        collapse_button.connect(
            "clicked", lambda e: self.treeview.collapse_all())

        self.tool_bar.insert(update_now_button, 0)
        self.tool_bar.insert(clear_stopped_button, 0)
        self.tool_bar.insert(collapse_button, 0)
        self.tool_bar.insert(expand_button, 0)
        separator = gtk.SeparatorToolItem()
        separator.set_expand(True)
        self.tool_bar.insert(separator, 0)

        self.tool_bar.show_all()

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
            path, column, cell_x = pth[:3]
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
            if suite is not None:
                suite_keys.append((host, owner, suite))

            elif suite is None:
                # On an expanded cycle point row, so get from parent.
                try:
                    host, owner, suite = treemodel.get(
                        treemodel.iter_parent(iter_),
                        self.HOST_COLUMN, self.OWNER_COLUMN, self.SUITE_COLUMN)
                    suite_keys.append((host, owner, suite))

                except:
                    # Now iterate over the children instead.
                    # We need to iterate over the children as there can be more
                    # than one suite in a group of suites.
                    # Get a TreeIter pointing to the first child of parent iter
                    suite_iter = treemodel.iter_children(iter_)

                    # Iterate over the children until you get to end
                    while suite_iter is not None:
                        host, owner, suite = treemodel.get(suite_iter,
                                                           self.HOST_COLUMN,
                                                           self.OWNER_COLUMN,
                                                           self.SUITE_COLUMN)
                        suite_keys.append((host, owner, suite))
                        # Advance to the next pointer in the treemodel
                        suite_iter = treemodel.iter_next(suite_iter)

        if event.type == gtk.gdk._2BUTTON_PRESS:
            if suite_keys:
                launch_gcylc(suite_keys[0])
            return False

        menu = get_scan_menu(suite_keys, self._toggle_hide_menu_bar)
        menu.popup(None, None, None, event.button, event.time)
        return False

    def _on_destroy_event(self, _):
        """Callback on destroy of main window."""
        try:
            self.updater.quit = True
            gtk.main_quit()
        except RuntimeError:
            pass
        return False

    def _toggle_hide_menu_bar(self, *_):
        if self.menu_hbox.get_property("visible"):
            self.menu_hbox.hide_all()
        else:
            self.menu_hbox.show_all()

    def _on_query_tooltip(self, _, x, y, kbd_ctx, tooltip):
        """Handle a tooltip creation request."""
        tip_context = self.treeview.get_tooltip_context(x, y, kbd_ctx)
        if tip_context is None:
            self._prev_tooltip_location_id = None
            return False
        x, y = self.treeview.convert_widget_to_bin_window_coords(x, y)
        path, column, cell_x = (self.treeview.get_path_at_pos(x, y))[:3]
        model = self.treeview.get_model()
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
            if (self.updater.prev_norm_update is not None and
                    suite_update_time != int(self.updater.prev_norm_update)):
                text = "Last changed at %s\n" % suite_update_point
                text += "Last scanned at %s" % timepoint_from_epoch(
                    int(self.updater.prev_norm_update))
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
        column_index = menu_item._connect_args
        column = self.treeview.get_columns()[column_index]
        is_visible = column.get_visible()
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
        current_point = timepoint_from_epoch(time())
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
        self._set_dots()
        self.updater.update()
        self.update_theme_legend()

    @staticmethod
    def _set_tooltip(widget, text):
        """Set tooltip for a widget."""
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip(widget, text)


class ScanAppUpdater(threading.Thread):

    """Update the scan app."""

    INTERVAL_NORM = 15
    INTERVAL_FULL = 300

    UNGROUPED = "(ungrouped)"

    def __init__(self, window, hosts, suite_treemodel, suite_treeview,
                 comms_timeout=None, interval=None, group_column_id=0,
                 name_pattern=None, owner_pattern=None):
        self.window = window
        if hosts:
            self.hosts = hosts
        elif owner_pattern is not None:
            self.hosts = GLOBAL_CFG.get(["suite host scanning", "hosts"])
        else:
            self.hosts = []
        self.comms_timeout = comms_timeout
        if interval is None:
            interval = self.INTERVAL_FULL
        self.interval_full = interval
        self.suite_info_map = {}
        self.prev_full_update = None
        self.prev_norm_update = None
        self.quit = False
        self.suite_treemodel = suite_treemodel
        self.treeview = suite_treeview
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
            self.treeview.expand_to_path(rpath)
        return False

    def _get_user_expanded_row_ids(self):
        """Return a list of user-expanded row point_strings and names."""
        names = []
        model = self.treeview.get_model()
        if model is None or model.get_iter_first() is None:
            return names
        self.treeview.map_expanded_rows(self._add_expanded_row, names)
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
        warnings = sorted(warn for warn in failed_tasks if warn[0] > warn_time)
        return warnings[-5:]

    def clear_stopped_suites(self, _=None):
        """Clear stopped suite information that may have built up."""
        for key, result in self.suite_info_map.copy().items():
            if KEY_PORT not in result:
                del self.suite_info_map[key]
        gobject.idle_add(self.update)

    def clear_warnings(self, host, owner, suite):
        """Marks all presently issued warnings for a suite as read."""
        self.warning_times[(host, owner, suite)] = time()

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
        return any(
            KEY_PORT not in result for result in self.suite_info_map.values())

    def run(self):
        """Execute the main loop of the thread."""
        while not self.quit:
            now = time()
            full_mode = (
                self.prev_full_update is None or
                now >= self.prev_full_update + self.interval_full)
            if (full_mode or
                    self.prev_norm_update is None or
                    now >= self.prev_norm_update + self.INTERVAL_NORM):
                title = self.window.get_title()
                if full_mode:
                    gobject.idle_add(
                        self.window.set_title, title + " (listing + updating)")
                else:
                    gobject.idle_add(
                        self.window.set_title, title + " (updating)")
                self.suite_info_map = update_suites_info(self, full_mode)
                self.prev_norm_update = time()
                if full_mode:
                    self.prev_full_update = self.prev_norm_update
                gobject.idle_add(self.window.set_title, title)
                gobject.idle_add(self.update)
            sleep(1)

    def set_hosts(self, new_hosts):
        """Set new hosts."""
        del self.hosts[:]
        self.hosts.extend(new_hosts)
        self.set_update_listing()

    def update(self):
        """Update the Applet."""
        # Get expanded row IDs here, so the same expansion can be applied again
        # after the update.
        row_ids = self._get_user_expanded_row_ids()
        group_counts = self._update_group_counts()
        self.suite_treemodel.clear()
        group_iters = {}
        hosts = set()
        owners = set()
        for key, suite_info in sorted(self.suite_info_map.items()):
            host, owner, suite = key
            hosts.add(host)
            owners.add(owner)
            suite_updated_time = suite_info.get(KEY_UPDATE_TIME)
            if suite_updated_time is None:
                suite_updated_time = int(time())
            try:
                title = suite_info[KEY_META].get(KEY_TITLE)
                group = suite_info[KEY_META].get(KEY_GROUP)
            except KeyError:
                # Compat:<=7.5.0
                title = suite_info.get(KEY_TITLE)
                group = suite_info.get(KEY_GROUP)
            # For the purpose of this method, it is OK to handle both
            # witheld (None) and unset (empty string) together
            if not group:
                group = self.UNGROUPED

            try:
                self.tasks_by_state[key] = suite_info[KEY_TASKS_BY_STATE]
            except KeyError:
                pass

            # Build up and assign group iters across the various suites
            if (group_iters.get(group) is None and
                    self.treeview.get_column(
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
                (warn[1] + '.' + warn[2] for warn in tasks[0:6]))

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
        if len(hosts) > 1:
            self.treeview.get_column(ScanApp.HOST_COLUMN).set_visible(True)
        if len(owners) > 1:
            self.treeview.get_column(ScanApp.OWNER_COLUMN).set_visible(True)
        return False

    def _update_group_counts(self):
        """Helper for self.update."""
        group_counts = {"": {'total': 0}}
        for suite_info in self.suite_info_map.values():
            try:
                group_id = suite_info[KEY_META].get(KEY_GROUP)
            except KeyError:
                # Compat:<=7.5.0
                group_id = suite_info.get(KEY_GROUP)
            # For the purpose of this method, it is OK to handle both
            # witheld (None) and unset (empty string) together
            if not group_id:
                group_id = self.UNGROUPED

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

    def set_update_listing(self, _=None):
        """Force an update of suite listing as soon as possible."""
        self.prev_full_update = None
        self.prev_norm_update = None
