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
"""The main control GUI of gcylc."""

import os
import re
import sys
import gtk
import gobject
import pango
import socket
import subprocess
from isodatetime.parsers import TimePointParser

from cylc.suite_host import is_remote_host
from cylc.owner import is_remote_user
from cylc.gui.dbchooser import dbchooser
from cylc.gui.combo_logviewer import ComboLogViewer
from cylc.gui.warning_dialog import warning_dialog, info_dialog

try:
    from cylc.gui.view_graph import ControlGraph
    from cylc.gui.graph import graph_suite_popup
except ImportError, x:
    # pygraphviz not installed
    warning_dialog("WARNING: graph view disabled\n" + str(x)).warn()
    graphing_disabled = True
else:
    graphing_disabled = False

from cylc.gui.legend import ThemeLegendWindow
from cylc.gui.view_dot import ControlLED
from cylc.gui.view_tree import ControlTree
from cylc.gui.dot_maker import DotMaker
from cylc.gui.updater import Updater
from cylc.gui.util import (
    get_icon, get_image_dir, get_logo, EntryTempText,
    EntryDialog, setup_icons, set_exception_hook_dialog)
from cylc import cylc_pyro_client
from cylc.state_summary import extract_group_state
from cylc.task_id import TaskID
from cylc.version import CYLC_VERSION
from cylc.gui.option_group import controlled_option_group
from cylc.gui.color_rotator import rotator
from cylc.gui.cylc_logviewer import cylc_logviewer
from cylc.gui.gcapture import gcapture_tmpfile
from cylc.task_state import task_state
from cylc.passphrase import passphrase
from cylc.suite_logging import suite_log
from cylc.registration import localdb
from cylc.cfgspec.globalcfg import GLOBAL_CFG
from cylc.cfgspec.gcylc import gcfg
from cylc.wallclock import get_time_string_from_unix_time


def run_get_stdout(command, filter=False):
    try:
        popen = subprocess.Popen(command, shell=True, stderr=subprocess.PIPE,
                                 stdout=subprocess.PIPE)
        out = popen.stdout.read()
        err = popen.stderr.read()
        res = popen.wait()
        if res < 0:
            warning_dialog(
                "ERROR: command terminated by signal %d\n%s" % (res, err)
            ).warn()
            return (False, [])
        elif res > 0:
            warning_dialog(
                "ERROR: command failed %d\n%s" % (res, err)).warn()
            return (False, [])
    except OSError, e:
        warning_dialog(
            "ERROR: command invocation failed %s\n%s" % (str(e), err)).warn()
        return (False, [])
    else:
        # output is a single string with newlines; but we return a list of
        # lines filtered (optionally) for a special '!cylc!' prefix.
        res = []
        for line in out.split('\n'):
            line.strip()
            if filter:
                if line.startswith('!cylc!'):
                    res.append(line[6:])
            else:
                res.append(line)
        return (True, res)
    return (False, [])


class TaskFilterWindow(gtk.Window):
    """
    A popup window displaying task filtering options.
    """
    def __init__(self, parent_window, widgets, reset_task_filters):
        super(TaskFilterWindow, self).__init__()
        self.set_border_width(10)
        self.set_title("Task Filtering")
        if parent_window is None:
            self.set_icon(get_icon())
        else:
            self.set_transient_for(parent_window)
        self.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
        vbox = gtk.VBox()
        button = gtk.Button("_Reset")
        button.connect("clicked", reset_task_filters)
        vbox.pack_start(widgets)
        vbox.pack_start(button)
        self.add(vbox)
        self.show_all()


class InitData(object):
    """
Class to hold initialisation data.
    """
    def __init__(self, suite, owner, host, port, db,
                 pyro_timeout, template_vars, template_vars_file,
                 ungrouped_views, use_defn_order):
        self.suite = suite
        self.owner = owner
        self.host = host
        self.port = port
        self.db = db
        if pyro_timeout:
            self.pyro_timeout = float(pyro_timeout)
        else:
            self.pyro_timeout = None

        self.template_vars_opts = ""
        for tv in template_vars:
            self.template_vars_opts += " --set " + tv
        if template_vars_file:
            self.template_vars_opts += " --set-file " + template_vars_file
        self.template_vars = template_vars
        self.template_vars_file = template_vars_file
        self.ungrouped_views = ungrouped_views
        self.use_defn_order = use_defn_order

        self.cylc_tmpdir = GLOBAL_CFG.get_tmpdir()
        self.no_prompt = GLOBAL_CFG.get(
            ['disable interactive command prompts']
        )
        self.imagedir = get_image_dir()

        if suite:
            self.reset(suite)

    def reset(self, suite):
        self.suite = suite
        suitedir = None
        if not is_remote_host(self.host) and not is_remote_user(self.owner):
            db = localdb(file=self.db)
            suitedir = db.get_suitedir(suite)
        # get the suite passphrase (required for local or remote suites)
        self.pphrase = passphrase(suite, self.owner,
                                  self.host).get(suitedir=suitedir)
        self.logdir = suite_log(suite).get_dir()


class InfoBar(gtk.VBox):
    """
Class to create an information bar.
    """

    def __init__(self, host, theme, dot_size, filter_states_excl,
                 filter_launcher,
                 status_changed_hook=lambda s: False,
                 log_launch_hook=lambda: False):
        super(InfoBar, self).__init__()

        self.host = host

        self.set_theme(theme, dot_size)

        self.filter_launcher = filter_launcher
        self._suite_states = []
        self._filter_states_excl = filter_states_excl
        self._filter_name_string = None
        self._is_suite_stopped = False
        self.state_widget = gtk.HBox()
        self.filter_state_widget = gtk.HBox()
        self._set_tooltip(self.state_widget, "states")
        self._set_tooltip(self.filter_state_widget, "states filtered out")

        self._status = "status..."
        self.notify_status_changed = status_changed_hook
        self.status_widget = gtk.Label()
        self._set_tooltip(self.status_widget, "status")

        self._log_content = ""
        self._log_size = 0
        self.log_launch_hook = log_launch_hook
        self.log_widget = gtk.HBox()
        eb = gtk.EventBox()
        eb.connect('enter-notify-event',
                   lambda b, e: b.set_state(gtk.STATE_ACTIVE))
        eb.connect('leave-notify-event',
                   lambda b, e: b.set_state(gtk.STATE_NORMAL))
        self._log_widget_image = gtk.image_new_from_stock(
            gtk.STOCK_DIALOG_WARNING, gtk.ICON_SIZE_MENU)
        eb.add(self._log_widget_image)
        eb.connect('button-press-event', self._log_widget_launch_hook)
        self._log_widget_image.set_sensitive(False)
        self.log_widget.pack_start(eb, expand=False)
        self._set_tooltip(self.log_widget, "log")

        self._mode = "mode..."
        self.mode_widget = gtk.Label()
        self._set_tooltip(self.mode_widget, "mode")

        self._runahead = ""
        self.runahead_widget = gtk.Label()
        self._set_tooltip(self.runahead_widget, "runahead limit")

        self._time = "time..."
        self.time_widget = gtk.Label()
        self._set_tooltip(self.time_widget, "last update time")

        hbox = gtk.HBox()
        self.pack_start(hbox, False, True)

        eb = gtk.EventBox()
        eb.add(self.status_widget)
        hbox.pack_start(eb, False)

        eb = gtk.EventBox()
        eb.add(self.filter_state_widget)
        hbox.pack_start(eb, False)

        eb = gtk.EventBox()
        hbox.pack_start(eb, True)

        eb = gtk.EventBox()
        eb.add(self.state_widget)
        hbox.pack_start(eb, False)

        eb = gtk.EventBox()
        eb.add(self.mode_widget)
        hbox.pack_start(eb, False)

        eb = gtk.EventBox()
        eb.add(self.runahead_widget)
        hbox.pack_start(eb, False)

        eb = gtk.EventBox()
        eb.add(self.time_widget)
        hbox.pack_start(eb, False)

        eb = gtk.EventBox()
        eb.add(self.log_widget)
        hbox.pack_start(eb, False)

    def set_theme(self, theme, dot_size):
        self.dots = DotMaker(theme, size=dot_size)

    def set_log(self, log_text, log_size):
        """Set log text."""
        if log_size == 0:
            self._log_widget_image.hide()
        else:
            self._log_widget_image.show()
        if log_size == self._log_size:
            return False
        self._log_widget_image.set_sensitive(True)
        if hasattr(self.log_widget, "set_tooltip_markup"):
            for snippet, colour in [("WARNING", "orange"),
                                    ("ERROR", "red"),
                                    ("CRITICAL", "purple")]:
                log_text = log_text.replace(
                    snippet,
                    "<span background='%s' foreground='black'>%s</span>" % (
                        colour, snippet))
            self._log_content = log_text
            gobject.idle_add(self.log_widget.set_tooltip_markup,
                             self._log_content)
        else:
            self._log_content = log_text
            gobject.idle_add(self._set_tooltip, self.log_widget,
                             self._log_content)
        self._log_size = log_size

    def set_mode(self, mode):
        """Set mode text."""
        if mode == self._mode:
            return False
        self._mode = mode
        gobject.idle_add(self.mode_widget.set_markup,
                         "  " + self._mode + "  ")

    def set_runahead(self, runahead):
        """Set runahead limit."""
        if runahead == self._runahead:
            return False
        self._runahead = runahead
        text = "runahead:" + str(runahead) + "h  "
        if runahead is None:
            text = ""
        gobject.idle_add(self.runahead_widget.set_text, text)

    def set_state(self, suite_states, is_suite_stopped=None):
        """Set state text."""
        if (suite_states == self._suite_states and
            (is_suite_stopped is None or
             is_suite_stopped == self._is_suite_stopped)):
            return False
        self._suite_states = suite_states
        self._is_suite_stopped = is_suite_stopped
        gobject.idle_add(self._set_state_widget)

    def _set_state_widget(self):
        state_info = {}
        for state in self._suite_states:
            state_info.setdefault(state, 0)
            state_info[state] += 1
        for child in self.state_widget.get_children():
            self.state_widget.remove(child)
        items = state_info.items()
        items.sort()
        items.sort(lambda x, y: cmp(y[1], x[1]))
        for state, num in items:
            icon = self.dots.get_image(state,
                                       is_stopped=self._is_suite_stopped)
            icon.show()
            self.state_widget.pack_start(icon, False, False)
            if self._is_suite_stopped:
                text = str(num) + " tasks stopped with " + str(state)
            else:
                text = str(num) + " tasks " + str(state)
            self._set_tooltip(icon, text)

    def set_filter_state(self, filter_states_excl, filter_name_string):
        """Set filter state text."""
        if filter_states_excl == self._filter_states_excl and (
                filter_name_string == self._filter_name_string):
            return False
        self._filter_states_excl = filter_states_excl
        self._filter_name_string = filter_name_string
        gobject.idle_add(self._set_filter_state_widget)

    def _set_filter_state_widget(self):
        for child in self.filter_state_widget.get_children():
            self.filter_state_widget.remove(child)
        if not self._filter_states_excl and not self._filter_name_string:
            label = gtk.Label("(click-to-filter)")
            ebox = gtk.EventBox()
            ebox.add(label)
            ebox.connect("button_press_event", self.filter_launcher)
            self.filter_state_widget.pack_start(ebox, False, False)
            ttip_text = "Click to filter tasks by state or name"
        else:
            ttip_text = "Current filtering (click to alter):\n%s" % (
                ", ".join(self._filter_states_excl))
            hbox = gtk.HBox()
            hbox.pack_start(gtk.Label("(filtered:"))
            for state in self._filter_states_excl:
                icon = self.dots.get_image(state, is_filtered=True)
                icon.show()
                hbox.pack_start(icon, False, False)
            if self._filter_name_string:
                label = gtk.Label(" %s" % self._filter_name_string)
                hbox.pack_start(label)
                ttip_text += ", %s" % self._filter_name_string
            hbox.pack_start(gtk.Label(")"))
            ebox = gtk.EventBox()
            ebox.add(hbox)
            ebox.connect("button_press_event", self.filter_launcher)
            self.filter_state_widget.pack_start(ebox, False, False)
        self.filter_state_widget.show_all()
        self._set_tooltip(self.filter_state_widget, ttip_text)

    def set_status(self, status):
        """Set status text."""
        if status == self._status:
            return False
        self._status = status
        gobject.idle_add(
            self.status_widget.set_text, " " + self._status + "   ")
        gobject.idle_add(self.notify_status_changed, self._status)

    def set_stop_summary(self, summary_maps):
        """Set various summary info."""
        # new string format() introduced in Python 2.6
        # o>summary = "stopped with '{0}'"
        summary = "stopped with '%s'"
        glob, task, fam = summary_maps
        states = [t["state"] for t in task.values() if "state" in t]

        self.set_state(states, is_suite_stopped=True)
        suite_state = "?"
        if states:
            suite_state = extract_group_state(states, is_stopped=True)
        # o>summary = summary.format(suite_state)
        summary = summary % suite_state
        num_failed = 0
        for task_id in task:
            if task[task_id].get("state") == "failed":
                num_failed += 1
        if num_failed:
            # o> summary += ": {0} failed tasks".format(num_failed)
            summary += ": %s failed tasks" % num_failed
        self.set_status(summary)
        dt = glob["last_updated"]
        self.set_time(get_time_string_from_unix_time(dt))

    def set_time(self, time):
        """Set last update text."""
        if time == self._time:
            return False
        self._time = time
        time_for_display = time.strip().rsplit(".", 1)[0]
        gobject.idle_add(self.time_widget.set_text, time_for_display + " ")

    def _set_tooltip(self, widget, text):
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip(widget, text)

    def _log_widget_launch_hook(self, widget, event):
        self._log_widget_image.set_sensitive(False)
        self.log_launch_hook()


