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

"""Turn a cylc scheduler into a Unix daemon."""

import os
import sys
from time import sleep, time
from cylc.suite_logging import SuiteLog, SUITE_LOG


SUITE_SCAN_INFO_TMPL = r"""

To view suite server program contact information:
 $ cylc get-suite-contact %(suite)s

Other ways to see if the suite is still running:
 $ cylc scan -n '\b%(suite)s\b' %(host)s
 $ cylc ping -v --host=%(host)s %(suite)s
 $ ps %(ps_opts)s %(pid)s  # on %(host)s

"""

_INFO_TMPL = r"""
*** listening on %(host)s:%(port)s ***""" + SUITE_SCAN_INFO_TMPL

_TIMEOUT = 300.0  # 5 minutes


def daemonize(server):
    """Turn a cylc scheduler into a Unix daemon.

    Do the UNIX double-fork magic, see Stevens' "Advanced Programming in the
    UNIX Environment" for details (ISBN 0201563177)

    ATTRIBUTION: base on a public domain code recipe by Jurgen Hermann:
    http://code.activestate.com/recipes/66012-fork-a-daemon-process-on-unix/

    """
    logd = SuiteLog.get_dir_for_suite(server.suite)
    log_fname = os.path.join(logd, SUITE_LOG)
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
                    # Line 1 (or 2 in debug mode) of suite log should contain
                    # start up message, host name and port number. Format is:
                    #  LOG-PREFIX Suite starting: server=HOST:PORT, pid=PID
                    # Otherwise, something has gone wrong, print the suite log
                    # and exit with an error.
                    log_stat = os.stat(log_fname)
                    if (log_stat.st_mtime == old_log_mtime or
                            log_stat.st_size == 0):
                        continue
                    with open(log_fname) as log_f:
                        try:
                            first_two_lines = next(log_f), next(log_f)
                        except StopIteration:
                            continue
                    ok = False
                    for log_line in first_two_lines:
                        if server.START_MESSAGE_PREFIX in log_line:
                            ok = True
                            server_str, pid_str = log_line.rsplit()[-2:]
                            suite_pid = pid_str.rsplit("=", 1)[-1]
                            suite_port = server_str.rsplit(":", 1)[-1]
                    if not ok:
                        try:
                            sys.stderr.write(open(log_fname).read())
                            sys.exit(1)
                        except IOError:
                            sys.exit("Suite server program exited")
                except (IOError, OSError, ValueError):
                    pass
            if suite_pid is None or suite_port is None:
                sys.exit("Suite not started after %ds" % _TIMEOUT)
            # Print suite information
            sys.stdout.write(_INFO_TMPL % {
                "suite": server.suite,
                "host": server.host,
                "port": suite_port,
                "ps_opts": server.suite_srv_files_mgr.PS_OPTS,
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

    # Redirect /dev/null to stdin.
    # Note that simply reassigning the sys streams is not sufficient
    # if we import modules that write to stdin and stdout from C
    # code - evidently the subprocess module is in this category!
    dvnl = file(os.devnull, 'r')
    os.dup2(dvnl.fileno(), sys.stdin.fileno())
