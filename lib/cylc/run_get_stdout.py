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
"""Provide a utility function to get STDOUT from a shell command."""


from os import killpg, setpgrp
from signal import SIGTERM
from subprocess import Popen, PIPE
from time import sleep, time


POLL_DELAY = 0.1


def run_get_stdout(command, timeout=None, poll_delay=None):
    """Get standard output from a shell command.

    If "timeout" is specified, it should be the number of seconds before
    timeout.  On timeout, the command will be killed. The argument "poll_delay"
    is only relevant if "timeout" is specified. It specifies the intervals in
    number of seconds between polling for the completion of the command.

    Return (True, [stdoutline1, ...]) on success.
    Return (False, [err_msg, command]) on failure.

    """
    try:
        popen = Popen(
            command, shell=True, preexec_fn=setpgrp, stderr=PIPE, stdout=PIPE)
        if timeout:
            if poll_delay is None:
                poll_delay = POLL_DELAY
            timeout_time = time() + timeout
            while popen.poll() is None:
                if time() > timeout_time:
                    killpg(popen.pid, SIGTERM)
                    break
                sleep(poll_delay)
        out, err = popen.communicate()
        res = popen.wait()
        if res < 0:
            msg = "ERROR: command terminated by signal %d\n%s" % (res, err)
            return (False, [msg, command])
        elif res > 0:
            msg = "ERROR: command failed %d\n%s" % (res, err)
            return (False, [msg, command])
    except OSError:  # should never do this with shell=True
        msg = "ERROR: command invocation failed"
        return (False, [msg, command])
    else:
        return (True, out.strip().splitlines())