class ControlApp(object):
    """
Main Control GUI that displays one or more views or interfaces to the suite.
    """

    DEFAULT_VIEW = "text"

    VIEWS_ORDERED = ["text", "dot"]

    VIEWS = {"text": ControlTree,
             "dot": ControlLED}

    VIEW_DESC = {"text": "Detailed list view",
                 "dot": "Dot summary view",
                 "graph": "Dependency graph view"}

    VIEW_ICON_PATHS = {"text": "/icons/tab-tree.png",
                       "dot": "/icons/tab-dot.png",
                       "graph": "/icons/tab-graph.png"}

    if not graphing_disabled:
        VIEWS["graph"] = ControlGraph
        VIEWS_ORDERED.append("graph")

    def __init__(self, suite, db, owner, host, port, pyro_timeout,
                 template_vars, template_vars_file, restricted_display):

        gobject.threads_init()

        set_exception_hook_dialog("gcylc")
        self.restricted_display = restricted_display
        if self.restricted_display:
            if "graph" in self.__class__.VIEWS:
                del self.__class__.VIEWS["graph"]
            if "graph" in self.__class__.VIEWS_ORDERED:
                self.__class__.VIEWS_ORDERED.remove('graph')

        self.cfg = InitData(suite, owner, host, port, db, pyro_timeout,
                            template_vars, template_vars_file,
                            gcfg.get(["ungrouped views"]),
                            gcfg.get(["sort by definition order"]))

        self.theme_name = gcfg.get(['use theme'])
        self.theme = gcfg.get(['themes', self.theme_name])
        self.dot_size = gcfg.get(['dot icon size'])

        self.current_views = []

        self.theme_legend_window = None
        self.filter_dialog_window = None

        setup_icons()

        self.view_layout_horizontal = False

        self.quitters = []
        self.gcapture_windows = []

        self.log_colors = rotator()
        hcolor = gcfg.get(['task filter highlight color'])
        try:
            self.filter_highlight_color = gtk.gdk.color_parse(hcolor)
        except Exception:
            print >> sys.stderr, ("WARNING: bad gcylc.rc 'task filter "
                                  "highlight color' (defaulting to yellow)")
            self.filter_highlight_color = gtk.gdk.color_parse("yellow")

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)

        self.window.set_icon(get_icon())
        self.window.set_default_size(800, 500)
        self.window.connect("delete_event", self.delete_event)

        self._prev_status = None
        self.create_main_menu()

        bigbox = gtk.VBox()
        bigbox.pack_start(self.menu_bar, False)

        self.initial_views = gcfg.get(['initial views'])
        if graphing_disabled or self.restricted_display:
            try:
                self.initial_views.remove("graph")
            except ValueError:
                pass
        if len(self.initial_views) == 0:
            self.initial_views = [self.VIEWS_ORDERED[0]]

        self.create_tool_bar()
        bigbox.pack_start(self.tool_bar_box, False, False)

        self.tool_bar_box.set_sensitive(False)

        self.updater = None

        self.views_parent = gtk.VBox()
        bigbox.pack_start(self.views_parent, True)

        if self.restricted_display:
            self.legal_task_states = task_state.legal_for_restricted_monitoring
        else:
            self.legal_task_states = task_state.legal

        self.filter_states_excl = ["runahead"]
        self.filter_name_string = None
        self.create_info_bar()

        hbox = gtk.HBox()
        hbox.pack_start(self.info_bar, True)
        bigbox.pack_start(hbox, False)

        self.window.add(bigbox)
        title = "gcylc"
        if self.restricted_display:
            title += " -r (restricted display)"
        self.window.set_title(title)

        self.window.show_all()

        self.setup_views()
        if suite:
            self.reset(suite)

    def reset(self, suite):
        title = suite
        self.cfg.suite = suite
        if self.cfg.host != socket.getfqdn():
            title += " - " + self.cfg.host
        title += " - gcylc"
        if self.restricted_display:
            title += " -r (restricted display)"
        self.window.set_title(title)
        self.cfg.reset(suite)

        self.tool_bar_box.set_sensitive(True)
        for menu in self.suite_menus:
            menu.set_sensitive(True)

        if self.updater is not None:
            self.updater.stop()
        self.updater = Updater(self.cfg, self.info_bar,
                               self.restricted_display)
        self.updater.start()

        self.restart_views()

    def setup_views(self):
        """Create our view containers."""
        num_views = 2
        self.view_containers = []
        self.current_view_toolitems = []
        for i in range(num_views):
            self.current_views.append(None)
            self.view_containers.append(gtk.HBox())
            self.current_view_toolitems.append([])
        self.views_parent.pack_start(self.view_containers[0],
                                     expand=True, fill=True)

    def create_views(self):
        for i, view in enumerate(self.initial_views):
            self.create_view(view, i)
            if i == 0:
                self._set_menu_view0(view)
                self._set_tool_bar_view0(view)
            elif i == 1:
                self._set_menu_view1(view)
                self._set_tool_bar_view1(view)

    def change_view_layout(self, horizontal=False):
        """Switch between horizontal or vertical positioning of views."""
        self.view_layout_horizontal = horizontal
        old_pane = self.view_containers[0].get_parent()
        if not isinstance(old_pane, gtk.Paned):
            return False
        old_pane.remove(self.view_containers[0])
        old_pane.remove(self.view_containers[1])
        top_parent = old_pane.get_parent()
        top_parent.remove(old_pane)
        if self.view_layout_horizontal:
            new_pane = gtk.HPaned()
            extent = top_parent.get_allocation().width
        else:
            new_pane = gtk.VPaned()
            extent = top_parent.get_allocation().height
        new_pane.pack1(self.view_containers[0], resize=True, shrink=True)
        new_pane.pack2(self.view_containers[1], resize=True, shrink=True)
        new_pane.set_position(extent / 2)
        top_parent.pack_start(new_pane, expand=True, fill=True)
        self.window.show_all()

    def set_theme(self, item):
        """Change self.theme and then replace each view with itself"""
        if not item.get_active():
            return False
        self.theme = gcfg.get(['themes', item.theme_name])
        self.restart_views()

    def set_dot_size(self, item, dsize):
        """Change self.dot_size and then replace each view with itself"""
        if not item.get_active():
            return False
        self.dot_size = dsize
        self.restart_views()

    def restart_views(self):
        """Replace each view with itself"""
        if not self.current_views[0]:
            # first time
            self.create_views()
            return False

        for view_num in range(len(self.current_views)):
            if self.current_views[view_num]:
                # (may be None if the second view pane is turned off)
                self.switch_view(self.current_views[view_num].name, view_num,
                                 force=True)
        self._set_info_bar()
        self.update_theme_legend()
        self.update_filter_dialog()
        return False

    def _set_info_bar(self):
        self.info_bar.set_theme(self.theme, self.dot_size)
        # (to update info bar immediately:)
        self.info_bar._set_state_widget()
        # (to update info bar immediately)
        self.info_bar._set_filter_state_widget()

    def _cb_change_view0_menu(self, item):
        # This is the view menu callback for the primary view.
        if not item.get_active():
            return False
        if self.current_views[0].name == item._viewname:
            return False
        self.switch_view(item._viewname)
        self._set_tool_bar_view0(item._viewname)
        return False

    def _set_tool_bar_view0(self, viewname):
        # Set the tool bar state for the primary view.
        model = self.tool_bar_view0.get_model()
        c_iter = model.get_iter_first()
        while c_iter is not None:
            if model.get_value(c_iter, 1) == viewname:
                index = model.get_path(c_iter)[0]
                self.tool_bar_view0.set_active(index)
                break
            c_iter = model.iter_next(c_iter)

    def _cb_change_view0_tool(self, widget):
        # This is the tool bar callback for the primary view.
        viewname = widget.get_model().get_value(widget.get_active_iter(), 1)
        if self.current_views[0].name == viewname:
            return False
        self.switch_view(viewname)
        self._set_menu_view0(viewname)
        return False

    def _set_menu_view0(self, viewname):
        # Set the view menu state for the primary view.
        for view_item in self.view_menu_views0:
            if (view_item._viewname == viewname and
                    not view_item.get_active()):
                return view_item.set_active(True)

    def _cb_change_view1_menu(self, item):
        # This is the view menu callback for the secondary view.
        if not item.get_active():
            return False
        if self.current_views[1] is None:
            if item._viewname not in self.VIEWS:
                return False
        elif self.current_views[1].name == item._viewname:
            return False
        self.switch_view(item._viewname, view_num=1)
        self._set_tool_bar_view1(item._viewname)
        return False

    def _set_tool_bar_view1(self, viewname):
        # Set the tool bar state for the secondary view.
        model = self.tool_bar_view1.get_model()
        c_iter = model.get_iter_first()
        while c_iter is not None:
            if model.get_value(c_iter, 1) == viewname:
                index = model.get_path(c_iter)[0]
                self.tool_bar_view1.set_active(index)
                break
            c_iter = model.iter_next(c_iter)
        else:
            self.tool_bar_view1.set_active(0)

    def _cb_change_view1_tool(self, widget):
        # This is the tool bar callback for the secondary view.
        viewname = widget.get_model().get_value(widget.get_active_iter(), 1)
        if self.current_views[1] is None:
            if viewname not in self.VIEWS:
                return False
        elif self.current_views[1].name == viewname:
            return False
        self.switch_view(viewname, view_num=1)
        self._set_menu_view1(viewname)
        return False

    def _set_menu_view1(self, viewname):
        # Set the view menu state for the secondary view.
        for view_item in self.view_menu_views1:
            if (view_item._viewname == viewname and
                    not view_item.get_active()):
                return view_item.set_active(True)
            if (view_item._viewname not in self.VIEWS and
                    viewname not in self.VIEWS and
                    not view_item.get_active()):
                return view_item.set_active(True)
        return False

    def _cb_change_view_align(self, widget):
        # This is the view menu callback to toggle side-by-side layout.
        horizontal = widget.get_active()
        if self.view_layout_horizontal == horizontal:
            return False
        self.change_view_layout(widget.get_active())
        if widget == self.layout_toolbutton:
            self.view1_align_item.set_active(horizontal)
        else:
            self.layout_toolbutton.set_active(horizontal)

    def switch_view(self, new_viewname, view_num=0, force=False):
        """Remove a view instance and replace with a different one."""
        if new_viewname not in self.VIEWS:
            self.remove_view(view_num)
            return False
        old_position = -1
        if self.current_views[view_num] is not None:
            if not force and self.current_views[view_num].name == new_viewname:
                return False
            if view_num == 1:
                old_position = (
                    self.views_parent.get_children()[0].get_position())
            self.remove_view(view_num)
        self.create_view(new_viewname, view_num, pane_position=old_position)
        return False

    def create_view(self, viewname, view_num=0, pane_position=-1):
        """Create a view instance.

        Toolbars and menus must be updated, as well as pane positioning.

        """
        container = self.view_containers[view_num]
        self.current_views[view_num] = self.VIEWS[viewname](
            self.cfg, self.updater, self.theme, self.dot_size, self.info_bar,
            self.get_right_click_menu, self.log_colors, self.insert_task_popup)
        view = self.current_views[view_num]
        view.name = viewname
        if view_num == 1:
            # Secondary view creation
            viewbox0 = self.view_containers[0]
            zero_parent = viewbox0.get_parent()
            zero_parent.remove(viewbox0)
            if self.view_layout_horizontal:
                pane = gtk.HPaned()
                extent = zero_parent.get_allocation().width
            else:
                pane = gtk.VPaned()
                extent = zero_parent.get_allocation().height
            pane.pack1(viewbox0, resize=True, shrink=True)
            pane.pack2(container, resize=True, shrink=True)
            # Handle pane positioning
            if pane_position == -1:
                pane_position = extent / 2
            pane.set_position(pane_position)
            zero_parent.pack_start(pane, expand=True, fill=True)
        view_widgets = view.get_control_widgets()
        if view_widgets.size_request() == (0, 0):
            view_widgets.set_size_request(1, 1)
        container.pack_start(view_widgets,
                             expand=True, fill=True)
        # Handle menu
        menu = self.views_option_menus[view_num]
        for item in menu.get_children():
            menu.remove(item)
        new_menuitems = view.get_menuitems()
        for item in new_menuitems:
            menu.append(item)
        self.views_option_menuitems[view_num].set_sensitive(True)
        # Handle toolbar
        for view_toolitems in self.current_view_toolitems[view_num]:
            for item in view_toolitems:
                self.tool_bars[view_num].remove(item)
        new_toolitems = view.get_toolitems()
        if new_toolitems:
            index = self.tool_bars[view_num].get_children().index(
                self.view_toolitems[view_num])
        for toolitem in reversed(new_toolitems):
            self.tool_bars[view_num].insert(toolitem, index + 1)
        self.current_view_toolitems[view_num] = new_toolitems
        self.window.show_all()

    def remove_view(self, view_num):
        """Remove a view instance."""
        self.current_views[view_num].stop()
        self.current_views[view_num] = None
        menu = self.views_option_menus[view_num]
        for item in menu.get_children():
            menu.remove(item)
        self.views_option_menuitems[view_num].set_sensitive(False)
        while len(self.current_view_toolitems[view_num]):
            self.tool_bars[view_num].remove(
                self.current_view_toolitems[view_num].pop())
        if view_num == 1:
            parent = self.view_containers[0].get_parent()
            parent.remove(self.view_containers[0])
            parent.remove(self.view_containers[1])
            top_parent = parent.get_parent()
            top_parent.remove(parent)
            top_parent.pack_start(self.view_containers[0],
                                  expand=True, fill=True)
        for child in self.view_containers[view_num].get_children():
            child.destroy()

    def quit_gcapture(self):
        for gwindow in self.gcapture_windows:
            if not gwindow.quit_already:
                gwindow.quit(None, None)

    def quit(self):
        self.quit_gcapture()
        for q in self.quitters:
            q.quit()
        for view in self.current_views:
            if view is not None:
                view.stop()
        if self.updater is not None:
            self.updater.stop()
        gtk.main_quit()

    def delete_event(self, widget, event, data=None):
        self.quit()

    def click_exit(self, foo):
        self.quit()

    def click_open(self, foo=None):
        app = dbchooser(self.window, self.cfg.db, self.cfg.owner,
                        self.cfg.cylc_tmpdir, self.cfg.pyro_timeout)
        chosen = None
        while True:
            response = app.window.run()
            if response == gtk.RESPONSE_OK:
                if app.regname:
                    chosen = app.regname
                    break
                else:
                    warning_dialog("Choose a suite or cancel!",
                                   self.window).warn()
            if response == gtk.RESPONSE_CANCEL:
                break
        app.updater.quit = True
        app.window.destroy()
        if chosen:
            self.reset(chosen)

    def pause_suite(self, bt):
        try:
            result = self.get_pyro('command-interface').put('hold suite now')
        except Exception, x:
            warning_dialog(x.__str__(), self.window).warn()
        else:
            if not result[0]:
                warning_dialog(result[1], self.window).warn()

    def resume_suite(self, bt):
        try:
            result = self.get_pyro('command-interface').put('release suite')
        except Exception, x:
            warning_dialog(x.__str__(), self.window).warn()
            return
        if not result[0]:
            warning_dialog(result[1], self.window).warn()

    def stopsuite_default(self, *args):
        """Try to stop the suite (after currently running tasks...)."""
        try:
            result = self.get_pyro('command-interface').put('stop cleanly')
        except Exception, x:
            warning_dialog(x.__str__(), self.window).warn()
        else:
            if not result[0]:
                warning_dialog(result[1], self.window).warn()

    def stopsuite(self, bt, window, kill_rb, stop_rb, stopat_rb, stopct_rb,
                  stoptt_rb, stopnow_rb, stoppoint_entry, stopclock_entry,
                  stoptask_entry):
        stop = False
        stopat = False
        stopnow = False
        stopclock = False
        stoptask = False
        stopkill = False

        if stop_rb.get_active():
            stop = True
        elif kill_rb.get_active():
            stopkill = True
        elif stopat_rb.get_active():
            stopat = True
            stop_point_string = stoppoint_entry.get_text()
            if stop_point_string == '':
                warning_dialog(
                    "ERROR: No stop CYCLE_POINT entered", self.window
                ).warn()
                return
        elif stopnow_rb.get_active():
            stopnow = True
        elif stopct_rb.get_active():
            stopclock = True
            stopclock_time = stopclock_entry.get_text()
            if stopclock_time == '':
                warning_dialog(
                    "ERROR: No stop time entered", self.window
                ).warn()
                return
            try:
                parser = TimePointParser()
                timepoint = parser.parse(stopclock_time)
            except ValueError:
                warning_dialog(
                    "ERROR: Bad ISO 8601 date-time: %s" % stopclock_time,
                    self.window
                ).warn()
                return
        elif stoptt_rb.get_active():
            stoptask = True
            stoptask_id = stoptask_entry.get_text()
            if stoptask_id == '':
                warning_dialog(
                    "ERROR: No stop task ID entered", self.window
                ).warn()
                return
            if not TaskID.is_valid_id(stoptask_id):
                warning_dialog(
                    "ERROR: Bad task ID (%s): %s" % (
                        TaskID.SYNTAX, stoptask_id,
                    ), self.window
                ).warn()
                return
        else:
            # SHOULD NOT BE REACHED
            warning_dialog("ERROR: Bug in GUI?", self.window).warn()
            return

        window.destroy()
        try:
            god = self.get_pyro('command-interface')
            if stop:
                result = god.put('stop cleanly', False)
            elif stopkill:
                result = god.put('stop cleanly', True)
            elif stopat:
                result = god.put('stop after point', stop_point_string)
            elif stopnow:
                result = god.put('stop now')
            elif stopclock:
                result = god.put('stop after clock time', stopclock_time)
            elif stoptask:
                result = god.put('stop after task', stoptask_id)
        except Exception, x:
            warning_dialog(x.__str__(), self.window).warn()
        else:
            if not result[0]:
                warning_dialog(result[1], self.window).warn()

    def load_point_strings(self, bt, startentry, stopentry):
        item1 = " -i '[scheduling]initial cycle point'"
        item2 = " -i '[scheduling]final cycle point'"
        command = (
            "cylc get-suite-config --mark-up --host=" + self.cfg.host +
            " " + self.cfg.template_vars_opts + " " + " --user=" +
            self.cfg.owner + " --one-line" + item1 + item2 + " " +
            self.cfg.suite)
        res = run_get_stdout(command, filter=True)  # (T/F, ['ct ct'])

        if res[0]:
            out1, out2 = res[1][0].split()
            if out1 == "None" and out2 == "None":
                # (default value from suite.rc spec)
                info_dialog("""Initial and final cycle points have not
been defined for this suite""").inform()
            elif out1 == "None":
                info_dialog("""An initial cycle point has not
been defined for this suite""").inform()
                stopentry.set_text(out2)
            elif out2 == "None":
                info_dialog("""A final cycle point has not
been defined for this suite""").inform()
                startentry.set_text(out1)
            else:
                startentry.set_text(out1)
                stopentry.set_text(out2)
        else:
            # error dialogs done by run_get_stdout()
            pass

    def startsuite(self, bt, window, coldstart_rb, warmstart_rb, restart_rb,
                   entry_point_string, stop_point_string_entry,
                   statedump_entry, optgroups, mode_live_rb, mode_sim_rb,
                   mode_dum_rb, hold_cb, holdpoint_entry):

        command = 'cylc run ' + self.cfg.template_vars_opts
        options = ''
        method = ''
        if coldstart_rb.get_active():
            method = 'coldstart'
        elif warmstart_rb.get_active():
            method = 'warmstart'
            options += ' -w'
        elif restart_rb.get_active():
            method = 'restart'
            command = 'cylc restart ' + self.cfg.template_vars_opts

        if mode_live_rb.get_active():
            pass
        elif mode_sim_rb.get_active():
            command += ' --mode=simulation'
        elif mode_dum_rb.get_active():
            command += ' --mode=dummy'

        point_string = ''
        if method != 'restart':
            # start time
            point_string = entry_point_string.get_text()

        ste = stop_point_string_entry.get_text()
        if ste:
            options += ' --until=' + ste

        hetxt = holdpoint_entry.get_text()
        if hold_cb.get_active():
            options += ' --hold'
        elif hetxt != '':
            options += ' --hold-after=' + hetxt

        for group in optgroups:
            options += group.get_options()
        window.destroy()

        options += ' --user=' + self.cfg.owner + ' --host=' + self.cfg.host

        command += ' ' + options + ' ' + self.cfg.suite + ' ' + point_string

        print command

        if method == 'restart':
            if statedump_entry.get_text():
                command += ' ' + statedump_entry.get_text()

        # #DEBUGGING:
        # info_dialog("I'm about to run this command: \n" + command,
        #             self.window).inform()
        # return

        try:
            subprocess.Popen([command], shell=True)
        except OSError, e:
            warning_dialog('Error: failed to start ' + self.cfg.suite,
                           self.window).warn()
            success = False

        self.reset_connection_polling(None)

    def about(self, bt):
        about = gtk.AboutDialog()
        if gtk.gtk_version[0] == 2:
            if gtk.gtk_version[1] >= 12:
                # set_program_name() was added in PyGTK 2.12
                about.set_program_name("cylc")
        about.set_version(CYLC_VERSION)
        about.set_copyright("Copyright (C) 2008-2015 NIWA")

        about.set_comments(
            """
The Cylc Suite Engine.
"""
        )
        about.set_logo(get_logo())
        about.set_transient_for(self.window)
        about.run()
        about.destroy()

    def view_task_descr(self, w, e, task_id):
        command = ("cylc show --host=" + self.cfg.host + " --user=" +
                   self.cfg.owner + " " + self.cfg.suite + " " + task_id)
        foo = gcapture_tmpfile(command, self.cfg.cylc_tmpdir, 600, 400)
        self.gcapture_windows.append(foo)
        foo.run()

    def view_task_info(self, w, e, task_id, choice):
        if hasattr(e, "button") and e.button != 1:
            return False
        try:
            [glbl, states, fam_states] = (
                self.get_pyro('state_summary').get_state_summary())
        except Exception, x:
            warning_dialog(str(x), self.window).warn()
            return
        view = True
        reasons = []
        try:
            logfiles = states[task_id]['logfiles']
        except KeyError:
            warning_dialog(task_id + ' is no longer live', self.window).warn()
            return False

        if len(logfiles) == 0:
            view = False
            reasons.append(task_id + ' has no associated log files')

        if states[task_id]['state'] == 'waiting' or \
                states[task_id]['state'] == 'ready' or \
                states[task_id]['state'] == 'submit-failed' or \
                states[task_id]['state'] == 'queued':
            view = False
            reasons.append(task_id + ' has not started running yet')

        if not view:
            warning_dialog('\n'.join(reasons), self.window).warn()
        else:
            self.popup_logview(task_id, logfiles, choice)

        return False

    def get_right_click_menu(self, task_id, hide_task=False,
                             task_is_family=False):
        """Return the default menu for a task."""
        menu = gtk.Menu()
        if not hide_task:
            menu_root = gtk.MenuItem(task_id)
            menu_root.set_submenu(menu)

            title_item = gtk.MenuItem('Task: ' + task_id.replace("_", "__"))
            title_item.set_sensitive(False)
            menu.append(title_item)

        menu_items = self._get_right_click_menu_items(task_id, task_is_family)
        for item in menu_items:
            menu.append(item)

        menu.show_all()
        return menu

    def _get_right_click_menu_items(self, task_id, task_is_family=False):
        # Return the default menu items for a task
        name, point_string = TaskID.split(task_id)

        items = []

        # This method of setting a custom menu item is not supported
        # pre-PyGTK 2.16 (~Python 2.65?) due to MenuItem.set_label():
        # cug_pdf_item = gtk.ImageMenuItem(stock_id=gtk.STOCK_EDIT)
        # cug_pdf_item.set_label('_PDF User Guide')
        # help_menu.append(cug_pdf_item)
        # cug_pdf_item.connect('activate', self.browse, '--pdf')

        items.append(gtk.SeparatorMenuItem())

        if not task_is_family:

            view_menu = gtk.Menu()
            view_item = gtk.ImageMenuItem("View")
            img = gtk.image_new_from_stock(gtk.STOCK_DIALOG_INFO,
                                           gtk.ICON_SIZE_MENU)
            view_item.set_image(img)
            view_item.set_submenu(view_menu)
            items.append(view_item)

            # NOTE: we have to respond to 'button-press-event' rather than
            # 'activate' in order for sub-menus to work in the graph-view.

            js_item = gtk.ImageMenuItem('job script')
            img = gtk.image_new_from_stock(gtk.STOCK_DND, gtk.ICON_SIZE_MENU)
            js_item.set_image(img)
            view_menu.append(js_item)
            js_item.connect('button-press-event', self.view_task_info, task_id,
                            'job')

            out_item = gtk.ImageMenuItem('job stdout')
            img = gtk.image_new_from_stock(gtk.STOCK_DND, gtk.ICON_SIZE_MENU)
            out_item.set_image(img)
            view_menu.append(out_item)
            out_item.connect('button-press-event', self.view_task_info, task_id,
                             'job.out')

            err_item = gtk.ImageMenuItem('job stderr')
            img = gtk.image_new_from_stock(gtk.STOCK_DND, gtk.ICON_SIZE_MENU)
            err_item.set_image(img)
            view_menu.append(err_item)
            err_item.connect('button-press-event', self.view_task_info, task_id,
                             'job.err')

            info_item = gtk.ImageMenuItem('prereq\'s & outputs')
            img = gtk.image_new_from_stock(
                gtk.STOCK_DIALOG_INFO, gtk.ICON_SIZE_MENU)
            info_item.set_image(img)
            view_menu.append(info_item)
            info_item.connect(
                'button-press-event', self.popup_requisites, task_id)

            js0_item = gtk.ImageMenuItem('run "cylc show"')
            img = gtk.image_new_from_stock(
                gtk.STOCK_DIALOG_INFO, gtk.ICON_SIZE_MENU)
            js0_item.set_image(img)
            view_menu.append(js0_item)
            js0_item.connect(
                'button-press-event', self.view_task_descr, task_id)

            items.append(gtk.SeparatorMenuItem())

        trigger_now_item = gtk.ImageMenuItem('Trigger (run now)')
        img = gtk.image_new_from_stock(
            gtk.STOCK_MEDIA_PLAY, gtk.ICON_SIZE_MENU)
        trigger_now_item.set_image(img)
        items.append(trigger_now_item)
        trigger_now_item.connect(
            'activate', self.trigger_task_now, task_id, task_is_family)

        if not task_is_family:
            trigger_edit_item = gtk.ImageMenuItem('Trigger (edit run)')
            img = gtk.image_new_from_stock(
                gtk.STOCK_MEDIA_PLAY, gtk.ICON_SIZE_MENU)
            trigger_edit_item.set_image(img)
            items.append(trigger_edit_item)
            trigger_edit_item.connect(
                'activate', self.trigger_task_edit_run, task_id)

        items.append(gtk.SeparatorMenuItem())

        # TODO - grey out poll and kill if the task is not active.
        poll_item = gtk.ImageMenuItem('Poll')
        img = gtk.image_new_from_stock(gtk.STOCK_REFRESH, gtk.ICON_SIZE_MENU)
        poll_item.set_image(img)
        items.append(poll_item)
        poll_item.connect('activate', self.poll_task, task_id, task_is_family)

        kill_item = gtk.ImageMenuItem('Kill')
        img = gtk.image_new_from_stock(gtk.STOCK_CANCEL, gtk.ICON_SIZE_MENU)
        kill_item.set_image(img)
        items.append(kill_item)
        kill_item.connect('activate', self.kill_task, task_id, task_is_family)

        items.append(gtk.SeparatorMenuItem())

        reset_menu = gtk.Menu()
        reset_item = gtk.ImageMenuItem("Reset State")
        reset_img = gtk.image_new_from_stock(
            gtk.STOCK_CONVERT, gtk.ICON_SIZE_MENU)
        reset_item.set_image(reset_img)
        reset_item.set_submenu(reset_menu)
        items.append(reset_item)

        reset_ready_item = gtk.ImageMenuItem('"ready"')
        reset_img = gtk.image_new_from_stock(
            gtk.STOCK_CONVERT, gtk.ICON_SIZE_MENU)
        reset_ready_item.set_image(reset_img)
        reset_menu.append(reset_ready_item)
        reset_ready_item.connect('button-press-event', self.reset_task_state,
                                 task_id, 'ready', task_is_family)

        reset_waiting_item = gtk.ImageMenuItem('"waiting"')
        reset_img = gtk.image_new_from_stock(
            gtk.STOCK_CONVERT, gtk.ICON_SIZE_MENU)
        reset_waiting_item.set_image(reset_img)
        reset_menu.append(reset_waiting_item)
        reset_waiting_item.connect('button-press-event', self.reset_task_state,
                                   task_id, 'waiting', task_is_family)

        reset_succeeded_item = gtk.ImageMenuItem('"succeeded"')
        reset_img = gtk.image_new_from_stock(gtk.STOCK_CONVERT,
                                             gtk.ICON_SIZE_MENU)
        reset_succeeded_item.set_image(reset_img)
        reset_menu.append(reset_succeeded_item)
        reset_succeeded_item.connect('button-press-event',
                                     self.reset_task_state, task_id,
                                     'succeeded', task_is_family)

        reset_failed_item = gtk.ImageMenuItem('"failed"')
        reset_img = gtk.image_new_from_stock(gtk.STOCK_CONVERT,
                                             gtk.ICON_SIZE_MENU)
        reset_failed_item.set_image(reset_img)
        reset_menu.append(reset_failed_item)
        reset_failed_item.connect('button-press-event', self.reset_task_state,
                                  task_id, 'failed', task_is_family)

        spawn_item = gtk.ImageMenuItem('Force spawn')
        img = gtk.image_new_from_stock(gtk.STOCK_ADD, gtk.ICON_SIZE_MENU)
        spawn_item.set_image(img)
        items.append(spawn_item)
        spawn_item.connect('button-press-event', self.reset_task_state,
                           task_id, 'spawn', task_is_family)

        items.append(gtk.SeparatorMenuItem())

        stoptask_item = gtk.ImageMenuItem('Hold')
        img = gtk.image_new_from_stock(gtk.STOCK_MEDIA_PAUSE,
                                       gtk.ICON_SIZE_MENU)
        stoptask_item.set_image(img)
        items.append(stoptask_item)
        stoptask_item.connect('activate', self.hold_task, task_id, True,
                              task_is_family)

        unstoptask_item = gtk.ImageMenuItem('Release')
        img = gtk.image_new_from_stock(gtk.STOCK_MEDIA_PLAY,
                                       gtk.ICON_SIZE_MENU)
        unstoptask_item.set_image(img)
        items.append(unstoptask_item)
        unstoptask_item.connect('activate', self.hold_task, task_id, False,
                                task_is_family)

        items.append(gtk.SeparatorMenuItem())

        remove_item = gtk.ImageMenuItem('Remove after spawning')
        img = gtk.image_new_from_stock(gtk.STOCK_CLEAR, gtk.ICON_SIZE_MENU)

        remove_item.set_image(img)
        items.append(remove_item)
        remove_item.connect('activate', self.remove_task, task_id,
                            task_is_family)

        remove_nospawn_item = gtk.ImageMenuItem('Remove without spawning')
        img = gtk.image_new_from_stock(gtk.STOCK_CLEAR, gtk.ICON_SIZE_MENU)

        remove_nospawn_item.set_image(img)
        items.append(remove_nospawn_item)
        remove_nospawn_item.connect('activate', self.remove_task_nospawn,
                                    task_id, task_is_family)

        if not task_is_family:
            purge_item = gtk.ImageMenuItem('Remove Tree (Recursive Purge)')
            img = gtk.image_new_from_stock(gtk.STOCK_DELETE,
                                           gtk.ICON_SIZE_MENU)
            purge_item.set_image(img)
            items.append(purge_item)
            purge_item.connect('activate', self.popup_purge, task_id)

            items.append(gtk.SeparatorMenuItem())

            addprereq_item = gtk.ImageMenuItem('Add A Prerequisite')
            img = gtk.image_new_from_stock(gtk.STOCK_ADD, gtk.ICON_SIZE_MENU)
            addprereq_item.set_image(img)
            items.append(addprereq_item)
            addprereq_item.connect('activate', self.add_prerequisite_popup,
                                   task_id)

        return items

    def change_runahead_popup(self, b):
        window = gtk.Window()
        window.modify_bg(gtk.STATE_NORMAL,
                         gtk.gdk.color_parse(self.log_colors.get_color()))
        window.set_border_width(5)
        window.set_title("Change Suite Runahead Limit")
        window.set_transient_for(self.window)
        window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        vbox = gtk.VBox()

        label = gtk.Label('SUITE: ' + self.cfg.suite)
        vbox.pack_start(label, True)

        entry = gtk.Entry()

        hbox = gtk.HBox()
        label = gtk.Label('HOURS')
        hbox.pack_start(label, True)
        hbox.pack_start(entry, True)
        vbox.pack_start(hbox)

        cancel_button = gtk.Button("_Cancel")
        cancel_button.connect("clicked", lambda x: window.destroy())

        start_button = gtk.Button("_Change")
        start_button.connect("clicked", self.change_runahead, entry, window)

        help_button = gtk.Button("_Help")
        help_button.connect(
            "clicked", self.command_help, "control", "set-runahead")

        hbox = gtk.HBox()
        hbox.pack_start(cancel_button, True)
        hbox.pack_start(start_button, True)
        hbox.pack_start(help_button, True)
        vbox.pack_start(hbox)

        window.add(vbox)
        window.show_all()

    def change_runahead(self, w, entry, window):
        ent = entry.get_text()
        if ent == '':
            limit = None
        else:
            try:
                int(ent)
            except ValueError:
                warning_dialog(
                    'Hours value must be integer!', self.window).warn()
                return
            else:
                limit = ent
        window.destroy()
        try:
            result = self.get_pyro(
                'command-interface').put('set runahead', limit)
        except Exception, x:
            warning_dialog(x.__str__(), self.window).warn()
            return
        if not result[0]:
            warning_dialog(result[1], self.window).warn()

    def add_prerequisite_popup(self, b, task_id):
        window = gtk.Window()
        window.modify_bg(gtk.STATE_NORMAL,
                         gtk.gdk.color_parse(self.log_colors.get_color()))
        window.set_border_width(5)
        window.set_title("Add A Prequisite")
        window.set_transient_for(self.window)
        window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        vbox = gtk.VBox()

        label = gtk.Label('SUITE: ' + self.cfg.suite)
        vbox.pack_start(label, True)

        label = gtk.Label('TASK: ' + task_id)
        vbox.pack_start(label, True)

        label = gtk.Label(
            'DEP (' + TaskID.SYNTAX + ' or message)')

        entry = gtk.Entry()

        hbox = gtk.HBox()
        hbox.pack_start(label, True)
        hbox.pack_start(entry, True)
        vbox.pack_start(hbox)

        cancel_button = gtk.Button("_Cancel")
        cancel_button.connect("clicked", lambda x: window.destroy())

        start_button = gtk.Button("_Add")
        start_button.connect(
            "clicked", self.add_prerequisite, entry, window, task_id)

        help_button = gtk.Button("_Help")
        help_button.connect("clicked", self.command_help, "control", "depend")

        hbox = gtk.HBox()
        hbox.pack_start(start_button, True)
        hbox.pack_start(help_button, True)
        hbox.pack_start(cancel_button, True)
        vbox.pack_start(hbox)

        window.add(vbox)
        window.show_all()

    def add_prerequisite(self, w, entry, window, task_id):
        dep = entry.get_text()
        if TaskID.is_valid_id(dep):
            msg = dep + ' succeeded'
        else:
            msg = dep

        try:
            name, cycle = TaskID.split(task_id)
        except ValueError:
            warning_dialog(
                "ERROR, Task or Group ID must be " + TaskID.SYNTAX,
                self.window
            ).warn()
            return

        window.destroy()
        try:
            result = self.get_pyro(
                'command-interface').put('add prerequisite', task_id, msg)
        except Exception, x:
            warning_dialog(x.__str__(), self.window).warn()
            return
        if not result[0]:
            warning_dialog(result[1], self.window).warn()

    def update_tb(self, tb, line, tags=None):
        if tags:
            tb.insert_with_tags(tb.get_end_iter(), line, *tags)
        else:
            tb.insert(tb.get_end_iter(), line)

    def popup_requisites(self, w, e, task_id):
        try:
            name, point_string = TaskID.split(task_id)
            result = self.get_pyro('suite-info').get(
                'task requisites', name, point_string)
        except Exception, x:
            warning_dialog(str(x), self.window).warn()
            return

        if result:
            # (else no tasks were found at all -suite shutting down)
            if task_id not in result:
                warning_dialog(
                    "Task proxy " + task_id +
                    " not found in " + self.cfg.suite +
                    ".\nTasks are removed once they are no longer needed.",
                    self.window).warn()
                return

        window = gtk.Window()
        window.set_title(task_id + " State")
        window.set_size_request(600, 400)
        window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        vbox = gtk.VBox()
        quit_button = gtk.Button("_Close")
        quit_button.connect("clicked", lambda x: window.destroy())
        vbox.pack_start(sw)
        vbox.pack_start(quit_button, False)

        textview = gtk.TextView()
        textview.set_border_width(5)
        textview.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("#fff"))
        textview.set_editable(False)
        sw.add(textview)
        window.add(vbox)
        tb = textview.get_buffer()

        blue = tb.create_tag(None, foreground="blue")
        red = tb.create_tag(None, foreground="red")
        bold = tb.create_tag(None, weight=pango.WEIGHT_BOLD)

        self.update_tb(tb, 'TASK ', [bold])
        self.update_tb(tb, task_id, [bold, blue])
        self.update_tb(tb, ' in SUITE ', [bold])
        self.update_tb(tb, self.cfg.suite + '\n\n', [bold, blue])

        [pre, out, extra_info] = result[task_id]

        self.update_tb(tb, 'Prerequisites', [bold])
        self.update_tb(tb, ' (')
        self.update_tb(tb, 'red', [red])
        self.update_tb(tb, '=> NOT satisfied)\n')

        if len(pre) == 0:
            self.update_tb(tb, ' - (None)\n')
        for item in pre:
            [msg, state] = item
            if state:
                tags = None
            else:
                tags = [red]
            self.update_tb(tb, ' - ' + msg + '\n', tags)

        self.update_tb(tb, '\nOutputs', [bold])
        self.update_tb(tb, ' (')
        self.update_tb(tb, 'red', [red])
        self.update_tb(tb, '=> NOT completed)\n')

        if len(out) == 0:
            self.update_tb(tb, ' - (None)\n')
        for item in out:
            [msg, state] = item
            if state:
                tags = []
            else:
                tags = [red]
            self.update_tb(tb, ' - ' + msg + '\n', tags)

        if len(extra_info.keys()) > 0:
            self.update_tb(tb, '\nOther\n', [bold])
            for item in extra_info:
                self.update_tb(
                    tb, ' - ' + item + ': ' + str(extra_info[item]) + '\n')

        self.update_tb(tb, '\nNOTE: ', [bold])
        self.update_tb(
            tb, ''' for tasks that have triggered already, prerequisites are
shown here in the state they were in at the time of triggering.''')
        window.show_all()

    def on_popup_quit(self, b, lv, w):
        lv.quit()
        self.quitters.remove(lv)
        w.destroy()

    def get_confirmation(self, cmd, name, msg=None):

        if self.cfg.no_prompt:
            return True

        if not msg:
            msg = cmd + " " + name + "?"

        prompt = gtk.MessageDialog(self.window, gtk.DIALOG_MODAL,
                                   gtk.MESSAGE_QUESTION,
                                   gtk.BUTTONS_OK_CANCEL, msg)

        prompt.add_button(gtk.STOCK_HELP, gtk.RESPONSE_HELP)
        response = prompt.run()

        while response == gtk.RESPONSE_HELP:
            self.command_help(cmd)
            response = prompt.run()

        prompt.destroy()
        if response != gtk.RESPONSE_OK:
            return False

    def hold_task(self, b, task_id, stop=True, is_family=False):
        if stop:
            cmd = "hold"
        else:
            cmd = "release"
        if not self.get_confirmation(cmd, task_id):
            return

        name, point_string = TaskID.split(task_id)
        try:
            if stop:
                result = self.get_pyro('command-interface').put(
                    'hold task now', name, point_string, is_family)
            else:
                result = self.get_pyro('command-interface').put(
                    'release task', name, point_string, is_family)
        except Exception, x:
            # the suite was probably shut down by another process
            warning_dialog(x.__str__(), self.window).warn()
            return

        if not result[0]:
            warning_dialog(result[1], self.window).warn()

    def trigger_task_now(self, b, task_id, is_family=False):
        """Trigger task via the suite daemon's command interface."""
        cmd = "trigger"
        if not self.get_confirmation(cmd, task_id):
            return

        name, point_string = TaskID.split(task_id)
        try:
            result = self.get_pyro('command-interface').put(
                'trigger task', name, point_string, is_family)
        except Exception, x:
            # the suite was probably shut down by another process
            warning_dialog(x.__str__(), self.window).warn()
            return
        if not result[0]:
            warning_dialog(result[1], self.window).warn()

    def trigger_task_edit_run(self, b, task_id):
        """
        Do an edit-run by invoking 'cylc trigger --edit' on the suite host.
        """
        name, point_string = TaskID.split(task_id)
        command = (
            "cylc trigger --notify-completion --use-ssh --edit --geditor -f" +
            self.get_remote_run_opts() + " " + self.cfg.suite +
            " %s %s" % (name, point_string))
        foo = gcapture_tmpfile(command, self.cfg.cylc_tmpdir, 400, 400)
        self.gcapture_windows.append(foo)
        foo.run()

    def poll_task(self, b, task_id, is_family=False):
        cmd = "poll"
        if not self.get_confirmation(cmd, task_id):
            return

        name, point_string = TaskID.split(task_id)
        try:
            result = self.get_pyro('command-interface').put(
                'poll tasks', name, point_string, is_family)
        except Exception, x:
            # the suite was probably shut down by another process
            warning_dialog(x.__str__(), self.window).warn()
            return
        if not result[0]:
            warning_dialog(result[1], self.window).warn()

    def kill_task(self, b, task_id, is_family=False):
        cmd = "kill"
        if not self.get_confirmation(cmd, task_id):
            return

        name, point_string = TaskID.split(task_id)
        try:
            result = self.get_pyro('command-interface').put(
                'kill tasks', name, point_string, is_family)
        except Exception, x:
            # the suite was probably shut down by another process
            warning_dialog(x.__str__(), self.window).warn()
            return
        if not result[0]:
            warning_dialog(result[1], self.window).warn()

    def reset_task_state(self, b, e, task_id, state, is_family=False):
        if hasattr(e, "button") and e.button != 1:
            return False
        cmd = "reset"

        name, point_string = TaskID.split(task_id)
        msg = "reset " + task_id + " to " + state + "?"
        if not self.get_confirmation(cmd, task_id, msg):
            return

        try:
            result = self.get_pyro('command-interface').put(
                'reset task state', name, point_string, state, is_family)
        except Exception, x:
            # the suite was probably shut down by another process
            warning_dialog(x.__str__(), self.window).warn()
            return
        if not result[0]:
            warning_dialog(result[1], self.window).warn()

    def remove_task(self, b, task_id, is_family):
        cmd = "remove"
        msg = "remove " + task_id + " (after spawning)?"
        if not self.get_confirmation(cmd, task_id, msg):
            return

        name, point_string = TaskID.split(task_id)
        try:
            result = self.get_pyro('command-interface').put(
                'remove task', name, point_string, is_family, True)
        except Exception, x:
            warning_dialog(str(x), self.window).warn()
            return
        if not result[0]:
            warning_dialog(result[1], self.window).warn()

    def remove_task_nospawn(self, b, task_id, is_family=False):
        cmd = "remove"
        msg = "remove " + task_id + " (without spawning)?"
        if not self.get_confirmation(cmd, task_id, msg):
            return

        name, point_string = TaskID.split(task_id)
        try:
            result = self.get_pyro('command-interface').put(
                'remove task', name, point_string, is_family, False)
        except Exception, x:
            warning_dialog(str(x), self.window).warn()
            return
        if not result[0]:
            warning_dialog(result[1], self.window).warn()

    def purge_cycle_entry(self, e, w, task_id):
        stop = e.get_text()
        w.destroy()
        try:
            result = self.get_pyro('command-interface').put(
                'purge tree', task_id, stop)
        except Exception, x:
            warning_dialog(str(x), self.window).warn()
            return
        if not result[0]:
            warning_dialog(result[1], self.window).warn()

    def purge_cycle_button(self, b, e, w, task_id):
        stop = e.get_text()
        w.destroy()
        try:
            result = self.get_pyro('command-interface').put(
                'purge tree', task_id, stop)
        except Exception, x:
            warning_dialog(str(x), self.window).warn()
            return
        if not result[0]:
            warning_dialog(result[1], self.window).warn()

    def stopsuite_popup(self, b):
        window = gtk.Window()
        window.modify_bg(gtk.STATE_NORMAL,
                         gtk.gdk.color_parse(self.log_colors.get_color()))
        window.set_border_width(5)
        window.set_title("Stop Suite Daemon %s" % self.cfg.suite)
        window.set_transient_for(self.window)
        window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)

        rb_vbox = gtk.VBox(spacing=15)

        vbox = gtk.VBox()
        stop_rb = gtk.RadioButton(
            None, "Stop after _active tasks have finished")
        label = gtk.Label("   cylc stop %s" % self.cfg.suite)
        label.modify_font(pango.FontDescription("monospace"))
        label.set_alignment(0, 0)
        vbox.pack_start(stop_rb)
        vbox.pack_start(label)
        rb_vbox.pack_start(vbox, True)

        vbox = gtk.VBox()
        kill_rb = gtk.RadioButton(stop_rb, "Stop after _killing active tasks")
        label = gtk.Label("   cylc stop --kill %s" % self.cfg.suite)
        label.modify_font(pango.FontDescription("monospace"))
        label.set_alignment(0, 0)
        vbox.pack_start(kill_rb, True)
        vbox.pack_start(label, True)
        rb_vbox.pack_start(vbox, True)

        vbox = gtk.VBox()
        stopnow_rb = gtk.RadioButton(
            stop_rb,
            "Stop _now (restart will follow up on orphaned tasks)")
        label = gtk.Label("   cylc stop --now %s" % self.cfg.suite)
        label.modify_font(pango.FontDescription("monospace"))
        label.set_alignment(0, 0)
        vbox.pack_start(stopnow_rb, True)
        vbox.pack_start(label, True)
        rb_vbox.pack_start(vbox, True)

        vbox = gtk.VBox()
        stopat_rb = gtk.RadioButton(stop_rb, "Stop after _cycle point")
        label = gtk.Label("   cylc stop %s CYCLE_POINT" % self.cfg.suite)
        label.modify_font(pango.FontDescription("monospace"))
        label.set_alignment(0, 0)
        vbox.pack_start(stopat_rb, True)
        vbox.pack_start(label, True)
        rb_vbox.pack_start(vbox, True)

        st_box = gtk.HBox()
        label = gtk.Label("      CYCLE_POINT ")
        st_box.pack_start(label, False, False)
        stop_point_string_entry = gtk.Entry()
        stop_point_string_entry.set_max_length(14)
        stop_point_string_entry.set_sensitive(False)
        label.set_sensitive(False)
        st_box.pack_start(stop_point_string_entry, True, True)
        rb_vbox.pack_start(st_box)

        vbox = gtk.VBox()
        stopct_rb = gtk.RadioButton(
            stop_rb, "Stop after _wall-clock date-time (e.g. CCYYMMDDThhmmZ)")
        label = gtk.Label("   cylc stop %s DATE_TIME" % self.cfg.suite)
        label.modify_font(pango.FontDescription("monospace"))
        label.set_alignment(0, 0)
        vbox.pack_start(stopct_rb, True)
        vbox.pack_start(label, True)
        rb_vbox.pack_start(vbox, True)

        sc_box = gtk.HBox()
        label = gtk.Label("      DATE_TIME ")
        sc_box.pack_start(label, False, False)
        stopclock_entry = gtk.Entry()
        stopclock_entry.set_max_length(16)
        stopclock_entry.set_sensitive(False)
        label.set_sensitive(False)
        sc_box.pack_start(stopclock_entry, True, True)
        rb_vbox.pack_start(sc_box)

        vbox = gtk.VBox()
        # Escape keyboard mnemonics.
        syntax = (TaskID.SYNTAX).replace('_', '__')
        stoptt_rb = gtk.RadioButton(
            stop_rb, "Stop after _task finishes (%s)" % syntax)
        label = gtk.Label("   cylc stop %s TASK_ID" % self.cfg.suite)
        label.modify_font(pango.FontDescription("monospace"))
        label.set_alignment(0, 0)
        vbox.pack_start(stoptt_rb, True)
        vbox.pack_start(label, True)
        rb_vbox.pack_start(vbox, True)

        stop_rb.set_active(True)

        tt_box = gtk.HBox()
        label = gtk.Label("      TASK_ID ")
        tt_box.pack_start(label, False, False)
        stoptask_entry = gtk.Entry()
        stoptask_entry.set_sensitive(False)
        label.set_sensitive(False)
        tt_box.pack_start(stoptask_entry, True, True)
        rb_vbox.pack_start(tt_box)

        stop_rb.connect(
            "toggled", self.stop_method, "stop", st_box, sc_box, tt_box)
        stopat_rb.connect(
            "toggled", self.stop_method, "stopat", st_box, sc_box, tt_box)
        stopnow_rb.connect(
            "toggled", self.stop_method, "stopnow", st_box, sc_box, tt_box)
        stopct_rb.connect(
            "toggled", self.stop_method, "stopclock", st_box, sc_box, tt_box)
        stoptt_rb.connect(
            "toggled", self.stop_method, "stoptask", st_box, sc_box, tt_box)
        cancel_button = gtk.Button("_Cancel")
        cancel_button.connect("clicked", lambda x: window.destroy())

        stop_button = gtk.Button(" _OK ")
        stop_button.connect("clicked", self.stopsuite, window, kill_rb,
                            stop_rb, stopat_rb, stopct_rb, stoptt_rb,
                            stopnow_rb, stop_point_string_entry,
                            stopclock_entry, stoptask_entry)
        help_button = gtk.Button("_Help")
        help_button.connect("clicked", self.command_help, "control", "stop")

        vbox = gtk.VBox()

        hbox = gtk.HBox()
        hbox.pack_start(rb_vbox, padding=10)
        vbox.pack_start(hbox, padding=10)

        hbox = gtk.HBox()
        hbox.pack_start(stop_button, False)
        hbox.pack_end(cancel_button, False)
        hbox.pack_end(help_button, False)
        vbox.pack_start(hbox, True, True)

        window.add(vbox)
        window.show_all()

    def stop_method(self, b, meth, st_box, sc_box, tt_box):
        for ch in (
                st_box.get_children() +
                sc_box.get_children() +
                tt_box.get_children()):
            ch.set_sensitive(False)
        if meth == 'stopat':
            for ch in st_box.get_children():
                ch.set_sensitive(True)
        elif meth == 'stopclock':
            for ch in sc_box.get_children():
                ch.set_sensitive(True)
        elif meth == 'stoptask':
            for ch in tt_box.get_children():
                ch.set_sensitive(True)

    def hold_cb_toggled(self, b, box):
        if b.get_active():
            box.set_sensitive(False)
        else:
            box.set_sensitive(True)

    def startup_method(self, b, meth, ic_box, is_box):
        if meth in ['cold', 'warm']:
            for ch in ic_box.get_children():
                ch.set_sensitive(True)
            for ch in is_box.get_children():
                ch.set_sensitive(False)
        else:
            # restart
            for ch in ic_box.get_children():
                ch.set_sensitive(False)
            for ch in is_box.get_children():
                ch.set_sensitive(True)

    def startsuite_popup(self, b):
        window = gtk.Window()
        window.modify_bg(gtk.STATE_NORMAL,
                         gtk.gdk.color_parse(self.log_colors.get_color()))
        window.set_border_width(5)
        window.set_title("Start Suite '" + self.cfg.suite + "'")
        window.set_transient_for(self.window)
        window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)

        vbox = gtk.VBox()

        box = gtk.HBox()
        coldstart_rb = gtk.RadioButton(None, "Cold-start")
        box.pack_start(coldstart_rb, True)
        restart_rb = gtk.RadioButton(coldstart_rb, "Restart")
        box.pack_start(restart_rb, True)
        warmstart_rb = gtk.RadioButton(coldstart_rb, "Warm-start")
        box.pack_start(warmstart_rb, True)
        coldstart_rb.set_active(True)
        vbox.pack_start(box)

        box = gtk.HBox()
        box.pack_start(gtk.Label('Mode'), True)
        mode_live_rb = gtk.RadioButton(None, "live")
        box.pack_start(mode_live_rb, True)
        mode_sim_rb = gtk.RadioButton(mode_live_rb, "simulation")
        box.pack_start(mode_sim_rb, True)
        mode_dum_rb = gtk.RadioButton(mode_live_rb, "dummy")
        box.pack_start(mode_dum_rb, True)

        mode_live_rb.set_active(True)
        vbox.pack_start(box)

        nvbox = gtk.VBox()
        nhbox = gtk.HBox()

        ic_box = gtk.HBox()
        label = gtk.Label('START')
        ic_box.pack_start(label, True)
        point_string_entry = gtk.Entry()
        point_string_entry.set_max_length(20)
        ic_box.pack_start(point_string_entry, True)

        nvbox.pack_start(ic_box)

        fc_box = gtk.HBox()
        label = gtk.Label('[STOP]')
        fc_box.pack_start(label, True)
        stop_point_string_entry = gtk.Entry()
        stop_point_string_entry.set_max_length(20)
        fc_box.pack_start(stop_point_string_entry, True)

        nvbox.pack_start(fc_box)

        nhbox.pack_start(nvbox)

        load_button = gtk.Button("_Load")
        load_button.connect(
            "clicked", self.load_point_strings,
            point_string_entry, stop_point_string_entry
        )

        nhbox.pack_start(load_button)

        vbox.pack_start(nhbox)

        is_box = gtk.HBox()
        label = gtk.Label('[State Dump FILE]')
        is_box.pack_start(label, True)
        statedump_entry = gtk.Entry()
        statedump_entry.set_text('state')
        statedump_entry.set_sensitive(False)
        label.set_sensitive(False)
        is_box.pack_start(statedump_entry, True)
        vbox.pack_start(is_box)

        coldstart_rb.connect(
            "toggled", self.startup_method, "cold", ic_box, is_box)
        warmstart_rb.connect(
            "toggled", self.startup_method, "warm", ic_box, is_box)
        restart_rb.connect(
            "toggled", self.startup_method, "re",   ic_box, is_box)

        hbox = gtk.HBox()

        hold_cb = gtk.CheckButton("Hold on start-up")

        hold_box = gtk.HBox()
        holdpoint_entry = EntryTempText()
        holdpoint_entry.set_temp_text("Hold after cycle")
        holdpoint_entry.set_width_chars(17)
        hold_box.pack_start(holdpoint_entry, True)

        hbox.pack_start(hold_cb)
        hbox.pack_start(hold_box)

        vbox.pack_start(hbox)

        hold_cb.connect("toggled", self.hold_cb_toggled, hold_box)

        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label('Options'), True)
        debug_group = controlled_option_group("Debug", "--debug")
        debug_group.pack(hbox)

        nodetach_group = controlled_option_group("No-detach", "--no-detach")
        nodetach_group.pack(hbox)
        vbox.pack_start(hbox)

        optgroups = [nodetach_group, debug_group]

        cancel_button = gtk.Button("_Cancel")
        cancel_button.connect("clicked", lambda x: window.destroy())

        start_button = gtk.Button("_Start")
        start_button.connect("clicked", self.startsuite, window, coldstart_rb,
                             warmstart_rb, restart_rb, point_string_entry,
                             stop_point_string_entry, statedump_entry,
                             optgroups, mode_live_rb, mode_sim_rb,
                             mode_dum_rb, hold_cb, holdpoint_entry)

        help_run_button = gtk.Button("_Help Run")
        help_run_button.connect("clicked", self.command_help, "control", "run")

        help_restart_button = gtk.Button("_Help Restart")
        help_restart_button.connect(
            "clicked", self.command_help, "control", "restart")

        hbox = gtk.HBox()
        hbox.pack_start(start_button, False)
        hbox.pack_end(cancel_button, False)
        hbox.pack_end(help_run_button, False)
        hbox.pack_end(help_restart_button, False)
        vbox.pack_start(hbox)

        window.add(vbox)
        window.show_all()

    def popup_purge(self, b, task_id):
        window = gtk.Window()
        window.modify_bg(gtk.STATE_NORMAL,
                         gtk.gdk.color_parse(self.log_colors.get_color()))
        window.set_border_width(5)
        window.set_title("Purge " + task_id)
        window.set_transient_for(self.window)
        window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        vbox = gtk.VBox()
        label = gtk.Label('stop cycle (inclusive)')

        entry = gtk.Entry()
        entry.set_max_length(14)
        entry.connect("activate", self.purge_cycle_entry, window, task_id)

        hbox = gtk.HBox()
        hbox.pack_start(label, True)
        hbox.pack_start(entry, True)
        vbox.pack_start(hbox)

        start_button = gtk.Button("_Purge")
        start_button.connect(
            "clicked", self.purge_cycle_button, entry, window, task_id)

        help_button = gtk.Button("_Help")
        help_button.connect("clicked", self.command_help, "control", "purge")

        cancel_button = gtk.Button("_Cancel")
        cancel_button.connect("clicked", lambda x: window.destroy())

        hbox = gtk.HBox()
        hbox.pack_start(start_button, True)
        hbox.pack_start(help_button, True)
        hbox.pack_start(cancel_button, True)
        vbox.pack_start(hbox)

        window.add(vbox)
        window.show_all()

    def point_string_entry_popup(self, b, callback, title):
        window = gtk.Window()
        window.modify_bg(gtk.STATE_NORMAL,
                         gtk.gdk.color_parse(self.log_colors.get_color()))
        window.set_border_width(5)
        window.set_title(title)
        window.set_transient_for(self.window)
        window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        vbox = gtk.VBox()

        hbox = gtk.HBox()
        label = gtk.Label('Cycle Point')
        hbox.pack_start(label, True)
        entry_point_string = gtk.Entry()
        entry_point_string.set_max_length(14)
        hbox.pack_start(entry_point_string, True)
        vbox.pack_start(hbox)

        go_button = gtk.Button("Go")
        go_button.connect("clicked", callback, window, entry_point_string)
        vbox.pack_start(go_button)

        window.add(vbox)
        window.show_all()

    def insert_task_popup(self, *b, **kwargs):
        window = gtk.Window()
        window.modify_bg(gtk.STATE_NORMAL,
                         gtk.gdk.color_parse(self.log_colors.get_color()))
        window.set_border_width(5)
        window.set_title("Insert Task")
        window.set_transient_for(self.window)
        window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        vbox = gtk.VBox()

        label = gtk.Label('SUITE: ' + self.cfg.suite)
        vbox.pack_start(label, True)

        fam_cb = gtk.CheckButton("Insert a family?")
        vbox.pack_start(fam_cb, True)

        if "is_fam" in kwargs:
            fam_cb.set_active(kwargs['is_fam'])

        hbox = gtk.HBox()
        label = gtk.Label('MATCH')
        hbox.pack_start(label, True)
        entry_match = gtk.Entry()
        hbox.pack_start(entry_match, True)
        vbox.pack_start(hbox)

        if "name" in kwargs:
            entry_match.set_text(kwargs['name'])

        hbox = gtk.HBox()
        label = gtk.Label('CYCLE_POINT')
        hbox.pack_start(label, True)
        entry_point_string = gtk.Entry()
        hbox.pack_start(entry_point_string, True)
        vbox.pack_start(hbox)

        if "point_string" in kwargs:
            entry_point_string.set_text(kwargs['point_string'])

        hbox = gtk.HBox()
        label = gtk.Label('[STOP]')
        hbox.pack_start(label, True)
        entry_stoppoint = gtk.Entry()
        entry_stoppoint.set_max_length(20)
        hbox.pack_start(entry_stoppoint, True)
        vbox.pack_start(hbox)

        help_button = gtk.Button("_Help")
        help_button.connect("clicked", self.command_help, "control", "insert")

        hbox = gtk.HBox()
        insert_button = gtk.Button("_Insert")
        insert_button.connect(
            "clicked", self.insert_task, window, entry_match,
            entry_point_string, entry_stoppoint, fam_cb
        )
        cancel_button = gtk.Button("_Cancel")
        cancel_button.connect("clicked", lambda x: window.destroy())
        hbox.pack_start(insert_button, False)
        hbox.pack_end(cancel_button, False)
        hbox.pack_end(help_button, False)
        vbox.pack_start(hbox)

        window.add(vbox)
        window.show_all()

    def insert_task(self, w, window, entry_match, entry_point_string,
                    entry_stoppoint, fam_cb):
        match = entry_match.get_text()
        point_string = entry_point_string.get_text()
        is_family = fam_cb.get_active()
        stop_point_string = entry_stoppoint.get_text()

        if match == '' or point_string == '':
            warning_dialog(
                "Enter task or family name MATCH expression",
                self.window).warn()
            return

        window.destroy()

        stop = None
        if stop_point_string != '':
            stop = stop_point_string

        try:
            result = self.get_pyro('command-interface').put(
                'insert task', match, point_string, is_family, stop)
        except Exception, x:
            warning_dialog(x.__str__(), self.window).warn()
            return
        if not result[0]:
            warning_dialog(result[1], self.window).warn()

    def poll_all(self, w):
        command = "cylc poll " + self.cfg.suite + " --host=" + self.cfg.host
        foo = gcapture_tmpfile(command, self.cfg.cylc_tmpdir, 600, 400)
        self.gcapture_windows.append(foo)
        foo.run()

    def reload_suite(self, w):
        msg = """Reload the suite definition.
This allows you change task runtime configuration and add
or remove task definitions without restarting the suite."""
        prompt = gtk.MessageDialog(self.window, gtk.DIALOG_MODAL,
                                   gtk.MESSAGE_QUESTION,
                                   gtk.BUTTONS_OK_CANCEL, msg)

        prompt.add_button(gtk.STOCK_HELP, gtk.RESPONSE_HELP)
        response = prompt.run()

        while response == gtk.RESPONSE_HELP:
            self.command_help("control", "reload")
            response = prompt.run()

        prompt.destroy()
        if response != gtk.RESPONSE_OK:
            return

        command = (
            "cylc reload -f --host=" + self.cfg.host +
            " --user=" + self.cfg.owner + " " + self.cfg.suite)
        foo = gcapture_tmpfile(command, self.cfg.cylc_tmpdir, 600, 400)
        self.gcapture_windows.append(foo)
        foo.run()

    def nudge_suite(self, w):
        try:
            result = self.get_pyro('command-interface').put('nudge suite')
        except Exception, x:
            warning_dialog(str(x), self.window).warn()
            return False
        if not result:
            warning_dialog('Failed to nudge the suite', self.window).warn()

    def popup_logview(self, task_id, logfiles, choice=None):
        """Display task job log files in a combo log viewer."""
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.modify_bg(gtk.STATE_NORMAL,
                         gtk.gdk.color_parse(self.log_colors.get_color()))
        window.set_border_width(5)
        window.set_size_request(800, 400)
        log_paths = list(logfiles)
        log_paths.sort(key=self._sort_key_func, reverse=True)
        init_active_index = None
        if choice:
            for i, log in enumerate(log_paths):
                if log.endswith("/" + choice):
                    init_active_index = i
                    break

        auth = None
        if is_remote_host(self.cfg.host):
            auth = self.cfg.host
        elif is_remote_user(self.cfg.owner):
            auth = self.cfg.owner + "@" + self.cfg.host
        if auth:
            for i, log in enumerate(log_paths):
                if ":" not in log:
                    log_paths[i] = auth + ":" + log
        window.set_title(task_id + ": Log Files")
        print init_active_index
        lv = ComboLogViewer(task_id, log_paths, init_active_index)
        self.quitters.append(lv)

        window.add(lv.get_widget())

        quit_button = gtk.Button("_Close")
        quit_button.connect("clicked", self.on_popup_quit, lv, window)

        lv.hbox.pack_start(quit_button, False)

        window.connect("delete_event", lv.quit_w_e)
        window.show_all()

    def _sort_key_func(self, log_path):
        """Sort key for a task job log path."""
        head, submit_num, base = log_path.rsplit("/", 2)
        try:
            submit_num = int(submit_num)
        except ValueError:
            pass
        return (submit_num, base, head)

    def _set_tooltip(self, widget, tip_text):
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip(widget, tip_text)

    def create_main_menu(self):
        self.menu_bar = gtk.MenuBar()

        file_menu = gtk.Menu()

        file_menu_root = gtk.MenuItem('_File')
        file_menu_root.set_submenu(file_menu)

        open_item = gtk.ImageMenuItem('_Switch To Another Suite')
        img = gtk.image_new_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_MENU)
        open_item.set_image(img)
        open_item.connect('activate', self.click_open)
        file_menu.append(open_item)

        reg_new_item = gtk.ImageMenuItem('Register A _New Suite')
        img = gtk.image_new_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_MENU)
        reg_new_item.set_image(img)
        reg_new_item.connect('activate', self.newreg_popup)
        file_menu.append(reg_new_item)

        exit_item = gtk.ImageMenuItem('E_xit Gcylc')
        img = gtk.image_new_from_stock(gtk.STOCK_QUIT, gtk.ICON_SIZE_MENU)
        exit_item.set_image(img)
        exit_item.connect('activate', self.click_exit)
        file_menu.append(exit_item)

        self.view_menu = gtk.Menu()
        view_menu_root = gtk.MenuItem('_View')
        view_menu_root.set_submenu(self.view_menu)

        self.view1_align_item = gtk.CheckMenuItem(
            label="Toggle views _side-by-side")
        self._set_tooltip(
            self.view1_align_item, "Toggle horizontal layout of views.")
        self.view1_align_item.connect(
            'toggled', self._cb_change_view_align)
        self.view_menu.append(self.view1_align_item)

        self.view_menu.append(gtk.SeparatorMenuItem())

        poll_item = gtk.ImageMenuItem("Reset Connection _Polling")
        img = gtk.image_new_from_stock(gtk.STOCK_REFRESH, gtk.ICON_SIZE_MENU)
        poll_item.set_image(img)
        self._set_tooltip(
            poll_item,
            """If gcylc is not connected to a running suite
it tries to reconnect after increasingly long delays,
to reduce network traffic.""")
        self.view_menu.append(poll_item)
        poll_item.connect('activate', self.reset_connection_polling)

        self.view_menu.append(gtk.SeparatorMenuItem())
        filter_item = gtk.ImageMenuItem("Task _Filtering")
        img = gtk.image_new_from_stock(gtk.STOCK_CONVERT,
                                       gtk.ICON_SIZE_MENU)
        filter_item.set_image(img)
        self._set_tooltip(
            filter_item, "Filter by task state or name")
        self.view_menu.append(filter_item)
        filter_item.connect('activate', self.popup_filter_dialog)

        self.view_menu.append(gtk.SeparatorMenuItem())

        key_item = gtk.ImageMenuItem("State Icon _Key")
        dots = DotMaker(self.theme, size='small')
        img = dots.get_image("running")
        key_item.set_image(img)
        self._set_tooltip(
            key_item, "Describe what task states the colors represent")
        self.view_menu.append(key_item)
        key_item.connect('activate', self.popup_theme_legend)

        dot_size_item = gtk.ImageMenuItem('State Icon _Size')
        img = gtk.image_new_from_stock(
            gtk.STOCK_ZOOM_FIT, gtk.ICON_SIZE_MENU)
        dot_size_item.set_image(img)
        self.view_menu.append(dot_size_item)
        dot_sizemenu = gtk.Menu()
        dot_size_item.set_submenu(dot_sizemenu)

        dot_sizes = ['small', 'medium', 'large', 'extra large']
        dot_size_items = {}
        self.dot_size = gcfg.get(['dot icon size'])
        dot_size_items[self.dot_size] = gtk.RadioMenuItem(
            label='_' + self.dot_size)
        dot_sizemenu.append(dot_size_items[self.dot_size])
        self._set_tooltip(
            dot_size_items[self.dot_size],
            self.dot_size + " state icon dot size")
        for dsize in dot_sizes:
            if dsize == self.dot_size:
                continue
            dot_size_items[dsize] = gtk.RadioMenuItem(
                group=dot_size_items[self.dot_size], label='_' + dsize)
            dot_sizemenu.append(dot_size_items[dsize])
            self._set_tooltip(
                dot_size_items[dsize], dsize + " state icon size")

        # set_active then connect, to avoid causing an unnecessary toggle now.
        dot_size_items[self.dot_size].set_active(True)
        for dot_size in dot_sizes:
            dot_size_items[dot_size].connect(
                'toggled', self.set_dot_size, dot_size)

        theme_item = gtk.ImageMenuItem('State Icon _Theme')
        img = gtk.image_new_from_stock(
            gtk.STOCK_SELECT_COLOR, gtk.ICON_SIZE_MENU)
        theme_item.set_image(img)
        self.view_menu.append(theme_item)
        thememenu = gtk.Menu()
        theme_item.set_submenu(thememenu)

        theme_items = {}
        theme = "default"
        theme_items[theme] = gtk.RadioMenuItem(label='_' + theme)
        thememenu.append(theme_items[theme])
        self._set_tooltip(theme_items[theme], theme + " state icon theme")
        theme_items[theme].theme_name = theme
        for theme in gcfg.get(['themes']):
            if theme == "default":
                continue
            theme_items[theme] = gtk.RadioMenuItem(
                group=theme_items['default'], label='_' + theme)
            thememenu.append(theme_items[theme])
            self._set_tooltip(theme_items[theme], theme + " state icon theme")
            theme_items[theme].theme_name = theme

        # set_active then connect, to avoid causing an unnecessary toggle now.
        theme_items[self.theme_name].set_active(True)
        for theme in gcfg.get(['themes']):
            theme_items[theme].connect('toggled', self.set_theme)

        self.view_menu.append(gtk.SeparatorMenuItem())

        text_view0_item = gtk.RadioMenuItem(label="1 - _Text View")
        self.view_menu.append(text_view0_item)
        self._set_tooltip(
            text_view0_item, self.VIEW_DESC["text"] + " - primary panel")
        text_view0_item._viewname = "text"
        text_view0_item.set_active(self.DEFAULT_VIEW == "text")
        text_view0_item.connect('toggled', self._cb_change_view0_menu)

        dot_view0_item = gtk.RadioMenuItem(
            group=text_view0_item, label="1 - _Dot View")
        self.view_menu.append(dot_view0_item)
        self._set_tooltip(
            dot_view0_item, self.VIEW_DESC["dot"] + " - primary panel")
        dot_view0_item._viewname = "dot"
        dot_view0_item.set_active(self.DEFAULT_VIEW == "dot")
        dot_view0_item.connect('toggled', self._cb_change_view0_menu)

        graph_view0_item = gtk.RadioMenuItem(
            group=text_view0_item, label="1 - _Graph View")
        self.view_menu.append(graph_view0_item)
        self._set_tooltip(
            graph_view0_item, self.VIEW_DESC["graph"] + " - primary panel")
        graph_view0_item._viewname = "graph"
        graph_view0_item.set_active(self.DEFAULT_VIEW == "graph")
        graph_view0_item.connect('toggled', self._cb_change_view0_menu)
        if graphing_disabled or self.restricted_display:
            graph_view0_item.set_sensitive(False)

        self.view_menu_views0 = [
            text_view0_item, dot_view0_item, graph_view0_item]

        self.views_option_menuitems = [gtk.MenuItem("1 - _Options")]
        self.views_option_menus = [gtk.Menu()]
        self.views_option_menuitems[0].set_submenu(self.views_option_menus[0])
        self._set_tooltip(
            self.views_option_menuitems[0], "Options for primary panel")
        self.view_menu.append(self.views_option_menuitems[0])

        self.view_menu.append(gtk.SeparatorMenuItem())

        no_view1_item = gtk.RadioMenuItem(label="2 - Off")
        no_view1_item.set_active(True)
        self.view_menu.append(no_view1_item)
        self._set_tooltip(no_view1_item, "Switch off secondary view panel")
        no_view1_item._viewname = "None"
        no_view1_item.connect('toggled', self._cb_change_view1_menu)

        text_view1_item = gtk.RadioMenuItem(
            group=no_view1_item, label="2 - Te_xt View")
        self.view_menu.append(text_view1_item)
        self._set_tooltip(
            text_view1_item, self.VIEW_DESC["text"] + " - secondary panel")
        text_view1_item._viewname = "text"
        text_view1_item.connect('toggled', self._cb_change_view1_menu)

        dot_view1_item = gtk.RadioMenuItem(
            group=no_view1_item, label="2 - Dot _View")
        self.view_menu.append(dot_view1_item)
        self._set_tooltip(
            dot_view1_item, self.VIEW_DESC["dot"] + " - secondary panel")
        dot_view1_item._viewname = "dot"
        dot_view1_item.connect('toggled', self._cb_change_view1_menu)

        graph_view1_item = gtk.RadioMenuItem(
            group=no_view1_item, label="2 - Grap_h View")
        self.view_menu.append(graph_view1_item)
        self._set_tooltip(
            graph_view1_item, self.VIEW_DESC["graph"] + " - secondary panel")
        graph_view1_item._viewname = "graph"
        graph_view1_item.connect('toggled', self._cb_change_view1_menu)

        if graphing_disabled or self.restricted_display:
            graph_view1_item.set_sensitive(False)

        self.view_menu_views1 = [
            no_view1_item, text_view1_item, dot_view1_item, graph_view1_item]

        self.views_option_menuitems.append(gtk.MenuItem("2 - O_ptions"))
        self.views_option_menus.append(gtk.Menu())
        self._set_tooltip(self.views_option_menuitems[1],
                          "Options for secondary panel")
        self.views_option_menuitems[1].set_submenu(self.views_option_menus[1])
        self.view_menu.append(self.views_option_menuitems[1])

        start_menu = gtk.Menu()
        start_menu_root = gtk.MenuItem('_Control')
        start_menu_root.set_submenu(start_menu)

        self.run_menuitem = gtk.ImageMenuItem('_Run Suite ... ')
        img = gtk.image_new_from_stock(gtk.STOCK_MEDIA_PLAY,
                                       gtk.ICON_SIZE_MENU)
        self.run_menuitem.set_image(img)
        start_menu.append(self.run_menuitem)
        self.run_menuitem.connect('activate', self.startsuite_popup)

        self.pause_menuitem = gtk.ImageMenuItem('_Hold Suite (pause)')
        img = gtk.image_new_from_stock(gtk.STOCK_MEDIA_PAUSE,
                                       gtk.ICON_SIZE_MENU)
        self.pause_menuitem.set_image(img)
        start_menu.append(self.pause_menuitem)
        self.pause_menuitem.connect('activate', self.pause_suite)

        self.unpause_menuitem = gtk.ImageMenuItem('R_elease Suite (unpause)')
        img = gtk.image_new_from_stock(gtk.STOCK_MEDIA_PLAY,
                                       gtk.ICON_SIZE_MENU)
        self.unpause_menuitem.set_image(img)
        start_menu.append(self.unpause_menuitem)
        self.unpause_menuitem.connect('activate', self.resume_suite)

        self.stop_menuitem = gtk.ImageMenuItem('_Stop Suite ... ')
        img = gtk.image_new_from_stock(gtk.STOCK_MEDIA_STOP,
                                       gtk.ICON_SIZE_MENU)
        self.stop_menuitem.set_image(img)
        start_menu.append(self.stop_menuitem)
        self.stop_menuitem.connect('activate', self.stopsuite_popup)

        start_menu.append(gtk.SeparatorMenuItem())

        nudge_item = gtk.ImageMenuItem('_Nudge (updates times)')
        img = gtk.image_new_from_stock(gtk.STOCK_REFRESH, gtk.ICON_SIZE_MENU)
        nudge_item.set_image(img)
        start_menu.append(nudge_item)
        nudge_item.connect('activate', self.nudge_suite)

        reload_item = gtk.ImageMenuItem('Re_load Suite Definition ...')
        img = gtk.image_new_from_stock(gtk.STOCK_CDROM, gtk.ICON_SIZE_MENU)
        reload_item.set_image(img)
        start_menu.append(reload_item)
        reload_item.connect('activate', self.reload_suite)

        insert_item = gtk.ImageMenuItem('_Insert Task(s) ...')
        img = gtk.image_new_from_stock(gtk.STOCK_PASTE, gtk.ICON_SIZE_MENU)
        insert_item.set_image(img)
        start_menu.append(insert_item)
        insert_item.connect('activate', self.insert_task_popup)

        poll_item = gtk.ImageMenuItem('Poll All ...')
        img = gtk.image_new_from_stock(gtk.STOCK_REFRESH, gtk.ICON_SIZE_MENU)
        poll_item.set_image(img)
        start_menu.append(poll_item)
        poll_item.connect('activate', self.poll_all)

        start_menu.append(gtk.SeparatorMenuItem())

        runahead_item = gtk.ImageMenuItem('_Change Runahead Limit ...')
        img = gtk.image_new_from_stock(gtk.STOCK_JUMP_TO, gtk.ICON_SIZE_MENU)
        runahead_item.set_image(img)
        start_menu.append(runahead_item)
        runahead_item.connect('activate', self.change_runahead_popup)

        tools_menu = gtk.Menu()
        tools_menu_root = gtk.MenuItem('_Suite')
        tools_menu_root.set_submenu(tools_menu)

        val_item = gtk.ImageMenuItem('_Validate')
        img = gtk.image_new_from_stock(gtk.STOCK_APPLY, gtk.ICON_SIZE_MENU)
        val_item.set_image(img)
        tools_menu.append(val_item)
        val_item.connect('activate', self.run_suite_validate)

        tools_menu.append(gtk.SeparatorMenuItem())

        des_item = gtk.ImageMenuItem('_Describe')
        img = gtk.image_new_from_stock(gtk.STOCK_DND, gtk.ICON_SIZE_MENU)
        des_item.set_image(img)
        tools_menu.append(des_item)
        des_item.connect('activate', self.describe_suite)

        info_item = gtk.ImageMenuItem('_Info (Running)')
        img = gtk.image_new_from_stock(gtk.STOCK_DIALOG_INFO,
                                       gtk.ICON_SIZE_MENU)
        info_item.set_image(img)
        tools_menu.append(info_item)
        info_item.connect('activate', self.run_suite_info)

        tools_menu.append(gtk.SeparatorMenuItem())

        graph_item = gtk.ImageMenuItem('_Graph')
        img = gtk.image_new_from_stock(gtk.STOCK_SELECT_COLOR,
                                       gtk.ICON_SIZE_MENU)
        graph_item.set_image(img)
        tools_menu.append(graph_item)
        graphmenu = gtk.Menu()
        graph_item.set_submenu(graphmenu)

        gtree_item = gtk.MenuItem('_Dependencies')
        graphmenu.append(gtree_item)
        gtree_item.connect('activate', self.run_suite_graph, False)

        gns_item = gtk.MenuItem('_Namespaces')
        graphmenu.append(gns_item)
        gns_item.connect('activate', self.run_suite_graph, True)

        if graphing_disabled:
            gtree_item.set_sensitive(False)
            gns_item.set_sensitive(False)

        list_item = gtk.ImageMenuItem('_List')
        img = gtk.image_new_from_stock(gtk.STOCK_INDEX, gtk.ICON_SIZE_MENU)
        list_item.set_image(img)
        tools_menu.append(list_item)
        list_menu = gtk.Menu()
        list_item.set_submenu(list_menu)

        flat_item = gtk.MenuItem('_Tasks')
        list_menu.append(flat_item)
        flat_item.connect('activate', self.run_suite_list)

        tree_item = gtk.MenuItem('_Namespaces')
        list_menu.append(tree_item)
        tree_item.connect('activate', self.run_suite_list, '-t')

        view_item = gtk.ImageMenuItem('_View')
        img = gtk.image_new_from_stock(gtk.STOCK_EDIT, gtk.ICON_SIZE_MENU)
        view_item.set_image(img)
        tools_menu.append(view_item)
        subviewmenu = gtk.Menu()
        view_item.set_submenu(subviewmenu)

        rw_item = gtk.MenuItem('_Raw')
        subviewmenu.append(rw_item)
        rw_item.connect('activate', self.run_suite_view, 'raw')

        viewi_item = gtk.MenuItem('_Inlined')
        subviewmenu.append(viewi_item)
        viewi_item.connect('activate', self.run_suite_view, 'inlined')

        viewp_item = gtk.MenuItem('_Processed')
        subviewmenu.append(viewp_item)
        viewp_item.connect('activate', self.run_suite_view, 'processed')

        edit_item = gtk.ImageMenuItem('_Edit')
        img = gtk.image_new_from_stock(gtk.STOCK_EDIT, gtk.ICON_SIZE_MENU)
        edit_item.set_image(img)
        tools_menu.append(edit_item)
        edit_menu = gtk.Menu()
        edit_item.set_submenu(edit_menu)

        raw_item = gtk.MenuItem('_Raw')
        edit_menu.append(raw_item)
        raw_item.connect('activate', self.run_suite_edit, False)

        inl_item = gtk.MenuItem('_Inlined')
        edit_menu.append(inl_item)
        inl_item.connect('activate', self.run_suite_edit, True)

        search_item = gtk.ImageMenuItem('_Search')
        img = gtk.image_new_from_stock(gtk.STOCK_FIND, gtk.ICON_SIZE_MENU)
        search_item.set_image(img)
        tools_menu.append(search_item)
        search_item.connect('activate', self.search_suite_popup)

        tools_menu.append(gtk.SeparatorMenuItem())

        log_item = gtk.ImageMenuItem('Std _Output')
        img = gtk.image_new_from_stock(gtk.STOCK_DND, gtk.ICON_SIZE_MENU)
        log_item.set_image(img)
        tools_menu.append(log_item)
        log_item.connect('activate', self.run_suite_log, 'out')

        out_item = gtk.ImageMenuItem('Std _Error')
        img = gtk.image_new_from_stock(gtk.STOCK_DND, gtk.ICON_SIZE_MENU)
        out_item.set_image(img)
        tools_menu.append(out_item)
        out_item.connect('activate', self.run_suite_log, 'err')

        log_item = gtk.ImageMenuItem('Event _Log')
        img = gtk.image_new_from_stock(gtk.STOCK_DND, gtk.ICON_SIZE_MENU)
        log_item.set_image(img)
        tools_menu.append(log_item)
        log_item.connect('activate', self.run_suite_log, 'log')

        help_menu = gtk.Menu()
        help_menu_root = gtk.MenuItem('_Help')
        help_menu_root.set_submenu(help_menu)

        doc_menu = gtk.Menu()
        doc_item = gtk.ImageMenuItem("_Documentation")
        img = gtk.image_new_from_stock(gtk.STOCK_COPY, gtk.ICON_SIZE_MENU)
        doc_item.set_image(img)
        doc_item.set_submenu(doc_menu)
        help_menu.append(doc_item)

        cug_html_item = gtk.ImageMenuItem('(file://) Documentation Index')
        img = gtk.image_new_from_stock(gtk.STOCK_DND, gtk.ICON_SIZE_MENU)
        cug_html_item.set_image(img)
        doc_menu.append(cug_html_item)
        cug_html_item.connect('activate', self.browse)

        cug_pdf_item = gtk.ImageMenuItem('(file://) PDF User Guide')
        img = gtk.image_new_from_stock(gtk.STOCK_EDIT, gtk.ICON_SIZE_MENU)
        cug_pdf_item.set_image(img)
        doc_menu.append(cug_pdf_item)
        cug_pdf_item.connect('activate', self.browse, '-p')

        doc_menu.append(gtk.SeparatorMenuItem())

        if GLOBAL_CFG.get(['documentation', 'urls', 'local index']):
            cug_www_item = gtk.ImageMenuItem('(http://) Local Document Index')
            img = gtk.image_new_from_stock(gtk.STOCK_JUMP_TO,
                                           gtk.ICON_SIZE_MENU)
            cug_www_item.set_image(img)
            doc_menu.append(cug_www_item)
            cug_www_item.connect('activate', self.browse, '-x')

        cug_www_item = gtk.ImageMenuItem('(http://) _Internet Home Page')
        img = gtk.image_new_from_stock(gtk.STOCK_JUMP_TO, gtk.ICON_SIZE_MENU)
        cug_www_item.set_image(img)
        doc_menu.append(cug_www_item)
        cug_www_item.connect('activate', self.browse, '-w')

        chelp_menu = gtk.ImageMenuItem('_Command Help')
        img = gtk.image_new_from_stock(gtk.STOCK_EXECUTE, gtk.ICON_SIZE_MENU)
        chelp_menu.set_image(img)
        help_menu.append(chelp_menu)
        self.construct_command_menu(chelp_menu)

        about_item = gtk.ImageMenuItem('_About')
        img = gtk.image_new_from_stock(gtk.STOCK_ABOUT, gtk.ICON_SIZE_MENU)
        about_item.set_image(img)
        help_menu.append(about_item)
        about_item.connect('activate', self.about)

        start_menu_root.set_sensitive(False)
        view_menu_root.set_sensitive(False)
        tools_menu_root.set_sensitive(False)
        self.suite_menus = (start_menu_root, view_menu_root, tools_menu_root)

        self.menu_bar.append(file_menu_root)
        self.menu_bar.append(view_menu_root)
        self.menu_bar.append(start_menu_root)
        self.menu_bar.append(tools_menu_root)
        self.menu_bar.append(help_menu_root)

    def describe_suite(self, w):
        command = (
            "echo '> TITLE:'; " +
            "cylc get-suite-config -i title " + self.cfg.suite + "; " +
            "echo '> DESCRIPTION:'; " +
            "cylc get-suite-config --notify-completion -i description " +
            self.cfg.suite)
        foo = gcapture_tmpfile(command, self.cfg.cylc_tmpdir, 800, 400)
        self.gcapture_windows.append(foo)
        foo.run()

    def search_suite_popup(self, w):
        reg = self.cfg.suite
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title("Suite Search")
        window.set_transient_for(self.window)
        window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)

        vbox = gtk.VBox()

        label = gtk.Label("SUITE: " + reg)
        vbox.pack_start(label)

        label = gtk.Label("PATTERN")
        pattern_entry = gtk.Entry()
        hbox = gtk.HBox()
        hbox.pack_start(label)
        hbox.pack_start(pattern_entry, True)
        vbox.pack_start(hbox)

        yesbin_cb = gtk.CheckButton("Also search suite bin directory")
        yesbin_cb.set_active(True)
        vbox.pack_start(yesbin_cb, True)

        cancel_button = gtk.Button("_Cancel")
        cancel_button.connect("clicked", lambda x: window.destroy())

        ok_button = gtk.Button("_Search")
        ok_button.connect("clicked", self.search_suite, reg, yesbin_cb,
                          pattern_entry)

        help_button = gtk.Button("_Help")
        help_button.connect("clicked", self.command_help, 'prep', 'search')

        hbox = gtk.HBox()
        hbox.pack_start(ok_button, False)
        hbox.pack_end(cancel_button, False)
        hbox.pack_end(help_button, False)
        vbox.pack_start(hbox)

        window.add(vbox)
        window.show_all()

    def search_suite(self, w, reg, yesbin_cb, pattern_entry):
        pattern = pattern_entry.get_text()
        options = ''
        if not yesbin_cb.get_active():
            options += ' -x '
        command = (
            "cylc search --notify-completion %s %s %s" % (
                options, reg, pattern)
        )
        foo = gcapture_tmpfile(command, self.cfg.cylc_tmpdir, width=600,
                               height=500)
        self.gcapture_windows.append(foo)
        foo.run()

    def newreg_popup(self, w):
        dialog = gtk.FileChooserDialog(
            title='Register Or Create A Suite',
            action=gtk.FILE_CHOOSER_ACTION_SAVE,
            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                     gtk.STOCK_OPEN, gtk.RESPONSE_OK)
        )
        filter = gtk.FileFilter()
        filter.set_name("Cylc Suite Definition Files")
        filter.add_pattern("suite.rc")
        dialog.add_filter(filter)

        response = dialog.run()
        if response != gtk.RESPONSE_OK:
            dialog.destroy()
            return False

        res = dialog.get_filename()

        dialog.destroy()

        dir = os.path.dirname(res)
        fil = os.path.basename(res)

        if fil != "suite.rc":
            warning_dialog(
                "Suite definitions filenames must be \"suite.rc\" : " +
                fil, self.window).warn()
            fil = "suite.rc"

        # handle home directories under gpfs filesets, e.g.: if my home
        # directory is /home/oliver:
        home = os.environ['HOME']
        # but is really located on a gpfs fileset such as this:
        # /gpfs/filesets/hpcf/home/oliver; the pygtk file chooser will
        # return the "real" path that really should be hidden:
        home_real = os.path.realpath(home)
        # so let's restore it to the familiar form (/home/oliver):
        dir = re.sub('^' + home_real, home, dir)

        suiterc = os.path.join(dir, fil)

        if not os.path.isfile(suiterc):
            info_dialog(
                "creating a template suite definition: %s" % suiterc,
                self.window).inform()
            template = open(suiterc, 'wb')
            template.write(
                '''
title = "my new suite definition"
description = """
This is what my suite does:..."""
[scheduling]
    [[dependencies]]
        graph = "foo"
[runtime]
    [[foo]]
       # settings...'''
            )
            template.close()

        window = EntryDialog(parent=self.window, flags=0,
                             type=gtk.MESSAGE_QUESTION,
                             buttons=gtk.BUTTONS_OK_CANCEL,
                             message_format="Suite name for " + dir)

        suite = window.run()
        window.destroy()
        if suite:
            command = "cylc register " + suite + ' ' + dir
            res, stdout = run_get_stdout(command)
            if res:
                self.reset(suite)

    def reset_connection_polling(self, bt):
        # Force the polling schedule to go back to short intervals so
        # that the GUI can immediately connect to the started suite.
        self.updater.poll_schd.t_init = None

    def construct_command_menu(self, menu):
        cat_menu = gtk.Menu()
        menu.set_submenu(cat_menu)

        cylc_help_item = gtk.MenuItem('cylc')
        cat_menu.append(cylc_help_item)
        cylc_help_item.connect('activate', self.command_help)

        cout = subprocess.Popen(["cylc", "categories"],
                                stdout=subprocess.PIPE).communicate()[0]
        categories = cout.rstrip().split()
        for category in categories:
            foo_item = gtk.MenuItem(category)
            cat_menu.append(foo_item)
            com_menu = gtk.Menu()
            foo_item.set_submenu(com_menu)
            cout = subprocess.Popen(["cylc", "category="+category],
                                    stdout=subprocess.PIPE).communicate()[0]
            commands = cout.rstrip().split()
            for command in commands:
                bar_item = gtk.MenuItem(command)
                com_menu.append(bar_item)
                bar_item.connect('activate', self.command_help, category,
                                 command)

    def check_task_filter_buttons(self, tb=None):
        task_states = []
        for subbox in self.task_filter_box.get_children():
            for ebox in subbox.get_children():
                box = ebox.get_children()[0]
                try:
                    icon, cb = box.get_children()
                except (ValueError, AttributeError) as exc:
                    # ValueError: an empty box to line things up.
                    # AttributeError: the name filter entry box.
                    pass
                else:
                    if cb.get_active():
                        ebox.modify_bg(gtk.STATE_NORMAL, None)
                    else:
                        # Remove '_' (keyboard mnemonics) from state name.
                        task_states.append(cb.get_label().replace('_', ''))
                        ebox.modify_bg(gtk.STATE_NORMAL,
                                       self.filter_highlight_color)

        self.updater.filter_states_excl = task_states
        self.filter_states_excl = task_states
        self.info_bar.set_filter_state(task_states, self.filter_name_string)
        self.updater.refilter()
        self.refresh_views()

    def reset_filter_box(self, w=None):
        for subbox in self.task_filter_box.get_children():
            for ebox in subbox.get_children():
                box = ebox.get_children()[0]
                try:
                    icon, cb = box.get_children()
                except (ValueError, AttributeError) as exc:
                    # ValueError: an empty box to line things up.
                    # AttributeError: the name filter entry box.
                    pass
                else:
                    cb.set_active(True)
        self.check_task_filter_buttons()
        self.filter_entry.set_text("")
        self.check_filter_entry()

    def check_filter_entry(self, e=None):
        filter_text = self.filter_entry.get_text()
        try:
            re.compile(filter_text)
        except re.error as exc:
            warning_dialog(
                "Bad filter regex: '%s': error: %s.\n"
                "Enter a string literal or valid regular expression." % (
                    filter_text, exc)).warn()
            return
        if filter_text != "":
            self.filter_entry.modify_base(gtk.STATE_NORMAL,
                                          self.filter_highlight_color)
        else:
            self.filter_entry.modify_base(gtk.STATE_NORMAL, None)
        self.filter_name_string = filter_text
        self.updater.filter_name_string = filter_text
        self.info_bar.set_filter_state(self.filter_states_excl, filter_text)
        self.updater.refilter()
        self.refresh_views()

    def refresh_views(self):
        for view in self.current_views:
            if view is not None:
                view.refresh()

    def create_task_filter_widgets(self):
        self.task_filter_box = gtk.VBox()
        PER_ROW = 3
        n_states = len(self.legal_task_states)
        n_rows = n_states / PER_ROW
        if n_states % PER_ROW:
            n_rows += 1
        dotm = DotMaker(self.theme, size=self.dot_size)
        for row in range(0, n_rows):
            subbox = gtk.HBox(homogeneous=True)
            self.task_filter_box.pack_start(subbox)
            for i in range(0, PER_ROW):
                ebox = gtk.EventBox()
                box = gtk.HBox()
                ebox.add(box)
                try:
                    st = self.legal_task_states[row * PER_ROW + i]
                except Exception:
                    pass
                else:
                    icon = dotm.get_image(st)
                    cb = gtk.CheckButton(task_state.labels[st])
                    cb.set_active(st not in self.filter_states_excl)
                    cb.connect('toggled', self.check_task_filter_buttons)
                    tooltip = gtk.Tooltips()
                    tooltip.enable()
                    tooltip.set_tip(cb, "Filter by task state = %s" % st)
                    box.pack_start(icon, expand=False)
                    box.pack_start(cb, expand=False)
                subbox.pack_start(ebox, fill=True)

        self.filter_entry = EntryTempText()
        self.filter_entry.set_width_chars(7)
        self.filter_entry.connect("activate", self.check_filter_entry)
        self.filter_entry.set_temp_text("task name filter")
        hbox = gtk.HBox()
        ebox = gtk.EventBox()
        ebox.add(self.filter_entry)
        hbox.pack_start(ebox)
        self.task_filter_box.pack_start(hbox)
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip(self.filter_entry,
                        "Filter by task name.\n"
                        "Enter a sub-string or regex and hit Enter\n"
                        "(to reset, clear the entry and hit Enter)")

    def create_tool_bar(self):
        """Create the tool bar for the control GUI."""
        initial_views = self.initial_views
        self.tool_bars = [gtk.Toolbar(), gtk.Toolbar()]
        views = self.VIEWS_ORDERED
        self.tool_bar_view0 = gtk.ComboBox()
        self.tool_bar_view1 = gtk.ComboBox()
        pixlist0 = gtk.ListStore(gtk.gdk.Pixbuf, str)
        pixlist1 = gtk.ListStore(gtk.gdk.Pixbuf, str, bool, bool)
        view_items = []
        for v in views:
            pixbuf = gtk.gdk.pixbuf_new_from_file(self.cfg.imagedir +
                                                  self.VIEW_ICON_PATHS[v])
            pixlist0.append((pixbuf, v))
            pixlist1.append((pixbuf, v, True, False))
        pixlist1.insert(0, (pixbuf, "None", False, True))
        # Primary view chooser
        self.tool_bar_view0.set_model(pixlist0)
        cell_pix0 = gtk.CellRendererPixbuf()
        self.tool_bar_view0.pack_start(cell_pix0)
        self.tool_bar_view0.add_attribute(cell_pix0, "pixbuf", 0)
        self.tool_bar_view0.set_active(views.index(initial_views[0]))
        self.tool_bar_view0.connect("changed", self._cb_change_view0_tool)
        self._set_tooltip(self.tool_bar_view0, "Change primary view")
        self.view_toolitems = [gtk.ToolItem()]
        self.view_toolitems[0].add(self.tool_bar_view0)
        # Secondary view chooser
        self.tool_bar_view1.set_model(pixlist1)
        cell_pix1 = gtk.CellRendererPixbuf()
        cell_text1 = gtk.CellRendererText()
        self.tool_bar_view1.pack_start(cell_pix1)
        self.tool_bar_view1.pack_start(cell_text1)
        self.tool_bar_view1.add_attribute(cell_pix1, "pixbuf", 0)
        self.tool_bar_view1.add_attribute(cell_text1, "text", 1)
        self.tool_bar_view1.add_attribute(cell_pix1, "visible", 2)
        self.tool_bar_view1.add_attribute(cell_text1, "visible", 3)
        if len(initial_views) == 1:
            # Only one view specified, set second to the null view.
            self.tool_bar_view1.set_active(0)
        else:
            self.tool_bar_view1.set_active(views.index(initial_views[1]) + 1)

        self.tool_bar_view1.connect("changed", self._cb_change_view1_tool)
        self._set_tooltip(self.tool_bar_view1, "Change secondary view")
        self.view_toolitems.append(gtk.ToolItem())
        self.view_toolitems[1].add(self.tool_bar_view1)
        # Horizontal layout toggler
        self.layout_toolbutton = gtk.ToggleToolButton()
        image = gtk.image_new_from_stock(
            gtk.STOCK_GOTO_LAST, gtk.ICON_SIZE_MENU)
        self.layout_toolbutton.set_icon_widget(image)
        self.layout_toolbutton.set_label("Layout")
        self.layout_toolbutton.set_homogeneous(False)
        self.layout_toolbutton.connect("toggled", self._cb_change_view_align)
        self.layout_toolbutton.set_active(self.view_layout_horizontal)
        self._set_tooltip(self.layout_toolbutton,
                          "Toggle views side-by-side.")
        # Insert the view choosers
        view0_label_item = gtk.ToolItem()
        view0_label_item.add(gtk.Label("View 1: "))
        self._set_tooltip(view0_label_item, "Primary view (top or left)")
        view1_label_item = gtk.ToolItem()
        view1_label_item.add(gtk.Label("View 2: "))
        self._set_tooltip(view1_label_item,
                          "Secondary view (bottom or right)")
        self.tool_bars[1].insert(self.view_toolitems[1], 0)
        self.tool_bars[1].insert(view1_label_item, 0)
        self.tool_bars[1].insert(gtk.SeparatorToolItem(), 0)
        self.tool_bars[1].insert(self.layout_toolbutton, 0)
        self.tool_bars[0].insert(self.view_toolitems[0], 0)
        self.tool_bars[0].insert(view0_label_item, 0)
        self.tool_bars[0].insert(gtk.SeparatorToolItem(), 0)
        stop_icon = gtk.image_new_from_stock(gtk.STOCK_MEDIA_STOP,
                                             gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.stop_toolbutton = gtk.ToolButton(icon_widget=stop_icon)
        self.stop_toolbutton.set_label("Stop Suite")
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip(self.stop_toolbutton,
                        """Stop Suite after current active tasks finish.
For more Stop options use the Control menu.""")
        self.stop_toolbutton.connect("clicked", self.stopsuite_default)
        self.tool_bars[0].insert(self.stop_toolbutton, 0)

        run_icon = gtk.image_new_from_stock(gtk.STOCK_MEDIA_PLAY,
                                            gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.run_pause_toolbutton = gtk.ToolButton(icon_widget=run_icon)
        self.run_pause_toolbutton.set_label("Run")
        self.run_pause_toolbutton.click_func = self.startsuite_popup
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip(self.run_pause_toolbutton, "Run Suite...")
        self.run_pause_toolbutton.connect("clicked", lambda w: w.click_func(w))
        self.tool_bars[0].insert(self.run_pause_toolbutton, 0)
        self.tool_bar_box = gtk.HPaned()
        self.tool_bar_box.pack1(self.tool_bars[0], resize=True, shrink=True)
        self.tool_bar_box.pack2(self.tool_bars[1], resize=True, shrink=True)

    def _alter_status_toolbar_menu(self, new_status):
        # Handle changes in status for some toolbar/menuitems.
        if new_status == self._prev_status:
            return False
        self._prev_status = new_status
        if "connected" in new_status:
            self.stop_toolbutton.set_sensitive(False)
            return False
        run_ok = bool("stopped" in new_status)
        pause_ok = bool("running" in new_status)
        unpause_ok = bool("hold at" in new_status or "held" in new_status or
                          "stopping" in new_status)
        stop_ok = bool("stopped" not in new_status)
        self.run_menuitem.set_sensitive(run_ok)
        self.pause_menuitem.set_sensitive(pause_ok)
        self.unpause_menuitem.set_sensitive(unpause_ok)
        self.stop_menuitem.set_sensitive(stop_ok)
        self.stop_toolbutton.set_sensitive(stop_ok and
                                           "stopping" not in new_status)
        if pause_ok:
            icon = gtk.STOCK_MEDIA_PAUSE
            tip_text = "Hold Suite (pause)"
            click_func = self.pause_suite
            label = "Hold"
        elif run_ok:
            icon = gtk.STOCK_MEDIA_PLAY
            tip_text = "Run Suite ..."
            click_func = self.startsuite_popup
            label = "Run"
        elif unpause_ok:
            icon = gtk.STOCK_MEDIA_PLAY
            tip_text = "Release Suite (unpause)"
            click_func = self.resume_suite
            label = "Release"
        else:
            # how do we end up here?
            self.run_pause_toolbutton.set_sensitive(False)
            return False
        icon_widget = gtk.image_new_from_stock(icon,
                                               gtk.ICON_SIZE_SMALL_TOOLBAR)
        icon_widget.show()
        self.run_pause_toolbutton.set_icon_widget(icon_widget)
        self.run_pause_toolbutton.set_label(label)
        tip_tuple = gtk.tooltips_data_get(self.run_pause_toolbutton)
        if tip_tuple is None:
            tips = gtk.Tooltips()
            tips.enable()
            tips.set_tip(self.run_pause_toolbutton, tip_text)
        self.run_pause_toolbutton.click_func = click_func

    def create_info_bar(self):
        self.info_bar = InfoBar(
            self.cfg.host, self.theme, self.dot_size,
            self.filter_states_excl,
            self.popup_filter_dialog,
            self._alter_status_toolbar_menu,
            lambda: self.run_suite_log(None, type="err"))
        self._set_info_bar()

    def popup_theme_legend(self, widget=None):
        """Popup a theme legend window."""
        if self.theme_legend_window is None:
            self.theme_legend_window = ThemeLegendWindow(
                self.window, self.theme, self.dot_size)
            self.theme_legend_window.connect(
                "destroy", self.destroy_theme_legend)
        else:
            self.theme_legend_window.present()

    def popup_filter_dialog(self, x=None, y=None):
        """Popup a task filtering diaolog."""
        if self.filter_dialog_window is None:
            self.create_task_filter_widgets()
            self.filter_dialog_window = TaskFilterWindow(
                self.window, self.task_filter_box, self.reset_filter_box)
            self.filter_dialog_window.connect(
                "destroy", self.destroy_filter_dialog)
        else:
            self.filter_dialog_window.present()
        self.check_task_filter_buttons()

    def destroy_filter_dialog(self, widget):
        """Handle a destroy of the filter dialog window."""
        self.filter_dialog_window = None

    def update_theme_legend(self):
        """Update the theme legend window, if it exists."""
        if self.theme_legend_window is not None:
            self.theme_legend_window.update(self.theme, self.dot_size)

    def update_filter_dialog(self):
        """Update the filter dialog window, if it exists."""
        # TODO - it would be nicer to update the dialog in-place!
        if self.filter_dialog_window is not None:
            self.filter_dialog_window.destroy()
            self.popup_filter_dialog()

    def destroy_theme_legend(self, widget):
        """Handle a destroy of the theme legend window."""
        self.theme_legend_window = None

    def get_pyro(self, object):
        return cylc_pyro_client.client(
            self.cfg.suite, self.cfg.pphrase, self.cfg.owner, self.cfg.host,
            self.cfg.pyro_timeout, self.cfg.port).get_proxy(object)

    def run_suite_validate(self, w):
        command = ("cylc validate -v " + self.get_remote_run_opts() +
                   " --notify-completion " + self.cfg.template_vars_opts +
                   " " + self.cfg.suite)
        foo = gcapture_tmpfile(command, self.cfg.cylc_tmpdir, 700)
        self.gcapture_windows.append(foo)
        foo.run()
        return False

    def run_suite_edit(self, w, inlined=False):
        extra = ''
        if inlined:
            extra = '-i '
        command = ("cylc edit --notify-completion -g" + " " +
                   self.cfg.template_vars_opts + " " +
                   self.get_remote_run_opts() + " " + extra + ' ' +
                   self.cfg.suite)
        foo = gcapture_tmpfile(command, self.cfg.cylc_tmpdir)
        self.gcapture_windows.append(foo)
        foo.run()
        return False

    def run_suite_graph(self, w, show_ns=False):
        if show_ns:
            command = "cylc graph --notify-completion -n %s %s %s" % (
                self.cfg.template_vars_opts,
                self.get_remote_run_opts(),
                self.cfg.suite)
            foo = gcapture_tmpfile(command, self.cfg.cylc_tmpdir)
            self.gcapture_windows.append(foo)
            foo.run()
        else:
            # TODO - a "load" button as for suite startup cycle points.
            graph_suite_popup(
                self.cfg.suite, self.command_help, None, None,
                self.get_remote_run_opts(), self.gcapture_windows,
                self.cfg.cylc_tmpdir, self.cfg.template_vars_opts,
                parent_window=self.window)

    def run_suite_info(self, w):
        command = (
            "cylc show --notify-completion" + self.get_remote_run_opts() +
            " " + self.cfg.suite)
        foo = gcapture_tmpfile(command, self.cfg.cylc_tmpdir, 600, 400)
        self.gcapture_windows.append(foo)
        foo.run()

    def run_suite_list(self, w, opt=''):
        command = (
            "cylc list " + self.get_remote_run_opts() + " " + opt +
            " --notify-completion " + " " + self.cfg.template_vars_opts + " " +
            self.cfg.suite)
        foo = gcapture_tmpfile(command, self.cfg.cylc_tmpdir, 600, 600)
        self.gcapture_windows.append(foo)
        foo.run()

    def run_suite_log(self, w, type='log'):
        if is_remote_host(self.cfg.host) or is_remote_user(self.cfg.owner):
            if type == 'out':
                xopts = ' --stdout '
            elif type == 'err':
                xopts = ' --stderr '
            else:
                xopts = ' '

            command = ("cylc cat-log --notify-completion" +
                       self.get_remote_run_opts() +
                       xopts + self.cfg.suite)
            foo = gcapture_tmpfile(command, self.cfg.cylc_tmpdir, 800, 400,
                                   title="%s %s" % (self.cfg.suite, type))
            self.gcapture_windows.append(foo)
            foo.run()
            return

        task_name_list = []  # TODO
        # assumes suite out, err, and log are in the same location:
        foo = cylc_logviewer(type, self.cfg.logdir, task_name_list)
        self.quitters.append(foo)

    def run_suite_view(self, w, method):
        extra = ''
        if method == 'inlined':
            extra = ' -i'
        elif method == 'processed':
            extra = ' -j'

        command = ("cylc view --notify-completion -g " +
                   self.get_remote_run_opts() + " " + extra + " " +
                   self.cfg.template_vars_opts + " " + self.cfg.suite)
        foo = gcapture_tmpfile(command, self.cfg.cylc_tmpdir, 400)
        self.gcapture_windows.append(foo)
        foo.run()
        return False

    def get_remote_run_opts(self):
        return " --host=" + self.cfg.host + " --user=" + self.cfg.owner

    def browse(self, b, option=''):
        command = 'cylc doc ' + option
        foo = gcapture_tmpfile(command, self.cfg.cylc_tmpdir, 700)
        self.gcapture_windows.append(foo)
        foo.run()

    def command_help(self, w, cat='', com=''):
        command = "cylc " + cat + " " + com + " help"
        foo = gcapture_tmpfile(command, self.cfg.cylc_tmpdir, 700, 600)
        self.gcapture_windows.append(foo)
        foo.run()
