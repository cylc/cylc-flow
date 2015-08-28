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
import datetime
import os
import re
import shlex
import subprocess
import sys
import threading
import time
import traceback

import gtk
import gobject
import warnings
#import pygtk
#pygtk.require('2.0')

from cylc.cfgspec.globalcfg import GLOBAL_CFG
from cylc.cfgspec.gcylc import gcfg
from cylc.gui.gscan import (get_scan_menu, launch_gscan,
                            BaseScanTimeoutUpdater)
from cylc.gui.app_gcylc import run_get_stdout
from cylc.gui.dot_maker import DotMaker
from cylc.gui.util import get_icon, setup_icons
from cylc.owner import user
from cylc.network.suite_state import extract_group_state


class ScanPanelApplet(object):

    """Panel Applet (GNOME 2) to summarise running suite statuses."""

    def __init__(self, hosts=None, owner=None, poll_interval=None,
                 is_compact=False):
        # We can't use gobject.threads_init() for panel applets.
        warnings.filterwarnings('ignore', 'use the new', Warning)
        setup_icons()
        if not hosts:
            try:
                hosts = GLOBAL_CFG.get( ["suite host scanning","hosts"] )
            except KeyError:
                hosts = ["localhost"]
        self.is_compact = is_compact
        self.hosts = hosts
        if owner is None:
            owner = user
        self.owner = owner
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
        self.updater = ScanPanelAppletUpdater(hosts, dot_hbox, image,
                                              self.is_compact,
                                              owner=owner,
                                              poll_interval=poll_interval)
        self.top_hbox.connect("destroy", self.stop)

    def get_widget(self):
        """Return the topmost widget for embedding in the panel."""
        return self.top_hbox

    def stop(self, widget):
        """Handle a stop."""
        sys.exit()

    def _on_button_press_event(self, widget, event):
        if event.button == 1:
            self.updater.launch_context_menu(event)
            return False

    def _set_tooltip(self, widget, text):
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip(widget, text)


