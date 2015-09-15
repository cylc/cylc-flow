#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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

import copy
import os
import re
import shlex
from subprocess import Popen, PIPE, STDOUT
import sys
import threading
import time

import gtk
import gobject
from isodatetime.data import get_timepoint_from_seconds_since_unix_epoch

from cylc.cfgspec.globalcfg import GLOBAL_CFG
from cylc.cfgspec.gcylc import gcfg
import cylc.flags
from cylc.gui.legend import ThemeLegendWindow
from cylc.gui.app_gcylc import run_get_stdout
from cylc.gui.dot_maker import DotMaker
from cylc.gui.util import get_icon, setup_icons, set_exception_hook_dialog
from cylc.owner import user
from cylc.registration import localdb
from cylc.version import CYLC_VERSION
from operator import itemgetter
from itertools import groupby
from cylc.task_state import task_state

PYRO_TIMEOUT = 2


def parse_cylc_scan_raw(text):
    """Parse cylc scan --raw formatted output.

    Return a nested host->suite->property->value dictionary,
    where the properties are as named in the 4th column of
    cylc scan --raw output.

    For the states properties, translate the state lines into
    key-value pairs (e.g. failed:1 => {failed: 1}).

    """
    host_suite_properties = {}
    for line in text.splitlines():
        suite, owner, host, property, value = line.strip().split("|")
        host_suite_properties.setdefault(host, {}).setdefault(suite, {})
        if property.startswith("states"):
            new_value = {}
            for item in value.split():
                state, num = item.rsplit(":", 1)
                new_value[state] = int(num)
            value = new_value
        if property == "update-time":
            value = int(float(value))
        host_suite_properties[host][suite][property] = value
    return host_suite_properties


def get_hosts_suites_info(hosts, timeout=None, owner=None):
    """Return a dictionary of hosts, suites, and their properties."""
    host_suites_map = {}
    if timeout is None:
        timeout = PYRO_TIMEOUT
    command = ["cylc", "scan", "--raw",
               "--pyro-timeout=%s" % timeout]
    if owner:
        command.append("--owner=%s" % owner)
    if hosts:
        command += hosts
    if cylc.flags.debug:
        stderr = sys.stderr
        command.append("--debug")
    else:
        stderr = PIPE
    env = os.environ.copy()
    env["PATH"] = ":".join(sys.path) + ":" + env["PATH"]
    popen = Popen(command, stdout=PIPE, stderr=stderr, env=env)
    if popen.wait() == 0:
        host_suites_map = parse_cylc_scan_raw(popen.communicate()[0])
    else:
        print >> sys.stderr, popen.communicate()[1]
    for host, suites_map in host_suites_map.items():
        for suite, suite_info in suites_map.items():
            if suite_info.keys() == ["port"]:
                # Just the port file - could be an older suite daemon.
                suite_info.update(
                    get_unscannable_suite_info(
                        host, suite, owner=owner))
    return host_suites_map


def get_unscannable_suite_info(host, suite, owner=None):
    """Return a map like cylc scan --raw for states and last update time."""
    if owner is None:
        owner = user
    command = ["cylc", "cat-state", "--host=" + host, "--user=" + owner]
    if cylc.flags.debug:
        stderr = sys.stderr
        command.append("--debug")
    else:
        stderr = PIPE
    popen = Popen(command + [suite], stdout=PIPE, stderr=stderr)
    out = popen.communicate()[0]
    if popen.wait():  # non-zero return code
        return {}
    suite_info = {}
    for line in out.rpartition("Begin task states")[2].splitlines():
        task_result = re.match("([^ ]+) : status=([^,]+), spawned", line)
        if not task_result:
            continue
        task, state = task_result.groups()
        task_name, task_point = task.split(".")
        for states_point in ("states", "states:" + task_point):
            suite_info.setdefault(states_point, {})
            suite_info[states_point].setdefault(state, 0)
            suite_info[states_point][state] += 1
    suite_update_time_match = re.search(
        "^time : [^ ]+ \(([0-9]+)\)$", out, re.M)
    if suite_update_time_match is None:
        suite_update_time = int(time.time())
    else:
        suite_update_time = int(suite_update_time_match.group(1))
    suite_info['update-time'] = suite_update_time
    return suite_info


