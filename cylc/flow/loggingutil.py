# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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
- A custom rolling file handler for workflow logs with date-time names.
- A formatter with ISO date time and indented multi-line messages.
  Note: The ISO date time bit is redundant in Python 3,
  because "time.strftime" will handle time zone from "localtime" properly.
"""
from contextlib import suppress
from glob import glob
import logging
import os
from pathlib import Path
import re
import sys
import textwrap
from typing import List, Optional, Union

from ansimarkup import parse as cparse

from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.wallclock import get_time_string_from_unix_time


LOG_FILE_EXTENSION = '.log'
START_LOAD_TYPE = 'start'
RESTART_LOAD_TYPE = 'restart'


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
    #       daemonise script (url, pid) are not wrapped
    MAX_WIDTH = 999

    def __init__(
        self,
        timestamp: bool = True,
        color: bool = False,
        max_width: Optional[int] = None,
        dev_info: bool = False
    ) -> None:
        self.timestamp = None
        self.color = None
        self.max_width = self.MAX_WIDTH
        self.configure(timestamp, color, max_width)
        prefix = '%(asctime)s %(levelname)-2s - '
        if dev_info is True:
            prefix += '[%(module)s:%(lineno)d] - '

        logging.Formatter.__init__(
            self,
            prefix + '%(message)s',
            '%Y-%m-%dT%H:%M:%S%Z')

    def configure(self, timestamp=None, color=None, max_width=None):
        """Reconfigure the format settings."""
        if timestamp is not None:
            self.timestamp = timestamp
        if color is not None:
            self.color = color
        if max_width is not None:
            self.max_width = max_width

    def format(self, record):  # noqa: A003 (method name not local)
        """Indent continuation lines in multi-line messages."""
        text = logging.Formatter.format(self, record)
        if not self.timestamp:
            _, text = text.split(' ', 1)  # ISO8601 time points have no spaces
        if self.color and record.levelname in self.COLORS:
            text = self.COLORS[record.levelname].format(text)
        if self.max_width:
            return '\n'.join(
                line
                for part_num, part in enumerate(text.splitlines())
                for line in textwrap.wrap(
                    part,
                    width=self.max_width,
                    initial_indent='' if part_num == 0 else '    ',
                    subsequent_indent='    ',
                )
            )
        else:
            return '\n    '.join(text.splitlines())

    def formatTime(self, record, datefmt=None):
        """Formats the record time as an ISO date time with correct time zone.

        Note: This should become redundant in Python 3, because
        "time.strftime" will handle time zone from "localtime" properly.
        """
        return get_time_string_from_unix_time(record.created)


class RotatingLogFileHandler(logging.FileHandler):
    """Rotating workflow logs using cumulative log number and (re)start number
    for names.

    Argument:
        log_file_path: path to the log file
        no_detach: non-detach mode?
        restart_num: restart number for the run
        timestamp: Add timestamp to log formatting?
    """

    FILE_HEADER_FLAG = 'cylc_log_file_header'
    FILE_NUM = 'cylc_log_num'
    MIN_BYTES = 1024

    extra = {FILE_HEADER_FLAG: True}
    extra_num = {
        FILE_HEADER_FLAG: True,
        FILE_NUM: 1
    }

    def __init__(
        self,
        log_file_path: str,
        no_detach: bool = False,
        restart_num: int = 0,
        timestamp: bool = True,
    ):
        logging.FileHandler.__init__(self, log_file_path)
        self.no_detach = no_detach
        self.formatter = CylcLogFormatter(timestamp=timestamp)
        self.header_records: List[logging.LogRecord] = []
        self.restart_num = restart_num
        self.log_num: Optional[int] = None

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

    def load_type_change(self):
        """Has there been a load-type change, e.g. restart?"""
        current_load_type = self.get_load_type()
        existing_load_type = self.existing_log_load_type()
        # Rollover if the load type has changed.
        if existing_load_type and current_load_type != existing_load_type:
            return True
        return False

    def existing_log_load_type(self):
        """Return a log load type, if one currently exists"""
        try:
            existing_log_name = os.readlink(self.baseFilename)
        except OSError:
            return None
        # find load type, check restart first
        for load_type in [RESTART_LOAD_TYPE, START_LOAD_TYPE]:
            if existing_log_name.find(load_type) > 0:
                return load_type

    def should_rollover(self, record):
        """Should rollover?"""
        if (self.stream is None or
                self.load_type_change() or
                self.log_num is None):
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

    def get_load_type(self):
        """Establish current load type, as perceived by scheduler."""
        if self.restart_num > 0:
            return RESTART_LOAD_TYPE
        return START_LOAD_TYPE

    def do_rollover(self):
        """Create and rollover log file if necessary."""
        # Generate new file name
        filename = self.get_new_log_filename()
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
            self.update_log_archive(arch_len)
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
                # strip the hard coded log number (1) from the log message
                # replace with the log number for that start.
                # Note this is different from the log number in the file name
                # which is cumulative over the workflow.
                header_record.args = header_record.args[0:-1] + (
                    header_record.__dict__[self.FILE_NUM],)
            logging.FileHandler.emit(self, header_record)

    def update_log_archive(self, arch_len):
        """Maintain configured log file archive.
            - Sort logs by file modification time
            - Delete old log files in line with archive length configured in
              Global Config.
        """
        log_files = get_sorted_logs_by_time(
            Path(self.baseFilename).parent, f"*{LOG_FILE_EXTENSION}")
        while len(log_files) > arch_len:
            os.unlink(log_files.pop(0))

    def get_new_log_filename(self):
        """Build filename for log"""
        base_dir = Path(self.baseFilename).parent
        load_type = self.get_load_type()
        if load_type == START_LOAD_TYPE:
            run_num = 1
        elif load_type == RESTART_LOAD_TYPE:
            run_num = self.restart_num + 1
        self.set_log_num()
        filename = base_dir.joinpath(
            f'{self.log_num:02d}-{load_type}-{run_num:02d}{LOG_FILE_EXTENSION}'
        )
        return filename

    def set_log_num(self):
        if not self.log_num:
            try:
                current_log = os.readlink(self.baseFilename)
                self.log_num = int(get_next_log_number(current_log))
            except OSError:
                self.log_num = 1
        else:
            self.log_num = int(self.log_num) + 1


class ReferenceLogFileHandler(logging.FileHandler):
    """A handler class which writes filtered reference logging records
    to disk files.
    """

    REF_LOG_TEXTS = (
        'triggered off',
        'Initial point',
        'Start point',
        'Final point',
        'Start task'
    )
    """List of texts used for filtering messages."""

    def __init__(self, filename):
        """Create the reference log file handler, specifying the file to
        write the reference log lines."""
        with suppress(OSError):
            os.unlink(filename)
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


def disable_timestamps(logger: logging.Logger) -> None:
    """For readability omit timestamps from logging."""
    for handler in logger.handlers:
        if isinstance(handler.formatter, CylcLogFormatter):
            handler.formatter.configure(timestamp=False)


def setup_segregated_log_streams(
    logger: logging.Logger, stderr_handler: logging.StreamHandler
) -> None:
    """Set up a logger so that info and debug messages get printed to stdout,
    while warnings and above get printed to stderr.

    Args:
        logger: The logger to modify.
        stderr_handler: The existing stderr stream handler.
    """
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    # Filter out >= warnings from stdout
    stdout_handler.addFilter(lambda rec: int(rec.levelno < logging.WARNING))
    if stderr_handler.formatter:
        stdout_handler.setFormatter(stderr_handler.formatter)
    logger.addHandler(stdout_handler)

    stderr_handler.setLevel(logging.WARNING)


def close_log(logger: logging.Logger) -> None:
    """Close log handlers for the specified logger."""
    for handler in logger.handlers:
        with suppress(IOError):
            # suppress traceback which `logging` might try to write to the
            # log we are trying to close
            handler.close()


def get_next_log_number(log: str) -> str:
    """Returns the next log number for the log specified.

    Log name formats are of the form :
        <log number>-<load type>-<start number>
    When given the latest log it returns the next log number, with padded 0s.

    Examples:
        >>> get_next_log_number('01-restart-02.log')
            '02'
        >>> get_next_log_number('/some/path/to/19-start-20.cylc')
            '20'
        >>> get_next_log_number('199-start-08.log')
            '200'
        >>> get_next_log_number('blah')
            '01'
    """
    try:
        stripped_log = os.path.basename(log)
        next_log_num = int(stripped_log.partition("-")[0]) + 1
    except ValueError:
        next_log_num = 1
    return f'{next_log_num:02d}'


def get_sorted_logs_by_time(
    log_dir: Union[Path, str], pattern: str
) -> List[str]:
    """Returns time sorted logs from directory provided, filtered by pattern"""
    log_files = glob(os.path.join(log_dir, pattern))
    # Sort log files by modification time
    return sorted(log_files, key=os.path.getmtime)


def get_reload_start_number(config_logs: List[str]) -> str:
    """Find the start number, for reload config filename.
    """
    if not config_logs:
        return '01'
    else:
        try:
            latest_log = config_logs.pop(-1)
            start_num = int(
                latest_log.rpartition("-")[2].replace('.cylc', ''))
        except Exception:
            return '01'
        return f'{start_num:02d}'
