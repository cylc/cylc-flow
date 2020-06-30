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

"""Turn a cylc scheduler into a Unix daemon."""

import json
import os
import sys
from time import sleep, time

from cylc.flow.pathutil import get_suite_run_log_name
from cylc.flow.suite_files import PS_OPTS


SUITE_SCAN_INFO_TMPL = r"""

To view suite server program contact information:
 $ cylc get-suite-contact %(suite)s

Other ways to see if the suite is still running:
 $ cylc scan -n '%(suite)s'
 $ cylc ping -v %(suite)s
 $ ssh %(host)s ps %(ps_opts)s %(pid)s
 $ cylc tui %(suite)s    # A terminal graphic UI

"""

_INFO_TMPL = r"""
*** listening on %(url)s ***
*** publishing on %(pub_url)s ***""" + SUITE_SCAN_INFO_TMPL


_TIMEOUT = 300.0  # 5 minutes


def daemonize(schd):
    """Turn a cylc scheduler into a Unix daemon.

    Do the UNIX double-fork magic, see Stevens' "Advanced Programming in the
    UNIX Environment" for details (ISBN 0201563177)

    ATTRIBUTION: base on a public domain code recipe by Jurgen Hermann:
    http://code.activestate.com/recipes/66012-fork-a-daemon-process-on-unix/

    """
    logfname = get_suite_run_log_name(schd.suite)
    try:
        old_log_mtime = os.stat(logfname).st_mtime
    except OSError:
        old_log_mtime = None
    # fork 1
    try:
        pid = os.fork()
        if pid > 0:
            # Poll for suite log to be populated
            suite_pid = None
            suite_url = None
            pub_url = None
            timeout = time() + _TIMEOUT
            while time() <= timeout and (
                    suite_pid is None or
                    suite_url is None or
                    pub_url is None):
                sleep(0.1)
                try:
                    # First INFO line of suite log should contain
                    # start up message, URL and PID. Format is:
                    #  LOG-PREFIX Suite schd program: url=URL, pid=PID
                    # Otherwise, something has gone wrong, print the suite log
                    # and exit with an error.
                    log_stat = os.stat(logfname)
                    if (log_stat.st_mtime == old_log_mtime or
                            log_stat.st_size == 0):
                        continue
                    for line in open(logfname):
                        if schd.START_MESSAGE_PREFIX in line:
                            suite_url, suite_pid = (
                                item.rsplit("=", 1)[-1]
                                for item in line.rsplit()[-2:])
                        if schd.START_PUB_MESSAGE_PREFIX in line:
                            pub_url = line.rsplit("=", 1)[-1].rstrip()
                        if suite_url and pub_url:
                            break
                        elif ' ERROR -' in line or ' CRITICAL -' in line:
                            # ERROR and CRITICAL before suite starts
                            try:
                                sys.stderr.write(open(logfname).read())
                                sys.exit(1)
                            except IOError:
                                sys.exit("Suite schd program exited")
                except (IOError, OSError, ValueError):
                    pass
            if suite_pid is None or suite_url is None:
                sys.exit("Suite not started after %ds" % _TIMEOUT)
            # Print suite information
            info = {
                "suite": schd.suite,
                "host": schd.host,
                "url": suite_url,
                "pub_url": pub_url,
                "ps_opts": PS_OPTS,
                "pid": suite_pid
            }
            if schd.options.format == 'json':
                sys.stdout.write(json.dumps(info, indent=4))
            else:
                sys.stdout.write(_INFO_TMPL % info)
            # exit parent 1
            sys.exit(0)
    except OSError as exc:
        sys.exit("fork #1 failed: %d (%s)\n" % (exc.errno, exc.strerror))

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
    except OSError as exc:
        sys.exit("fork #2 failed: %d (%s)\n" % (exc.errno, exc.strerror))

    # reset umask, octal
    os.umask(0o22)

    # Redirect /dev/null to stdin.
    # Note that simply reassigning the sys streams is not sufficient
    # if we import modules that write to stdin and stdout from C
    # code - evidently the subprocess module is in this category!
    # TODO: close resource? atexit?
    dvnl = open(os.devnull, 'r')
    os.dup2(dvnl.fileno(), sys.stdin.fileno())