def get_scan_menu(suite_host_tuples,
                  theme_name, set_theme_func,
                  has_stopped_suites, clear_stopped_suites_func,
                  scanned_hosts, change_hosts_func,
                  update_now_func, start_func,
                  program_name, extra_items=None, owner=None,
                  is_stopped=False):
    """Return a right click menu for scan GUIs.

    suite_host_tuples should be a list of (suite, host) tuples (if any).
    theme_name should be the name of the current theme.
    set_theme_func should be a function accepting a new theme name.
    has_stopped_suites should be a boolean denoting currently
    stopped suites.
    clear_stopped_suites should be a function with no arguments that
    removes stopped suites from the current view.
    scanned_hosts should be a list of currently scanned suite hosts.
    change_hosts_func should be a function accepting a new list of
    suite hosts to scan.
    update_now_func should be a function with no arguments that
    forces an update now or soon.
    start_func should be a function with no arguments that
    re-activates idle GUIs.
    program_name should be a string describing the parent program.
    extra_items (keyword) should be a list of extra menu items to add
    to the right click menu.
    owner (keyword) should be the owner of the suites, if not the
    current user.
    is_stopped (keyword) denotes whether the GUI is in an inactive
    state.

    """
    menu = gtk.Menu()

    if is_stopped:
        switch_on_item = gtk.ImageMenuItem("Activate")
        img = gtk.image_new_from_stock(gtk.STOCK_YES, gtk.ICON_SIZE_MENU)
        switch_on_item.set_image(img)
        switch_on_item.show()
        switch_on_item.connect("button-press-event",
                               lambda b, e: start_func())
        menu.append(switch_on_item)

    # Construct gcylc launcher items for each relevant suite.
    for suite, host in suite_host_tuples:
        gcylc_item = gtk.ImageMenuItem("Launch gcylc: %s - %s" % (suite, host))
        img = gtk.image_new_from_stock("gcylc", gtk.ICON_SIZE_MENU)
        gcylc_item.set_image(img)
        gcylc_item._connect_args = (suite, host)
        gcylc_item.connect(
            "button-press-event",
            lambda b, e: launch_gcylc(b._connect_args[1],
                                      b._connect_args[0],
                                      owner=owner)
        )
        gcylc_item.show()
        menu.append(gcylc_item)
    if suite_host_tuples:
        sep_item = gtk.SeparatorMenuItem()
        sep_item.show()
        menu.append(sep_item)

    if extra_items is not None:
        for item in extra_items:
            menu.append(item)
        sep_item = gtk.SeparatorMenuItem()
        sep_item.show()
        menu.append(sep_item)

    # Construct theme chooser items (same as cylc.gui.app_main).
    theme_item = gtk.ImageMenuItem('Theme')
    img = gtk.image_new_from_stock(gtk.STOCK_SELECT_COLOR, gtk.ICON_SIZE_MENU)
    theme_item.set_image(img)
    theme_item.set_sensitive(not is_stopped)
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
    theme_items[theme_name].set_active(True)
    for theme in gcfg.get(['themes']):
        theme_items[theme].show()
        theme_items[theme].connect('toggled',
                                   lambda i: (i.get_active() and
                                              set_theme_func(i.theme_name)))

    menu.append(theme_item)
    theme_legend_item = gtk.MenuItem("Show task state key")
    theme_legend_item.show()
    theme_legend_item.set_sensitive(not is_stopped)
    theme_legend_item.connect(
        "button-press-event",
        lambda b, e: launch_theme_legend(gcfg.get(['themes', theme_name]))
    )
    menu.append(theme_legend_item)
    sep_item = gtk.SeparatorMenuItem()
    sep_item.show()
    menu.append(sep_item)

    # Construct a trigger update item.
    update_now_item = gtk.ImageMenuItem("Update Now")
    img = gtk.image_new_from_stock(gtk.STOCK_REFRESH, gtk.ICON_SIZE_MENU)
    update_now_item.set_image(img)
    update_now_item.show()
    update_now_item.set_sensitive(not is_stopped)
    update_now_item.connect("button-press-event",
                            lambda b, e: update_now_func())
    menu.append(update_now_item)

    # Construct a clean stopped suites item.
    clear_item = gtk.ImageMenuItem("Clear Stopped Suites")
    img = gtk.image_new_from_stock(gtk.STOCK_CLEAR, gtk.ICON_SIZE_MENU)
    clear_item.set_image(img)
    clear_item.show()
    clear_item.set_sensitive(has_stopped_suites)
    clear_item.connect("button-press-event",
                       lambda b, e: clear_stopped_suites_func())
    menu.append(clear_item)

    # Construct a configure scanned hosts item.
    hosts_item = gtk.ImageMenuItem("Configure Hosts")
    img = gtk.image_new_from_stock(gtk.STOCK_PREFERENCES, gtk.ICON_SIZE_MENU)
    hosts_item.set_image(img)
    hosts_item.show()
    hosts_item.connect("button-press-event",
                       lambda b, e: launch_hosts_dialog(scanned_hosts,
                                                        change_hosts_func))
    menu.append(hosts_item)

    sep_item = gtk.SeparatorMenuItem()
    sep_item.show()
    menu.append(sep_item)

    # Construct an about dialog item.
    info_item = gtk.ImageMenuItem("About")
    img = gtk.image_new_from_stock(gtk.STOCK_ABOUT, gtk.ICON_SIZE_MENU)
    info_item.set_image(img)
    info_item.show()
    info_item.connect(
        "button-press-event",
        lambda b, e: launch_about_dialog(program_name,
                                         scanned_hosts)
    )
    menu.append(info_item)
    return menu


