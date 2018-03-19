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
"""
Provides loggers for use by cylc suites.
"""
from __future__ import print_function

import glob
import logging
import logging.handlers
import os
import sys
from time import time


from cylc.cfgspec.glbl_cfg import glbl_cfg
import cylc.flags
from cylc.wallclock import (get_time_string_from_unix_time,
                            get_current_time_string)


LOG_DELIMITER = '.'


def get_logs(directory, basename, absolute_path=True):
    """Returns a list of log files is the given directory for the provided
    basename (i.e. log, err, out) ordered newest to oldest."""
    log_files = glob.glob(os.path.join(directory,
                                       basename + LOG_DELIMITER + '*'))

    if LOG_DELIMITER != '.':
        old_logs = glob.glob(os.path.join(directory,
                                          basename + '.*'))
        new_logs = log_files
    else:
        old_logs = [log for log in log_files if len(log.split('.')[-1]) < 3]
        new_logs = [log for log in log_files if log not in old_logs]
    old_logs.sort()
    new_logs.sort(reverse=True)
    if absolute_path:
        return new_logs + old_logs
    else:
        return [os.path.basename(log) for log in new_logs + old_logs]


class StreamRedirectRoller(object):
    """Redirect a stream to a rolling file.

    Note that simply reassigning the sys streams is not sufficient
    if we import modules that write to stdin and stdout from C
    code - evidently the subprocess module is in this category!

    Args:
        stream (file): The stream to redirect.
        link_path (str): The path to the symlink pointing at the log file.

    """

    def __init__(self, stream, link_path):
        self.stream = stream
        self.path = link_path

    def doRollover(self):
        file_handle = file(self.path, 'a+', 0)  # 0 => unbuffered
        os.dup2(file_handle.fileno(), self.stream.fileno())


class RollingFileHandler(logging.handlers.BaseRotatingHandler):
    """A file handler for log files rotated by symlinking with support for
       synchronised rotating of multiple logs."""

    def __init__(self, filename, mode='a', maxBytes=0, encoding=None,
                 file_stamp_fcn=None, archive_length=None):
        logging.handlers.BaseRotatingHandler.__init__(
            self, filename, mode, encoding, 0)
        self.maxBytes = maxBytes
        self.archive_length = archive_length
        self.syncronised_group = None
        self.file_stamp_fcn = file_stamp_fcn

    def _gen_file_stamp(self):
        """Use time or self.file_stamp_fcn to generate file name."""
        if callable(self.file_stamp_fcn):
            return self.file_stamp_fcn()
        else:
            return ('%f' % time()).replace('.', '')

    def notifyRollover(self):
        """Notify this RollingFilehandler that its log file has been rolled.
        To be called on all other RollingFilehandlers if multiple
        RollingFilehandlers are working with the same file and one rolls."""
        self.stream = self._open()

    def doRollover(self, trigger=True, stamp=None):
        """Create new log file and point the symlink at it."""
        # Generate new file name.
        if not stamp:
            stamp = self._gen_file_stamp()
        filename = os.path.basename(self.baseFilename) + LOG_DELIMITER + stamp
        new_file = os.path.join(os.path.dirname(self.baseFilename), filename)
        self.touch(new_file)

        if self.stream:
            self.stream.close()
            self.stream = None

        # Update symlink.
        if os.path.exists(self.baseFilename):
            if os.path.islink(self.baseFilename):
                os.unlink(self.baseFilename)
            else:
                if os.path.getsize(self.baseFilename) != 0:
                    # File exists in place of link, is old legacy log system.
                    os.rename(self.baseFilename, self.baseFilename + '.0')
                else:
                    # File exists but is empty (has probably been created by
                    # BaseRotatingFileHandler) safe to remove.
                    os.remove(self.baseFilename)
        os.symlink(filename, self.baseFilename)

        self.stream = self._open()

        # Rollover synchronised logs.
        if self.syncronised_group and trigger:
            self.syncronised_group.broadcast_roll(self, False, stamp)

        # Housekeep log files.
        if not self.archive_length:
            return
        log_files = get_logs(os.path.dirname(self.baseFilename),
                             os.path.basename(self.baseFilename))
        if len(log_files) > self.archive_length:
            os.remove(log_files.pop())

    def shouldRollover(self, record):
        """Determines whether the log file would exceed the maximum size given
        the provided record entry."""
        if self.stream is None:  # delay was set...
            self.stream = self._open()
        if self.maxBytes > 0:  # are we rolling over?
            msg = "%s\n" % self.format(record)
            self.stream.seek(0, 2)  # due to non-posix-compliant Windows
            if self.stream.tell() + len(msg) >= self.maxBytes:
                return 1
        return 0

    def register_syncronised_group(self, group):
        """Register a RollingFileHandlerGroup instance representing a
        collection of synchronised logs. Only one group permitted."""
        if not isinstance(group, RollingFileHandlerGroup):
            return False
        self.syncronised_group = group

    @staticmethod
    def touch(filename):
        """Creates a blank file."""
        with open(filename, 'w+'):
            os.utime(filename, None)


