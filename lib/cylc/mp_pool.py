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
"""Manage queueing and pooling of subprocesses for the suite server program."""

from collections import deque
import os
from pipes import quote
from signal import SIGKILL
from subprocess import Popen, PIPE
from tempfile import TemporaryFile
from threading import RLock

from cylc.cfgspec.glbl_cfg import glbl_cfg
from cylc.suite_logging import LOG
from cylc.wallclock import get_current_time_string


class SuiteProcContext(object):
    """Represent the context of a command to run.

    Attributes:
        .cmd (list/str):
            The command to run expressed as a list (or as a str if shell=True
            is set in cmd_kwargs).
        .cmd_key (str):
            A key to identify the type of command. E.g. "jobs-submit".
        .cmd_kwargs (dict):
            Extra information about the command. This may contain:
                env (dict):
                    Specify extra environment variables for command.
                err (str):
                    Default STDERR content.
                out (str):
                    Default STDOUT content.
                ret_code (int):
                    Default return code.
                shell (boolean):
                    Launch command with "/bin/sh"?
                stdin_file_paths (list):
                    Files with content to send to command's STDIN.
                stdin_str (str):
                    Content to send to command's STDIN.
        .err (str):
            Content of the command's STDERR.
        .out (str)
            Content of the command's STDOUT.
        .ret_code (int):
            Return code of the command.
        .timestamp (str):
            Time string of latest update.
    """

    # Format string for single line output
    JOB_LOG_FMT_1 = '[%(cmd_key)s %(attr)s] %(mesg)s'
    # Format string for multi-line output
    JOB_LOG_FMT_M = '[%(cmd_key)s %(attr)s]\n%(mesg)s'

    def __init__(self, cmd_key, cmd, **cmd_kwargs):
        self.timestamp = get_current_time_string()
        self.cmd_key = cmd_key
        self.cmd = cmd
        self.cmd_kwargs = cmd_kwargs

        self.err = cmd_kwargs.get('err')
        self.ret_code = cmd_kwargs.get('ret_code')
        self.out = cmd_kwargs.get('out')

    def __str__(self):
        ret = ''
        for attr in 'cmd', 'ret_code', 'out', 'err':
            value = getattr(self, attr, None)
            if value is not None and str(value).strip():
                mesg = ''
                if attr == 'cmd' and self.cmd_kwargs.get('stdin_file_paths'):
                    mesg += 'cat'
                    for file_path in self.cmd_kwargs.get('stdin_file_paths'):
                        mesg += ' ' + quote(file_path)
                    mesg += ' | '
                if attr == 'cmd' and isinstance(value, list):
                    mesg += ' '.join(quote(item) for item in value)
                else:
                    mesg = str(value).strip()
                if attr == 'cmd' and self.cmd_kwargs.get('stdin_str'):
                    mesg += ' <<<%s' % quote(self.cmd_kwargs.get('stdin_str'))
                if len(mesg.splitlines()) > 1:
                    fmt = self.JOB_LOG_FMT_M
                else:
                    fmt = self.JOB_LOG_FMT_1
                if not mesg.endswith('\n'):
                    mesg += '\n'
                ret += fmt % {
                    'cmd_key': self.cmd_key,
                    'attr': attr,
                    'mesg': mesg}
        return ret.rstrip()