def launch_about_dialog(program_name, hosts):
    """Launch a modified version of the app_main.py About dialog."""
    hosts_text = "Hosts monitored: " + ", ".join(hosts)
    comments_text = hosts_text
    about = gtk.AboutDialog()
    if gtk.gtk_version[0] == 2 and gtk.gtk_version[1] >= 12:
        # set_program_name() was added in PyGTK 2.12
        about.set_program_name(program_name)
    else:
        comments_text = program_name + "\n" + hosts_text

    about.set_version(CYLC_VERSION)
    about.set_copyright("Copyright (C) 2008-2015 NIWA")
    about.set_comments(comments_text)
    about.set_icon(get_icon())
    about.run()
    about.destroy()


def launch_gcylc(host, suite, owner=None):
    """Launch gcylc for a given suite and host."""
    if owner is None:
        owner = user
    args = ["--host=" + host, "--user=" + owner, suite]

    # Get version of suite
    f_null = open(os.devnull, "w")
    if cylc.flags.debug:
        stderr = sys.stderr
        args = ["--debug"] + args
    else:
        stderr = f_null
    command = ["cylc", "get-suite-version"] + args
    proc = Popen(command, stdout=PIPE, stderr=stderr)
    suite_version = proc.communicate()[0].strip()
    proc.wait()

    # Run correct version of "cylc gui", provided that "admin/cylc-wrapper" is
    # installed.
    env = None
    if suite_version != CYLC_VERSION:
        env = dict(os.environ)
        env["CYLC_VERSION"] = suite_version
    command = ["cylc", "gui"] + args
    if cylc.flags.debug:
        stdout = sys.stdout
        stderr = sys.stderr
        Popen(command, env=env, stdout=stdout, stderr=stderr)
    else:
        stdout = f_null
        stderr = STDOUT
        Popen(["nohup"] + command, env=env, stdout=stdout, stderr=stderr)


def launch_gscan(hosts=None, owner=None):
    """Launch gscan for a given list of hosts and/or owner."""
    if cylc.flags.debug:
        stdout = sys.stdout
        stderr = sys.stderr
        command = ["cylc", "gscan", "--debug"]
    else:
        stdout = open(os.devnull, "w")
        stderr = STDOUT
        command = ["cylc", "gscan"]
    if hosts is not None:
        for host in hosts:
            command += ["--host=%s" % host]
    if owner is not None:
        command += ["--user=%s" % owner]
    Popen(command, stdout=stdout, stderr=stderr)


