#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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
"""Utility function to evaluate a task host string."""


import os
import re
from cylc.cfgspec.globalcfg import GLOBAL_CFG
from cylc.run_get_stdout import run_get_stdout
from cylc.suite_host import is_remote_host


REC_COMMAND = re.compile(r"(`|\$\()\s*(.*)\s*(`|\))$")
REC_ENVIRON = re.compile(r"^\$\{{0,1}(\w+)\}{0,1}$")


class HostSelectError(Exception):
    """Exception raised when "get_task_host" fails."""

    FMT = "Host selection by %(host)s failed:\n  %(mesg)s"

    def __str__(self):
        host, mesg = self.args
        return self.FMT % {"host": host, "mesg": mesg}


def get_task_host(cfg_item):
    """Evaluate a task host string.

    E.g.:

    [runtime]
        [[NAME]]
            [[[remote]]]
                host = cfg_item

    cfg_item -- An explicit host name, a command in back-tick or $(command)
                format, or an environment variable holding a hostname.

    Return "localhost" if cfg_item is not defined or if the evaluated host name
    is equivalent to "localhost". Otherwise, return the evaluated host name on
    success.

    """

    host = cfg_item

    if not host:
        return "localhost"

    # 1) host selection command: $(command) or `command`
    match = REC_COMMAND.match(host)
    if match:
        # extract the command and execute it
        hs_command = match.groups()[1]
        timeout = GLOBAL_CFG.get(["task host select command timeout"])
        is_ok, outlines = run_get_stdout(hs_command, timeout)
        if is_ok:
            # host selection command succeeded
            host = outlines[0]
        else:
            # host selection command failed
            raise HostSelectError(host, "\n".join(outlines))

    # 2) environment variable: ${VAR} or $VAR
    # (any quotes are stripped by file parsing)
    match = REC_ENVIRON.match(host)
    if match:
        name = match.groups()[0]
        try:
            host = os.environ[name]
        except KeyError, exc:
            raise HostSelectError(host, "Variable not defined: " + str(exc))
    try:
        if is_remote_host(host):
            return host
        else:
            return "localhost"
    except:
        return host
