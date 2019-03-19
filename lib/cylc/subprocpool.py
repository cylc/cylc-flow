#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
import json
import os
import select
from signal import SIGKILL
import sys
from tempfile import SpooledTemporaryFile
from threading import RLock
from time import time

from cylc import LOG
from cylc.cfgspec.glbl_cfg import glbl_cfg
from cylc.cylc_subproc import procopen
from cylc.wallclock import get_current_time_string

_XTRIG_FUNCS = {}


def get_func(func_name, src_dir):
    """Find and return an xtrigger function from a module of the same name.

    Can be in <src_dir>/lib/python, CYLC_MOD_LOC, or in Python path.
    Suite source directory passed in because this is executed in an independent
    process in the command pool - and therefore doesn't know about the suite.

    """
    if func_name in _XTRIG_FUNCS:
        return _XTRIG_FUNCS[func_name]
    # First look in <src-dir>/lib/python.
    sys.path.insert(0, os.path.join(src_dir, 'lib', 'python'))
    mod_name = func_name
    try:
        mod_by_name = __import__(mod_name, fromlist=[mod_name])
    except ImportError:
        # Then look in built-in xtriggers.
        mod_name = "%s.%s" % ("cylc.xtriggers", func_name)
        try:
            mod_by_name = __import__(mod_name, fromlist=[mod_name])
        except ImportError:
            raise
    try:
        _XTRIG_FUNCS[func_name] = getattr(mod_by_name, func_name)
    except AttributeError:
        # Module func_name has no function func_name.
        raise
    return _XTRIG_FUNCS[func_name]


def run_function(func_name, json_args, json_kwargs, src_dir):
    """Run a Python function in the process pool.

    func_name(*func_args, **func_kwargs)

    Redirect any function stdout to stderr (and suite log in debug mode).
    Return value printed to stdout as a JSON string - allows use of the
    existing process pool machinery as-is. src_dir is for local modules.

    """
    func_args = json.loads(json_args)
    func_kwargs = json.loads(json_kwargs)
    # Find and import then function.
    func = get_func(func_name, src_dir)
    # Redirect stdout to stderr.
    orig_stdout = sys.stdout
    sys.stdout = sys.stderr
    res = func(*func_args, **func_kwargs)
    # Restore stdout.
    sys.stdout = orig_stdout
    # Write function return value as JSON to stdout.
    sys.stdout.write(json.dumps(res))


