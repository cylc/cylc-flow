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

import os
import gtk
from cylc.gui.logviewer import logviewer
from cylc.gui.tailer import Tailer
from cylc.gui.util import get_icon
from cylc.gui.warning_dialog import warning_dialog
from cylc.suite_logging import SUITE_LOG_OPTS


class SuiteLogViewer(logviewer):
    """A popup window to view suite logs.

    Implemented using "cylc cat-log".

    """
    def __init__(self, suite_name, suite_log, remote_run_opts, task_list=None):
        """Initialise the suite log viewer."""
        if task_list is None:
            self.task_list = []
        self.suite_name = suite_name
        self.suite_log = suite_log
        self.suite_log_name = SUITE_LOG_OPTS[suite_log]
        self.rotation = 0
        self.cmd_tmpl = "cylc cat-log %s" % remote_run_opts + (
            " -m t -r %(rotation)s -f %(suite_log)s %(suite_name)s")
        self.task_filter = None
        self.custom_filter = None
        logviewer.__init__(self)
        self.update_view()

    def create_gui_panel(self):
        """Create the GUI panel."""
        logviewer.create_gui_panel(self)

        self.window = gtk.Window()
        # self.window.set_border_width(5)
        self.window.set_title("log viewer")
        self.window.set_size_request(800, 400)
        self.window.set_icon(get_icon())

        combobox = gtk.combo_box_new_text()
        combobox.append_text('Task')
        combobox.append_text('all')
        for task in self.task_list:
            combobox.append_text(task)

        combobox.connect("changed", self.filter_log)
        combobox.set_active(0)

        newer = gtk.Button("_newer")
        newer.connect("clicked", self.rotate_log, False)
        self.hbox.pack_end(newer, False)

        older = gtk.Button("_older")
        older.connect("clicked", self.rotate_log, True)
        self.hbox.pack_end(older, False)

        self.hbox.pack_end(combobox, False)

        filterbox = gtk.HBox()
        entry = gtk.Entry()
        entry.connect("activate", self.custom_filter_log)
        label = gtk.Label('Filter')
        filterbox.pack_start(label, True)
        filterbox.pack_start(entry, True)
        self.hbox.pack_end(filterbox, False)

        close = gtk.Button("_Close")
        close.connect("clicked", self.shutdown, None, self.window)
        self.hbox.pack_start(close, False)

        self.window.add(self.vbox)
        self.window.connect("delete_event", self.shutdown, self.window)

        self.window.show_all()

    def shutdown(self, w, e, wind):
        """Quite the suite log viewer."""
        self.quit()
        wind.destroy()

    def filter_log(self, cb):
        """Filter for task names."""
        model = cb.get_model()
        index = cb.get_active()
        if index == 0:
            return False
        task = model[index][0]
        if task == 'all':
            filter_ = None
        else:
            # Good enough to match "[task.CYCLE]"?
            filter_ = r'\[' + task + r'\.[^\]]+\]'
        self.task_filter = filter_
        self.update_view()
        return False

    def custom_filter_log(self, e):
        """Filter for arbitrary text."""
        txt = e.get_text()
        if txt == '':
            filter_ = None
        else:
            filter_ = txt
        self.custom_filter = filter_
        self.update_view()
        return False

    def rotate_log(self, bt, go_older):
        """Switch to other log rotations."""
        if go_older:
            self.rotation += 1
        elif self.rotation > 0:
            self.rotation -= 1
        self.update_view()

    def connect(self):
        """Run the tailer command."""
        cmd = self.cmd_tmpl % {'rotation': self.rotation,
                               'suite_name': self.suite_name,
                               'suite_log': self.suite_log}
        self.t = Tailer(
            self.logview, cmd,
            filters=[f for f in [self.task_filter, self.custom_filter] if f])
        self.t.start()

    def update_view(self):
        """Restart the log view on another log."""
        self.t.stop()
        logbuffer = self.logview.get_buffer()
        s, e = logbuffer.get_bounds()
        self.reset_logbuffer()
        logbuffer.delete(s, e)
        label = "%s (rot %d)" % (self.suite_log_name, self.rotation)
        self.log_label.set_text(label)
        self.connect()
