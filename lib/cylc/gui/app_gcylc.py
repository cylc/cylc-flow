#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA
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
import pango
import gobject
import shlex
from subprocess import Popen, PIPE, STDOUT
from uuid import uuid4
from isodatetime.parsers import TimePointParser

from cylc.hostuserutil import is_remote, is_remote_host, is_remote_user
from cylc.gui.dbchooser import dbchooser
from cylc.gui.combo_logviewer import ComboLogViewer
from cylc.gui.warning_dialog import warning_dialog, info_dialog

try:
    from cylc.gui.view_graph import ControlGraph
    from cylc.gui.graph import graph_suite_popup
except ImportError as exc:
    # pygraphviz not installed
    warning_dialog("WARNING: graph view disabled\n%s" % exc).warn()
    del exc
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
from cylc.network.httpclient import ClientError
from cylc.suite_status import SUITE_STATUS_STOPPED_WITH
from cylc.task_id import TaskID
from cylc.task_state_prop import extract_group_state
from cylc.version import CYLC_VERSION
from cylc.gui.option_group import controlled_option_group
from cylc.gui.color_rotator import ColorRotator
from cylc.gui.cylc_logviewer import cylc_logviewer
from cylc.gui.gcapture import gcapture_tmpfile
from cylc.suite_srv_files_mgr import SuiteSrvFilesManager
from cylc.suite_logging import SuiteLog
from cylc.cfgspec.glbl_cfg import glbl_cfg
from cylc.cfgspec.gcylc import gcfg
from cylc.wallclock import get_current_time_string
from cylc.task_state import (
    TASK_STATUSES_ALL, TASK_STATUSES_RESTRICTED, TASK_STATUSES_CAN_RESET_TO,
    TASK_STATUSES_WITH_JOB_SCRIPT, TASK_STATUSES_WITH_JOB_LOGS,
    TASK_STATUSES_TRIGGERABLE, TASK_STATUSES_ACTIVE, TASK_STATUS_RUNNING,
    TASK_STATUS_HELD, TASK_STATUS_FAILED)
from cylc.task_state_prop import get_status_prop


def run_get_stdout(command, filter_=False):
    try:
        popen = Popen(
            command,
            shell=True, stdin=open(os.devnull), stderr=PIPE, stdout=PIPE)
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
    except OSError as exc:
        warning_dialog(
            "ERROR: command invocation failed %s\n%s" % (exc, err)).warn()
        return (False, [])
    else:
        # output is a single string with newlines; but we return a list of
        # lines filtered (optionally) for a special '!cylc!' prefix.
        res = []
        for line in out.split('\n'):
            line.strip()
            if filter_:
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
    def __init__(self, parent_window, widgets):
        super(TaskFilterWindow, self).__init__()
        self.set_border_width(10)
        self.set_title("Task Filtering")
        if parent_window is None:
            self.set_icon(get_icon())
        else:
            self.set_transient_for(parent_window)
        self.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
        self.add(widgets)
        self.show_all()


class InitData(object):
    """
Class to hold initialisation data.
    """
    def __init__(self, suite, owner, host, port,
                 comms_timeout, template_vars, ungrouped_views,
                 use_defn_order):
        self.suite = suite
        self.owner = owner
        self.host = host
        self.port = port
        if comms_timeout:
            self.comms_timeout = float(comms_timeout)
        else:
            self.comms_timeout = None

        self.template_vars_opts = ""
        for item in template_vars.items():
            self.template_vars_opts += " --set=%s=%s" % item
        self.template_vars = template_vars
        self.ungrouped_views = ungrouped_views
        self.use_defn_order = use_defn_order

        self.cylc_tmpdir = glbl_cfg().get_tmpdir()
        self.no_prompt = glbl_cfg().get(
            ['disable interactive command prompts']
        )
        self.imagedir = get_image_dir()
        self.my_uuid = uuid4()
        self.logdir = None

    def reset(self, suite, auth=None):
        self.suite = suite
        if auth == '-':  # stopped suite from dbchooser
            self.host = None
            self.port = None
        elif auth:
            if '@' in auth:
                self.owner, host_port = auth.split('@', 1)
            else:
                host_port = auth
            if ':' in host_port:
                self.host, self.port = host_port.split(':', 1)
                self.port = int(self.port)
            else:
                self.host = auth
                self.port = None
        self.logdir = SuiteLog.get_dir_for_suite(suite)


