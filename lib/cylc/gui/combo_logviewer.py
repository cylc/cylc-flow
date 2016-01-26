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
"""Cylc gui log viewer, with a combo box for log file selection."""

import gtk
import os

from parsec.OrderedDict import OrderedDict

from cylc.gui.logviewer import logviewer
from cylc.gui.tailer import Tailer
from cylc.task_id import TaskID


class ComboLogViewer(logviewer):

    """Implement a viewer for task jobs in the "cylc gui".

    It has a a combo box for log file selection.

    task_id -- The NAME.POINT of a task proxy.
    filenames -- The names of the task job logs.
    cmd_tmpls -- A dict to map file names and alternate commands to tail follow
                 the file.
    init_active_index -- The index for selecting the initial log file.
    """

    LABEL_TEXT = "Choose Log File: "

    def __init__(self, task_id, filenames, cmd_tmpls, init_active_index):
        self.filenames = OrderedDict()
        name_str, point_str = TaskID.split(task_id)
        for filename in filenames:
            try:
                f_point_str, f_name_str, f_submit_num_str, f_base_name = (
                    filename.rsplit(os.sep, 4)[1:])
                if (f_point_str == point_str and f_name_str == name_str and
                        int(f_submit_num_str) and f_base_name):
                    name = f_submit_num_str + os.sep + f_base_name
                if ":" in filename:
                    name += " (%s)" % (filename.split(":", 1)[0])
            except ValueError:
                name = filename
            self.filenames[name] = filename
        self.init_active_index = init_active_index
        self.cmd_tmpls = cmd_tmpls
        logviewer.__init__(
            self, task_id, None, filenames[self.init_active_index])

    def connect(self):
        """Connect to the selected log file tailer."""
        try:
            cmd_tmpl = self.cmd_tmpls[self.filename]
        except (KeyError, TypeError):
            cmd_tmpl = None
        self.t = Tailer(self.logview, self.filename, cmd_tmpl=cmd_tmpl)
        self.t.start()

    def create_gui_panel(self):
        """Create the panel."""
        logviewer.create_gui_panel(self)
        label = gtk.Label(self.LABEL_TEXT)
        combobox = gtk.combo_box_new_text()

        for name in self.filenames:
            combobox.append_text(name)

        combobox.connect("changed", self.switch_log)
        if self.init_active_index:
            combobox.set_active(self.init_active_index)
        else:
            combobox.set_active(0)

        self.hbox.pack_end(combobox, False)
        self.hbox.pack_end(label, False)

    def switch_log(self, callback):
        """Switch to another file, if necessary."""
        if self.t is None:
            return False
        model = callback.get_model()
        index = callback.get_active()

        name = model[index][0]
        filename = self.filenames[name]
        if filename != self.filename:
            self.filename = filename
            self.t.stop()
            self.t.join()
            logbuffer = self.logview.get_buffer()
            pos_start, pos_end = logbuffer.get_bounds()
            self.reset_logbuffer()
            logbuffer.delete(pos_start, pos_end)
            self.log_label.set_text(name)
            self.connect()

        return False
