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

from contextlib import contextmanager, suppress
from glob import glob
import logging
import os
from pathlib import Path
import re
import sys
import textwrap
from time import time
from typing import List, Optional, Union

from ansimarkup import parse as cparse, strip as cstrip

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
        'CRITICAL': '<red><bold>{0}</bold></red>',
        'ERROR': '<red>{0}</red>',
        'WARNING': '<yellow>{0}</yellow>',
        'DEBUG': '<fg #888888>{0}</fg #888888>'
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
            text = cparse(self.COLORS[record.levelname].format(text))
        elif not self.color:
            text = cstrip(text)
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
        log_file_path: path to the log file (symlink to latest log file)
        no_detach: non-detach mode?
        restart_num: restart number for the run
        timestamp: Add timestamp to log formatting?
    """

    FILE_HEADER_FLAG = 'cylc_log_file_header'
    ROLLOVER_NUM = 'cylc_log_num'

    header_extra = {FILE_HEADER_FLAG: True}
    """Use to indicate the log msg is a header that should be logged on
    every rollover"""

    def __init__(
        self,
        log_file_path: Union[Path, str],
        no_detach: bool = False,
        restart_num: int = 0,
        timestamp: bool = True,
    ):
        logging.FileHandler.__init__(self, log_file_path)
        self.no_detach = no_detach
        self.formatter = CylcLogFormatter(timestamp=timestamp)
        # Header records get appended to when calling
        # `LOG.info(extra=RotatingLogFileHandler.[rollover_]header_extra)`:
        self.header_records: List[logging.LogRecord] = []
        self.restart_num = restart_num
        self.log_num: Optional[int] = None  # null value until log file created
        # Get & cache properties from global config (note: we should not access
        # the global config object when emitting log messages as as doing so
        # can have the side effect of expanding the global config):
        self.max_bytes: int = max(
            glbl_cfg().get(['scheduler', 'logging', 'maximum size in bytes']),
            1024  # Max size must be >= 1KB
        )
        self.arch_len: Optional[int] = glbl_cfg().get([
            'scheduler', 'logging', 'rolling archive length'
        ])

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

    def load_type_change(self) -> bool:
        """Has there been a load-type change, e.g. restart?"""
        existing_load_type = self.existing_log_load_type()
        if existing_load_type and self.load_type != existing_load_type:
            return True
        return False

    def existing_log_load_type(self) -> Optional[str]:
        """Return a log load type, if one currently exists"""
        try:
            existing_log_name = os.readlink(self.baseFilename)
        except OSError:
            return None
        # find load type, check restart first
        for load_type in [RESTART_LOAD_TYPE, START_LOAD_TYPE]:
            if existing_log_name.find(load_type) > 0:
                return load_type
        return None

    def should_rollover(self, record: logging.LogRecord) -> bool:
        """Should rollover?"""
        if self.log_num is None or self.stream is None:
            return True
        msg = "%s\n" % self.format(record)
        try:
            # due to non-posix-compliant Windows feature
            self.stream.seek(0, 2)
        except ValueError as exc:
            # intended to catch - ValueError: I/O operation on closed file
            raise SystemExit(exc) from None
        return self.stream.tell() + len(msg.encode('utf8')) >= self.max_bytes

    @property
    def load_type(self) -> str:
        """Establish current load type, as perceived by scheduler."""
        if self.restart_num > 0:
            return RESTART_LOAD_TYPE
        return START_LOAD_TYPE

    def do_rollover(self) -> None:
        """Create and rollover log file if necessary."""
        # Create new log file
        self.new_log_file()
        # Housekeep old log files
        if self.arch_len:
            self.update_log_archive(self.arch_len)
        # Reopen stream, redirect STDOUT and STDERR to log
        if self.stream:
            self.stream.close()
        self.stream = self._open()
        # Dup STDOUT and STDERR in detach mode
        if not self.no_detach:
            os.dup2(self.stream.fileno(), sys.stdout.fileno())
            os.dup2(self.stream.fileno(), sys.stderr.fileno())
        # Emit header records (should only do this for subsequent log files)
        for header_record in self.header_records:
            now = time()
            if self.ROLLOVER_NUM in header_record.__dict__:
                # A hack to increment the rollover number that gets logged in
                # the log file. (Rollover number only applies to a particular
                # workflow run; note this is different from the log count
                # number in the log filename.)

                header_record.__dict__[self.ROLLOVER_NUM] += 1
                header_record.args = (
                    header_record.__dict__[self.ROLLOVER_NUM],
                )

            # patch the record time (otherwise this will be logged with the
            # original timestamp)
            header_record.created = now

            logging.FileHandler.emit(self, header_record)

    def update_log_archive(self, arch_len: int) -> None:
        """Maintain configured log file archive.
            - Sort logs by file modification time
            - Delete old log files in line with archive length configured in
              Global Config.
        """
        log_files = get_sorted_logs_by_time(
            Path(self.baseFilename).parent, f"*{LOG_FILE_EXTENSION}")
        while len(log_files) > arch_len:
            os.unlink(log_files.pop(0))

    def new_log_file(self) -> Path:
        """Set self.log_num and create new log file."""
        try:
            log_file = os.readlink(self.baseFilename)
        except OSError:
            # "log" symlink not yet created, this is the first log
            self.log_num = 1
        else:
            self.log_num = get_next_log_number(log_file)
        log_dir = Path(self.baseFilename).parent
        # User-facing restart num is 1 higher than backend value
        restart_num = self.restart_num + 1
        filename = log_dir.joinpath(
            f'{self.log_num:02d}-{self.load_type}-{restart_num:02d}'
            f'{LOG_FILE_EXTENSION}'
        )
        os.makedirs(filename.parent, exist_ok=True)
        # Touch file
        with open(filename, 'w+'):
            os.utime(filename, None)
        # Update symlink
        if os.path.lexists(self.baseFilename):
            os.unlink(self.baseFilename)
        os.symlink(os.path.basename(filename), self.baseFilename)
        return filename


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
        log_string = cparse(sub.sub(repl, log_string))
    return log_string


def set_timestamps(logger: logging.Logger, enable: bool) -> None:
    """Enable or disable logging timestamps."""
    for handler in logger.handlers:
        if isinstance(handler.formatter, CylcLogFormatter):
            handler.formatter.configure(timestamp=enable)


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
    stdout_handler.addFilter(lambda rec: rec.levelno < logging.WARNING)
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


def get_next_log_number(log_filepath: Union[str, Path]) -> int:
    """Returns the next log number for the given log file path/name.

    Log name formats are of the form :
        <log number>-<load type>-<start number>
    When given the latest log it returns the next log number.

    Examples:
        >>> get_next_log_number('03-restart-02.log')
        4
        >>> get_next_log_number('/some/path/to/19-start-01.cylc')
        20
        >>> get_next_log_number('199-start-08.log')
        200
        >>> get_next_log_number('blah')
        1
    """
    try:
        stripped_log = os.path.basename(log_filepath)
        return int(stripped_log.partition("-")[0]) + 1
    except ValueError:
        return 1


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


@contextmanager
def patch_log_level(logger: logging.Logger, level: int = logging.INFO):
    """Temporarily patch the logging level of a logger if the specified level
    is less severe than the current level.

    Defaults to INFO.
    """
    orig_level = logger.level
    if level < orig_level:
        logger.setLevel(level)
        yield
        logger.setLevel(orig_level)
    else:  # No need to patch
        yield
