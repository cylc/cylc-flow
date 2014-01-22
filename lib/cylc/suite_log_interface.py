#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
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

import Pyro.core
import os


class log_interface(Pyro.core.ObjBase):

    """Implement an interface to the log files."""

    def __init__(self, log):
        Pyro.core.ObjBase.__init__(self)
        self.log = log
        self.err_file = log.get_err_path()

    def get_err_has_changed(self, prev_err_size):
        """Return True if the file has changed size compared to prev_size."""
        return self.get_err_size() != prev_err_size

    def get_err_size(self):
        """Return the os.path.getsize result for the error file."""
        try:
            size = os.path.getsize(self.err_file)
        except (IOError, OSError) as e:
            self.log.warning("Could not read suite err log file: %s" % e)
            return 0
        return size

    def get_err_content(self, prev_size=0, max_lines=100):
        """Return the content and new size of the error file."""
        if not self.get_err_has_changed(prev_size):
            return [], prev_size
        try:
            f = open(self.err_file, "r")
            f.seek(prev_size)
            new_content = f.read()
            f.close()
            size = self.get_err_size()
        except (IOError, OSError) as e:
            self.log.warning("Could not read suite err log file: %s" % e)
            return "", prev_size
        new_content_lines = new_content.splitlines()[-max_lines:]
        return "\n".join(new_content_lines), size
