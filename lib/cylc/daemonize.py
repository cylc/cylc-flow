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

"""Turn a cylc scheduler into a Unix daemon."""

import os
import sys
from time import sleep, time
from cylc.suite_logging import SuiteLog


SUITE_SCAN_INFO_TMPL = r"""

To see if '%(suite)s' is running on '%(host)s:%(port)s':
 * cylc scan -n '\b%(suite)s\b' %(host)s
 * cylc ping -v --host=%(host)s %(suite)s
 * ssh %(host)s "pgrep -a -P 1 -fu $USER 'cylc-r.* \b%(suite)s\b'"

"""


_INFO_TMPL = r"""
Suite Info:
 + Name: %(suite)s
 + PID: %(pid)s
 + Host: %(host)s
 + Port: %(port)s
 + Logs: %(logd)s/{log,out,err}""" + SUITE_SCAN_INFO_TMPL

_TIMEOUT = 300.0  # 5 minutes


def redirect(logd):
    """Redirect standard file descriptors

    Note that simply reassigning the sys streams is not sufficient
    if we import modules that write to stdin and stdout from C
    code - evidently the subprocess module is in this category!
    """
    sout = file(os.path.join(logd, SuiteLog.OUT), 'a+', 0)  # 0 => unbuffered
    serr = file(os.path.join(logd, SuiteLog.ERR), 'a+', 0)
    dvnl = file(os.devnull, 'r')
    os.dup2(sout.fileno(), sys.stdout.fileno())
    os.dup2(serr.fileno(), sys.stderr.fileno())
    os.dup2(dvnl.fileno(), sys.stdin.fileno())


def daemonize(server):
    """Turn a cylc scheduler into a Unix daemon.

    Do the UNIX double-fork magic, see Stevens' "Advanced Programming in the
    UNIX Environment" for details (ISBN 0201563177)

    ATTRIBUTION: base on a public domain code recipe by Jurgen Hermann:
    http://code.activestate.com/recipes/66012-fork-a-daemon-process-on-unix/

    """
    logd = SuiteLog.get_dir_for_suite(server.suite)
    log_fname = os.path.join(logd, SuiteLog.LOG)
    try:
        old_log_mtime = os.stat(log_fname).st_mtime
    except OSError:
        old_log_mtime = None
    # fork 1
    try:
        pid = os.fork()
        if pid > 0:
            # Poll for suite log to be populated
            suite_pid = None
            suite_port = None
            timeout = time() + _TIMEOUT
            while time() <= timeout and (
                    suite_pid is None or suite_port is None):
                sleep(0.1)
                try:
                    log_stat = os.stat(log_fname)
                    if (log_stat.st_mtime == old_log_mtime or
                            log_stat.st_size == 0):
                        continue
                    # Line 1 of suite log should contain start up message, host
                    # name and port number. Format is:
                    # LOG-PREIFX Suite starting: server=HOST:PORT, pid=PID
                    # Otherwise, something has gone wrong, print the suite log
                    # and exit with an error.
                    log_line1 = open(log_fname).readline()
                    if server.START_MESSAGE_PREFIX in log_line1:
                        server_str, pid_str = log_line1.rsplit()[-2:]
                        suite_pid = pid_str.rsplit("=", 1)[-1]
                        suite_port = server_str.rsplit(":", 1)[-1]
                    else:
                        try:
                            sys.stderr.write(open(log_fname).read())
                            sys.exit(1)
                        except IOError:
                            sys.exit("Suite daemon exited")
                except (IOError, OSError, ValueError):
                    pass
            if suite_pid is None or suite_port is None:
                sys.exit("Suite not started after %ds" % _TIMEOUT)
            # Print suite information
            sys.stdout.write(_INFO_TMPL % {
                "suite": server.suite,
                "host": server.host,
                "port": suite_port,
                "pid": suite_pid,
                "logd": logd,
            })
            # exit parent 1
            sys.exit(0)
    except OSError, exc:
        sys.stderr.write(
            "fork #1 failed: %d (%s)\n" % (exc.errno, exc.strerror))
        sys.exit(1)

    # decouple from parent environment
    os.chdir("/")
    os.setsid()
    os.umask(0)

    # fork 2
    try:
        pid = os.fork()
        if pid > 0:
            # exit parent 2
            sys.exit(0)
    except OSError, exc:
        sys.stderr.write(
            "fork #2 failed: %d (%s)\n" % (exc.errno, exc.strerror))
        sys.exit(1)

    # reset umask, octal
    os.umask(022)

    # redirect output to the suite log files
    redirect(logd)