def launch_hosts_dialog(existing_hosts, change_hosts_func):
    """Launch a dialog for configuring the suite hosts to scan.

    Arguments:
    existing_hosts should be a list of currently scanned host names.
    change_hosts_func should be a function accepting a new list of
    host names to scan.

    """
    dialog = gtk.Dialog()
    dialog.set_icon(get_icon())
    dialog.vbox.set_border_width(5)
    dialog.set_title("Configure suite hosts")
    cancel_button = dialog.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
    ok_button = dialog.add_button(gtk.STOCK_OK, gtk.RESPONSE_OK)
    label = gtk.Label("Enter a comma-delimited list of suite hosts to scan")
    label.show()
    label_hbox = gtk.HBox()
    label_hbox.pack_start(label, expand=False, fill=False)
    label_hbox.show()
    entry = gtk.Entry()
    entry.set_text(", ".join(existing_hosts))
    entry.connect("activate", lambda e: dialog.response(gtk.RESPONSE_OK))
    entry.show()
    dialog.vbox.pack_start(label_hbox, expand=False, fill=False, padding=5)
    dialog.vbox.pack_start(entry, expand=False, fill=False, padding=5)
    response = dialog.run()
    if response == gtk.RESPONSE_OK:
        new_hosts = [h.strip() for h in entry.get_text().split(",")]
        change_hosts_func(new_hosts)
    dialog.destroy()


def launch_theme_legend(theme):
    """Launch a theme legend window."""
    ThemeLegendWindow(None, theme)