class InfoBar(gtk.VBox):
    """Class to create an information bar."""

    DISCONNECTED_TEXT = "(not connected)"

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
        self.prog_bar_timer = None
        self.prog_bar_disabled = False

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

        self.update_time_str = "time..."
        self.time_widget = gtk.Label()
        self._set_tooltip(self.time_widget, "last update time")

        self.reconnect_interval_widget = gtk.Label()
        self._set_tooltip(
            self.reconnect_interval_widget,
            r"""Time interval to next reconnect attempt

Use *Connect Now* button to reconnect immediately.""")

        hbox = gtk.HBox(spacing=0)
        self.pack_start(hbox, False, False)

        # Note: using box padding or spacing creates spurious spacing around
        # the hidden widgets; instead we add spaces to text widgets labels.

        # From the left.
        vbox = gtk.VBox()
        self.prog_bar = gtk.ProgressBar()
        vbox.pack_end(self.prog_bar, False, True)
        # Add some text to get full height.
        self.prog_bar.set_text("...")

        eb = gtk.EventBox()
        eb.add(vbox)
        eb.connect('button-press-event', self.prog_bar_disable)
        hbox.pack_start(eb, False)

        for widget in [
                self.status_widget, self.state_widget,
                self.filter_state_widget, self.mode_widget]:
            eb = gtk.EventBox()
            eb.add(widget)
            hbox.pack_start(eb, False)

        # From the right.
        for widget in [
                self.log_widget, self.time_widget,
                self.reconnect_interval_widget]:
            eb = gtk.EventBox()
            eb.add(widget)
            hbox.pack_end(eb, False)

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
        gobject.idle_add(self.mode_widget.set_markup, " %s " % self._mode)

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
            ttip_text = "Filtering (click to alter):\n"
            if self._filter_states_excl:
                ttip_text += "STATES EXCLUDED:\n  %s" % (
                    ", ".join(self._filter_states_excl))
            if self._filter_name_string:
                ttip_text += "\nNAMES INCLUDED:\n  %s" % (
                    self._filter_name_string)
            hbox = gtk.HBox()
            hbox.pack_start(gtk.Label(" (filtered:"))
            for state in self._filter_states_excl:
                icon = self.dots.get_image(state, is_filtered=True)
                icon.show()
                hbox.pack_start(icon, False, False)
            if self._filter_name_string:
                label = gtk.Label(" %s" % self._filter_name_string)
                hbox.pack_start(label)
            hbox.pack_start(gtk.Label(") "))
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
            self.status_widget.set_text, " %s " % self._status)
        gobject.idle_add(self.notify_status_changed, self._status)

    def set_stop_summary(self, summary_maps):
        """Set various summary info."""
        task_summary = summary_maps[1]
        states = [t["state"] for t in task_summary.values() if "state" in t]

        self.set_state(states, is_suite_stopped=True)
        suite_state = "?"
        if states:
            suite_state = extract_group_state(states, is_stopped=True)
        summary = SUITE_STATUS_STOPPED_WITH % suite_state
        num_failed = 0
        for item in task_summary.values():
            if item.get("state") == TASK_STATUS_FAILED:
                num_failed += 1
        if num_failed:
            summary += ": %s failed tasks" % num_failed
        self.set_status(summary)
        # (called on idle_add)
        return False

    def set_update_time(self, update_time_str, next_update_dt_str=None):
        """Set last update text."""
        if self.update_time_str is None and update_time_str is None:
            update_time_str = get_current_time_string()
        if update_time_str and update_time_str != self.update_time_str:
            self.update_time_str = update_time_str
            gobject.idle_add(
                self.time_widget.set_text, " %s " % update_time_str)
        if next_update_dt_str is None:
            gobject.idle_add(self.reconnect_interval_widget.set_text, "")
        elif next_update_dt_str == self.DISCONNECTED_TEXT:
            gobject.idle_add(
                self.reconnect_interval_widget.set_text, next_update_dt_str)
        else:
            gobject.idle_add(
                self.reconnect_interval_widget.set_text,
                " (next connect: %s) " % next_update_dt_str)

    @staticmethod
    def _set_tooltip(widget, text):
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip(widget, text)

    def _log_widget_launch_hook(self, widget, event):
        self._log_widget_image.set_sensitive(False)
        self.log_launch_hook()

    def prog_bar_start(self, msg):
        """Start the progress bar running"""
        if self.prog_bar_active():
            # Already started (multiple calls are possible via idle_add).
            return False
        self.prog_bar_timer = gobject.timeout_add(100, self.prog_bar_pulse)
        self.prog_bar.set_text(msg)
        self.prog_bar.show()
        self.status_widget.hide()
        self.prog_bar.show()
        self._set_tooltip(
            self.prog_bar,
            "%s\n(click to remove the progress bar)." % msg)
        return False

    def prog_bar_pulse(self):
        self.prog_bar.pulse()
        return True

    def prog_bar_stop(self):
        """Stop the progress bar running."""
        if not self.prog_bar_active():
            # Already stopped (multiple calls are possible via idle_add).
            return False
        gobject.source_remove(self.prog_bar_timer)
        self.prog_bar.set_fraction(0)
        self.prog_bar.set_text('')
        self.prog_bar_timer = None
        self.prog_bar.hide()
        self.status_widget.show()
        return False

    def prog_bar_disable(self, w=None, e=None):
        """Disable the progress bar (users may find it annoying)"""
        self.prog_bar_stop()
        self.prog_bar_disabled = True

    def prog_bar_can_start(self):
        if not self.prog_bar_active() and not self.prog_bar_disabled:
            return True

    def prog_bar_active(self):
        return self.prog_bar_timer is not None


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

    def __init__(self, suite, owner, host, port, comms_timeout,
                 template_vars, restricted_display):

        gobject.threads_init()

        set_exception_hook_dialog("gcylc")
        self.restricted_display = restricted_display
        if self.restricted_display:
            if "graph" in self.__class__.VIEWS:
                del self.__class__.VIEWS["graph"]
            if "graph" in self.__class__.VIEWS_ORDERED:
                self.__class__.VIEWS_ORDERED.remove('graph')

        self.cfg = InitData(
            suite, owner, host, port, comms_timeout, template_vars,
            gcfg.get(["ungrouped views"]),
            gcfg.get(["sort by definition order"]))

        self.theme_name = gcfg.get(['use theme'])
        self.theme = gcfg.get(['themes', self.theme_name])
        self.dot_size = gcfg.get(['dot icon size'])

        self.current_views = []

        self.theme_legend_window = None
        self.filter_dialog_window = None

        setup_icons()

        self.view_layout_horizontal = gcfg.get(['initial side-by-side views'])
        self.quitters = []
        self.gcapture_windows = []

        self.log_colors = ColorRotator()
        hcolor = gcfg.get(['task filter highlight color'])
        try:
            self.filter_highlight_color = gtk.gdk.color_parse(hcolor)
        except Exception:
            try:
                print >> sys.stderr, ("WARNING: bad gcylc.rc 'task filter "
                                      "highlight color' (defaulting to yellow)"
                                      )
            except IOError:
                pass  # Cannot print to terminal (session may be closed).
            self.filter_highlight_color = gtk.gdk.color_parse("yellow")

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)

        self.window.set_icon(get_icon())
        window_size = gcfg.get(['window size'])
        self.window.set_default_size(window_size[0], window_size[1])
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
            self.legal_task_states = list(TASK_STATUSES_RESTRICTED)
        else:
            self.legal_task_states = list(TASK_STATUSES_ALL)

        filter_excl = gcfg.get(['task states to filter out'])
        filter_excl = list(set(filter_excl))

        for filter_state in filter_excl:
            if filter_state not in TASK_STATUSES_ALL:
                try:
                    print >> sys.stderr, (
                        "WARNING: bad gcylc.rc 'task states to filter out' "
                        "value (ignoring): %s" % filter_state)
                except IOError:
                    pass  # Cannot print to terminal (session may be closed).
                filter_excl.remove(filter_state)

        self.filter_states_excl = filter_excl

        self.filter_name_string = None
        self.create_info_bar()

        hbox = gtk.HBox()
        hbox.pack_start(self.info_bar, True)
        bigbox.pack_start(hbox, False)

        self.window.add(bigbox)
        self.window.set_title('')
        self.window.show_all()
        self.info_bar.prog_bar.hide()

        self.setup_views()
        if suite:
            self.reset(suite)

    def reset(self, suite, auth=None):
        self.cfg.reset(suite, auth)

        win_title = suite
        if (self.cfg.host is not None and self.cfg.port is not None and
                is_remote_host(self.cfg.host)):
            win_title += " - %s:%d" % (self.cfg.host, int(self.cfg.port))
        self.window.set_title(win_title)

        self.tool_bar_box.set_sensitive(True)
        for menu in self.suite_menus:
            menu.set_sensitive(True)

        if self.updater is not None:
            self.updater.stop()
        self.updater = Updater(self)
        self.updater.start()
        self.restart_views()

        self.updater.filter_states_excl = self.filter_states_excl
        self.updater.filter_name_string = self.filter_name_string
        self.updater.refilter()
        self.refresh_views()

    def setup_views(self):
        """Create two view containers."""
        self.view_containers = [gtk.HBox(), gtk.HBox()]
        self.current_view_toolitems = [[], []]
        self.current_views += [None, None]
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
        self.window_show_all()

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
        """This is the view menu callback for the primary view."""
        self.reset_connect()
        if not item.get_active():
            return False
        if self.current_views[0].name == item._viewname:
            return False
        self.switch_view(item._viewname)
        self._set_tool_bar_view0(item._viewname)
        return False

    def _set_tool_bar_view0(self, viewname):
        """Set the tool bar state for the primary view."""
        model = self.tool_bar_view0.get_model()
        c_iter = model.get_iter_first()
        while c_iter is not None:
            if model.get_value(c_iter, 1) == viewname:
                index = model.get_path(c_iter)[0]
                self.tool_bar_view0.set_active(index)
                break
            c_iter = model.iter_next(c_iter)

    def _cb_change_view0_tool(self, widget):
        """This is the tool bar callback for the primary view."""
        self.reset_connect()
        viewname = widget.get_model().get_value(widget.get_active_iter(), 1)
        if self.current_views[0].name == viewname:
            return False
        self.switch_view(viewname)
        self._set_menu_view0(viewname)
        return False

    def _set_menu_view0(self, viewname):
        """Set the view menu state for the primary view."""
        for view_item in self.view_menu_views0:
            if (view_item._viewname == viewname and
                    not view_item.get_active()):
                return view_item.set_active(True)

    def _cb_change_view1_menu(self, item):
        """This is the view menu callback for the secondary view."""
        self.reset_connect()
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
        """Set the tool bar state for the secondary view."""
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
        """This is the tool bar callback for the secondary view"""
        self.reset_connect()
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
        """Set the view menu state for the secondary view."""
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
        """This is the view menu callback to toggle side-by-side layout."""
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

        # Set user default values for this view
        self.set_view_defaults(viewname, view_num)

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
        self.window_show_all()

    def set_view_defaults(self, viewname, view_num):
        """Apply user settings defined in gcylc.rc on a new view.
        Run this method before handling menus or toolbars."""
        # Sort text view by column ('sort column')
        if gcfg.get(['sort column']) != 'none' and viewname == 'text':
            self.current_views[view_num].sort_by_column(
                gcfg.get(['sort column']),
                ascending=gcfg.get(['sort column ascending'])
            )
        # Transpose graph view ('transpose graph')
        elif gcfg.get(['transpose graph']) and viewname == 'graph':
            self.current_views[view_num].toggle_left_to_right_mode(None)
        # Transpose dot view ('transpose dot')
        elif gcfg.get(['transpose dot']) and viewname == 'dot':
            view = self.current_views[view_num]
            view.t.should_transpose_view = True

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

    def click_open(self, widget, new_window=False):
        """Callback for File -> Open Another Suite."""
        if new_window:
            title = "Open Another Suite In New Window"
        else:
            title = "Open Another Suite"
        app = dbchooser(
            title, self.window, self.cfg.cylc_tmpdir, self.cfg.comms_timeout)
        reg, auth = None, None
        while True:
            response = app.window.run()
            if response == gtk.RESPONSE_OK:
                if app.chosen:
                    reg, auth = app.chosen
                    break
                else:
                    warning_dialog("Choose a suite or cancel!",
                                   self.window).warn()
            if response == gtk.RESPONSE_CANCEL:
                break
        app.updater.quit = True
        app.window.destroy()
        if not reg:
            return
        if new_window:
            # This is essentially a double fork to ensure that the child
            # process can detach as a process group leader and not subjected to
            # SIGHUP from the current process.
            # See also "cylc.batch_sys_handlers.background".
            Popen(
                [
                    "nohup",
                    "bash",
                    "-c",
                    "exec cylc gui \"$0\" <'/dev/null' >'/dev/null' 2>&1",
                    reg,
                ],
                preexec_fn=os.setpgrp,
                stdin=open(os.devnull),
                stdout=open(os.devnull, "wb"),
                stderr=STDOUT)
        else:
            self.reset(reg, auth)

    def pause_suite(self, bt):
        """Tell suite to hold (go into "held" status)."""
        self.put_comms_command('hold_suite')

    def resume_suite(self, bt):
        """Tell suite to release "held" status."""
        self.put_comms_command('release_suite')
        self.reset_connect()

    def stopsuite_default(self, *args):
        """Try to stop the suite (after currently running tasks...)."""
        if not self.get_confirmation("Stop suite %s?" % self.cfg.suite):
            return
        self.put_comms_command('set_stop_cleanly')

    def stopsuite(self, bt, window, kill_rb, stop_rb, stopat_rb, stopct_rb,
                  stoptt_rb, stopnow_rb, stopnownow_rb, stoppoint_entry,
                  stopclock_entry, stoptask_entry):
        stop = False
        stopat = False
        stopnow = False
        stopclock = False
        stoptask = False
        stopkill = False
        stopnownow = False

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
        elif stopnownow_rb.get_active():
            stopnownow = True
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
                parser.parse(stopclock_time)
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
        if stop:
            self.put_comms_command('set_stop_cleanly',
                                   kill_active_tasks=False)
        elif stopkill:
            self.put_comms_command('set_stop_cleanly',
                                   kill_active_tasks=True)
        elif stopat:
            self.put_comms_command('set_stop_after_point',
                                   point_string=stop_point_string)
        elif stopnow:
            self.put_comms_command('stop_now')
        elif stopnownow:
            self.put_comms_command('stop_now', terminate=True)
        elif stopclock:
            self.put_comms_command('set_stop_after_clock_time',
                                   datetime_string=stopclock_time)
        elif stoptask:
            self.put_comms_command('set_stop_after_task',
                                   task_id=stoptask_id)

    def load_point_strings(self, bt, startentry, stopentry):
        item1 = " -i '[scheduling]initial cycle point'"
        item2 = " -i '[scheduling]final cycle point'"
        command = (
            "cylc get-suite-config --mark-up" + self.get_remote_run_opts() +
            " " + self.cfg.template_vars_opts + " --one-line" + item1 +
            item2 + " " + self.cfg.suite)
        res = run_get_stdout(command, filter_=True)  # (T/F, ['ct ct'])

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
                   checkpoint_entry, optgroups, mode_live_rb, mode_sim_rb,
                   mode_dum_rb, mode_dum_loc_rb, hold_cb, holdpoint_entry):
        """Call back for "Run Suite" dialog box.

        Build "cylc run/restart" command from dialog box options and entries,
        and run the command.
        Destroy the dialog box.
        Reset connection.
        """

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
        elif mode_dum_loc_rb.get_active():
            command += ' --mode=dummy-local'

        if method == 'restart' and checkpoint_entry.get_text():
            command += ' --checkpoint=' + checkpoint_entry.get_text()

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

        options += self.get_remote_run_opts()

        command += ' ' + options + ' ' + self.cfg.suite + ' ' + point_string
        try:
            print command
        except IOError:
            pass  # Cannot print to terminal (session may be closed).

        try:
            Popen([command], shell=True, stdin=open(os.devnull))
        except OSError:
            warning_dialog('Error: failed to start ' + self.cfg.suite,
                           self.window).warn()
        self.reset_connect()

    def about(self, bt):
        about = gtk.AboutDialog()
        if gtk.gtk_version[0] == 2:
            if gtk.gtk_version[1] >= 12:
                # set_program_name() was added in PyGTK 2.12
                about.set_program_name("cylc")
        about.set_version(CYLC_VERSION)
        about.set_copyright("Copyright (C) 2008-2018 NIWA")
        about.set_comments(
            "The Cylc Suite Engine.\n\nclient UUID:\n%s" % self.cfg.my_uuid)
        about.set_logo(get_logo())
        about.set_transient_for(self.window)
        about.run()
        about.destroy()

    def _gcapture_cmd(self, command, xdim=400, ydim=400, title=None):
        """Run given command and capture its stdout and stderr in a window."""
        gcap_win = gcapture_tmpfile(command, self.cfg.cylc_tmpdir,
                                    xdim, ydim, title=title)
        self.gcapture_windows.append(gcap_win)
        gcap_win.run()

    def view_task_descr(self, w, e, task_id, *args):
        """Run 'cylc show SUITE TASK' and capture output in a viewer window."""
        self._gcapture_cmd(
            "cylc show %s %s %s" % (
                self.get_remote_run_opts(), self.cfg.suite, task_id),
            600, 400)

    def view_jobscript_preview(self, task_id, geditor=False):
        """View generated jobscript in a text editor."""
        self._gcapture_cmd(
            "cylc jobscript %s %s %s %s" % (
                self.get_remote_run_opts(), self.cfg.suite, task_id,
                '-g' if geditor else '--plain'),
            600, 400)

    def view_in_editor(self, w, e, task_id, choice):
        """View various job logs in your configured text editor."""
        if choice == 'job-preview':
            self.view_jobscript_preview(task_id, geditor=True)
            return False
        try:
            task_state_summary = self.updater.full_state_summary[task_id]
        except KeyError:
            warning_dialog('%s is not live' % task_id, self.window).warn()
            return False
        if (not task_state_summary['logfiles'] and
                not task_state_summary.get('job_hosts')):
            warning_dialog('%s has no log files' % task_id, self.window).warn()
        else:
            if choice == 'job-activity.log':
                command_opt = "--activity"
            elif choice == 'job.status':
                command_opt = "--status"
            elif choice == 'job.xtrace':
                command_opt = "--xtrace"
            elif choice == 'job.out':
                command_opt = "--stdout"
            elif choice == 'job-edit.diff':
                command_opt = "--diff"
            elif choice == 'job.err':
                command_opt = "--stderr"
            elif choice == 'job':
                command_opt = ""
            else:
                # Custom job log (see "extra log files").
                command_opt = '--filename %s' % choice
            self._gcapture_cmd("cylc cat-log %s --geditor %s %s" % (
                command_opt, self.cfg.suite, task_id))

    def view_task_info(self, w, e, task_id, choice):
        """Viewer window with a drop-down list of job logs to choose from."""
        if choice == 'job-preview':
            self.view_jobscript_preview(task_id, geditor=False)
            return
        try:
            task_state_summary = self.updater.full_state_summary[task_id]
        except KeyError:
            warning_dialog(task_id + ' is not live', self.window).warn()
            return False
        if (not task_state_summary['logfiles'] and
                not task_state_summary.get('job_hosts')):
            warning_dialog('%s has no log files' % task_id,
                           self.window).warn()
        else:
            self._popup_logview(task_id, task_state_summary, choice)
        return False

    @staticmethod
    def connect_right_click_sub_menu(is_graph_view, item, x, y, z):
        """Handle right-clicks in sub-menus."""
        if is_graph_view:
            item.connect('button-release-event', x, y, z)
        else:
            item.connect('activate', x, None, y, z)

    def get_right_click_menu(self, task_ids, t_states, task_is_family=False,
                             is_graph_view=False):
        """Return the default menu for a list of tasks."""

        # NOTE: we have to respond to 'button-release-event' rather than
        # 'activate' in order for sub-menus to work in the graph-view.
        # connect_right_click_sub_menu should be used in preference to
        # item.connect to handle this

        if isinstance(task_is_family, bool):
            task_is_family = [task_is_family] * len(task_ids)
        if any(not isinstance(item, list)
               for item in (task_ids, t_states, task_is_family)):
            return False

        # Consistency check.
        if not (len(task_ids) == len(t_states) and
                len(t_states) == len(task_is_family)):
            return False

        # Menu root.
        menu = gtk.Menu()
        menu_root = gtk.MenuItem(task_ids[0])
        menu_root.set_submenu(menu)

        # Title.
        if len(task_ids) > 1:
            title_item = gtk.MenuItem('Multiple Tasks')
            title_item.set_sensitive(False)
            menu.append(title_item)
        else:
            title_item = gtk.MenuItem('Task: ' + task_ids[0].replace(
                "_", "__"))
            title_item.set_sensitive(False)
            menu.append(title_item)

        if len(task_ids) == 1:
            # Browse task URL.
            url_item = gtk.MenuItem('_Browse task URL')
            url_item.connect('activate', self.browse_suite, task_ids[0])
            menu.append(url_item)

            if not task_is_family[0]:
                # Separator.
                menu.append(gtk.SeparatorMenuItem())

                # View.
                view_menu = gtk.Menu()
                view_item = gtk.ImageMenuItem("View")
                img = gtk.image_new_from_stock(gtk.STOCK_DIALOG_INFO,
                                               gtk.ICON_SIZE_MENU)
                view_item.set_image(img)
                view_item.set_submenu(view_menu)
                menu.append(view_item)

                # NOTE: we have to respond to 'button-release-event' rather
                # than 'activate' in order for sub-menus to work in the
                # graph-view so use connect_right_click_sub_menu instead of
                # item.connect

                if t_states[0] in TASK_STATUSES_WITH_JOB_SCRIPT:
                    job_script = ('job script', 'job')
                else:
                    job_script = ('preview job script', 'job-preview')

                for key, filename in [
                        job_script,
                        ('job activity log', 'job-activity.log'),
                        ('job status file', 'job.status'),
                        ('job edit diff', 'job-edit.diff'),
                        ('job debug xtrace', 'job.xtrace')]:
                    item = gtk.ImageMenuItem(key)
                    item.set_image(gtk.image_new_from_stock(
                        gtk.STOCK_DND, gtk.ICON_SIZE_MENU))
                    view_menu.append(item)
                    self.connect_right_click_sub_menu(is_graph_view, item,
                                                      self.view_task_info,
                                                      task_ids[0], filename)
                    item.set_sensitive(
                        '-preview' in filename or
                        t_states[0] in TASK_STATUSES_WITH_JOB_SCRIPT)

                try:
                    logfiles = sorted(map(str, self.updater.full_state_summary[
                        task_ids[0]]['logfiles']))
                except KeyError:
                    logfiles = []
                for key, filename in [
                        ('job stdout', 'job.out'),
                        ('job stderr', 'job.err')] + [
                        (fname, fname) for fname in logfiles]:
                    item = gtk.ImageMenuItem(key)
                    item.set_image(gtk.image_new_from_stock(
                        gtk.STOCK_DND, gtk.ICON_SIZE_MENU))
                    view_menu.append(item)
                    self.connect_right_click_sub_menu(is_graph_view, item,
                                                      self.view_task_info,
                                                      task_ids[0], filename)
                    item.set_sensitive(
                        t_states[0] in TASK_STATUSES_WITH_JOB_LOGS)

                info_item = gtk.ImageMenuItem('prereq\'s & outputs')
                img = gtk.image_new_from_stock(
                    gtk.STOCK_DIALOG_INFO, gtk.ICON_SIZE_MENU)
                info_item.set_image(img)
                view_menu.append(info_item)
                self.connect_right_click_sub_menu(is_graph_view, info_item,
                                                  self.popup_requisites,
                                                  task_ids[0], None)

                js0_item = gtk.ImageMenuItem('run "cylc show"')
                img = gtk.image_new_from_stock(
                    gtk.STOCK_DIALOG_INFO, gtk.ICON_SIZE_MENU)
                js0_item.set_image(img)
                view_menu.append(js0_item)
                self.connect_right_click_sub_menu(is_graph_view, js0_item,
                                                  self.view_task_descr,
                                                  task_ids[0], None)

                # PDF user guide.
                # This method of setting a custom menu item is not supported
                # pre-PyGTK 2.16 (~Python 2.65?) due to MenuItem.set_label():
                # cug_pdf_item = gtk.ImageMenuItem(stock_id=gtk.STOCK_EDIT)
                # cug_pdf_item.set_label('_PDF User Guide')
                # help_menu.append(cug_pdf_item)
                # cug_pdf_item.connect('activate', self.browse, '--pdf')

                # View In Editor.
                view_editor_menu = gtk.Menu()
                view_editor_item = gtk.ImageMenuItem("View In Editor")
                img = gtk.image_new_from_stock(gtk.STOCK_DIALOG_INFO,
                                               gtk.ICON_SIZE_MENU)
                view_editor_item.set_image(img)
                view_editor_item.set_submenu(view_editor_menu)
                menu.append(view_editor_item)

                # NOTE: we have to respond to 'button-release-event' rather
                # than 'activate' in order for sub-menus to work in the
                # graph-view so use connect_right_click_sub_menu instead of
                # item.connect

                for key, filename in [
                        job_script,
                        ('job activity log', 'job-activity.log'),
                        ('job status file', 'job.status'),
                        ('job edit diff', 'job-edit.diff'),
                        ('job debug xtrace', 'job.xtrace')]:
                    item = gtk.ImageMenuItem(key)
                    item.set_image(gtk.image_new_from_stock(
                        gtk.STOCK_DND, gtk.ICON_SIZE_MENU))
                    view_editor_menu.append(item)
                    self.connect_right_click_sub_menu(is_graph_view, item,
                                                      self.view_in_editor,
                                                      task_ids[0], filename)
                    item.set_sensitive(
                        '-preview' in filename or
                        t_states[0] in TASK_STATUSES_WITH_JOB_SCRIPT)

                for key, filename in [
                        ('job stdout', 'job.out'),
                        ('job stderr', 'job.err')] + [
                        (fname, fname) for fname in logfiles]:
                    item = gtk.ImageMenuItem(key)
                    item.set_image(gtk.image_new_from_stock(
                        gtk.STOCK_DND, gtk.ICON_SIZE_MENU))
                    view_editor_menu.append(item)
                    self.connect_right_click_sub_menu(is_graph_view, item,
                                                      self.view_in_editor,
                                                      task_ids[0], filename)
                    item.set_sensitive(
                        t_states[0] in TASK_STATUSES_WITH_JOB_LOGS)

        # Separator
        menu.append(gtk.SeparatorMenuItem())

        # Trigger (run now).
        trigger_now_item = gtk.ImageMenuItem('Trigger (run now)')
        img = gtk.image_new_from_stock(
            gtk.STOCK_MEDIA_PLAY, gtk.ICON_SIZE_MENU)
        trigger_now_item.set_image(img)
        menu.append(trigger_now_item)
        trigger_now_item.connect(
            'activate', self.trigger_task_now, task_ids)
        trigger_now_item.set_sensitive(
            all(t_state in TASK_STATUSES_TRIGGERABLE for t_state in t_states)
        )

        if len(task_ids) == 1 and not task_is_family[0]:
            # Trigger (edit run).
            trigger_edit_item = gtk.ImageMenuItem('Trigger (edit run)')
            img = gtk.image_new_from_stock(
                gtk.STOCK_MEDIA_PLAY, gtk.ICON_SIZE_MENU)
            trigger_edit_item.set_image(img)
            menu.append(trigger_edit_item)
            trigger_edit_item.connect(
                'activate', self.trigger_task_edit_run, task_ids[0])
            trigger_edit_item.set_sensitive(
                t_states[0] in TASK_STATUSES_TRIGGERABLE)

        # Separator.
        menu.append(gtk.SeparatorMenuItem())

        # Poll.
        # TODO - grey out poll and kill if the task is not active.
        poll_item = gtk.ImageMenuItem('Poll')
        img = gtk.image_new_from_stock(gtk.STOCK_REFRESH, gtk.ICON_SIZE_MENU)
        poll_item.set_image(img)
        menu.append(poll_item)
        poll_item.connect('activate', self.poll_task, task_ids)
        poll_item.set_sensitive(
            all(t_state in TASK_STATUSES_ACTIVE for t_state in t_states)
        )

        menu.append(gtk.SeparatorMenuItem())

        # Kill.
        kill_item = gtk.ImageMenuItem('Kill')
        img = gtk.image_new_from_stock(gtk.STOCK_CANCEL, gtk.ICON_SIZE_MENU)
        kill_item.set_image(img)
        menu.append(kill_item)
        kill_item.connect('activate', self.kill_task, task_ids)
        kill_item.set_sensitive(
            all(t_state in TASK_STATUSES_ACTIVE for t_state in t_states)
        )

        # Separator.
        menu.append(gtk.SeparatorMenuItem())

        # Reset state.
        reset_menu = gtk.Menu()
        reset_item = gtk.ImageMenuItem("Reset State")
        reset_img = gtk.image_new_from_stock(
            gtk.STOCK_CONVERT, gtk.ICON_SIZE_MENU)
        reset_item.set_image(reset_img)
        reset_item.set_submenu(reset_menu)
        menu.append(reset_item)

        # NOTE: we have to respond to 'button-release-event' rather
        # than 'activate' in order for sub-menus to work in the
        # graph-view so use connect_right_click_sub_menu instead of
        # item.connect

        for status in TASK_STATUSES_CAN_RESET_TO:
            reset_item = gtk.ImageMenuItem('"%s"' % status)
            reset_img = gtk.image_new_from_stock(
                gtk.STOCK_CONVERT, gtk.ICON_SIZE_MENU)
            reset_item.set_image(reset_img)
            reset_menu.append(reset_item)
            self.connect_right_click_sub_menu(is_graph_view, reset_item,
                                              self.reset_task_state, task_ids,
                                              status)

        spawn_item = gtk.ImageMenuItem('Force spawn')
        img = gtk.image_new_from_stock(gtk.STOCK_ADD, gtk.ICON_SIZE_MENU)
        spawn_item.set_image(img)
        menu.append(spawn_item)
        spawn_item.connect('activate', self.spawn_task, task_ids)

        # Separator.
        menu.append(gtk.SeparatorMenuItem())

        # Hold.
        stoptask_item = gtk.ImageMenuItem('Hold')
        img = gtk.image_new_from_stock(gtk.STOCK_MEDIA_PAUSE,
                                       gtk.ICON_SIZE_MENU)
        stoptask_item.set_image(img)
        menu.append(stoptask_item)
        stoptask_item.connect('activate', self.hold_task, task_ids, True)

        # Release.
        unstoptask_item = gtk.ImageMenuItem('Release')
        img = gtk.image_new_from_stock(gtk.STOCK_MEDIA_PLAY,
                                       gtk.ICON_SIZE_MENU)
        unstoptask_item.set_image(img)
        menu.append(unstoptask_item)
        unstoptask_item.connect('activate', self.hold_task, task_ids, False)

        # Separator.
        menu.append(gtk.SeparatorMenuItem())

        # Remove after spawning.
        remove_item = gtk.ImageMenuItem('Remove after spawning')
        img = gtk.image_new_from_stock(gtk.STOCK_CLEAR, gtk.ICON_SIZE_MENU)

        remove_item.set_image(img)
        menu.append(remove_item)
        remove_item.connect('activate', self.remove_tasks, task_ids, True)

        # Remove without spawning.
        remove_nospawn_item = gtk.ImageMenuItem('Remove without spawning')
        img = gtk.image_new_from_stock(gtk.STOCK_CLEAR, gtk.ICON_SIZE_MENU)

        remove_nospawn_item.set_image(img)
        menu.append(remove_nospawn_item)
        remove_nospawn_item.connect(
            'activate', self.remove_tasks, task_ids, False)

        menu.show_all()
        return menu

    def window_show_all(self):
        """Show all window widgets."""
        self.window.show_all()
        if not self.info_bar.prog_bar_active():
            self.info_bar.prog_bar.hide()

    @staticmethod
    def update_tb(tb, line, tags=None):
        """Update a text view buffer."""
        if tags:
            tb.insert_with_tags(tb.get_end_iter(), line, *tags)
        else:
            tb.insert(tb.get_end_iter(), line)

    def popup_requisites(self, w, e, task_id, *args):
        """Show prerequisites of task_id in a pop up window."""
        name = TaskID.split(task_id)[0]
        try:
            results, bad_items = self.updater.client.get_info(
                'get_task_requisites', items=[task_id])
        except ClientError as exc:
            warning_dialog(str(exc), self.window).warn()
        if not results or task_id in bad_items:
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
        self.update_tb(tb, self.cfg.suite + '\n', [bold, blue])

        for name, done in [
                ("prerequisites", "satisfied"), ("outputs", "completed")]:
            self.update_tb(tb, '\n' + name.title(), [bold])
            self.update_tb(tb, ' (')
            self.update_tb(tb, 'red', [red])
            self.update_tb(tb, '=> NOT %s)\n' % done)
            if not results[task_id][name]:
                self.update_tb(tb, ' - (None)\n')
            for msg, state in results[task_id][name]:
                if state:
                    tags = None
                else:
                    tags = [red]
                self.update_tb(tb, ' - ' + msg + '\n', tags)

        if results[task_id]['extras']:
            self.update_tb(tb, '\nOther\n', [bold])
            for key, value in results[task_id]['extras'].items():
                self.update_tb(tb, ' - %s: %s\n' % (key, value))

        self.update_tb(tb, '\nNOTE: ', [bold])
        self.update_tb(
            tb, ''' for tasks that have triggered already, prerequisites are
shown here in the state they were in at the time of triggering.''')
        window.show_all()

    def on_popup_quit(self, b, lv, w):
        """Destroy a popup window on quit."""
        lv.quit()
        self.quitters.remove(lv)
        w.destroy()

    def get_confirmation(self, question, force_prompt=False):
        """Pop up a confirmation prompt window."""
        if self.cfg.no_prompt and not force_prompt:
            return True
        prompt = gtk.MessageDialog(self.window, gtk.DIALOG_MODAL,
                                   gtk.MESSAGE_QUESTION,
                                   gtk.BUTTONS_YES_NO, question)
        response = prompt.run()
        prompt.destroy()
        return response == gtk.RESPONSE_YES

    def hold_task(self, b, task_ids, stop=True):
        """Hold or release a task."""
        if not isinstance(task_ids, list):
            task_ids = [task_ids]

        if stop:
            for task_id in task_ids:
                if not self.get_confirmation("Hold %s?" % (task_id)):
                    return
            self.put_comms_command('hold_tasks', items=task_ids)
        else:
            for task_id in task_ids:
                if not self.get_confirmation("Release %s?" % (task_id)):
                    return
            self.put_comms_command('release_tasks', items=task_ids)

    def trigger_task_now(self, b, task_ids):
        """Trigger task via the suite server program's command interface."""
        if not isinstance(task_ids, list):
            task_ids = [task_ids]

        for task_id in task_ids:
            if not self.get_confirmation("Trigger %s?" % task_id):
                return
        self.put_comms_command('trigger_tasks', items=task_ids)

    def trigger_task_edit_run(self, b, task_id):
        """Trigger an edit run with 'cylc trigger --edit'."""
        if not self.get_confirmation("Edit run %s?" % task_id):
            return
        self._gcapture_cmd(
            "cylc trigger --use-ssh --edit --geditor -f %s %s %s" % (
                self.get_remote_run_opts(), self.cfg.suite, task_id))

    def poll_task(self, b, task_ids):
        """Poll a task/family."""
        if not isinstance(task_ids, list):
            task_ids = [task_ids]

        for task_id in task_ids:
            if not self.get_confirmation("Poll %s?" % task_id):
                return
        self.put_comms_command('poll_tasks', items=task_ids)

    def kill_task(self, b, task_ids):
        """Kill a task/family."""
        if not isinstance(task_ids, list):
            task_ids = [task_ids]

        for task_id in task_ids:
            if not self.get_confirmation("Kill %s?" % task_id,
                                         force_prompt=True):
                return
        self.put_comms_command('kill_tasks', items=task_ids)

    def spawn_task(self, b, task_ids):
        """For tasks to spawn their successors."""
        if not isinstance(task_ids, list):
            task_ids = [task_ids]

        for task_id in task_ids:
            if not self.get_confirmation("Force spawn %s?" % task_id):
                return
        self.put_comms_command('spawn_tasks', items=task_ids)

    def reset_task_state(self, b, e, task_ids, state):
        """Reset the state of a task/family."""
        if not isinstance(task_ids, list):
            task_ids = [task_ids]

        for task_id in task_ids:
            if not self.get_confirmation("reset %s to %s?" % (task_id, state)):
                return
        self.put_comms_command('reset_task_states', items=task_ids,
                               state=state)

    def remove_tasks(self, b, task_ids, spawn):
        """Send command to suite to remove tasks matching task_ids."""
        if not isinstance(task_ids, list):
            task_ids = [task_ids]
        if spawn:
            message = "Remove %s after spawning?"
        else:
            message = "Remove %s without spawning?"
        if not self.get_confirmation(message % task_ids):
            return
        self.put_comms_command('remove_tasks', items=task_ids, spawn=spawn)

    def stopsuite_popup(self, b):
        """Suite shutdown dialog window popup."""
        window = gtk.Window()
        window.modify_bg(gtk.STATE_NORMAL,
                         gtk.gdk.color_parse(self.log_colors.get_color()))
        window.set_border_width(5)
        window.set_title("Stop Suite Server Program %s" % self.cfg.suite)
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
        stopnownow_rb = gtk.RadioButton(
            stop_rb,
            "Terminate _now (restart will follow up on orphaned tasks)")
        label = gtk.Label("   cylc stop --now --now %s" % self.cfg.suite)
        label.modify_font(pango.FontDescription("monospace"))
        label.set_alignment(0, 0)
        vbox.pack_start(stopnownow_rb, True)
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
        stopnownow_rb.connect(
            "toggled", self.stop_method, "stopnownow", st_box, sc_box, tt_box)
        stopct_rb.connect(
            "toggled", self.stop_method, "stopclock", st_box, sc_box, tt_box)
        stoptt_rb.connect(
            "toggled", self.stop_method, "stoptask", st_box, sc_box, tt_box)
        cancel_button = gtk.Button("_Cancel")
        cancel_button.connect("clicked", lambda x: window.destroy())

        stop_button = gtk.Button(" _OK ")
        stop_button.connect("clicked", self.stopsuite, window, kill_rb,
                            stop_rb, stopat_rb, stopct_rb, stoptt_rb,
                            stopnow_rb, stopnownow_rb, stop_point_string_entry,
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

    @staticmethod
    def stop_method(b, meth, st_box, sc_box, tt_box):
        """Determine the suite stop method."""
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

    @staticmethod
    def hold_cb_toggled(b, box):
        if b.get_active():
            box.set_sensitive(False)
        else:
            box.set_sensitive(True)

    @staticmethod
    def startup_method(b, meth, ic_box, is_box):
        """Determine the suite start-up method."""
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
        """Suite start-up dialog window popup."""
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
        if self.updater is not None and self.updater.stop_summary is not None:
            # Restart is more likely for a suite that has run before?
            restart_rb.set_active(True)
        else:
            coldstart_rb.set_active(True)
        vbox.pack_start(box)

        box = gtk.HBox()
        box.pack_start(gtk.Label('Mode'), True)
        mode_live_rb = gtk.RadioButton(None, "live")
        box.pack_start(mode_live_rb, True)
        mode_dum_rb = gtk.RadioButton(mode_live_rb, "dummy")
        box.pack_start(mode_dum_rb, True)
        mode_dum_loc_rb = gtk.RadioButton(mode_live_rb, "dummy-local")
        box.pack_start(mode_dum_loc_rb, True)
        mode_sim_rb = gtk.RadioButton(mode_live_rb, "simulation")
        box.pack_start(mode_sim_rb, True)

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
        label = gtk.Label('Restart checkpoint')
        is_box.pack_start(label, True)
        checkpoint_entry = gtk.Entry()
        if self.updater is not None and self.updater.stop_summary is not None:
            checkpoint_entry.set_sensitive(True)
            label.set_sensitive(True)
        else:
            checkpoint_entry.set_sensitive(False)
            label.set_sensitive(False)
        is_box.pack_start(checkpoint_entry, True)
        vbox.pack_start(is_box)

        coldstart_rb.connect(
            "toggled", self.startup_method, "cold", ic_box, is_box)
        warmstart_rb.connect(
            "toggled", self.startup_method, "warm", ic_box, is_box)
        restart_rb.connect(
            "toggled", self.startup_method, "re", ic_box, is_box)

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

        noautoshutdown_group = controlled_option_group(
            "No-auto-shutdown", "--no-auto-shutdown")
        noautoshutdown_group.pack(hbox)
        vbox.pack_start(hbox)

        optgroups = [nodetach_group, noautoshutdown_group, debug_group]

        cancel_button = gtk.Button("_Cancel")
        cancel_button.connect("clicked", lambda x: window.destroy())

        start_button = gtk.Button("_Start")
        start_button.connect("clicked", self.startsuite, window, coldstart_rb,
                             warmstart_rb, restart_rb, point_string_entry,
                             stop_point_string_entry, checkpoint_entry,
                             optgroups, mode_live_rb, mode_sim_rb,
                             mode_dum_rb, mode_dum_loc_rb, hold_cb,
                             holdpoint_entry)

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

    def point_string_entry_popup(self, b, callback, title):
        """Cycle point entry popup."""
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
        """Display "Insert Task(s)" pop up box."""
        window = gtk.Window()
        window.modify_bg(gtk.STATE_NORMAL,
                         gtk.gdk.color_parse(self.log_colors.get_color()))
        window.set_border_width(5)
        window.set_title("Insert Task(s)")
        window.set_transient_for(self.window)
        window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        vbox = gtk.VBox()

        label = gtk.Label('SUITE: ' + self.cfg.suite)
        vbox.pack_start(label, True)

        hbox = gtk.HBox()
        label = gtk.Label('TASK-NAME.CYCLE-POINT [...]')
        hbox.pack_start(label, True)
        entry_task_ids = gtk.Entry()
        hbox.pack_start(entry_task_ids, True)
        vbox.pack_start(hbox)

        if "name" in kwargs and "point_string" in kwargs:
            entry_task_ids.set_text(
                kwargs['name'] + '.' + kwargs['point_string'])

        hbox = gtk.HBox()
        label = gtk.Label('[--stop-point=POINT]')
        hbox.pack_start(label, True)
        entry_stop_point = gtk.Entry()
        entry_stop_point.set_max_length(20)
        hbox.pack_start(entry_stop_point, True)
        vbox.pack_start(hbox)

        no_check_cb = gtk.CheckButton(
            "Do not check if cycle point is valid or not")
        no_check_cb.set_active(False)
        vbox.pack_start(no_check_cb, True)

        help_button = gtk.Button("_Help")
        help_button.connect("clicked", self.command_help, "control", "insert")

        hbox = gtk.HBox()
        insert_button = gtk.Button("_Insert")
        insert_button.connect(
            "clicked", self.insert_task, window, entry_task_ids,
            entry_stop_point, no_check_cb)
        cancel_button = gtk.Button("_Cancel")
        cancel_button.connect("clicked", lambda x: window.destroy())
        hbox.pack_start(insert_button, False)
        hbox.pack_end(cancel_button, False)
        hbox.pack_end(help_button, False)
        vbox.pack_start(hbox)

        window.add(vbox)
        window.show_all()

    def insert_task(
            self, w, window, entry_task_ids, entry_stop_point, no_check_cb):
        """Insert a task, callback for "insert_task_popup"."""
        task_ids = shlex.split(entry_task_ids.get_text())
        if not task_ids:
            warning_dialog('Enter valid task/family IDs', self.window).warn()
            return
        for i, task_id in enumerate(task_ids):
            if not TaskID.is_valid_id_2(task_id):
                warning_dialog(
                    '"%s": invalid task ID (argument %d)' % (task_id, i + 1),
                    self.window).warn()
                return
        stop_point_str = entry_stop_point.get_text()
        window.destroy()
        if not stop_point_str.strip():
            stop_point_str = None
        self.put_comms_command(
            'insert_tasks', items=task_ids,
            stop_point_string=stop_point_str,
            no_check=no_check_cb.get_active())

    def poll_all(self, w):
        """Poll all active tasks."""
        if not self.get_confirmation("Poll all submitted/running task jobs?"):
            return
        self.put_comms_command('poll_tasks')

    def reload_suite(self, w):
        """Tell the suite server program to reload."""
        if not self.get_confirmation("Reload suite definition?"):
            return
        self.put_comms_command('reload_suite')

    def nudge_suite(self, w):
        """Nudge the suite server program."""
        if not self.get_confirmation("Nudge suite?"):
            return
        self.put_comms_command('nudge')

    def _popup_logview(self, task_id, task_state_summary, choice=None):
        """Display task job log files in a combo log viewer."""
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.modify_bg(gtk.STATE_NORMAL,
                         gtk.gdk.color_parse(self.log_colors.get_color()))
        window.set_border_width(5)
        window.set_size_request(800, 400)

        # Derive file names from the job host of each submit
        # task_state_summary['logfiles'] logic retained for backward compat
        job_hosts = task_state_summary.get('job_hosts')
        if job_hosts:
            filenames = []
            name, point_str = TaskID.split(task_id)
            itask_log_dir = os.path.join(
                glbl_cfg().get_derived_host_item(
                    self.cfg.suite, "suite job log directory",
                ),
                point_str,
                name,
            )
            for submit_num, job_user_at_host in sorted(
                    job_hosts.items(), reverse=True, key=lambda x: int(x[0])):
                submit_num_str = "%02d" % int(submit_num)
                local_job_log_dir = os.path.join(itask_log_dir, submit_num_str)
                for filename in ["job", "job-activity.log"]:
                    filenames.append(os.path.join(local_job_log_dir, filename))
                if job_user_at_host is None:
                    continue
                if '@' in job_user_at_host:
                    job_user, job_host = job_user_at_host.split('@', 1)
                else:
                    job_user, job_host = (None, job_user_at_host)
                if is_remote(job_host, job_user):
                    job_log_dir = job_user_at_host + ':' + os.path.join(
                        glbl_cfg().get_derived_host_item(
                            self.cfg.suite, 'suite job log directory',
                            job_host, job_user,
                        ),
                        point_str, name, submit_num_str,
                    )
                else:
                    job_log_dir = local_job_log_dir
                for filename in ["job.out", "job.err", "job.status",
                                 "job-edit.diff", "job.xtrace"]:
                    filenames.append(os.path.join(job_log_dir, filename))

        # NOTE: Filenames come through as unicode and must be converted.
        for filename in map(str, sorted(list(task_state_summary['logfiles']))):
            if filename not in filenames:
                filenames.append(os.path.join(job_log_dir, filename))

        init_active_index = None
        if choice:
            for i, log in enumerate(filenames):
                if log.endswith("/" + choice):
                    init_active_index = i
                    break

        auth = None
        if is_remote_host(self.cfg.host):
            auth = self.cfg.host
        elif is_remote_user(self.cfg.owner):
            auth = self.cfg.owner + "@" + self.cfg.host
        if auth:
            for i, log in enumerate(filenames):
                if ":" not in log:
                    filenames[i] = auth + ":" + log
        window.set_title(task_id + ": Log Files")
        viewer = ComboLogViewer(
            task_id, filenames,
            self._get_logview_cmd_tmpls_map(task_id, filenames),
            init_active_index)
        self.quitters.append(viewer)

        window.add(viewer.get_widget())

        quit_button = gtk.Button("_Close")
        quit_button.connect("clicked", self.on_popup_quit, viewer, window)

        viewer.hbox.pack_start(quit_button, False)

        window.connect("delete_event", viewer.quit_w_e)
        window.show_all()

    def _get_logview_cmd_tmpls_map(self, task_id, filenames):
        """Helper for self._popup_logview()."""
        summary = self.updater.full_state_summary[task_id]
        if summary["state"] != "running":
            return {}
        ret = {}
        for key in "out", "err":
            suffix = "/%(submit_num)02d/job.%(key)s" % {
                "submit_num": summary["submit_num"], "key": key}
            for filename in filenames:
                if not filename.endswith(suffix):
                    continue
                user_at_host = None
                if ":" in filename:
                    user_at_host = filename.split(":", 1)[0]
                if user_at_host and "@" in user_at_host:
                    owner, host = user_at_host.split("@", 1)
                else:
                    owner, host = (None, user_at_host)
                try:
                    conf = glbl_cfg().get_host_item(
                        "batch systems", host, owner)
                    cmd_tmpl = conf[summary["batch_sys_name"]][key + " tailer"]
                    ret[filename] = cmd_tmpl % {
                        "job_id": summary["submit_method_id"]}
                except (KeyError, TypeError):
                    continue
        return ret

    @staticmethod
    def _sort_key_func(log_path):
        """Sort key for a task job log path."""
        head, submit_num, base = log_path.rsplit("/", 2)
        try:
            submit_num = int(submit_num)
        except ValueError:
            pass
        return (submit_num, base, head)

    @staticmethod
    def _set_tooltip(widget, tip_text):
        """Set a tool-tip text."""
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip(widget, tip_text)

    def create_main_menu(self):
        """Create the main menu."""
        self.menu_bar = gtk.MenuBar()

        file_menu = gtk.Menu()

        file_menu_root = gtk.MenuItem('_File')
        file_menu_root.set_submenu(file_menu)

        open_item = gtk.ImageMenuItem('_Open Another Suite')
        img = gtk.image_new_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_MENU)
        open_item.set_image(img)
        open_item.connect('activate', self.click_open)
        file_menu.append(open_item)

        open_new_item = gtk.ImageMenuItem('Open Another Suite In _New Window')
        img = gtk.image_new_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_MENU)
        open_new_item.set_image(img)
        open_new_item.connect(
            'activate', self.click_open, True)  # new_window=True
        file_menu.append(open_new_item)

        reg_new_item = gtk.ImageMenuItem('_Register A New Suite')
        img = gtk.image_new_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_MENU)
        reg_new_item.set_image(img)
        reg_new_item.connect('activate', self.click_register)
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
        if self.view_layout_horizontal is True:
            self.view1_align_item.set_active(self.view_layout_horizontal)
        self._set_tooltip(
            self.view1_align_item, "Toggle horizontal layout of views.")
        self.view1_align_item.connect(
            'toggled', self._cb_change_view_align)
        self.view_menu.append(self.view1_align_item)

        self.view_menu.append(gtk.SeparatorMenuItem())

        self.reset_connect_menuitem = gtk.ImageMenuItem("_Connect Now")
        img = gtk.image_new_from_stock(gtk.STOCK_REFRESH, gtk.ICON_SIZE_MENU)
        self.reset_connect_menuitem.set_image(img)
        self._set_tooltip(
            self.reset_connect_menuitem,
            """Connect to suite immediately.

If gcylc cannot connect to the suite,
it retries after increasingly long delays,
to reduce network traffic.""")
        self.view_menu.append(self.reset_connect_menuitem)
        self.reset_connect_menuitem.connect('activate', self.reset_connect)

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
        img = dots.get_image(TASK_STATUS_RUNNING)
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

        self.view_menu.append(gtk.SeparatorMenuItem())
        uuid_item = gtk.ImageMenuItem("Client _UUID")
        img = gtk.image_new_from_stock(gtk.STOCK_INDEX,
                                       gtk.ICON_SIZE_MENU)
        uuid_item.set_image(img)
        self._set_tooltip(
            uuid_item, "View the client UUID for this gcylc instance")
        self.view_menu.append(uuid_item)
        uuid_item.connect('activate', self.popup_uuid_dialog)
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

        url_item = gtk.ImageMenuItem('_Browse Suite URL')
        img = gtk.image_new_from_stock(gtk.STOCK_DND, gtk.ICON_SIZE_MENU)
        url_item.set_image(img)
        url_item.connect('activate', self.browse_suite)
        tools_menu.append(url_item)

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
        cug_html_item.connect('activate', self.browse_doc)

        cug_pdf_item = gtk.ImageMenuItem('(file://) PDF User Guide')
        img = gtk.image_new_from_stock(gtk.STOCK_EDIT, gtk.ICON_SIZE_MENU)
        cug_pdf_item.set_image(img)
        doc_menu.append(cug_pdf_item)
        cug_pdf_item.connect('activate', self.browse_doc, '-p')

        doc_menu.append(gtk.SeparatorMenuItem())

        if glbl_cfg().get(['documentation', 'urls', 'local index']):
            cug_www_item = gtk.ImageMenuItem('(http://) Local Document Index')
            img = gtk.image_new_from_stock(gtk.STOCK_JUMP_TO,
                                           gtk.ICON_SIZE_MENU)
            cug_www_item.set_image(img)
            doc_menu.append(cug_www_item)
            cug_www_item.connect('activate', self.browse_doc, '-x')

        cug_www_item = gtk.ImageMenuItem('(http://) _Internet Home Page')
        img = gtk.image_new_from_stock(gtk.STOCK_JUMP_TO, gtk.ICON_SIZE_MENU)
        cug_www_item.set_image(img)
        doc_menu.append(cug_www_item)
        cug_www_item.connect('activate', self.browse_doc, '-w')

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
        """Show suite title and description."""
        try:
            # Interrogate the suite server program
            info = self.updater.client.get_info('get_suite_info')
            descr = '\n'.join(
                "%s: %s" % (key, val) for key, val in info.items())
            info_dialog(descr, self.window).inform()
        except ClientError:
            # Parse the suite definition.
            self._gcapture_cmd(
                "cylc get-suite-config -i title -i description %s %s" % (
                    self.get_remote_run_opts(), self.cfg.suite), 800, 400)

    def search_suite_popup(self, w):
        """Pop up a suite source dir search dialog."""
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
        """Run 'cylc search', capture output in a viewer window."""
        pattern = pattern_entry.get_text()
        options = ''
        if not yesbin_cb.get_active():
            options += ' -x '
        self._gcapture_cmd("cylc search %s %s %s" % (
            options, reg, pattern), 600, 500)

    def click_register(self, w):
        """Callback for File -> Register A New Suite."""
        dialog = gtk.FileChooserDialog(
            title='Register Or Create A Suite',
            action=gtk.FILE_CHOOSER_ACTION_SAVE,
            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                     gtk.STOCK_OPEN, gtk.RESPONSE_OK)
        )
        filter_ = gtk.FileFilter()
        filter_.set_name("Cylc Suite Definition Files")
        filter_.add_pattern(SuiteSrvFilesManager.FILE_BASE_SUITE_RC)
        dialog.add_filter(filter_)

        response = dialog.run()
        if response != gtk.RESPONSE_OK:
            dialog.destroy()
            return False

        res = dialog.get_filename()

        dialog.destroy()

        directory = os.path.dirname(res)
        fil = os.path.basename(res)

        if fil != SuiteSrvFilesManager.FILE_BASE_SUITE_RC:
            warning_dialog(
                "Suite definitions filenames must be \"%s\" : %s" % (
                    SuiteSrvFilesManager.FILE_BASE_SUITE_RC, fil
                ),
                self.window
            ).warn()
            fil = SuiteSrvFilesManager.FILE_BASE_SUITE_RC

        # handle home directories under gpfs filesets, e.g.: if my home
        # directory is /home/oliver:
        home = os.environ['HOME']
        # but is really located on a gpfs fileset such as this:
        # /gpfs/filesets/hpcf/home/oliver; the pygtk file chooser will
        # return the "real" path that really should be hidden:
        home_real = os.path.realpath(home)
        # so let's restore it to the familiar form (/home/oliver):
        directory = re.sub('^' + home_real, home, directory)

        suiterc = os.path.join(directory, fil)

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
                             message_format="Suite name for " + directory)

        suite = window.run()
        window.destroy()
        if suite:
            command = "cylc register " + suite + ' ' + directory
            res = run_get_stdout(command)[0]
            if res:
                self.reset(suite)

    def reset_connect(self, _=None):
        """Force a suite API call as soon as possible."""
        self.updater.update_interval = 1.0

    def construct_command_menu(self, menu):
        """Constructs the top bar help menu in gcylc that lists all
        of the commands by categories."""
        cat_menu = gtk.Menu()
        menu.set_submenu(cat_menu)

        cylc_help_item = gtk.MenuItem('cylc')
        cat_menu.append(cylc_help_item)
        cylc_help_item.connect('activate', self.command_help)

        cout = Popen(
            ["cylc", "categories"],
            stdin=open(os.devnull), stdout=PIPE).communicate()[0]
        categories = cout.rstrip().split()
        for category in categories:
            foo_item = gtk.MenuItem(category)
            cat_menu.append(foo_item)
            com_menu = gtk.Menu()
            foo_item.set_submenu(com_menu)
            cout = Popen(
                ["cylc-help", "category=" + category],
                stdin=open(os.devnull), stdout=PIPE).communicate()[0]
            commands = cout.rstrip().split()
            for command in commands:
                bar_item = gtk.MenuItem(command)
                com_menu.append(bar_item)
                bar_item.connect('activate', self.command_help, category,
                                 command + " --help")

    def check_task_filter_buttons(self, tb=None):
        """Action task state filter settings."""
        task_states = []
        for subbox in self.state_filter_box.get_children():
            for ebox in subbox.get_children():
                box = ebox.get_children()[0]
                try:
                    cb_ = box.get_children()[1]
                except (IndexError, AttributeError):
                    # IndexError: an empty box to line things up.
                    # AttributeError: the name filter entry box.
                    pass
                else:
                    if cb_.get_active():
                        ebox.modify_bg(gtk.STATE_NORMAL, None)
                    else:
                        # Remove '_' (keyboard mnemonics) from state name.
                        task_states.append(cb_.get_label().replace('_', ''))
                        ebox.modify_bg(gtk.STATE_NORMAL,
                                       self.filter_highlight_color)

        self.filter_states_excl = task_states
        self.info_bar.set_filter_state(task_states, self.filter_name_string)
        if self.updater is not None:
            # Else no suite is connected yet.
            self.updater.filter_states_excl = task_states
            self.updater.refilter()
            self.refresh_views()

    def select_state_filters(self, w, arg):
        """Process task state filter settings."""
        for subbox in self.state_filter_box.get_children():
            for ebox in subbox.get_children():
                box = ebox.get_children()[0]
                try:
                    chb = box.get_children()[1]
                except (IndexError, AttributeError):
                    # IndexError: an empty box to line things up.
                    # AttributeError: the name filter entry box.
                    pass
                else:
                    chb.set_active(arg)
        self.check_task_filter_buttons()

    def reset_filter_entry(self, w):
        """Reset task state filter settings."""
        self.filter_entry.set_text("")
        self.check_filter_entry()

    def check_filter_entry(self, e=None):
        """Check the task name filter entry."""
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
        """Refresh all live views."""
        for view in self.current_views:
            if view is not None:
                view.refresh()

    def create_task_filter_widgets(self):
        """Create task filter widgets - state and name."""
        self.filter_widgets = gtk.VBox()
        self.filter_widgets.pack_start(
            gtk.Label("Filter by task state"))
        sel_button = gtk.Button("_Select All")
        des_button = gtk.Button("Select _None")
        sel_button.connect("clicked", self.select_state_filters, True)
        des_button.connect("clicked", self.select_state_filters, False)
        hbox = gtk.HBox()
        hbox.pack_start(sel_button)
        hbox.pack_start(des_button)
        self.filter_widgets.pack_start(hbox)

        self.state_filter_box = gtk.VBox()
        PER_ROW = 3
        n_states = len(self.legal_task_states)
        n_rows = n_states / PER_ROW
        if n_states % PER_ROW:
            n_rows += 1
        dotm = DotMaker(self.theme, size=self.dot_size)
        for row in range(n_rows):
            subbox = gtk.HBox(homogeneous=True)
            self.state_filter_box.pack_start(subbox)
            for i in range(PER_ROW):
                ebox = gtk.EventBox()
                box = gtk.HBox()
                ebox.add(box)
                try:
                    st = self.legal_task_states[row * PER_ROW + i]
                except IndexError:
                    pass
                else:
                    icon = dotm.get_image(st)
                    cb = gtk.CheckButton(get_status_prop(st, 'gtk_label'))
                    cb.set_active(st not in self.filter_states_excl)
                    cb.connect('toggled', self.check_task_filter_buttons)
                    tooltip = gtk.Tooltips()
                    tooltip.enable()
                    tooltip.set_tip(cb, "Filter by task state = %s" % st)
                    box.pack_start(icon, expand=False)
                    box.pack_start(cb, expand=False)
                subbox.pack_start(ebox, fill=True)

        self.filter_widgets.pack_start(self.state_filter_box)
        self.filter_widgets.pack_start(gtk.Label("Filter by task name"))
        self.filter_entry = EntryTempText()
        self.filter_entry.set_width_chars(7)
        self.filter_entry.connect("activate", self.check_filter_entry)
        filter_entry_help_text = "Enter a substring or regular expression"
        self.filter_entry.set_temp_text(filter_entry_help_text)
        ebox = gtk.EventBox()
        ebox.add(self.filter_entry)

        hbox = gtk.HBox()
        hbox.pack_start(ebox)
        button = gtk.Button("_Reset")
        button.connect("clicked", self.reset_filter_entry)
        hbox.pack_start(button, expand=False)
        self.filter_widgets.pack_start(hbox)
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip(self.filter_entry, filter_entry_help_text)

    def create_tool_bar(self):
        """Create the tool bar for the control GUI."""
        initial_views = self.initial_views
        self.tool_bars = [gtk.Toolbar(), gtk.Toolbar()]
        views = self.VIEWS_ORDERED
        self.tool_bar_view0 = gtk.ComboBox()
        self.tool_bar_view1 = gtk.ComboBox()
        pixlist0 = gtk.ListStore(gtk.gdk.Pixbuf, str)
        pixlist1 = gtk.ListStore(gtk.gdk.Pixbuf, str, bool, bool)
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

        self.reset_connect_toolbutton = gtk.ToolButton(
            icon_widget=gtk.image_new_from_stock(
                gtk.STOCK_REFRESH, gtk.ICON_SIZE_SMALL_TOOLBAR))
        self.reset_connect_toolbutton.set_label("Connect Now")
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip(
            self.reset_connect_toolbutton,
            """Connect to suite immediately.

If gcylc cannot connect to the suite
it retries after increasingly long delays,
to reduce network traffic.""")
        self.reset_connect_toolbutton.connect("clicked", self.reset_connect)
        self.tool_bars[0].insert(self.reset_connect_toolbutton, 0)

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
        """Handle changes in suite status for some toolbar/menuitems."""
        if new_status == self._prev_status:
            return False
        self.info_bar.prog_bar_disabled = False
        self._prev_status = new_status
        run_ok = "stopped" in new_status
        # Pause: avoid "stopped with TASK_STATUS_RUNNING".
        pause_ok = (
            "running" in new_status and "stopped" not in new_status)
        unpause_ok = TASK_STATUS_HELD == new_status
        stop_ok = ("stopped" not in new_status and
                   "connected" != new_status and
                   "initialising" != new_status)
        self.run_menuitem.set_sensitive(run_ok)
        self.pause_menuitem.set_sensitive(pause_ok)
        self.unpause_menuitem.set_sensitive(unpause_ok)
        self.stop_menuitem.set_sensitive(stop_ok)
        self.stop_toolbutton.set_sensitive(stop_ok and
                                           "stopping" not in new_status)
        self.reset_connect_menuitem.set_sensitive(run_ok)
        self.reset_connect_toolbutton.set_sensitive(run_ok)
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
        self.run_pause_toolbutton.set_sensitive(True)
        tip_tuple = gtk.tooltips_data_get(self.run_pause_toolbutton)
        if tip_tuple is None:
            tips = gtk.Tooltips()
            tips.enable()
            tips.set_tip(self.run_pause_toolbutton, tip_text)
        self.run_pause_toolbutton.click_func = click_func

    def create_info_bar(self):
        """Create the window info bar."""
        self.info_bar = InfoBar(
            self.cfg.host, self.theme, self.dot_size,
            self.filter_states_excl,
            self.popup_filter_dialog,
            self._alter_status_toolbar_menu,
            lambda: self.run_suite_log(None, type_="err"))
        self._set_info_bar()

    def popup_uuid_dialog(self, w):
        """Pop up the client UUID info."""
        info_dialog(
            "Client UUID %s\n"
            "(this identifies the client to the suite server program)" % (
                self.cfg.my_uuid), self.window).inform()

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
                self.window, self.filter_widgets)
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

    def put_comms_command(self, command, **kwargs):
        """Put a command to the suite client interface."""
        try:
            success, msg = self.updater.client.put_command(
                command, **kwargs)
        except Exception, x:
            warning_dialog(x.__str__(), self.window).warn()
        else:
            if not success:
                warning_dialog(msg, self.window).warn()

    def run_suite_validate(self, w):
        """Validate the suite and capture output in a viewer window."""
        self._gcapture_cmd(
            "cylc validate -v %s %s %s" % (
                self.get_remote_run_opts(), self.cfg.template_vars_opts,
                self.cfg.suite), 700)
        return False

    def run_suite_edit(self, w, inlined=False):
        """Run 'cylc edit' and capture output in a viewer window."""
        extra = ''
        if inlined:
            extra = '-i '
        self._gcapture_cmd(
            "cylc edit -g %s %s %s %s" % (
                self.cfg.template_vars_opts, self.get_remote_run_opts(), extra,
                self.cfg.suite))
        return False

    def run_suite_graph(self, w, show_ns=False):
        """Run 'cylc graph' and capture output in a viewer window."""
        if show_ns:
            self._gcapture_cmd(
                "cylc graph -n %s %s %s" % (
                    self.cfg.template_vars_opts, self.get_remote_run_opts(),
                    self.cfg.suite))
        else:
            # TODO - a "load" button as for suite startup cycle points.
            graph_suite_popup(
                self.cfg.suite, self.command_help, None, None,
                self.get_remote_run_opts(), self.gcapture_windows,
                self.cfg.cylc_tmpdir, self.cfg.template_vars_opts,
                parent_window=self.window)

    def run_suite_info(self, w):
        """Run 'cylc show SUITE' and capture output in a viewer window."""
        self._gcapture_cmd(
            "cylc show %s %s" % (
                self.get_remote_run_opts(), self.cfg.suite), 600, 400)

    def run_suite_list(self, w, opt=''):
        """Run 'cylc list' and capture output in a viewer window."""
        self._gcapture_cmd(
            "cylc list %s %s %s %s" % (
                self.get_remote_run_opts(), opt, self.cfg.template_vars_opts,
                self.cfg.suite), 600, 600)

    def run_suite_log(self, w, type_='log'):
        """Run 'cylc cat-log' and capture its output in a viewer window."""
        if is_remote(self.cfg.host, self.cfg.owner):
            if type_ == 'out':
                xopts = ' --stdout '
            elif type_ == 'err':
                xopts = ' --stderr '
            else:
                xopts = ' '
            self._gcapture_cmd(
                "cylc cat-log %s %s %s" % (
                    self.get_remote_run_opts(), xopts, self.cfg.suite),
                800, 400, title="%s %s" % (self.cfg.suite, type_))
            return

        task_name_list = []  # TODO
        # assumes suite out, err, and log are in the same location:
        foo = cylc_logviewer(type_, self.cfg.logdir, task_name_list)
        self.quitters.append(foo)

    def run_suite_view(self, w, method):
        """Run 'cylc view' and capture its output in a viewer window."""
        extra = ''
        if method == 'inlined':
            extra = ' -i'
        elif method == 'processed':
            extra = ' -j'
        self._gcapture_cmd(
            "cylc view -g %s %s %s %s" % (
                self.get_remote_run_opts(), extra, self.cfg.template_vars_opts,
                self.cfg.suite), 400)
        return False

    def get_remote_run_opts(self):
        """Return a string containing the remote run options.

        If to run as remote host, return string will contain " --host=HOST"
        If to run as remote user, return string will contain " --user=OWNER"
        """
        ret = ""
        if is_remote_host(self.cfg.host):
            ret += " --host=" + self.cfg.host
        if is_remote_user(self.cfg.owner):
            ret += " --user=" + self.cfg.owner
        return ret

    def browse_doc(self, b, *args):
        """Run 'cylc doc' and capture its output."""
        self._gcapture_cmd('cylc doc %s' % ' '.join(args), 700)

    def browse_suite(self, _, target='suite'):
        """Browse the suite or task URL, if any."""
        if not self.updater.global_summary:
            # Suite not running, revert to parsing (can only be suite URL).
            self._gcapture_cmd('cylc doc %s %s' % (
                self.get_remote_run_opts(), self.cfg.suite), 700)
            return
        if target != 'suite':
            # Task URL
            target = TaskID.split(target)[0]
        url = self.updater.global_summary['suite_urls'][target]
        if url == '':
            warning_dialog("No URL defined for %s" % target).warn()
            return
        self._gcapture_cmd('cylc doc --url=%s' % url, 700)

    def command_help(self, w, cat='', com=''):
        """Run 'cylc help' commands, and capture output in a viewer window."""
        self._gcapture_cmd("cylc %s %s" % (cat, com), 700, 600)
