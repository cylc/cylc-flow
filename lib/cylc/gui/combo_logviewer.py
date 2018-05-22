#!/usr/bin/env python2
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
"""Cylc gui log viewer, with a combo box for log file selection."""

import gtk

from cylc.gui.logviewer import logviewer
from cylc.gui.tailer import Tailer
from cylc.task_job_logs import JOB_LOG_OPTS


class ComboLogViewer(logviewer):

    """Implement a viewer for task job logs in the GUI, via "cylc cat-log".

    It has a a combo box for log file selection.

    """
    LABEL_TEXT = "File: "
    LABEL_TEXT2 = "Submit: "

    def __init__(self, suite, task_id, choice, extra_logs, nsubmits,
                 remote_run_opts):
        self.suite_name = suite
        self.task_id = task_id
        self.nsubmits = nsubmits
        self.nsubmit = nsubmits
        self.extra_logs = extra_logs
        self.suite = suite
        self.choice = choice
        self.cmd_tmpl = "cylc cat-log %s" % remote_run_opts + (
            " -m t -s %(subnum)s -f %(job_log)s %(suite_name)s %(task_id)s")
        logviewer.__init__(self)

    def connect(self):
        """Connect to the selected log file tailer."""
        cmd = self.cmd_tmpl % {'subnum': self.nsubmit,
                               'suite_name': self.suite_name,
                               'task_id': self.task_id,
                               'job_log': self.choice}
        self.log_label.set_text(self.choice)
        self.t = Tailer(self.logview, cmd)
        self.t.start()

    def create_gui_panel(self):
        """Create the panel."""
        logviewer.create_gui_panel(self)

        label2 = gtk.Label(self.LABEL_TEXT2)
        combobox2 = gtk.combo_box_new_text()
        snums = range(1, self.nsubmits + 1)
        for snum in snums:
            combobox2.append_text(str(snum))
        combobox2.connect("changed", self.switch_snum)
        combobox2.set_active(snums.index(self.nsubmit))
        self.hbox.pack_end(combobox2, False)
        self.hbox.pack_end(label2, False)

        label = gtk.Label(self.LABEL_TEXT)
        combobox = gtk.combo_box_new_text()
        names = JOB_LOG_OPTS.values() + self.extra_logs
        for name in names:
            combobox.append_text(name)
        combobox.connect("changed", self.switch_log)
        combobox.set_active(names.index(self.choice))
        self.hbox.pack_end(combobox, False)
        self.hbox.pack_end(label, False)

    def switch_log(self, callback):
        """Switch to another file."""
        if self.t is None:
            return False
        model = callback.get_model()
        index = callback.get_active()

        filename = model[index][0]
        if filename != self.choice:
            self.choice = filename
            self.t.stop()
            self.t.join()
            logbuffer = self.logview.get_buffer()
            pos_start, pos_end = logbuffer.get_bounds()
            self.reset_logbuffer()
            logbuffer.delete(pos_start, pos_end)
            self.connect()
        return False

    def switch_snum(self, callback):
        """Switch to another file."""
        if self.t is None:
            return False
        model = callback.get_model()
        index = callback.get_active()
        snum = model[index][0]
        if snum != self.nsubmit:
            self.nsubmit = snum
            self.t.stop()
            self.t.join()
            logbuffer = self.logview.get_buffer()
            pos_start, pos_end = logbuffer.get_bounds()
            self.reset_logbuffer()
            logbuffer.delete(pos_start, pos_end)
            self.connect()
        return False
