#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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
"""Utility for GUIs to call "cylc cat-state"."""

import os
import signal
from subprocess import Popen, PIPE
import sys

import cylc.flags


def cat_state(suite, host=None, owner=None):
    """Run "cylc cat-state", and return results."""
    cmd = ["cylc", "cat-state"]
    if host:
        cmd.append("--host=" + host)
    if owner:
        cmd.append("--user=" + owner)
    if cylc.flags.debug:
        stderr = sys.stderr
        cmd.append("--debug")
    else:
        stderr = PIPE
    cmd.append(suite)
    try:
        proc = Popen(
            cmd, stdin=open(os.devnull), stderr=stderr, stdout=PIPE,
            preexec_fn=os.setpgrp)
    except OSError:
        return []
    else:
        out = proc.communicate()[0]
        if proc.wait():  # non-zero return code
            return []
        return out.splitlines()
    finally:
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except OSError:
                pass