class ScanPanelAppletUpdater(BaseScanTimeoutUpdater):

    """Update the scan panel applet - subclass of gscan equivalent."""

    IDLE_STOPPED_TIME = 3600  # 1 hour.
    MAX_INDIVIDUAL_SUITES = 5

    def __init__(self, hosts, dot_hbox, gcylc_image, is_compact, owner=None,
                 poll_interval=None):
        self.quit = True
        self.dot_hbox = dot_hbox
        self.gcylc_image = gcylc_image
        self.is_compact = is_compact
        self._set_gcylc_image_tooltip()
        self.gcylc_image.set_sensitive(False)
        self.theme_name = gcfg.get( ['use theme'] )
        self.theme = gcfg.get( ['themes', self.theme_name] )
        self.dots = DotMaker(self.theme)
        self.hosts_suites_info = {}
        self.stopped_hosts_suites_info = {}
        self._set_exception_hook()
        super(ScanPanelAppletUpdater, self).__init__(
            hosts, owner=owner, poll_interval=poll_interval)

    def clear_stopped_suites(self):
        """Clear stopped suite information that may have built up."""
        self.stopped_hosts_suites_info.clear()
        gobject.idle_add(self.update)

    def start(self):
        self.gcylc_image.set_sensitive(True)
        super(ScanPanelAppletUpdater, self).start()
        self._set_gcylc_image_tooltip()

    def stop(self):
        self.gcylc_image.set_sensitive(False)
        super(ScanPanelAppletUpdater, self).stop()
        self._set_gcylc_image_tooltip()

    def launch_context_menu(self, event, suite_host_tuples=None,
                            extra_items=None):
        has_stopped_suites = bool(self.stopped_hosts_suites_info)

        if suite_host_tuples is None:
            suite_host_tuples = []

        if extra_items is None:
            extra_items = []

        gscan_item = gtk.ImageMenuItem("Launch cylc gscan")
        img = gtk.image_new_from_stock("gcylc", gtk.ICON_SIZE_MENU)
        gscan_item.set_image(img)
        gscan_item.show()
        gscan_item.connect("button-press-event",
                                self._on_button_press_event_gscan)

        extra_items.append(gscan_item)

        menu = get_scan_menu(suite_host_tuples, 
                             self.theme_name, self._set_theme,
                             has_stopped_suites,
                             self.clear_stopped_suites,
                             self.hosts,
                             self.set_hosts,
                             self.update_now,
                             self.start,
                             program_name="cylc gpanel",
                             extra_items=extra_items,
                             owner=self.owner,
                             is_stopped=self.quit)
        menu.popup( None, None, None, event.button, event.time )
        return False

    def update(self):
        """Update the Applet."""
        info = copy.deepcopy(self.hosts_suites_info)
        stop_info = copy.deepcopy(self.stopped_hosts_suites_info)
        suite_host_tuples = []
        for host in self.hosts:
            suites = (info.get(host, {}).keys() +
                      stop_info.get(host, {}).keys())
            for suite in suites:
                if (suite, host) not in suite_host_tuples:
                    suite_host_tuples.append((suite, host))
        suite_host_tuples.sort()
        for child in self.dot_hbox.get_children():
            self.dot_hbox.remove(child)
        number_mode = (not self.is_compact and
                       len(suite_host_tuples) > self.MAX_INDIVIDUAL_SUITES)
        suite_statuses = {}
        compact_suite_statuses = []
        for suite, host in suite_host_tuples:
            if suite in info.get(host, {}):
                suite_info = info[host][suite]
                is_stopped = False
            else:
                suite_info = stop_info[host][suite]
                is_stopped = True

            if "states" not in suite_info:
                continue

            status = extract_group_state(suite_info['states'].keys(),
                                         is_stopped=is_stopped)
            status_map = suite_info['states']
            if number_mode:
                suite_statuses.setdefault(is_stopped, {})
                suite_statuses[is_stopped].setdefault(status, [])
                suite_statuses[is_stopped][status].append(
                                           (suite, host, status_map.items()))
            elif self.is_compact:
                compact_suite_statuses.append((suite, host, status,
                                               status_map.items(), is_stopped))
            else:
                self._add_image_box([(suite, host, status, status_map.items(),
                                      is_stopped)])
        if number_mode:
            for is_stopped in sorted(suite_statuses.keys()):
                statuses = suite_statuses[is_stopped].items()
                # Sort by number of suites in this state.
                statuses.sort(lambda x, y: cmp(len(y[1]), len(x[1])))
                for status, suite_host_states_tuples in statuses:
                    label = gtk.Label(
                                str(len(suite_host_states_tuples)) + ":")
                    label.show()
                    self.dot_hbox.pack_start(label, expand=False, fill=False)
                    suite_info_tuples = []
                    for suite, host, task_states in suite_host_states_tuples:
                        suite_info_tuples.append((suite, host, status,
                                                  task_states, is_stopped))
                    self._add_image_box(suite_info_tuples)
        if self.is_compact:
            if not compact_suite_statuses:
                # No suites running or stopped.
                self.gcylc_image.show()
                return False
            self.gcylc_image.hide()
            self._add_image_box(compact_suite_statuses)
        return False

    def _add_image_box(self, suite_host_info_tuples):
        image_eb = gtk.EventBox()
        image_eb.show()
        is_all_stopped = False
        running_status_list = []
        status_list = []
        suite_host_tuples = []
        for info_tuple in suite_host_info_tuples:
            suite, host, status, task_states, is_stopped = info_tuple
            suite_host_tuples.append((suite, host))
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
        image_eb._connect_args = suite_host_tuples
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
            text += long_text_format % (suite, suite_summary, host, states_text)
        text = text.rstrip()
        if hasattr(gtk, "Tooltip"):
            image_eb.set_has_tooltip(True)
            image_eb.connect("query-tooltip", self._on_img_tooltip_query,
                             tip_vbox)
        else:
            self._set_tooltip(image_eb, text)
        self.dot_hbox.pack_start(image_eb, expand=False, fill=False,
                                 padding=1)

    def _on_button_press_event(self, widget, event):
        if event.button == 1:
            self.launch_context_menu(event,
                                     suite_host_tuples=widget._connect_args)
        return False

    def _on_button_press_event_gscan(self, widget, event):
        launch_gscan(hosts=self.hosts, owner=self.owner)

    def _on_img_tooltip_query(self, widget, x, y, kbd, tooltip, tip_widget):
        tooltip.set_custom(tip_widget)
        return True

    def _set_exception_hook(self):
        # Handle an uncaught exception.
        old_hook = sys.excepthook
        sys.excepthook = (lambda *a:
                          self._handle_exception(*a, old_hook=old_hook))

    def _handle_exception(self, e_type, e_value, e_traceback,
                          old_hook=None):
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
        self.theme = gcfg.get( ['themes', self.theme_name] )
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
