#!/usr/bin/env python3

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

""" A wrapper function to aggregate these calls in one file.
    Bandit B602: subprocess_popen_with_shell_equals_true
    https://docs.openstack.org/developer/bandit/plugins/subprocess_popen_with_shell_equals_true.html
    B605: start_process_with_a_shell
    https://docs.openstack.org/developer/bandit/plugins/start_process_with_a_shell.html
"""
from shlex import split
from subprocess import PIPE, STDOUT, Popen  # nosec

# pylint: disable=too-many-arguments
# pylint: disable=too-many-locals


def procopen(cmd, bufsize=0, executable=None, stdin=None, stdout=None,
             stderr=None, preexec_fn=None, close_fds=False, usesh=False,
             cwd=None, env=None, universal_newlines=False, startupinfo=None,
             creationflags=0, splitcmd=False, stdoutpipe=False,
             stdoutout=False, stderrpipe=False, stderrout=False):

    shell = usesh

    if stdoutpipe is True:
        stdout = PIPE
    elif stdoutout is True:
        stdout = STDOUT
    if stderrpipe is True:
        stderr = PIPE
    elif stderrout is True:
        stderr = STDOUT

    if splitcmd is True:
        command = split(cmd)
    else:
        command = cmd

    process = Popen(command, bufsize, executable, stdin, stdout,  # nosec
                    stderr, preexec_fn, close_fds, shell, cwd, env,
                    universal_newlines, startupinfo, creationflags)

    return process