class SubProcPool(object):
    """Manage queueing and pooling of subprocesses.

    This is mainly used by the main loop of the suite server program, although
    the SubProcPool.run_command can be used as a standalone utility function
    to run the command in a cylc.subprocctx.SubProcContext.

    A command to run under a subprocess in the pool is expected to be wrapped
    using a cylc.subprocctx.SubProcContext object. The caller will add the
    context object using the SubProcPool.put_command method. A callback can
    be specified to notify the caller on exit of the subprocess.

    A command launched by the pool is expected to write to STDOUT and STDERR.
    These are captured while the command runs and/or when the command exits.
    The contents are appended to the `.out` and `.err` attributes of the
    SubProcContext object as they are read. STDIN can also be specified for the
    command. This is currently fed into the command using a temporary file.

    Note: For a cylc command that uses `cylc.option_parsers.CylcOptionParser`,
    the default logging handler writes to the STDERR via a StreamHandler.
    Therefore, log messages will only be written to the suite log by the
    callback function when the command exits (and only if the callback function
    has the logic to do so).

    """

    ERR_SUITE_STOPPING = 'suite stopping, command not run'
    JOBS_SUBMIT = 'jobs-submit'
    POLLREAD = select.POLLIN | select.POLLPRI
    RET_CODE_SUITE_STOPPING = 999

    def __init__(self):
        self.size = glbl_cfg().get(['process pool size'])
        self.proc_pool_timeout = glbl_cfg().get(['process pool timeout'])
        self.closed = False  # Close queue
        self.stopping = False  # No more job submit if True
        # .stopping may be set by an API command in a different thread
        self.stopping_lock = RLock()
        self.queuings = deque()
        self.runnings = []
        try:
            self.pipepoller = select.poll()
        except AttributeError:  # select.poll not implemented for this OS
            self.pipepoller = None

    def close(self):
        """Close pool."""
        self.set_stopping()
        self.closed = True

    @staticmethod
    def get_temporary_file():
        """Return a SpooledTemporaryFile for feeding data to command STDIN."""
        return SpooledTemporaryFile()

    def is_not_done(self):
        """Return True if queuings or runnings not empty."""
        return self.queuings or self.runnings

    def _is_stopping(self):
        """Return True if .stopping is True."""
        stopping = False
        with self.stopping_lock:
            stopping = self.stopping
        return stopping

    def _proc_exit(self, proc, err_xtra, ctx, callback, callback_args):
        """Get ret_code, out, err of exited command, and call its callback."""
        ctx.ret_code = proc.wait()
        out, err = (f.decode() for f in proc.communicate())
        if out:
            if ctx.out is None:
                ctx.out = ''
            ctx.out += out
        if err + err_xtra:
            if ctx.err is None:
                ctx.err = ''
            ctx.err += err + err_xtra
        self._run_command_exit(ctx, callback, callback_args)

    def process(self):
        """Process done child processes and submit more."""
        # Handle child processes that are done
        runnings = []
        for proc, ctx, callback, callback_args in self.runnings:
            # Command completed/exited
            if proc.poll() is not None:
                self._proc_exit(proc, "", ctx, callback, callback_args)
                continue
            # Command timed out, kill it
            if time() > ctx.timeout:
                try:
                    os.killpg(proc.pid, SIGKILL)  # kill process group
                except OSError:
                    # must have just exited, since poll.
                    err_xtra = ""
                else:
                    err_xtra = "\nkilled on timeout (%s)" % (
                        self.proc_pool_timeout)
                self._proc_exit(proc, err_xtra, ctx, callback, callback_args)
                continue
            # Command still running, see if STDOUT/STDERR are readable or not
            runnings.append([proc, ctx, callback, callback_args])
            # Unblock proc's STDOUT/STDERR if necessary. Otherwise, a full
            # STDOUT or STDERR may stop command from proceeding.
            self._poll_proc_pipes(proc, ctx)

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
                    ctx.timeout = time() + self.proc_pool_timeout
                    self.runnings.append([proc, ctx, callback, callback_args])

    def put_command(self, ctx, callback=None, callback_args=None):
        """Queue a new shell command to execute.

        Arguments:
            ctx (cylc.subprocctx.SubProcContext):
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
            ctx (cylc.subprocctx.SubProcContext):
                A context object containing the command to run and its status.
        """
        proc = cls._run_command_init(ctx)
        if proc:
            ctx.out, ctx.err = (f.decode() for f in proc.communicate())
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

    def _poll_proc_pipes(self, proc, ctx):
        """Poll STDOUT/ERR of proc and read some data if possible.

        This helps to unblock the command by unblocking its pipes.
        """
        if self.pipepoller is None:
            return  # select.poll not supported on this OS
        for handle in [proc.stdout, proc.stderr]:
            if not handle.closed:
                self.pipepoller.register(handle.fileno(), self.POLLREAD)
        while True:
            fileno_list = [
                fileno
                for fileno, event in self.pipepoller.poll(0.0)
                if event & self.POLLREAD]
            if not fileno_list:
                # Nothing readable
                break
            for fileno in fileno_list:
                # If a file handle is readable, read something from it, add
                # results into the command context object's `.out` or `.err`,
                # whichever is relevant. To avoid blocking:
                # 1. Use `os.read` here instead of `file.read` to avoid any
                #    buffering that may cause the file handle to block.
                # 2. Call os.read only once after a poll. Poll again before
                #    another read - otherwise the os.read call may block.
                try:
                    data = os.read(fileno, 65536).decode()  # 64K
                except OSError:
                    continue
                if fileno == proc.stdout.fileno():
                    if ctx.out is None:
                        ctx.out = ''
                    ctx.out += data
                elif fileno == proc.stderr.fileno():
                    if ctx.err is None:
                        ctx.err = ''
                    ctx.err += data
        self.pipepoller.unregister(proc.stdout.fileno())
        self.pipepoller.unregister(proc.stderr.fileno())

    @classmethod
    def _run_command_init(cls, ctx, callback=None, callback_args=None):
        """Prepare and launch shell command in ctx."""
        try:
            if ctx.cmd_kwargs.get('stdin_files'):
                if len(ctx.cmd_kwargs['stdin_files']) > 1:
                    stdin_file = cls.get_temporary_file()
                    for file_ in ctx.cmd_kwargs['stdin_files']:
                        if hasattr(file_, 'read'):
                            stdin_file.write(file_.read())
                        else:
                            stdin_file.write(open(file_, 'rb').read())
                    stdin_file.seek(0)
                elif hasattr(ctx.cmd_kwargs['stdin_files'][0], 'read'):
                    stdin_file = ctx.cmd_kwargs['stdin_files'][0]
                else:
                    stdin_file = open(
                        ctx.cmd_kwargs['stdin_files'][0], 'rb')
            elif ctx.cmd_kwargs.get('stdin_str'):
                stdin_file = cls.get_temporary_file()
                stdin_file.write(ctx.cmd_kwargs.get('stdin_str').encode())
                stdin_file.seek(0)
            else:
                stdin_file = open(os.devnull)
            proc = procopen(
                ctx.cmd, stdin=stdin_file, stdoutpipe=True, stderrpipe=True,
                # Execute command as a process group leader,
                # so we can use "os.killpg" to kill the whole group.
                preexec_fn=os.setpgrp,
                env=ctx.cmd_kwargs.get('env'),
                usesh=ctx.cmd_kwargs.get('shell'))
            # calls to open a shell are aggregated in cylc_subproc.procopen()
            # with logging for what is calling it and the commands given
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