class RollingFileHandlerGroup(object):
    """Represents a group of synchronised logs."""

    def __init__(self):
        self.handlers = {}
        self.stream_handlers = []
        self.duplicate_handlers = []

    def add(self, log):
        """Add a logging.Logger to this group."""
        if not isinstance(log, logging.Logger):
            return False
        for handler in log.handlers:
            if isinstance(handler, RollingFileHandler):
                if handler.baseFilename not in self.handlers:
                    self.handlers[handler.baseFilename] = handler
                else:
                    self.duplicate_handlers.append(handler)

    def add_stream(self, stream):
        """Add a file stream to this group"""
        self.stream_handlers.append(stream)

    def broadcast_roll(self, origin, *args):
        """Roll all other logs in this group, origin should be the
        RollingFileHandler instance that is calling this method."""
        for handler_dest, handler in self.handlers.iteritems():
            if handler_dest != origin.baseFilename:
                handler.doRollover(*args)
        for handler in self.duplicate_handlers:
            handler.notifyRollover()
        for handler in self.stream_handlers:
            handler.doRollover()

    def roll_all(self):
        """Roll all logs in this group. Call with origin = False to roll all
        files or origin=RollingFileHandler to exclude a particular file."""
        if self._elegible_for_rollover():
            for _, handler in self.handlers.iteritems():
                handler.doRollover()  # Handler will call self.broadcast_roll
                return True
        return False

    def _elegible_for_rollover(self):
        """Used to prevent rollover in the event that the log files are all
        empty."""
        not_link = []
        zero = []
        for handler_dest, _ in self.handlers.iteritems():
            if not os.path.exists(handler_dest):
                return True
            not_link.append(not os.path.islink(handler_dest))
            zero.append(os.path.getsize(handler_dest) == 0)
        if any(not_link):
            return True  # Rollover if log has not yet been rolled.
        if all(zero):
            return False  # Don't rollover if all logs empty
        return True


