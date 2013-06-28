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

import copy
import datetime
import os
import re
import shlex
import subprocess
import threading
import time

import gtk
import gobject
#import pygtk
#pygtk.require('2.0')

from cylc.global_config import gcfg
from cylc.gui.gcylc_config import config
from cylc.gui.legend import ThemeLegendWindow
from cylc.gui.SuiteControl import run_get_stdout
from cylc.gui.DotMaker import DotMaker
from cylc.gui.util import get_icon, setup_icons
from cylc.owner import user
from cylc.version import cylc_version


PYRO_TIMEOUT = 2


def get_host_suites(hosts, timeout=None, owner=None):
    """Return a dictionary of hosts and their running suites."""
    if owner is None:
        owner = user
    host_suites_map = {}
    if timeout is None:
        timeout = PYRO_TIMEOUT
    for host in hosts:
        host_suites_map[host] = []
        command = ["cylc", "scan", "--host=%s" % host,
                   "--owner=%s" % owner, "--pyro-timeout=%s" % timeout]
        popen = subprocess.Popen( command,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE )
        stdout = popen.stdout.read()
        res = popen.wait()
        if res == 0 and stdout:
            for line in stdout.splitlines():
                if line:
                    host_suites_map[host].append(line.split()[0])
    return host_suites_map


def get_status_tasks(host, suite, owner=None):
    """Return a dictionary of statuses and tasks, or None."""
    if owner is None:
        owner = user
    command = ["cylc", "cat-state", "--host=%s" % host,
               "--owner=%s" % owner, suite]
    popen = subprocess.Popen( command,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE )
    stdout = popen.stdout.read()
    res = popen.wait()
    if res != 0:
        return None
    status_tasks = {}
    for line in stdout.rpartition("Begin task states")[2].splitlines():
        task_result = re.match("([^ ]+) : status=([^,]+), spawned", line)
        if not task_result:
            continue
        task, status = task_result.groups()
        status_tasks.setdefault(status, [])
        status_tasks[status].append(task)
    return status_tasks