class ScanApp(object):

    """Summarize running suite statuses for a given set of hosts."""

    def __init__(self, hosts=None, owner=None, poll_interval=None):
        gobject.threads_init()
        set_exception_hook_dialog("cylc gscan")
        setup_icons()
        if not hosts:
            hosts = GLOBAL_CFG.get(["suite host scanning", "hosts"])
        self.hosts = hosts
        if owner is None:
            owner = user
        self.owner = owner
        self.window = gtk.Window()
        self.window.set_title("cylc gscan")
        self.window.set_icon(get_icon())
        self.vbox = gtk.VBox()
        self.vbox.show()

        self.theme_name = gcfg.get(['use theme'])
        self.theme = gcfg.get(['themes', self.theme_name])

        self.dots = DotMaker(self.theme)
        suite_treemodel = gtk.TreeStore(str, str, bool, str, int, str, str)
        self._prev_tooltip_location_id = None
        self.suite_treeview = gtk.TreeView(suite_treemodel)

        # Construct the host column.
        host_name_column = gtk.TreeViewColumn("Host")
        cell_text_host = gtk.CellRendererText()
        host_name_column.pack_start(cell_text_host, expand=False)
        host_name_column.set_cell_data_func(
            cell_text_host, self._set_cell_text_host)
        host_name_column.set_sort_column_id(0)
        host_name_column.set_visible(False)
        host_name_column.set_resizable(True)

        # Construct the suite name column.
        suite_name_column = gtk.TreeViewColumn("Suite")
        cell_text_name = gtk.CellRendererText()
        suite_name_column.pack_start(cell_text_name, expand=False)
        suite_name_column.set_cell_data_func(
            cell_text_name, self._set_cell_text_name)
        suite_name_column.set_sort_column_id(1)
        suite_name_column.set_resizable(True)

        # Construct the suite title column.
        suite_title_column = gtk.TreeViewColumn("Title")
        cell_text_title = gtk.CellRendererText()
        suite_title_column.pack_start(cell_text_title, expand=False)
        suite_title_column.set_cell_data_func(
            cell_text_title, self._set_cell_text_title)
        suite_title_column.set_sort_column_id(3)
        suite_title_column.set_visible(False)
        suite_title_column.set_resizable(True)

        # Construct the update time column.
        time_column = gtk.TreeViewColumn("Updated")
        cell_text_time = gtk.CellRendererText()
        time_column.pack_start(cell_text_time, expand=False)
        time_column.set_cell_data_func(
            cell_text_time, self._set_cell_text_time)
        time_column.set_sort_column_id(4)
        time_column.set_visible(False)
        time_column.set_resizable(True)

        self.suite_treeview.append_column(host_name_column)
        self.suite_treeview.append_column(suite_name_column)
        self.suite_treeview.append_column(suite_title_column)
        self.suite_treeview.append_column(time_column)

        # Construct the status column.
        status_column = gtk.TreeViewColumn("Status")
        status_column.set_sort_column_id(5)
        status_column.set_resizable(True)
        status_column_info = 6
        cycle_column_info = 5
        cell_text_cycle = gtk.CellRendererText()
        status_column.pack_start(cell_text_cycle, expand=False)
        status_column.set_cell_data_func(
            cell_text_cycle, self._set_cell_text_cycle, cycle_column_info)
        self.suite_treeview.append_column(status_column)
        distinct_states = len(task_state.legal)
        for i in range(distinct_states):
            cell_pixbuf_state = gtk.CellRendererPixbuf()
            status_column.pack_start(cell_pixbuf_state, expand=False)
            status_column.set_cell_data_func(
                cell_pixbuf_state, self._set_cell_pixbuf_state,
                (status_column_info, i)
            )

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
        self.updater = ScanAppUpdater(
            self.hosts, suite_treemodel, self.suite_treeview,
            owner=self.owner, poll_interval=poll_interval
        )
        self.updater.start()
        self.window.add(self.vbox)
        self.window.connect("destroy", self._on_destroy_event)
        self.window.set_default_size(300, 150)
        self.suite_treeview.grab_focus()
        self.window.show()

    def _on_button_press_event(self, treeview, event):
        # DISPLAY MENU ONLY ON RIGHT CLICK ONLY

        if (event.type != gtk.gdk._2BUTTON_PRESS and
                event.button != 3):
            return False

        treemodel = treeview.get_model()

        x = int(event.x)
        y = int(event.y)
        time = event.time
        pth = treeview.get_path_at_pos(x, y)

        suite_host_tuples = []

        if pth is not None:
            # Add a gcylc launcher item.
            path, col, cellx, celly = pth

            iter_ = treemodel.get_iter(path)
            host, suite = treemodel.get(iter_, 0, 1)
            if suite is None:
                # On an expanded cycle point row, so get from parent.
                host, suite = treemodel.get(treemodel.iter_parent(iter_), 0, 1)
            suite_host_tuples.append((suite, host))

        if event.type == gtk.gdk._2BUTTON_PRESS:
            if suite_host_tuples:
                launch_gcylc(host, suite, owner=self.owner)
            return False

        has_stopped_suites = bool(self.updater.stopped_hosts_suites_info)

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
            suite_host_tuples,
            self.theme_name,
            self._set_theme,
            has_stopped_suites,
            self.updater.clear_stopped_suites,
            self.hosts,
            self.updater.set_hosts,
            self.updater.update_now,
            self.updater.start,
            program_name="cylc gscan",
            extra_items=[view_item],
            owner=self.owner
        )
        menu.popup(None, None, None, event.button, event.time)
        return False

    def _on_destroy_event(self, widget):
        self.updater.quit = True
        gtk.main_quit()
        return False

    def _on_query_tooltip(self, widget, x, y, kbd_ctx, tooltip):
        """Handle a tooltip creation request."""
        tip_context = self.suite_treeview.get_tooltip_context(x, y, kbd_ctx)
        if tip_context is None:
            self._prev_tooltip_location_id = None
            return False
        x, y = self.suite_treeview.convert_widget_to_bin_window_coords(x, y)
        path, column, cell_x, cell_y = (
            self.suite_treeview.get_path_at_pos(x, y))
        model = self.suite_treeview.get_model()
        iter_ = model.get_iter(path)
        parent_iter = model.iter_parent(iter_)
        if parent_iter is None:
            host = model.get_value(iter_, 0)
            suite = model.get_value(iter_, 1)
            child_row_number = None
        else:
            host = model.get_value(parent_iter, 0)
            suite = model.get_value(parent_iter, 1)
            child_row_number = path[-1]
        suite_update_time = model.get_value(iter_, 4)
        location_id = (host, suite, suite_update_time, column.get_title(),
                       child_row_number)

        if location_id != self._prev_tooltip_location_id:
            self._prev_tooltip_location_id = location_id
            tooltip.set_text(None)
            return False
        if column.get_title() in ["Host", "Suite"]:
            tooltip.set_text(suite + " - " + host)
            return True
        if column.get_title() == "Updated":
            time_point = get_timepoint_from_seconds_since_unix_epoch(
                suite_update_time)
            tooltip.set_text(str(time_point))
            return True

        if column.get_title() != "Status":
            tooltip.set_text(None)
            return False
        state_texts = []
        status_column_info = 6
        state_text = model.get_value(iter_, status_column_info)
        if state_text is None:
            tooltip.set_text(None)
            return False
        info = re.findall('\D+\d+', state_text)
        for status_number in info:
            status, number = status_number.rsplit(" ", 1)
            state_texts.append(number + " " + status.strip())
        text = "Tasks: " + ", ".join(state_texts)
        tooltip.set_text(text)
        return True

    def _on_toggle_column_visible(self, menu_item):
        column_index, is_visible = menu_item._connect_args
        column = self.suite_treeview.get_columns()[column_index]
        column.set_visible(not is_visible)
        return False

    def _set_cell_pixbuf_state(self, column, cell, model, iter_, index_tuple):
        status_column_info, index = index_tuple
        state_info = model.get_value(iter_, status_column_info)
        if state_info is not None:
            is_stopped = model.get_value(iter_, 2)
            info = re.findall('\D+\d+', state_info)
            if index < len(info):
                state, num_tasks = info[index].rsplit(" ", 1)
                icon = self.dots.get_icon(state.strip(), is_stopped=is_stopped)
                cell.set_property("visible", True)
            else:
                icon = None
                cell.set_property("visible", False)
        else:
            icon = None
            cell.set_property("visible", False)
        cell.set_property("pixbuf", icon)

    def _set_cell_text_host(self, column, cell, model, iter_):
        host = model.get_value(iter_, 0)
        is_stopped = model.get_value(iter_, 2)
        cell.set_property("sensitive", not is_stopped)
        cell.set_property("text", host)

    def _set_cell_text_name(self, column, cell, model, iter_):
        name = model.get_value(iter_, 1)
        is_stopped = model.get_value(iter_, 2)
        cell.set_property("sensitive", not is_stopped)
        cell.set_property("text", name)

    def _set_cell_text_title(self, column, cell, model, iter_):
        title = model.get_value(iter_, 3)
        is_stopped = model.get_value(iter_, 2)
        cell.set_property("sensitive", not is_stopped)
        cell.set_property("text", title)

    def _set_cell_text_time(self, column, cell, model, iter_):
        suite_update_time = model.get_value(iter_, 4)
        time_point = get_timepoint_from_seconds_since_unix_epoch(
            suite_update_time)
        time_point.set_time_zone_to_local()
        current_time = time.time()
        current_point = (
            get_timepoint_from_seconds_since_unix_epoch(current_time))
        if str(time_point).split("T")[0] == str(current_point).split("T")[0]:
            time_string = str(time_point).split("T")[1]
        else:
            time_string = str(time_point)
        is_stopped = model.get_value(iter_, 2)
        cell.set_property("sensitive", not is_stopped)
        cell.set_property("text", time_string)

    def _set_cell_text_cycle(self, column, cell, model, iter_, active_cycle):
        cycle = model.get_value(iter_, active_cycle)
        is_stopped = model.get_value(iter_, 2)
        cell.set_property("sensitive", not is_stopped)
        cell.set_property("text", cycle)

    def _set_theme(self, new_theme_name):
        self.theme_name = new_theme_name
        self.theme = gcfg.get(['themes', self.theme_name])
        self.dots = DotMaker(self.theme)

    def _set_tooltip(self, widget, text):
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip(widget, text)


