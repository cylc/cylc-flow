#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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

import os
from subprocess import Popen, STDOUT
import sys
from time import time
import traceback

import gtk
import gobject
import warnings

from cylc.cfgspec.gcylc import GcylcConfig
from cylc.cfgspec.gscan import GScanConfig
import cylc.flags
from cylc.gui.dot_maker import DotMaker
from cylc.gui.scanutil import (KEY_PORT, get_gpanel_scan_menu,
                               update_suites_info)
from cylc.gui.util import get_icon, setup_icons
from cylc.hostuserutil import get_user
from cylc.suite_status import KEY_STATES
from cylc.task_state_prop import extract_group_state


class ScanPanelApplet(object):

    """Panel Applet (GNOME 2) to summarise running suite statuses."""

    def __init__(self, is_compact=False):
        # We can't use gobject.threads_init() for panel applets.
        warnings.filterwarnings('ignore', 'use the new', Warning)
        setup_icons()
        self.is_compact = is_compact
        dot_hbox = gtk.HBox()
        dot_hbox.show()
        dot_eb = gtk.EventBox()
        dot_eb.show()
        dot_eb.add(dot_hbox)
        image = gtk.image_new_from_stock("gcylc", gtk.ICON_SIZE_MENU)
        image.show()
        image_eb = gtk.EventBox()
        image_eb.show()
        image_eb.connect("button-press-event", self._on_button_press_event)
        image_eb.add(image)
        self.top_hbox = gtk.HBox()
        self.top_hbox.pack_start(image_eb, expand=False, fill=False)
        self.top_hbox.pack_start(dot_eb, expand=False, fill=False, padding=2)
        self.top_hbox.show()
        self.updater = ScanPanelAppletUpdater(dot_hbox, image, self.is_compact)
        self.top_hbox.connect("destroy", self.stop)
        if GScanConfig.get_inst().get(["activate on startup"]):
            self.updater.start()

    def get_widget(self):
        """Return the topmost widget for embedding in the panel."""
        return self.top_hbox

    @staticmethod
    def stop(_):
        """Handle a stop."""
        sys.exit()

    def _on_button_press_event(self, widget, event):
        if event.button == 1:
            self.updater.launch_context_menu(event)
            return False

    @staticmethod
    def _set_tooltip(widget, text):
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip(widget, text)