def get_summary_menu(suite_host_tuples,
                     usercfg, theme_name, set_theme_func,
                     has_stopped_suites, clear_stopped_suites_func,
                     scanned_hosts, change_hosts_func,
                     program_name, extra_items=None, owner=None):
    """Return a right click menu for summary GUIs.

    suite_host_tuples should be a list of (suite, host) tuples (if any).
    usercfg should be the gcylc config object.
    theme_name should be the name of the current theme.
    set_theme_func should be a function accepting a new theme name.
    has_stopped_suites should be a boolean denoting currently
    stopped suites.
    clear_stopped_suites should be a function with no arguments that
    removes stopped suites from the current view.
    scanned_hosts should be a list of currently scanned suite hosts.
    change_hosts_func should be a function accepting a new list of
    suite hosts to scan.
    program_name should be a string describing the parent program.
    extra_items (keyword) should be a list of extra menu items to add
    to the right click menu.
    owner (keyword) should be the owner of the suites, if not the
    current user.

    """
    menu = gtk.Menu()
    
    for suite, host in suite_host_tuples:
        gcylc_item = gtk.ImageMenuItem(stock_id="gcylc")
        gcylc_item.set_label("Launch gcylc: %s - %s" % (suite, host))
        gcylc_item._connect_args = (suite, host)
        gcylc_item.connect("button-press-event",
                            lambda b, e: launch_gcylc(
                                                b._connect_args[1],
                                                b._connect_args[0],
                                                owner=owner))
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

    # Construct theme chooser items (same as cylc.gui.SuiteControl).
    theme_item = gtk.ImageMenuItem('Theme')
    img = gtk.image_new_from_stock(gtk.STOCK_SELECT_COLOR, gtk.ICON_SIZE_MENU)
    theme_item.set_image(img)
    thememenu = gtk.Menu()
    theme_item.set_submenu(thememenu)
    theme_item.show()

    theme_items = {}
    theme = "default"
    theme_items[theme] = gtk.RadioMenuItem(label=theme)
    thememenu.append(theme_items[theme])
    theme_items[theme].theme_name = theme
    for theme in usercfg['themes']:
        if theme == "default":
            continue
        theme_items[theme] = gtk.RadioMenuItem(group=theme_items['default'], label=theme)
        thememenu.append(theme_items[theme])
        theme_items[theme].theme_name = theme

    # set_active then connect, to avoid causing an unnecessary toggle now.
    theme_items[theme_name].set_active(True)
    for theme in usercfg['themes']:
        theme_items[theme].show()
        theme_items[theme].connect('toggled',
                                   lambda i: (i.get_active() and
                                              set_theme_func(i.theme_name)))

    menu.append(theme_item)
    theme_legend_item = gtk.MenuItem("Show task state key")
    theme_legend_item.show()
    theme_legend_item.connect("button-press-event",
                              lambda b, e: launch_theme_legend(
                                        usercfg['themes'][theme_name]))
    menu.append(theme_legend_item)
    sep_item = gtk.SeparatorMenuItem()
    sep_item.show()
    menu.append(sep_item)
    
    # Construct a clean stopped suites item.

    clear_item = gtk.ImageMenuItem(stock_id=gtk.STOCK_CLEAR)
    clear_item.set_label("Clear Stopped Suites")
    clear_item.show()
    clear_item.set_sensitive(has_stopped_suites)
    clear_item.connect("button-press-event",
                        lambda b, e: clear_stopped_suites_func())
    menu.append(clear_item)

    hosts_item = gtk.ImageMenuItem(stock_id=gtk.STOCK_PREFERENCES)
    hosts_item.set_label("Configure Hosts")
    hosts_item.show()
    hosts_item.connect("button-press-event",
                       lambda b, e: launch_hosts_dialog(scanned_hosts,
                                                        change_hosts_func))
    menu.append(hosts_item)

    sep_item = gtk.SeparatorMenuItem()
    sep_item.show()
    menu.append(sep_item)

    info_item = gtk.ImageMenuItem(stock_id=gtk.STOCK_ABOUT)
    info_item.set_label("About")
    info_item.show()
    info_item.connect("button-press-event",
                      lambda b, e: launch_about_dialog(
                                          program_name,
                                          scanned_hosts))
    menu.append(info_item)
    return menu


def launch_about_dialog(program_name, hosts):
    """Launch a modified version of the SuiteControl.py about dialog."""
    hosts_text = "Hosts monitored: " + ", ".join(hosts)
    comments_text = hosts_text
    about = gtk.AboutDialog()
    if gtk.gtk_version[0] == 2 and gtk.gtk_version[1] >= 12:
        # set_program_name() was added in PyGTK 2.12
        about.set_program_name(program_name)
    else:
        comments_text = program_name + "\n" + hosts_text

    about.set_version(cylc_version)
    about.set_copyright("Copyright (C) 2008-2013 Hilary Oliver, NIWA")
    about.set_comments(comments_text)
    about.set_icon(get_icon())
    about.run()
    about.destroy()


def launch_gcylc(host, suite, owner=None):
    """Launch gcylc for a given suite and host."""
    if owner is None:
        owner = user
    stdout = open(os.devnull, "w")
    stderr = stdout
    command = "cylc gui --host=%s --owner=%s %s" % (
                                         host, owner, suite)
    command = shlex.split(command)
    subprocess.Popen(command, stdout=stdout, stderr=stderr)


def launch_gsummary(*args, **kwargs):
    """Launch gcylc for a given suite and host."""
    stdout = open(os.devnull, "w")
    stderr = stdout
    command = "cylc gsummary"
    command = shlex.split(command)
    subprocess.Popen(command, stdout=stdout, stderr=stderr)


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