class SuiteLog(object):
    """Provides logging functionality for a cylc suite."""
    LOG = 'log'
    OUT = 'out'
    ERR = 'err'
    ALL_LOGS = [LOG, OUT, ERR]
    __INSTANCE = None

    def __init__(self, suite, test_params=None):
        if SuiteLog.__INSTANCE:
            raise Exception("Attempting to initiate a second singleton"
                            "instance.")

        self._group = None
        if not test_params:
            self.is_test = False
            self.max_bytes = glbl_cfg().get(
                ['suite logging', 'maximum size in bytes'])
            self.roll_at_startup = glbl_cfg().get(
                ['suite logging', 'roll over at start-up'])
            self.archive_length = glbl_cfg().get(
                ['suite logging', 'rolling archive length'])
        else:
            self.is_test = True
            self.max_bytes = test_params['max_bytes']
            self.roll_at_startup = test_params['roll_at_startup']
            self.archive_length = 4

        # Log paths.
        if test_params:
            self.ldir = test_params['ldir']
        else:
            self.ldir = glbl_cfg().get_derived_host_item(
                suite, 'suite log directory')
        self.log_paths = {}
        self.log_paths[self.LOG] = os.path.join(self.ldir, self.LOG)
        self.log_paths[self.OUT] = os.path.join(self.ldir, self.OUT)
        self.log_paths[self.ERR] = os.path.join(self.ldir, self.ERR)

        # The loggers.
        self.loggers = {}
        self.loggers[self.LOG] = None
        self.loggers[self.OUT] = None
        self.loggers[self.ERR] = None

        # File streams
        self.streams = []

        SuiteLog.__INSTANCE = self

    @classmethod
    def get_inst(cls, *args, **kwargs):
        """Return singleton instance."""
        if not cls.__INSTANCE:
            cls(*args, **kwargs)
        return cls.__INSTANCE

    def get_dir(self):
        """Returns the logging directory."""
        return self.ldir

    @staticmethod
    def get_dir_for_suite(suite):
        """Returns the logging directory for a given suite without setting up
        suite logging."""
        return glbl_cfg().get_derived_host_item(suite, 'suite log directory')

    def get_lines(self, log, prev_size, max_lines=10):
        """Read content from log file up to max_lines from prev_size."""
        if prev_size is None:
            prev_size = 0
        else:
            prev_size = int(prev_size)
        path = self.get_log_path(log)
        try:
            size = os.path.getsize(path)
        except (IOError, OSError):
            size = 0
        if size == prev_size:
            return "", prev_size
        try:
            handle = open(path, "r")
            handle.seek(prev_size)
            new_content = handle.read()
            handle.close()
        except (IOError, OSError):
            return "", prev_size
        new_content_lines = new_content.splitlines()[-int(max_lines):]
        return "\n".join(new_content_lines), size

    def get_log(self, log):
        """Return the requested logger."""
        if log in self.loggers:
            return self.loggers[log]

    @staticmethod
    def get_logs():
        """Return all loggers."""
        ret = []
        for log in SuiteLog.ALL_LOGS:
            ret.append(logging.getLogger(log))
        return tuple(ret)

    def get_log_path(self, log):
        """Return the path of the requested logger."""
        if log in self.loggers:
            return self.log_paths[log]

    def get_stamp(self):
        """Returns the current time stamp for logging."""
        if self.is_test:
            return get_current_time_string(True, True, True).replace('.', '-')
        else:
            return get_current_time_string(False, True, True)

    def pimp(self, detach=False, log_logger_level=None):
        """Initiate the suite logs."""
        if not self.loggers[self.LOG]:
            # Don't initiate logs if they exist already.
            self._create_logs(detach, log_logger_level=log_logger_level)
            self._register_syncronised_logs()
            self._group.roll_all()
        elif self.roll_at_startup:
            self._group.roll_all()

    def _create_logs(self, detach, log_logger_level=None):
        """Sets up the log files and their file handlers."""
        # Logging formatters.
        # plain_formatter = logging.Formatter('%(message)s')
        if self.is_test:
            iso8601_formatter = logging.Formatter(
                '<TIME> %(levelname)-2s - %(message)s')
        else:
            iso8601_formatter = ISO8601DateTimeFormatter(
                '%(asctime)s %(levelname)-2s - %(message)s',
                '%Y-%m-%dT%H:%M:%S')

        # Multi-line filters.
        multi_line_indented_filter = MultiLineFilter('\n\t')

        # Level
        if log_logger_level is None:
            if cylc.flags.debug:
                log_logger_level = logging.DEBUG
            elif cylc.flags.verbose:
                log_logger_level = logging.DEBUG
            else:
                log_logger_level = logging.INFO
        # --- Create the 'log' logger. ---
        log = logging.getLogger(self.LOG)
        self.loggers[self.LOG] = log
        log.setLevel(log_logger_level)
        log.addFilter(multi_line_indented_filter)

        # Output to the 'log' file.
        log_fh = RollingFileHandler(self.log_paths[self.LOG],
                                    mode='a',
                                    maxBytes=self.max_bytes,
                                    archive_length=self.archive_length,
                                    file_stamp_fcn=self.get_stamp)
        log_fh.setLevel(log_logger_level)
        log_fh.setFormatter(iso8601_formatter)
        log.addHandler(log_fh)

        # Output errors to the 'err' file.
        log_err_fh = RollingFileHandler(self.log_paths[self.ERR],
                                        mode='a',
                                        maxBytes=self.max_bytes,
                                        archive_length=self.archive_length,
                                        file_stamp_fcn=self.get_stamp)
        log_err_fh.setLevel(logging.WARNING)
        log_err_fh.setFormatter(iso8601_formatter)
        log.addHandler(log_err_fh)

        # --- Create the 'out' logger. ---
        out = logging.getLogger(self.OUT)
        self.loggers[self.OUT] = out
        out.setLevel(log_logger_level)

        # Output to the 'out' file.
        out_fh = RollingFileHandler(self.log_paths[self.OUT],
                                    mode='a',
                                    maxBytes=self.max_bytes,
                                    archive_length=self.archive_length,
                                    file_stamp_fcn=self.get_stamp)
        out_fh.setLevel(log_logger_level)
        out_fh.setFormatter(iso8601_formatter)
        out.addHandler(out_fh)

        # --- Create the 'err' logger. ---
        err = logging.getLogger(self.ERR)
        self.loggers[self.ERR] = err
        err.setLevel(log_logger_level)
        err.addFilter(multi_line_indented_filter)

        # Output to the 'err' file.
        err_fh = RollingFileHandler(self.log_paths[self.ERR],
                                    mode='a',
                                    maxBytes=self.max_bytes,
                                    file_stamp_fcn=self.get_stamp)
        err_fh.setLevel(log_logger_level)
        err_fh.setFormatter(iso8601_formatter)
        err.addHandler(err_fh)

        if detach:
            # If we are in detached mode redirect stdout/stderr to the logs.
            self.streams = [
                StreamRedirectRoller(sys.stdout, self.log_paths[self.OUT]),
                StreamRedirectRoller(sys.stderr, self.log_paths[self.ERR])
            ]
        else:
            # If we are not in detached mode redirect the logs to
            # stdout/stderr:

            # LOG: warnings or higher -> stderr
            log_stderr_fh = logging.StreamHandler(sys.stderr)
            log_stderr_fh.setLevel(log_logger_level)
            log_stderr_fh.setFormatter(iso8601_formatter)
            log.addHandler(log_stderr_fh)
            # OUT: info or higher -> stdout
            out_stdout_fh = logging.StreamHandler(sys.stdout)
            out_stdout_fh.setLevel(log_logger_level)
            out_stdout_fh.setFormatter(iso8601_formatter)
            out.addHandler(out_stdout_fh)
            # ERR: warnings or higher -> stderr
            err_stderr_fh = logging.StreamHandler(sys.stderr)
            err_stderr_fh.setLevel(log_logger_level)
            err_stderr_fh.setFormatter(iso8601_formatter)
            err.addHandler(err_stderr_fh)

    def _register_syncronised_logs(self):
        """Establishes synchronisation between the logs."""
        self._group = RollingFileHandlerGroup()
        for log in (self.loggers[log_name] for log_name in self.ALL_LOGS):
            self._group.add(log)
            for handler in log.handlers:
                if isinstance(handler, RollingFileHandler):
                    handler.register_syncronised_group(self._group)
        for stream in self.streams:
            self._group.add_stream(stream)


