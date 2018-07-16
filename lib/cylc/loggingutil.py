#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & Contributors.
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
"""Logging utilities.

This module provides:
- A custom rolling file handler for suite logs with date-time names.
- A formatter with ISO date time and indented multi-line messages.
  Note: The ISO date time bit is reducndant in Python 3,
  because "time.strftime" will handle time zone from "localtime" properly.
"""

import os
import sys
from glob import glob
import logging
import logging.handlers


from cylc.cfgspec.glbl_cfg import glbl_cfg
from cylc.mkdir_p import mkdir_p
from cylc.wallclock import (
    get_current_time_string, get_time_string_from_unix_time)


class CylcLogFormatter(logging.Formatter):
    """Format log record in standard Cylc way.

    Message in '%(asctime)s %(levelname)-2s - %(message)s' format.
    Indent continuation in multi-line messages.
    Date time in ISO date time with correct time zone.
    """

    def __init__(self):
        logging.Formatter.__init__(
            self,
            '%(asctime)s %(levelname)-2s - %(message)s',
            '%Y-%m-%dT%H:%M:%S%Z')

    def format(self, record):
        """Indent continuation lines in multi-line messages."""
        text = logging.Formatter.format(self, record)
        return '\t'.join(text.splitlines(True))

    def formatTime(self, record, datefmt=None):
        """Formats the record time as an ISO date time with correct time zone.

        Note: This should become redundant in Python 3, because
        "time.strftime" will handle time zone from "localtime" properly.
        """
        return get_time_string_from_unix_time(record.created)


class TimestampRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """Rotating suite logs using creation time stamps for names.

    Argument:
        suite (str): suite name
        no_detach (bool): non-detach mode? (Default=False)
    """

    GLBL_KEY = 'suite logging'

    def __init__(self, suite, no_detach=False):
        logging.handlers.RotatingFileHandler.__init__(
            self,
            glbl_cfg().get_derived_host_item(suite, 'suite log'),
            maxBytes=glbl_cfg().get(
                [self.GLBL_KEY, 'maximum size in bytes']),
            backupCount=glbl_cfg().get(
                [self.GLBL_KEY, 'rolling archive length']))
        self.no_detach = no_detach
        self.stamp = None
        self.formatter = CylcLogFormatter()

    def shouldRollover(self, record):
        """Create file if necessary."""
        return (
            self.stamp is None or
            logging.handlers.RotatingFileHandler.shouldRollover(self, record))

    def doRollover(self):
        """Create log file if necessary."""
        # Generate new file name
        self.stamp = get_current_time_string(use_basic_format=True)
        filename = self.baseFilename + '.' + self.stamp
        mkdir_p(os.path.dirname(filename))
        # Touch file
        with open(filename, 'w+'):
            os.utime(filename, None)
        # Update symlink
        if (os.path.exists(self.baseFilename) or
                os.path.lexists(self.baseFilename)):
            os.unlink(self.baseFilename)
        os.symlink(os.path.basename(filename), self.baseFilename)
        # Housekeep log files
        if self.backupCount:
            log_files = glob(self.baseFilename + '.*')
            log_files.sort()
            while len(log_files) > self.backupCount:
                os.unlink(log_files.pop(0))
        # Reopen stream, redirect STDOUT and STDERR to log
        if self.stream:
            self.stream.close()
            self.stream = None
        self.stream = self._open()
        if not self.no_detach:
            os.dup2(self.stream.fileno(), sys.stdout.fileno())
            os.dup2(self.stream.fileno(), sys.stderr.fileno())
