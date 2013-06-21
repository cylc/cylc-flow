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
                               get_summary_menu, launch_gcylc, BaseSummaryUpdater)
from cylc.gui.SuiteControl import run_get_stdout
from cylc.gui.DotMaker import DotMaker
from cylc.gui.util import get_icon, setup_icons
from cylc.owner import user
from cylc.state_summary import extract_group_state


class SummaryPanelApplet(object):

    """Panel Applet (GNOME 2) to summarise running suite statuses."""

    def __init__(self, hosts=None, owner=None):
        gobject.threads_init()
        warnings.filterwarnings('ignore', 'use the new', Warning)
        setup_icons()
        if not hosts:
            hosts = gcfg.sitecfg["suite host scanning"]["hosts"]
        self.hosts = hosts
        if owner is None:
            owner = user
        self.dot_hbox = gtk.HBox()
        self.dot_hbox.show()
        self.dot_eb = gtk.EventBox()
        self.dot_eb.show()
        self.dot_eb.add(self.dot_hbox)
        self.updater = SummaryPanelAppletUpdater(hosts, self.dot_hbox,
                                                 owner)
        self.updater.start()
        self.dot_eb.connect("destroy", self.stop)

    def stop(self, widget):
        """Handle a stop."""
        self.updater.quit = True


class SummaryPanelAppletUpdater(BaseSummaryUpdater):

    """Update the summary panel applet - subclass of gsummary equivalent."""
    
    MAX_INDIVIDUAL_SUITES = 5
    
    def __init__(self, hosts, dot_hbox, owner=None):
        self.dot_hbox = dot_hbox
        self.usercfg = config().cfg
        self.theme_name = self.usercfg['use theme'] 
        self.theme = self.usercfg['themes'][self.theme_name]
        self.dots = DotMaker(self.theme)
        self.statuses = {}
        self.stop_summaries = {}
        self.quit = False
        super(SummaryPanelAppletUpdater, self).__init__(hosts, owner=owner)

    def clear_stopped_suites(self):
        """Clear stopped suite information that may have built up."""
        self.stop_summaries.clear()
        gobject.idle_add(self.update)

    def update(self, update_time=None):
        """Update the Applet."""
        suite_host_tuples = []
        for host in self.hosts:
            suites = (self.statuses.get(host, {}).keys() +
                      self.stop_summaries.get(host, {}).keys())
            for suite in suites:
                suite_host_tuples.append((suite, host))
        suite_host_tuples.sort()
        for child in self.dot_hbox.get_children():
            self.dot_hbox.remove(child)
        number_mode = (len(suite_host_tuples) > self.MAX_INDIVIDUAL_SUITES)
        suite_statuses = {}
        for suite, host in suite_host_tuples:
            if suite in self.statuses.get(host, {}):
                status_map = self.statuses[host][suite]
                is_stopped = False
            else:
                info = self.stop_summaries[host][suite]
                status_map, suite_time = info
                is_stopped = True
            status = extract_group_state(status_map.keys())
            if number_mode:
                suite_statuses.setdefault(is_stopped, {})
                suite_statuses[is_stopped].setdefault(status, [])
                suite_statuses[is_stopped][status].append((suite, host))
            else:
                self._add_image_box(status, is_stopped, [(suite, host)])
        if number_mode:
            for is_stopped in sorted(suite_statuses.keys()):
                statuses = suite_statuses[is_stopped].items()
                statuses.sort(lambda x, y: cmp(len(y[1]), len(x[1])))
                for status, status_suite_host_tuples in statuses:
                    label = gtk.Label(
                                str(len(status_suite_host_tuples)) + ":")
                    label.show()
                    self.dot_hbox.pack_start(label, expand=False, fill=False)
                    self._add_image_box(status, is_stopped,
                                        status_suite_host_tuples)
        return False

    def _add_image_box(self, status, is_stopped, suite_host_tuples):
        image_eb = gtk.EventBox()
        image_eb.show()
        image = self.dots.get_image(status)
        image.show()            
        image.set_sensitive(not is_stopped)
        image_eb.add(image)
        image_eb._connect_args = suite_host_tuples
        image_eb.connect("button-press-event",
                            self._on_button_press_event)
        summary = status
        if is_stopped:
            summary = "stopped with " + status
        text_format = "%s - %s - %s"
        text = ""
        for suite, host in suite_host_tuples:
            text += text_format % (suite, summary, host) + "\n"
        text = text.rstrip()
        self._set_tooltip(image_eb, text)
        self.dot_hbox.pack_start(image_eb, expand=False, fill=False)

    def _on_button_press_event(self, widget, event):
        if event.button == 1:
            for suite, host in widget._connect_args:
                launch_gcylc(host, suite, owner=self.owner)

        if event.button != 3:
            return False

        has_stopped_suites = bool(self.stop_summaries)

        menu = get_summary_menu(widget._connect_args, self.usercfg,
                                self.theme_name, self._set_theme,
                                has_stopped_suites,
                                self.clear_stopped_suites,
                                owner=self.owner)
        menu.popup( None, None, None, event.button, event.time )
        return False

    def _set_theme(self, new_theme_name):
        self.theme_name = new_theme_name
        self.theme = self.usercfg['themes'][self.theme_name]
        self.dots = DotMaker(self.theme)

    def _set_tooltip(self, widget, text):
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip(widget, text)


def run_panel_applet_in_window():
    """Run the panel applet in stand-alone mode."""
    my_panel_app = SummaryPanelApplet()
    window = gtk.Window()
    window.set_title("Test cylc summary panel applet")
    window.add(my_panel_app.dot_eb)
    window.set_default_size(300, 50)
    window.show()
    window.connect("destroy", lambda w: gtk.main_quit())
    gtk.main()