class BaseScanUpdater(threading.Thread):

    """Retrieve running suite scan information.

    Subclasses must provide an update method.

    """

    POLL_INTERVAL = 60

    def __init__(self, hosts, owner=None, poll_interval=None):
        self.hosts = hosts
        if owner is None:
            owner = user
        if poll_interval is None:
            poll_interval = self.POLL_INTERVAL
        self.poll_interval = poll_interval
        self.owner = owner
        self.hosts_suites_info = {}
        self.stopped_hosts_suites_info = {}
        self.prev_hosts_suites = []
        self._should_force_update = False
        self.quit = False
        super(BaseScanUpdater, self).__init__()

    def update(self):
        """An update method that must be defined in subclasses."""
        raise NotImplementedError()

    def update_now(self):
        """Force an update as soon as possible."""
        self._should_force_update = True

    def run(self):
        """Execute the main loop of the thread."""
        prev_suites = []
        last_update_time = None
        while not self.quit:
            current_time = time.time()
            if (not self._should_force_update and
                (last_update_time is not None and
                 current_time < last_update_time + self.poll_interval)):
                time.sleep(1)
                continue
            if self._should_force_update:
                self._should_force_update = False

            # Sanitise hosts.
            for host in self.stopped_hosts_suites_info:
                if host not in self.hosts:
                    self.stopped_hosts_suites_info.pop(host)
            for (host, suite) in list(self.prev_hosts_suites):
                if host not in self.hosts:
                    self.prev_hosts_suites.remove((host, suite))

            # Get new information.
            self.hosts_suites_info, self.stopped_hosts_suites_info = (
                update_hosts_suites_info(
                    self.hosts, self.owner,
                    prev_stopped_hosts_suites_info=(
                        self.stopped_hosts_suites_info),
                    prev_hosts_suites=self.prev_hosts_suites
                )
            )
            prev_hosts_suites = []
            for host, suites in self.hosts_suites_info.items():
                for suite in suites:
                    prev_hosts_suites.append((host, suite))
            self.prev_hosts_suites = prev_hosts_suites
            last_update_time = time.time()
            gobject.idle_add(self.update)
            time.sleep(1)

    def set_hosts(self, new_hosts):
        """Set new hosts."""
        del self.hosts[:]
        self.hosts.extend(new_hosts)
        self.update_now()