class SuiteProcPool(object):
    """Manage queueing and pooling of subprocesses.

    This is mainly used by the main loop of the suite server program, although
    the SuiteProcPool.run_command can be used as a standalone utility function
    to run the command in a SuiteProcContext.

    Arguments:
        size (int): Pool size.
    """

    ERR_SUITE_STOPPING = 'suite stopping, command not run'
    JOBS_SUBMIT = 'jobs-submit'
    RET_CODE_SUITE_STOPPING = 999

    def __init__(self, size=None):
        if not size:
            size = glbl_cfg().get(['process pool size'], size)
        self.size = size
        self.closed = False  # Close queue
        self.stopping = False  # No more job submit if True
        # .stopping may be set by an API command in a different thread
        self.stopping_lock = RLock()
        self.queuings = deque()
        self.runnings = []

    def close(self):
        """Close pool."""
        self.set_stopping()
        self.closed = True

    def is_not_done(self):
        """Return True if queuings or runnings not empty."""
        return self.queuings or self.runnings

    def _is_stopping(self):
        """Return True if .stopping is True."""
        stopping = False
        with self.stopping_lock:
            stopping = self.stopping
        return stopping

    def process(self):
        """Process done child processes and submit more."""
        # Handle child processes that are done
        runnings = []
        for proc, ctx, callback, callback_args in self.runnings:
            ret_code = proc.poll()
            if ret_code is None:
                runnings.append([proc, ctx, callback, callback_args])
            else:
                ctx.out, ctx.err = proc.communicate()
                ctx.ret_code = ret_code
                self._run_command_exit(ctx, callback, callback_args)
        # Update list of running items
        self.runnings[:] = runnings
        # Create more child processes, if items in queue and space in pool
        stopping = self._is_stopping()
        while self.queuings and len(self.runnings) < self.size:
            ctx, callback, callback_args = self.queuings.popleft()
            if stopping and ctx.cmd_key == self.JOBS_SUBMIT:
                ctx.err = self.ERR_SUITE_STOPPING
                ctx.ret_code = self.RET_CODE_SUITE_STOPPING
                self._run_command_exit(ctx)
            else:
                proc = self._run_command_init(ctx, callback, callback_args)
                if proc is not None:
                    self.runnings.append([proc, ctx, callback, callback_args])

    def put_command(self, ctx, callback=None, callback_args=None):
        """Queue a new shell command to execute.

        Arguments:
            ctx (SuiteProcContext):
                A context object containing the command to run and its status.
            callback (callable):
                Function to call back when command exits or on error.
                Should have signature:
                    callback(ctx, *callback_args) -> None
            callback_args (list):
                Extra arguments to the callback function.
        """
        if (self.closed or self._is_stopping() and
                ctx.cmd_key == self.JOBS_SUBMIT):
            ctx.err = self.ERR_SUITE_STOPPING
            ctx.ret_code = self.RET_CODE_SUITE_STOPPING
            self._run_command_exit(ctx, callback, callback_args)
        else:
            self.queuings.append([ctx, callback, callback_args])

    @classmethod
    def run_command(cls, ctx):
        """Execute command in ctx and capture its output and exit status.

        Arguments:
            ctx (SuiteProcContext):
                A context object containing the command to run and its status.
        """
        proc = cls._run_command_init(ctx)
        if proc:
            ctx.out, ctx.err = proc.communicate()
            ctx.ret_code = proc.wait()
            cls._run_command_exit(ctx)

    def set_stopping(self):
        """Stop job submission."""
        with self.stopping_lock:
            self.stopping = True

    def terminate(self):
        """Drain queue, and kill and process remaining child processes."""
        self.close()
        # Drain queue
        while self.queuings:
            ctx = self.queuings.popleft()[0]
            ctx.err = self.ERR_SUITE_STOPPING
            ctx.ret_code = self.RET_CODE_SUITE_STOPPING
            self._run_command_exit(ctx)
        # Kill remaining processes
        for value in self.runnings:
            proc = value[0]
            if proc:
                os.killpg(proc.pid, SIGKILL)
        # Wait for child processes
        self.process()

    @classmethod
    def _run_command_init(cls, ctx, callback=None, callback_args=None):
        """Prepare and launch shell command in ctx."""
        try:
            if ctx.cmd_kwargs.get('stdin_file_paths'):
                if len(ctx.cmd_kwargs['stdin_file_paths']) > 1:
                    stdin_file = TemporaryFile()
                    for file_path in ctx.cmd_kwargs['stdin_file_paths']:
                        stdin_file.write(open(file_path, 'rb').read())
                    stdin_file.seek(0)
                else:
                    stdin_file = open(
                        ctx.cmd_kwargs['stdin_file_paths'][0], 'rb')
            elif ctx.cmd_kwargs.get('stdin_str'):
                stdin_file = TemporaryFile()
                stdin_file.write(ctx.cmd_kwargs.get('stdin_str'))
                stdin_file.seek(0)
            else:
                stdin_file = open(os.devnull)
            proc = Popen(
                ctx.cmd, stdin=stdin_file, stdout=PIPE, stderr=PIPE,
                # Execute command as a process group leader,
                # so we can use "os.killpg" to kill the whole group.
                preexec_fn=os.setpgrp,
                env=ctx.cmd_kwargs.get('env'),
                shell=ctx.cmd_kwargs.get('shell'))
        except (IOError, OSError) as exc:
            if exc.filename is None:
                exc.filename = ctx.cmd[0]
            LOG.exception(exc)
            ctx.ret_code = 1
            ctx.err = str(exc)
            cls._run_command_exit(ctx, callback, callback_args)
            return None
        else:
            LOG.debug(ctx.cmd)
            return proc

    @classmethod
    def _run_command_exit(cls, ctx, callback=None, callback_args=None):
        """Process command completion."""
        ctx.timestamp = get_current_time_string()
        if callable(callback):
            if not callback_args:
                callback_args = []
            callback(ctx, *callback_args)
