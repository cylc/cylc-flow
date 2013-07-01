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
import sys
import threading
import time

import gtk
import gobject
import warnings
#import pygtk
#pygtk.require('2.0')

from cylc.global_config import gcfg

from cylc.gui.gcylc_config import config
from cylc.gui.gsummary import (get_host_suites, get_status_tasks,
                               get_summary_menu, launch_gcylc,
                               launch_gsummary, BaseSummaryTimeoutUpdater)
from cylc.gui.SuiteControl import run_get_stdout
from cylc.gui.DotMaker import DotMaker
from cylc.gui.util import get_icon, setup_icons
from cylc.owner import user
from cylc.state_summary import extract_group_state


class SummaryPanelApplet(object):

    """Panel Applet (GNOME 2) to summarise running suite statuses."""

    def __init__(self, hosts=None, owner=None, poll_interval=None):
        # We can't use gobject.threads_init() for panel applets.
        warnings.filterwarnings('ignore', 'use the new', Warning)
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
        self._set_tooltip(image_eb, "Cylc Applet")
        image_eb.add(image)
        self.top_hbox = gtk.HBox()
        self.top_hbox.pack_start(image_eb, expand=False, fill=False)
        self.top_hbox.pack_start(dot_eb, expand=False, fill=False, padding=2)
        self.top_hbox.show()
        self.updater = SummaryPanelAppletUpdater(hosts, dot_hbox,
                                                 owner=owner,
                                                 poll_interval=poll_interval)
        gobject.idle_add(self.updater.start)  # Returns False, no loop.
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