class BaseScanTimeoutUpdater(object):

    """Retrieve running suite scan information.

    Subclasses must provide an update method.

    """

    IDLE_STOPPED_TIME = None
    POLL_INTERVAL = 60

    def __init__(self, hosts, owner=None, poll_interval=None):
        self.hosts = hosts
        if owner is None:
            owner = user
        if poll_interval is None:
            poll_interval = self.POLL_INTERVAL
        self.poll_interval = poll_interval
        self.owner = owner
        self.hosts_suites_info = {}
        self.stopped_hosts_suites_info = {}
        self._should_force_update = False
        self._last_running_time = None
        self.quit = True
        self.last_update_time = None
        self.prev_hosts_suites = []

    def update(self):
        """An update method that must be defined in subclasses."""
        raise NotImplementedError()

    def update_now(self):
        """Force an update as soon as possible."""
        self._should_force_update = True

    def start(self):
        """Start looping."""
        self.quit = False
        self._last_running_time = None
        gobject.timeout_add(1000, self.run)
        return False

    def stop(self):
        """Stop looping."""
        self.quit = True

    def run(self):
        """Extract running suite information at particular intervals."""
        if self.quit:
            return False
        current_time = time.time()
        if (self._last_running_time is not None and
                self.IDLE_STOPPED_TIME is not None and
                current_time > (
                    self._last_running_time + self.IDLE_STOPPED_TIME)):
            self.stop()
            return True
        if (not self._should_force_update and
                (self.last_update_time is not None and
                 current_time < self.last_update_time + self.poll_interval)):
            return True
        if self._should_force_update:
            self._should_force_update = False

        # Sanitise hosts.
        for host in self.stopped_hosts_suites_info.keys():
            if host not in self.hosts:
                self.stopped_hosts_suites_info.pop(host)
        for (host, suite) in list(self.prev_hosts_suites):
            if host not in self.hosts:
                self.prev_hosts_suites.remove((host, suite))

        # Get new information.
        self.hosts_suites_info, self.stopped_hosts_suites_info = (
            update_hosts_suites_info(
                self.hosts, self.owner,
                prev_stopped_hosts_suites_info=self.stopped_hosts_suites_info,
                prev_hosts_suites=self.prev_hosts_suites
            )
        )
        prev_hosts_suites = []
        for host, suites in self.hosts_suites_info.items():
            for suite in suites:
                prev_hosts_suites.append((host, suite))
        self.prev_hosts_suites = prev_hosts_suites
        self.last_update_time = time.time()
        if self.hosts_suites_info:
            self._last_running_time = None
        else:
            self._last_running_time = self.last_update_time
        gobject.idle_add(self.update)
        return True

    def set_hosts(self, new_hosts):
        del self.hosts[:]
        self.hosts.extend(new_hosts)
        self.update_now()


