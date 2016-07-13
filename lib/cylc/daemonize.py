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
from cylc.suite_output import SuiteOutput


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


def daemonize(server):
    """Turn a cylc scheduler into a Unix daemon.

    Do the UNIX double-fork magic, see Stevens' "Advanced Programming in the
    UNIX Environment" for details (ISBN 0201563177)

    ATTRIBUTION: base on a public domain code recipe by Jurgen Hermann:
    http://code.activestate.com/recipes/66012-fork-a-daemon-process-on-unix/

    """

    sout = SuiteOutput(server.suite)

    try:
        pid = os.fork()
        if pid > 0:
            # exit first parent
            sys.exit(0)
    except OSError, exc:
        sys.stderr.write(
            "fork #1 failed: %d (%s)\n" % (exc.errno, exc.strerror))
        sys.exit(1)

    # decouple from parent environment
    os.chdir("/")
    os.setsid()
    os.umask(0)

    # do second fork
    try:
        pid = os.fork()
        if pid > 0:
            # exit from second parent, print eventual PID before
            sys.stdout.write(_INFO_TMPL % {
                "suite": server.suite,
                "host": server.host,
                "port": server.port,
                "pid": pid,
                "logd": os.path.dirname(sout.get_path())})
            sys.exit(0)
    except OSError, exc:
        sys.stderr.write(
            "fork #2 failed: %d (%s)\n" % (exc.errno, exc.strerror))
        sys.exit(1)

    # reset umask, octal
    os.umask(022)

    # redirect output to the suite log files
    sout.redirect()