class ScanPanelAppletUpdater(object):

    """Update the scan panel applet - subclass of gscan equivalent."""

    IDLE_STOPPED_TIME = 3600  # 1 hour.
    MAX_INDIVIDUAL_SUITES = 5

    def __init__(self, dot_hbox, gcylc_image, is_compact):
        self.hosts = []
        self.dot_hbox = dot_hbox
        self.gcylc_image = gcylc_image
        self.is_compact = is_compact
        self.prev_full_update = None
        self.prev_norm_update = None
        self.quit = True
        self._set_gcylc_image_tooltip()
        self.gcylc_image.set_sensitive(False)
        gsfg = GScanConfig.get_inst()
        self.interval_full = gsfg.get(['suite listing update interval'])
        self.interval_part = gsfg.get(['suite status update interval'])
        gcfg = GcylcConfig.get_inst()
        self.theme_name = gcfg.get(['use theme'])
        self.theme = gcfg.get(['themes', self.theme_name])
        self.dots = DotMaker(self.theme)
        self.suite_info_map = {}
        self._set_exception_hook()
        self.owner_pattern = None

    def clear_stopped_suites(self):
        """Clear stopped suite information that may have built up."""
        for key, result in self.suite_info_map.copy().items():
            if KEY_PORT not in result:
                del self.suite_info_map[key]
        gobject.idle_add(self.update)

    def has_stopped_suites(self):
        """Return True if we have any stopped suite information."""
        for result in self.suite_info_map.copy().values():
            if KEY_PORT not in result:
                return True
        return False

    def run(self):
        """Extract running suite information at particular intervals."""
        if self.quit:
            return False
        now = time()
        if (self.prev_norm_update is not None and
                self.IDLE_STOPPED_TIME is not None and
                now > self.prev_norm_update + self.IDLE_STOPPED_TIME):
            self.stop()
            return True
        full_mode = (
            self.prev_full_update is None or
            now >= self.prev_full_update + self.interval_full)
        if (full_mode or
                self.prev_norm_update is None or
                now >= self.prev_norm_update + self.interval_part):
            # Get new information.
            self.suite_info_map = update_suites_info(self, full_mode=True)
            self.prev_norm_update = time()
            if full_mode:
                self.prev_full_update = self.prev_norm_update
            gobject.idle_add(self.update)
        return True

    def set_hosts(self, new_hosts):
        del self.hosts[:]
        self.hosts.extend(new_hosts)
        self.update_now()

    def start(self):
        self.gcylc_image.set_sensitive(True)
        self.quit = False
        self.prev_full_update = None
        self.prev_norm_update = None
        gobject.timeout_add(1000, self.run)
        self._set_gcylc_image_tooltip()

    def stop(self):
        self.gcylc_image.set_sensitive(False)
        self.quit = True
        self._set_gcylc_image_tooltip()

    def launch_context_menu(self, event, suite_keys=None, extra_items=None):

        if suite_keys is None:
            suite_keys = []

        if extra_items is None:
            extra_items = []

        gscan_item = gtk.ImageMenuItem("Launch cylc gscan")
        img = gtk.image_new_from_stock("gcylc", gtk.ICON_SIZE_MENU)
        gscan_item.set_image(img)
        gscan_item.show()
        gscan_item.connect("button-press-event",
                           self._on_button_press_event_gscan)

        extra_items.append(gscan_item)

        menu = get_gpanel_scan_menu(suite_keys,
                                    self.theme_name, self._set_theme,
                                    self.has_stopped_suites(),
                                    self.clear_stopped_suites,
                                    self.hosts,
                                    self.set_hosts,
                                    self.update_now,
                                    self.start,
                                    program_name="cylc gpanel",
                                    extra_items=extra_items,
                                    is_stopped=self.quit)
        menu.popup(None, None, None, event.button, event.time)
        return False

    def update(self):
        """Update the Applet."""
        for child in self.dot_hbox.get_children():
            self.dot_hbox.remove(child)
        number_mode = (
            not self.is_compact and
            len(self.suite_info_map) > self.MAX_INDIVIDUAL_SUITES)
        suite_statuses = {}
        compact_suite_statuses = []
        for key, suite_info in sorted(self.suite_info_map.items(),
                                      key=lambda details: details[0][2]):
            if KEY_STATES not in suite_info:
                continue
            host, _, suite = key
            is_stopped = KEY_PORT not in suite_info
            status = extract_group_state(
                suite_info[KEY_STATES][0].keys(), is_stopped=is_stopped)
            status_map = suite_info[KEY_STATES][0]
            if number_mode:
                suite_statuses.setdefault(is_stopped, {})
                suite_statuses[is_stopped].setdefault(status, [])
                suite_statuses[is_stopped][status].append(
                    (suite, host, status_map.items()))
            elif self.is_compact:
                compact_suite_statuses.append(
                    (suite, host, status, status_map.items(), is_stopped))
            else:
                self._add_image_box(
                    [(suite, host, status, status_map.items(), is_stopped)])
        if number_mode:
            for is_stopped, status_map in sorted(suite_statuses.items()):
                # Sort by number of suites in this state.
                statuses = status_map.items()
                statuses.sort(lambda x, y: cmp(len(y[1]), len(x[1])))
                for status, suite_host_states_tuples in statuses:
                    label = gtk.Label(str(len(suite_host_states_tuples)) + ":")
                    label.show()
                    self.dot_hbox.pack_start(label, expand=False, fill=False)
                    suite_info_tuples = []
                    for suite, host, task_states in suite_host_states_tuples:
                        suite_info_tuples.append(
                            (suite, host, status, task_states, is_stopped))
                    self._add_image_box(suite_info_tuples)
        if self.is_compact:
            if not compact_suite_statuses:
                # No suites running or stopped.
                self.gcylc_image.show()
                return False
            self.gcylc_image.hide()
            self._add_image_box(compact_suite_statuses)
        return False

    def update_now(self):
        """Force an update as soon as possible."""
        self.prev_full_update = None
        self.prev_norm_update = None

    def _add_image_box(self, suite_host_info_tuples):
        image_eb = gtk.EventBox()
        image_eb.show()
        running_status_list = []
        status_list = []
        suite_keys = []
        for info_tuple in suite_host_info_tuples:
            suite, host, status, _, is_stopped = info_tuple
            suite_keys.append((host, get_user(), suite))
            if not is_stopped:
                running_status_list.append(status)
            status_list.append(status)
        if running_status_list:
            status = extract_group_state(running_status_list,
                                         is_stopped=False)
            image = self.dots.get_image(status, is_stopped=False)
        else:
            status = extract_group_state(status_list, is_stopped=True)
            image = self.dots.get_image(status, is_stopped=True)
        image.show()
        image_eb.add(image)
        image_eb._connect_args = suite_keys
        image_eb.connect("button-press-event",
                         self._on_button_press_event)

        text_format = "%s - %s - %s"
        long_text_format = text_format + "\n    %s\n"
        text = ""
        tip_vbox = gtk.VBox()  # Only used in PyGTK 2.12+
        tip_vbox.show()
        for info_tuple in suite_host_info_tuples:
            suite, host, status, state_counts, is_stopped = info_tuple
            state_counts.sort(lambda x, y: cmp(y[1], x[1]))
            tip_hbox = gtk.HBox()
            tip_hbox.show()
            state_info = []
            for state_name, number in state_counts:
                state_info.append("%d %s" % (number, state_name))
                image = self.dots.get_image(state_name, is_stopped=is_stopped)
                image.show()
                tip_hbox.pack_start(image, expand=False, fill=False)
            states_text = ", ".join(state_info)
            if status is None:
                suite_summary = "?"
            else:
                suite_summary = status
            if is_stopped:
                suite_summary = "stopped with " + suite_summary
            tip_label = gtk.Label(text_format % (suite, suite_summary, host))
            tip_label.show()
            tip_hbox.pack_start(tip_label, expand=False, fill=False,
                                padding=5)
            tip_vbox.pack_start(tip_hbox, expand=False, fill=False)
            text += long_text_format % (
                suite, suite_summary, host, states_text)
        text = text.rstrip()
        if hasattr(gtk, "Tooltip"):
            image_eb.set_has_tooltip(True)
            image_eb.connect("query-tooltip", self._on_img_tooltip_query,
                             tip_vbox)
        else:
            self._set_tooltip(image_eb, text)
        self.dot_hbox.pack_start(image_eb, expand=False, fill=False,
                                 padding=1)

    def launch_gscan(self):
        """Launch gscan."""
        if cylc.flags.debug:
            stdout = sys.stdout
            stderr = sys.stderr
            command = ["cylc", "gscan", "--debug"]
        else:
            stdout = open(os.devnull, "w")
            stderr = STDOUT
            command = ["cylc", "gscan"]
        if self.hosts:
            command += self.hosts
        Popen(command, stdin=open(os.devnull), stdout=stdout, stderr=stderr)

    def _on_button_press_event(self, widget, event):
        if event.button == 1:
            self.launch_context_menu(event, suite_keys=widget._connect_args)
        return False

    def _on_button_press_event_gscan(self, widget, event):
        self.launch_gscan()

    @staticmethod
    def _on_img_tooltip_query(widget, x, y, kbd, tooltip, tip_widget):
        tooltip.set_custom(tip_widget)
        return True

    def _set_exception_hook(self):
        """Handle an uncaught exception."""
        sys.excepthook = lambda e_type, e_value, e_traceback: (
            self._handle_exception(
                e_type, e_value, e_traceback, sys.excepthook))

    def _handle_exception(self, e_type, e_value, e_traceback, old_hook):
        self.gcylc_image.set_from_stock(gtk.STOCK_DIALOG_ERROR,
                                        gtk.ICON_SIZE_MENU)
        exc_lines = traceback.format_exception(e_type, e_value, e_traceback)
        exc_text = "".join(exc_lines)
        info = "cylc gpanel has a problem.\n\n%s" % exc_text
        self._set_tooltip(self.gcylc_image, info.rstrip())
        if old_hook is not None:
            old_hook(e_type, e_value, e_traceback)

    def _set_gcylc_image_tooltip(self):
        if self.quit:
            self._set_tooltip(self.gcylc_image, "Cylc Applet - Off")
        else:
            self._set_tooltip(self.gcylc_image, "Cylc Applet - Active")

    def _set_theme(self, new_theme_name):
        self.theme_name = new_theme_name
        self.theme = GcylcConfig.get_inst().get(['themes', self.theme_name])
        self.dots = DotMaker(self.theme)

    def _set_tooltip(self, widget, text):
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip(widget, text)


def run_in_window(is_compact=False):
    """Run the panel applet in stand-alone mode."""
    my_panel_app = ScanPanelApplet(is_compact=is_compact)
    window = gtk.Window()
    window.set_title("cylc panel applet test")
    window.add(my_panel_app.top_hbox)
    window.set_default_size(300, 50)
    window.set_icon(get_icon())
    window.show()
    window.connect("destroy", lambda w: gtk.main_quit())
    gtk.main()