class SummaryPanelAppletUpdater(BaseSummaryTimeoutUpdater):

    """Update the summary panel applet - subclass of gsummary equivalent."""
    
    MAX_INDIVIDUAL_SUITES = 5
    
    def __init__(self, hosts, dot_hbox, owner=None, poll_interval=None):
        self.dot_hbox = dot_hbox
        self.usercfg = config().cfg
        self.theme_name = self.usercfg['use theme'] 
        self.theme = self.usercfg['themes'][self.theme_name]
        self.dots = DotMaker(self.theme)
        self.statuses = {}
        self.stop_summaries = {}
        self.quit = False
        super(SummaryPanelAppletUpdater, self).__init__(
                              hosts, owner=owner, poll_interval=poll_interval)

    def clear_stopped_suites(self):
        """Clear stopped suite information that may have built up."""
        self.stop_summaries.clear()
        gobject.idle_add(self.update)

    def launch_context_menu(self, event, suite_host_tuples=None,
                            extra_items=None):
        has_stopped_suites = bool(self.stop_summaries)

        if suite_host_tuples is None:
            suite_host_tuples = []

        if extra_items is None:
            extra_items = []

        gsummary_item = gtk.ImageMenuItem(stock_id="gcylc")
        gsummary_item.set_label("Launch cylc gsummary")
        gsummary_item.show()
        gsummary_item.connect("button-press-event",
                              lambda b, e: launch_gsummary())

        extra_items.append(gsummary_item)

        menu = get_summary_menu(suite_host_tuples, self.usercfg,
                                self.theme_name, self._set_theme,
                                has_stopped_suites,
                                self.clear_stopped_suites,
                                self.hosts,
                                self.set_hosts,
                                self.update_now,
                                program_name="cylc gpanel",
                                extra_items=extra_items,
                                owner=self.owner)
        menu.popup( None, None, None, event.button, event.time )
        return False

    def update(self, update_time=None):
        """Update the Applet."""
        suite_host_tuples = []
        statuses = copy.deepcopy(self.statuses)
        stop_summaries = copy.deepcopy(self.stop_summaries)
        for host in self.hosts:
            suites = (statuses.get(host, {}).keys() +
                      stop_summaries.get(host, {}).keys())
            for suite in suites:
                suite_host_tuples.append((suite, host))
        suite_host_tuples.sort()
        for child in self.dot_hbox.get_children():
            self.dot_hbox.remove(child)
        number_mode = (len(suite_host_tuples) > self.MAX_INDIVIDUAL_SUITES)
        suite_statuses = {}
        for suite, host in suite_host_tuples:
            if suite in statuses.get(host, {}):
                status_map = statuses[host][suite]
                is_stopped = False
            else:
                info = stop_summaries[host][suite]
                status_map, suite_time = info
                is_stopped = True
            status = extract_group_state(status_map.keys(),
                                         is_stopped=is_stopped)
            if number_mode:
                suite_statuses.setdefault(is_stopped, {})
                suite_statuses[is_stopped].setdefault(status, [])
                suite_statuses[is_stopped][status].append(
                                           (suite, host, status_map.items()))
            else:
                self._add_image_box(status, is_stopped,
                                    [(suite, host, status_map.items())])
        if number_mode:
            for is_stopped in sorted(suite_statuses.keys()):
                statuses = suite_statuses[is_stopped].items()
                statuses.sort(lambda x, y: cmp(len(y[1]), len(x[1])))
                for status, suite_host_states_tuples in statuses:
                    label = gtk.Label(
                                str(len(status_suite_host_tuples)) + ":")
                    label.show()
                    self.dot_hbox.pack_start(label, expand=False, fill=False)
                    self._add_image_box(status, is_stopped,
                                        suite_host_states_tuples)
        return False

    def _add_image_box(self, status, is_stopped, suite_host_states_tuples):
        image_eb = gtk.EventBox()
        image_eb.show()
        image = self.dots.get_image(status, is_stopped=is_stopped)
        image.show()
        image_eb.add(image)
        suite_host_tuples = [(s, h) for s, h, sts in suite_host_states_tuples]
        image_eb._connect_args = suite_host_tuples
        image_eb.connect("button-press-event",
                         self._on_button_press_event)
        summary = status
        if is_stopped:
            summary = "stopped with " + status
        
        text_format = "%s - %s - %s"
        long_text_format = text_format + "\n    Tasks: %s\n"
        text = ""
        tip_vbox = gtk.VBox()  # Only used in PyGTK 2.12+
        tip_vbox.show()
        for suite, host, states in suite_host_states_tuples:
            state_info = []
            states.sort(lambda x, y: cmp(len(y[1]), len(x[1])))
            tip_hbox = gtk.HBox()
            tip_hbox.show()
            for state_name, tasks in states:
                state_info.append(str(len(tasks)) + " " + state_name)
                image = self.dots.get_image(state_name, is_stopped=is_stopped)
                image.show()
                tip_hbox.pack_start(image, expand=False, fill=False)
            states_text = ", ".join(state_info)
            tip_label = gtk.Label(text_format % (suite, summary, host))
            tip_label.show()
            tip_hbox.pack_start(tip_label, expand=False, fill=False,
                                padding=5)
            tip_vbox.pack_start(tip_hbox, expand=False, fill=False)
            text += long_text_format % (suite, summary, host, states_text)
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

    def _on_img_tooltip_query(self, widget, x, y, kbd, tooltip, tip_widget):
        tooltip.set_custom(tip_widget)
        return True

    def _set_theme(self, new_theme_name):
        self.theme_name = new_theme_name
        self.theme = self.usercfg['themes'][self.theme_name]
        self.dots = DotMaker(self.theme)

    def _set_tooltip(self, widget, text):
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip(widget, text)


def run_in_window():
    """Run the panel applet in stand-alone mode."""
    my_panel_app = SummaryPanelApplet()
    window = gtk.Window()
    window.set_title("cylc panel applet test")
    window.add(my_panel_app.top_hbox)
    window.set_default_size(300, 50)
    window.set_icon(get_icon())
    window.show()
    window.connect("destroy", lambda w: gtk.main_quit())
    gtk.main()