class ScanAppUpdater(BaseScanUpdater):

    """Update the scan app."""

    def __init__(self, hosts, suite_treemodel, suite_treeview, owner=None,
                 poll_interval=None):
        self.suite_treemodel = suite_treemodel
        self.suite_treeview = suite_treeview
        super(ScanAppUpdater, self).__init__(hosts, owner=owner,
                                             poll_interval=poll_interval)

    def _add_expanded_row(self, view, rpath, row_ids):
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

    def clear_stopped_suites(self):
        """Clear stopped suite information that may have built up."""
        self.stopped_hosts_suites_info.clear()
        gobject.idle_add(self.update)

    def update(self):
        """Update the Applet."""
        row_ids = self._get_user_expanded_row_ids()
        info = copy.deepcopy(self.hosts_suites_info)
        stop_info = copy.deepcopy(self.stopped_hosts_suites_info)
        self.suite_treemodel.clear()
        suite_host_tuples = []
        for host in self.hosts:
            suites = (info.get(host, {}).keys() +
                      stop_info.get(host, {}).keys())
            for suite in suites:
                if (suite, host) not in suite_host_tuples:
                    suite_host_tuples.append((suite, host))
        suite_host_tuples.sort()
        for suite, host in suite_host_tuples:
            if suite in info.get(host, {}):
                suite_info = info[host][suite]
                is_stopped = False
            else:
                suite_info = stop_info[host][suite]
                is_stopped = True
            suite_updated_time = suite_info.get(
                "update-time", int(time.time())
            )
            title = suite_info.get("title")

            for key in sorted(suite_info):
                if key.startswith("states"):
                    # Set up the columns, including the cycle point column.
                    if key == "states":
                        model_data = [
                            host, suite, is_stopped, title, suite_updated_time]
                        model_data.append(None)
                    else:
                        model_data = [
                            None, None, is_stopped, title, suite_updated_time]
                        model_data.append(key.replace("states:", "", 1))

                    # Add the state count column (e.g. 'failed 1 succeeded 2').
                    states_text = ""
                    for state, number in sorted(suite_info[key].items(),
                                                key=lambda _: _[1]):
                        if state != "runahead":
                            # 'runahead' states are usually hidden.
                            states_text += '%s %d ' % (state, number)
                    if not states_text:
                        # Purely runahead cycle.
                        continue
                    model_data.append(states_text.rstrip())
                    if key == "states":
                        parent_iter = self.suite_treemodel.append(
                            None, model_data)
                    else:
                        self.suite_treemodel.append(parent_iter, model_data)
        self.suite_treemodel.foreach(self._expand_row, row_ids)
        return False


def update_hosts_suites_info(hosts, owner, prev_stopped_hosts_suites_info=None,
                             prev_hosts_suites=None,
                             stop_suite_clear_time=86400):
    """Return dictionaries of host suite info and stopped host suite info."""
    hosts = copy.deepcopy(hosts)
    hosts_suites_info = get_hosts_suites_info(hosts, owner=owner)

    if prev_stopped_hosts_suites_info is None:
        prev_stopped_hosts_suites_info = {}
    if prev_hosts_suites is None:
        prev_hosts_suites = []
    stopped_hosts_suites_info = copy.deepcopy(prev_stopped_hosts_suites_info)
    current_time = time.time()
    current_hosts_suites = []
    for host, suites in hosts_suites_info.items():
        for suite, suite_info in suites.items():
            if 'state' not in suite_info or 'update-time' not in suite_info:
                continue
            if (host in stopped_hosts_suites_info and
                    suite in stopped_hosts_suites_info[host]):
                stopped_hosts_suites_info[host].pop(suite)
            current_hosts_suites.append((host, suite))

    # Detect newly stopped suites and get some info for them.
    for host, suite in prev_hosts_suites:
        if (host, suite) not in current_hosts_suites:
            stopped_hosts_suites_info.setdefault(host, {})
            suite_info = get_unscannable_suite_info(host, suite, owner=owner)
            if suite_info:
                stopped_hosts_suites_info[host][suite] = suite_info

    # Remove expired stopped suites.
    for host in stopped_hosts_suites_info:
        remove_suites = []
        for suite, suite_info in stopped_hosts_suites_info[host].items():
            update_time = suite_info.get('update-time', 0)
            if (update_time + stop_suite_clear_time < current_time):
                remove_suites.append(suite)
        for suite in remove_suites:
            stopped_hosts_suites_info[host].pop(suite)
    return hosts_suites_info, stopped_hosts_suites_info