class ISO8601DateTimeFormatter(logging.Formatter):
    """Format date/times with the correct time zone."""

    def formatTime(self, record, datefmt=None):
        """Formats the time as an iso8601 datetime."""
        return get_time_string_from_unix_time(record.created)


class MultiLineFilter(logging.Filter):
    """Formats multi-line log messages."""

    def __init__(self, trailing_line_prefix):
        self.trailing_line_prefix = trailing_line_prefix
        logging.Filter.__init__(self)

    def filter(self, record):
        """Prefixes trailing lines using trailing_line_prefix."""
        lines = str(record.msg).split('\n')
        record.msg = self.trailing_line_prefix.join(lines)
        return logging.Filter.filter(self, record)


class STDLogger(object):
    """Stand-in for the OUT, ERR loggers which logs messages to the out, err
    logs if present otherwise to stdout, stderr.
    For use in code which can be run be run within a suite or standalone.
    If used with the LOG logger then output will only be printed if suite
    logging has been set up."""

    def __init__(self, log):
        if log not in SuiteLog.ALL_LOGS:
            raise Exception('Unknown logger provided "{0}"'.format(log))
        self.log_ = log
        self.logger = logging.getLogger(log)
        self.update_time = time()

    def log(self, level, *args, **kwargs):
        try:
            itask = kwargs.pop("itask")
        except KeyError:
            pass
        else:
            try:
                args = ("[%s] -%s" % (itask.identity, args[0]),) + args[1:]
            except AttributeError:
                args = ("[%s] -%s" % (itask, args[0]),) + args[1:]
            args = tuple(args)
        self.update_time = time()
        if self.logger.handlers:
            # If this logger has file handlers write out to it.
            self.logger.log(level, *args, **kwargs)
        else:
            # No file handlers, write out to stdout/stderr.
            msg = (get_current_time_string() + ' ' +
                   logging._levelNames[level] + ' - ' +
                   str(args[0]),) + tuple(*args[1:])
            if self.log_ in [SuiteLog.OUT, SuiteLog.LOG]:
                print(*msg)
            else:
                print(*msg, file=sys.stderr)

    def debug(self, msg, *args, **kwargs):
        self.log(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self.log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.log(logging.WARNING, msg, *args, **kwargs)

    def warn(self, msg, *args, **kwargs):
        self.log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.log(logging.ERROR, msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self.log(logging.CRITICAL, msg, *args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        if self.logger.handlers:
            self.logger.exception(msg, *args, **kwargs)
        else:
            self.log(logging.ERROR, msg, *args, **kwargs)


# Loggers as constants for convenience.
OUT = STDLogger(SuiteLog.OUT)  # Log to suite if defined || print out.
ERR = STDLogger(SuiteLog.ERR)  # Log to suite if defined || print err.
LOG = STDLogger(SuiteLog.LOG)  # Log to suite if defined || print out.


def test_log_rolling(ldir):
    """Generates a collection of log files in the provided directory to test
    rolling functionality."""
    # Setup test logging.
    suite_log = SuiteLog.get_inst(None, {'ldir': ldir, 'max_bytes': 500,
                                         'roll_at_startup': True})

    # Populate logs.
    suite_log.pimp()
    log, out, err = SuiteLog.get_logs()
    for num in range(50):
        if num % 2 == 0:
            log.info('log-info-%02d' % num)
        if num % 5 == 0:
            log.error('log-err-%02d' % num)
        if num % 7 == 0:
            err.warning('err-warn-%02d' % num)
        if num % 3 == 0:
            out.info('out-info-%02d' % num)


def test_back_compat(ldir):
    """Generates a collection of log files in the provided directory to test
    back compatibility with the old logging system (i.e. log.1, log.2, ...)."""
    # Setup test logging.
    suite_log = SuiteLog.get_inst(None, {'ldir': ldir, 'max_bytes': 9999,
                                         'roll_at_startup': True})

    # Create legacy logging files.
    for file_ in ['log', 'out', 'err']:
        with open(os.path.join(ldir, file_), 'w') as log_file:
            log_file.write(file_ + ':')
    for file_ in ['log.1', 'out.1', 'err.1']:
        with open(os.path.join(ldir, file_), 'w') as log_file:
            log_file.write(file_ + '\n')

    # Populate logs.
    suite_log.pimp()
    log, out, err = SuiteLog.get_logs()
    log.info('log_new')
    err.warning('err_new')
    out.critical('out_new')

    # Force roll.
    suite_log.pimp()
    log.critical('log_rolled')
    err.error('err_rolled')
    out.warning('out_rolled')


def test_housekeeping(ldir):
    """Generates a collection of log files in the provided directory to test
    archive housekeeping functionality."""
    # Setup test logging.
    suite_log = SuiteLog.get_inst(None, {'ldir': ldir, 'max_bytes': 100,
                                         'roll_at_startup': True})

    # Create log files.
    suite_log.pimp()
    log = suite_log.get_log(SuiteLog.LOG)
    for num in range(25):
        log.info('log-%02d' % num)


if __name__ == '__main__':
    if sys.argv[2] == 'test-roll':
        test_log_rolling(os.path.join(sys.argv[1], 'test_roll'))
    elif sys.argv[2] == 'test-back-compat':
        test_back_compat(os.path.join(sys.argv[1], 'test_back_compat'))
    elif sys.argv[2] == 'test-housekeep':
        test_housekeeping(os.path.join(sys.argv[1], 'test_housekeep'))
