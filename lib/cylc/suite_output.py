#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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
"""Redirect stdout and stderr to the suite logs."""

import os
import sys

from cylc.cfgspec.globalcfg import GLOBAL_CFG
from cylc.suite_logging import OUT


class SuiteOutput(object):
    """Redirects stdout and stderr to the out, err files in the suite logging
    directory."""

    def __init__(self, suite):
        sodir = GLOBAL_CFG.get_derived_host_item(suite, 'suite log directory')
        self.opath = os.path.join(sodir, 'out')
        self.epath = os.path.join(sodir, 'err')

    def get_path(self, err=False):
        """Returns the path to the suite 'out' file or 'err' if err=True."""
        if err:
            return self.epath
        else:
            return self.opath

    def redirect(self):
        """redirect the standard file descriptors to suite log files."""
        # record current standard file descriptors
        self.sys_stdout = sys.stdout
        self.sys_stderr = sys.stderr
        self.sys_stdin = sys.stdin

        # redirect standard file descriptors
        # note that simply reassigning the sys streams is not sufficient
        # if we import modules that write to stdin and stdout from C
        # code - evidently the subprocess module is in this category!
        sout = file(self.opath, 'a+', 0)  # 0 => unbuffered
        serr = file(self.epath, 'a+', 0)
        dvnl = file('/dev/null', 'r')
        os.dup2(sout.fileno(), sys.stdout.fileno())
        os.dup2(serr.fileno(), sys.stderr.fileno())
        os.dup2(dvnl.fileno(), sys.stdin.fileno())

    def restore(self):
        """Restores stdout, err to their normal output."""
        # (not used)
        sys.stdout.close()
        sys.stderr.close()
        sys.stdout = self.sys_stdout
        sys.stderr = self.sys_stderr
        sys.stdin = self.sys_stdin
        OUT.info("Restored stdout and stderr to normal")