class SummaryApp(object):

    """Summarize running suite statuses for a given set of hosts."""

    def __init__(self, hosts=None, owner=None, poll_interval=None):
        gobject.threads_init()
        setup_icons()
        if not hosts:
            try:
                hosts = gcfg.sitecfg["suite host scanning"]["hosts"]
            except KeyError:
                hosts = ["localhost"]
        self.hosts = hosts
        if owner is None:
            owner = user
        self.owner = owner
        self.window = gtk.Window()
        self.window.set_title("cylc gsummary")
        self.window.set_icon(get_icon())
        self.vbox = gtk.VBox()
        self.vbox.show()
        self.usercfg = config().cfg
        self.theme_name = self.usercfg['use theme'] 
        self.theme = self.usercfg['themes'][self.theme_name]
        self.dots = DotMaker(self.theme)
        suite_treemodel = gtk.TreeStore(*([str, str, bool, int] + [str] * 20))
        self.suite_treeview = gtk.TreeView(suite_treemodel)
        
        # Construct the host column.
        host_name_column = gtk.TreeViewColumn("Host")
        cell_text_host = gtk.CellRendererText()
        host_name_column.pack_start(cell_text_host, expand=False)
        host_name_column.set_cell_data_func(
                  cell_text_host, self._set_cell_text_host)
        host_name_column.set_sort_column_id(0)
        host_name_column.set_visible(False)
        
        # Construct the suite column.
        suite_name_column = gtk.TreeViewColumn("Suite")
        cell_text_name = gtk.CellRendererText()
        suite_name_column.pack_start(cell_text_name, expand=False)
        suite_name_column.set_cell_data_func(
                   cell_text_name, self._set_cell_text_name)
        suite_name_column.set_sort_column_id(1)
 
        # Construct the update time column.
        time_column = gtk.TreeViewColumn("Updated")
        cell_text_time = gtk.CellRendererText()
        time_column.pack_start(cell_text_time, expand=False)
        time_column.set_cell_data_func(
                    cell_text_time, self._set_cell_text_time)
        time_column.set_sort_column_id(2)
        time_column.set_visible(False)

        # Construct the status column.
        status_column = gtk.TreeViewColumn("Status")
        status_column.set_sort_column_id(4)
        for i in range(4, 24):
            cell_pixbuf_state = gtk.CellRendererPixbuf()
            status_column.pack_start(cell_pixbuf_state, expand=False)
            status_column.set_cell_data_func(
                   cell_pixbuf_state, self._set_cell_pixbuf_state, i)
        
        self.suite_treeview.append_column(host_name_column)
        self.suite_treeview.append_column(suite_name_column)
        self.suite_treeview.append_column(time_column)
        self.suite_treeview.append_column(status_column)
        self.suite_treeview.show()
        self.suite_treeview.connect("button-press-event",
                                    self._on_button_press_event)
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,
                                   gtk.POLICY_AUTOMATIC)
        scrolled_window.add(self.suite_treeview)
        scrolled_window.show()
        self.vbox.pack_start(scrolled_window, expand=True, fill=True)
        self.updater = SummaryAppUpdater(self.hosts, suite_treemodel,
                                         owner=self.owner,
                                         poll_interval=poll_interval)
        self.updater.start()
        self.window.add(self.vbox)
        self.window.connect("destroy", self._on_destroy_event)
        self.window.set_default_size(200, 100)
        self.suite_treeview.grab_focus()
        self.window.show()

    def _on_button_press_event(self, treeview, event):
        # DISPLAY MENU ONLY ON RIGHT CLICK ONLY
        if event.button != 3:
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
            suite_host_tuples.append((suite, host))

        has_stopped_suites = bool(self.updater.stop_summaries)

        view_item = gtk.ImageMenuItem(stock_id=gtk.STOCK_INDEX)
        view_item.set_label("View Column...")
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

        menu = get_summary_menu(suite_host_tuples,
                                self.usercfg,
                                self.theme_name,
                                self._set_theme,
                                has_stopped_suites,
                                self.updater.clear_stopped_suites,
                                program_name="cylc gsummary",
                                scanned_hosts=self.hosts,
                                change_hosts_func=self._set_hosts,
                                extra_items=[view_item],
                                owner=self.owner)
        menu.popup( None, None, None, event.button, event.time )
        return False

    def _on_destroy_event(self, widget):
        self.updater.quit = True
        gtk.main_quit()
        return False

    def _on_toggle_column_visible(self, menu_item):
        column_index, is_visible = menu_item._connect_args
        column = self.suite_treeview.get_columns()[column_index]
        column.set_visible(not is_visible)
        return False

    def _set_cell_pixbuf_state(self, column, cell, model, iter_, index):
        state_info = model.get_value(iter_, index)
        if state_info is None:
            cell.set_property("pixbuf", None)
            cell.set_property("visible", False)
            return
        is_stopped = model.get_value(iter_, 2)
        state, num_tasks = state_info.rsplit(" ", 1)
        icon = self.dots.get_icon(state, is_stopped=is_stopped)
        cell.set_property("pixbuf", icon)
        cell.set_property("visible", True)

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

    def _set_cell_text_time(self, column, cell, model, iter_):
        update_time = model.get_value(iter_, 3)
        time_object = datetime.datetime.fromtimestamp(update_time)
        time_string = time_object.strftime("%H:%M:%S")
        is_stopped = model.get_value(iter_, 2)
        cell.set_property("sensitive", not is_stopped)
        cell.set_property("text", time_string)

    def _set_hosts(self, new_hosts):
        del self.hosts[:]
        for host in new_hosts:
            self.hosts.append(host)

    def _set_theme(self, new_theme_name):
        self.theme_name = new_theme_name
        self.theme = self.usercfg['themes'][self.theme_name]
        self.dots = DotMaker(self.theme)

    def _set_tooltip(self, widget, text):
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip(widget, text)


