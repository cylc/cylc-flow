#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & Contributors.
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

""" Function to sanitize input to a spawning subprocess where shell==True
    Bandit B602: subprocess_popen_with_shell_equals_true
    https://docs.openstack.org/developer/bandit/plugins/subprocess_popen_with_shell_equals_true.html
    REASON IGNORED:
    Cylc inherently requires shell characters so escaping them
    isn't possible.
"""
from inspect import getframeinfo, stack
from subprocess import Popen  # nosec

from cylc import LOG

# pylint: disable=too-many-arguments
# pylint: disable=too-many-locals


def pcylc(cmd, bufsize=0, executable=None, stdin=None, stdout=None,
          stderr=None, preexec_fn=None,
          close_fds=False, shell=False, cwd=None, env=None,
          universal_newlines=False, startupinfo=None, creationflags=0):

    caller = getframeinfo(stack()[1][0])
    LOG.debug("pcylc: calling function: {}".format(caller.function))
    LOG.debug("pcylc: caller: %s:%d" % (caller.filename, caller.lineno))
    LOG.debug("pcylc: command: {}".format(cmd))
    LOG.debug("pcylc: shell == : %r " % shell)

    process = Popen(cmd, bufsize, executable, stdin, stdout, stderr,  # nosec
                    preexec_fn, close_fds, shell, cwd, env, universal_newlines,
                    startupinfo, creationflags)

    return process
