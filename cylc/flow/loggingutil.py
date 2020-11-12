# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
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
  Note: The ISO date time bit is redundant in Python 3,
  because "time.strftime" will handle time zone from "localtime" properly.
"""
import os
import re
import sys
import logging
import textwrap

from glob import glob
from functools import partial

from ansimarkup import parse as cparse

from cylc.flow.wallclock import (get_current_time_string,
                                 get_time_string_from_unix_time)
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg


class CylcLogFormatter(logging.Formatter):
    """Format log record in standard Cylc way.

    Message in '%(asctime)s %(levelname)-2s - %(message)s' format.
    Indent continuation in multi-line messages.
    Date time in ISO date time with correct time zone.
    """

    COLORS = {
        'CRITICAL': cparse('<red><bold>{0}</bold></red>'),
        'ERROR': cparse('<red>{0}</red>'),
        'WARNING': cparse('<yellow>{0}</yellow>'),
        'DEBUG': cparse('<fg #888888>{0}</fg #888888>')
    }

    # default hard-coded max width for log entries
    # NOTE: this should be sufficiently long that log entries read by the
    #       deamonise script (url, pid) are not wrapped
    MAX_WIDTH = 999

    def __init__(self, timestamp=True, color=False, max_width=None):
        self.timestamp = None
        self.color = None
        self.max_width = self.MAX_WIDTH
        self.wrapper = None
        self.configure(timestamp, color, max_width)
        # You may find adding %(filename)s %(lineno)d are useful when debugging
        logging.Formatter.__init__(
            self,
            '%(asctime)s %(levelname)-2s - %(message)s',
            '%Y-%m-%dT%H:%M:%S%Z')

    def configure(self, timestamp=None, color=None, max_width=None):
        """Reconfigure the format settings."""
        if timestamp is not None:
            self.timestamp = timestamp
        if color is not None:
            self.color = color
        if max_width is not None:
            self.max_width = max_width
        if self.max_width is None:
            self.wrapper = lambda x: [x]
        else:
            self.wrapper = partial(textwrap.wrap, width=self.max_width)

    def format(self, record):
        """Indent continuation lines in multi-line messages."""
        text = logging.Formatter.format(self, record)
        if not self.timestamp:
            _, text = text.split(' ', 1)  # ISO8601 time points have no spaces
        if self.color and record.levelname in self.COLORS:
            text = self.COLORS[record.levelname].format(text)
        return '\n\t'.join((
            wrapped_line
            for line in text.splitlines()
            for wrapped_line in self.wrapper(line)
        ))

    def formatTime(self, record, datefmt=None):
        """Formats the record time as an ISO date time with correct time zone.

        Note: This should become redundant in Python 3, because
        "time.strftime" will handle time zone from "localtime" properly.
        """
        return get_time_string_from_unix_time(record.created)


class TimestampRotatingFileHandler(logging.FileHandler):
    """Rotating suite logs using creation time stamps for names.

    Argument:
        suite (str): suite name
        no_detach (bool): non-detach mode? (Default=False)
    """

    FILE_HEADER_FLAG = 'cylc_log_file_header'
    FILE_NUM = 'cylc_log_num'
    MIN_BYTES = 1024

    def __init__(self, log_file_path, no_detach=False, timestamp=True):
        logging.FileHandler.__init__(self, log_file_path)
        self.no_detach = no_detach
        self.stamp = None
        self.formatter = CylcLogFormatter(timestamp=timestamp)
        self.header_records = []

    def emit(self, record):
        """Emit a record, rollover log if necessary."""
        try:
            if self.should_rollover(record):
                self.do_rollover()
            if record.__dict__.get(self.FILE_HEADER_FLAG):
                self.header_records.append(record)
            logging.FileHandler.emit(self, record)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)

    def should_rollover(self, record):
        """Should rollover?"""
        if self.stamp is None or self.stream is None:
            return True
        max_bytes = glbl_cfg().get(
            ['scheduler', 'logging', 'maximum size in bytes'])
        if max_bytes < self.MIN_BYTES:  # No silly value
            max_bytes = self.MIN_BYTES
        msg = "%s\n" % self.format(record)
        try:
            # due to non-posix-compliant Windows feature
            self.stream.seek(0, 2)
        except ValueError as exc:
            # intended to catch - ValueError: I/O operation on closed file
            raise SystemExit(exc)
        return self.stream.tell() + len(msg.encode('utf8')) >= max_bytes

    def do_rollover(self):
        """Create and rollover log file if necessary."""
        # Generate new file name
        self.stamp = get_current_time_string(use_basic_format=True)
        filename = self.baseFilename + '.' + self.stamp
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        # Touch file
        with open(filename, 'w+'):
            os.utime(filename, None)
        # Update symlink
        if (os.path.exists(self.baseFilename) or
                os.path.lexists(self.baseFilename)):
            os.unlink(self.baseFilename)
        os.symlink(os.path.basename(filename), self.baseFilename)
        # Housekeep log files
        arch_len = glbl_cfg().get(
            ['scheduler', 'logging', 'rolling archive length'])
        if arch_len:
            log_files = glob(self.baseFilename + '.*')
            log_files.sort()
            while len(log_files) > arch_len:
                os.unlink(log_files.pop(0))
        # Reopen stream, redirect STDOUT and STDERR to log
        if self.stream:
            self.stream.close()
            self.stream = None
        self.stream = self._open()
        # Dup STDOUT and STDERR in detach mode
        if not self.no_detach:
            os.dup2(self.stream.fileno(), sys.stdout.fileno())
            os.dup2(self.stream.fileno(), sys.stderr.fileno())
        # Emit header records (should only do this for subsequent log files)
        for header_record in self.header_records:
            if self.FILE_NUM in header_record.__dict__:
                # Increment log file number
                header_record.__dict__[self.FILE_NUM] += 1
                header_record.args = header_record.args[0:-1] + (
                    header_record.__dict__[self.FILE_NUM],)
            logging.FileHandler.emit(self, header_record)


class ReferenceLogFileHandler(logging.FileHandler):
    """A handler class which writes filtered reference logging records
    to disk files.
    """

    REF_LOG_TEXTS = (
        'triggered off', 'Initial point', 'Start point', 'Final point')
    """List of texts used for filtering messages."""

    def __init__(self, filename):
        """Create the reference log file handler, specifying the file to
        write the reference log lines."""
        try:
            os.unlink(filename)
        except OSError:
            pass
        super().__init__(filename)
        self.formatter = logging.Formatter('%(message)s')
        self.addFilter(self._filter)

    def _filter(self, record):
        """Filter a logging record. From the base class Filterer (parent of
            logging.Handler).

            Args:
                record (logging.LogRecord): a log record.
            Returns:
                bool: True for message to be logged, False otherwise.
        """
        return any(text in record.getMessage() for text in self.REF_LOG_TEXTS)


LOG_LEVEL_REGEXES = [
    (
        re.compile(r'(^.*%s.*\n((^\t.*\n)+)?)' % level, re.M),
        replacement.format(r'\1')
    )
    for level, replacement in CylcLogFormatter.COLORS.items()
]


def re_formatter(log_string):
    """Read in an uncoloured log_string file and apply colour formatting."""
    for sub, repl in LOG_LEVEL_REGEXES:
        log_string = sub.sub(repl, log_string)
    return log_string