class BaseSummaryUpdater(threading.Thread):

    """Retrieve running suite summary information.

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
        self.statuses = {}
        self.stop_summaries = {}
        self.prev_suites = []
        self.quit = False
        super(BaseSummaryUpdater, self).__init__()

    def update(self, update_time=None):
        """An update method that must be defined in subclasses."""
        raise NotImplementedError()

    def run(self):
        """Execute the main loop of the thread."""
        prev_suites = {}
        last_update_time = None
        while not self.quit:
            current_time = time.time()
            if (last_update_time is not None and
                current_time < last_update_time + self.poll_interval):
                time.sleep(1)
                continue
            statuses, stop_summaries = get_new_statuses_and_stop_summaries(
                            self.hosts, self.owner,
                            prev_stop_summaries=self.stop_summaries,
                            prev_suites=self.prev_suites)
            prev_suites = []
            for host in statuses:
                for suite in statuses[host]:
                    prev_suites.append((host, suite))
            self.prev_suites = prev_suites
            self.statuses = statuses
            self.stop_summaries = stop_summaries
            last_update_time = time.time()
            gobject.idle_add(self.update, current_time)
            time.sleep(1)


class BaseSummaryTimeoutUpdater(object):

    """Retrieve running suite summary information.

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
        self.statuses = {}
        self.stop_summaries = {}
        self.quit = False
        self.last_update_time = None
        self.prev_suites = []

    def update(self, update_time=None):
        """An update method that must be defined in subclasses."""
        raise NotImplementedError()

    def start(self):
        """Start looping."""
        gobject.timeout_add(1000, self.run)

    def run(self):
        """Extract running suite information at particular intervals."""
        if self.quit:
            return False
        current_time = time.time()
        if (self.last_update_time is not None and
            current_time < self.last_update_time + self.poll_interval):
            return True
        statuses, stop_summaries = get_new_statuses_and_stop_summaries(
                       self.hosts, self.owner,
                       prev_stop_summaries=self.stop_summaries,
                       prev_suites=self.prev_suites)
        prev_suites = []
        for host in statuses:
            for suite in statuses[host]:
                prev_suites.append((host, suite))
        self.prev_suites = prev_suites
        self.statuses = statuses
        self.stop_summaries = stop_summaries
        self.last_update_time = time.time()
        gobject.idle_add(self.update, current_time)
        return True


