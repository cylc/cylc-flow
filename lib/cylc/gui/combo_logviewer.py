#!/usr/bin/env python
#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2015 NIWA
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
"""Cylc gui log viewer, with a combo box for log file selection."""

import gtk
import os

from cylc.gui.logviewer import logviewer
from cylc.gui.tailer import tailer


class ComboLogViewer(logviewer):

    """Implement a log viewer for the "cylc gui".
    
    It has a a combo box for log file selection.

    """

    LABEL_TEXT = "Choose Log File: "

    def __init__(self, name, file_list):
        self.file_list = file_list
        self.common_dir = os.path.dirname(os.path.commonprefix(self.file_list))
        logviewer.__init__(self, name, None, self.file_list[0])

    def create_gui_panel(self):
        """Create the panel."""
        logviewer.create_gui_panel(self)
        label = gtk.Label(self.LABEL_TEXT)
        combobox = gtk.combo_box_new_text()

        for file_ in self.file_list:
            combobox.append_text(os.path.relpath(file_, self.common_dir))

        combobox.connect("changed", self.switch_log)
        combobox.set_active(0)

        self.hbox.pack_end(combobox, False)
        self.hbox.pack_end(label, False)

    def switch_log(self, callback):
        """Switch to another file, if necessary."""
        model = callback.get_model()
        index = callback.get_active()

        name = model[index][0]
        file_ = os.path.join(self.common_dir, name)
        if file_ != self.file:
            self.file = file_
            self.t.quit = True
            logbuffer = self.logview.get_buffer()
            pos_start, pos_end = logbuffer.get_bounds()
            self.reset_logbuffer()
            logbuffer.delete(pos_start, pos_end)
            self.log_label.set_text(name)
            self.t = tailer(self.logview, file_)
            self.t.start()

        return False
