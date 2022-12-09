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

"""Turn a cylc scheduler into a Unix daemon."""

import json
import os
import sys
from time import sleep, time

from cylc.flow.pathutil import get_workflow_run_scheduler_log_path

WORKFLOW_INFO_TMPL = (
    "%(workflow)s: %(host)s PID=%(pid)s\n"
)

_TIMEOUT = 300.0  # 5 minutes


def daemonize(schd):
    """Turn a cylc scheduler into a Unix daemon.

    Do the UNIX double-fork magic, see Stevens' "Advanced Programming in the
    UNIX Environment" for details (ISBN 0201563177)

    ATTRIBUTION: base on a public domain code recipe by Jurgen Hermann:
    https://web.archive.org/web/20220129150926/http://code.activestate.com/
    recipes/66012-fork-a-daemon-process-on-unix/

    """
    logfname = get_workflow_run_scheduler_log_path(schd.workflow)
    try:
        old_log_mtime = os.stat(logfname).st_mtime
    except OSError:
        old_log_mtime = None
    # fork 1
    try:
        pid = os.fork()
        if pid > 0:
            # Poll for workflow log to be populated
            workflow_pid = None
            workflow_url = None
            pub_url = None
            timeout = time() + _TIMEOUT
            while time() <= timeout and (
                    workflow_pid is None or
                    workflow_url is None or
                    pub_url is None):
                sleep(0.1)
                try:
                    # First INFO line of workflow log should contain
                    # start up message, URL and PID. Format is:
                    #  LOG-PREFIX Workflow schd program: url=URL, pid=PID
                    # Otherwise, something is wrong, print the workflow log
                    # and exit with an error.
                    log_stat = os.stat(logfname)
                    if (log_stat.st_mtime == old_log_mtime or
                            log_stat.st_size == 0):
                        continue
                    with open(logfname, 'r') as logfile:
                        for line in logfile:
                            if schd.START_MESSAGE_PREFIX in line:
                                workflow_url, workflow_pid = (
                                    item.rsplit("=", 1)[-1]
                                    for item in line.rsplit()[-2:])
                            if schd.START_PUB_MESSAGE_PREFIX in line:
                                pub_url = line.rsplit("=", 1)[-1].rstrip()
                            if workflow_url and pub_url:
                                break
                            elif ' ERROR -' in line or ' CRITICAL -' in line:
                                # ERROR and CRITICAL before workflow starts
                                try:
                                    with open(logfname, 'r') as logfile2:
                                        sys.stderr.write(logfile2.read())
                                    sys.exit(1)
                                except IOError:
                                    sys.exit("Workflow schd program exited")
                except (OSError, ValueError):
                    pass
            if workflow_pid is None or workflow_url is None:
                sys.exit("Workflow not started after %ds" % _TIMEOUT)
            # Print workflow information
            info = {
                "workflow": schd.workflow,
                "host": schd.host,
                "url": workflow_url,
                "pub_url": pub_url,
                "pid": workflow_pid
            }
            if schd.options.format == 'json':
                sys.stdout.write(json.dumps(info, indent=4))
            else:
                sys.stdout.write(WORKFLOW_INFO_TMPL % info)
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
    dvnl = open(os.devnull, 'r')  # noqa: SIM115 (keep devnull open until exit)
    os.dup2(dvnl.fileno(), sys.stdin.fileno())