class SummaryAppUpdater(BaseSummaryUpdater):

    """Update the summary app."""
    
    def __init__(self, hosts, suite_treemodel, owner=None,
                 poll_interval=None):
        self.suite_treemodel = suite_treemodel
        super(SummaryAppUpdater, self).__init__(hosts, owner=owner,
                                                poll_interval=poll_interval)

    def clear_stopped_suites(self):
        """Clear stopped suite information that may have built up."""
        self.stop_summaries.clear()
        gobject.idle_add(self.update)

    def update(self, update_time=None):
        """Update the Applet."""
        statuses = copy.deepcopy(self.statuses)
        stop_summaries = copy.deepcopy(self.stop_summaries)
        if update_time is None:
            update_time = time.time()
        self.suite_treemodel.clear()
        suite_host_tuples = []
        for host in self.hosts:
            suites = (statuses.get(host, {}).keys() +
                      stop_summaries.get(host, {}).keys())
            for suite in suites:
                suite_host_tuples.append((suite, host))
        suite_host_tuples.sort()
        for suite, host in suite_host_tuples:
            if suite in statuses.get(host, {}):
                status_map_items = statuses[host][suite].items()
                is_stopped = False
                suite_time = update_time
            else:
                info = stop_summaries[host][suite]
                status_map, suite_time = info
                status_map_items = status_map.items()
                is_stopped = True
            status_map_items.sort()
            status_map_items.sort(lambda x, y: cmp(len(y[1]), len(x[1])))
            states = [s[0] + " " + str(len(s[1])) for s in status_map_items]
            model_data = [host, suite, is_stopped, suite_time]
            model_data += states[:20]
            model_data += [None] * (24 - len(model_data))
            self.suite_treemodel.append(None, model_data)
        return False


def get_new_statuses_and_stop_summaries(hosts, owner, prev_stop_summaries=None,
                                        prev_suites=None,
                                        stop_suite_clear_time=86400):
    """Return dictionaries of statuses and stop_summaries."""
    hosts = copy.deepcopy(hosts)
    host_suites = get_host_suites(hosts, owner=owner)
    if prev_stop_summaries is None:
        prev_stop_summaries = {}
    if prev_suites is None:
        prev_suites = []
    statuses = {}
    stop_summaries = copy.deepcopy(prev_stop_summaries)
    current_time = time.time()
    current_suites = []
    for host in hosts:
        for suite in host_suites[host]:
            status_tasks = get_status_tasks(host, suite,
                                            owner=owner)
            if status_tasks is None:
                continue
            statuses.setdefault(host, {})
            statuses[host].setdefault(suite, {})
            statuses[host][suite] = status_tasks
            if (host in stop_summaries and
                suite in stop_summaries[host]):
                stop_summaries[host].pop(suite)
            current_suites.append((host, suite))
    for host, suite in prev_suites:
        if (host, suite) not in current_suites:
            stop_summaries.setdefault(host, {})
            summary_statuses = get_status_tasks(host, suite,
                                                owner=owner)
            if summary_statuses is None:
                continue
            stop_summaries[host][suite] = (summary_statuses,
                                           current_time)
    prev_suites = copy.deepcopy(current_suites)
    for host in stop_summaries:
        for suite in stop_summaries[host].keys():
            if (stop_summaries[host][suite][1] +
                stop_suite_clear_time < current_time):
                stop_summaries[host].pop(suite)
    return statuses, stop_summaries
