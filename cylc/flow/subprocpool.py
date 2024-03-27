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
"""Manage queueing and pooling of subprocesses for the scheduler."""

from collections import deque
import json
import os
import select
from signal import SIGKILL
import sys
import shlex
from tempfile import SpooledTemporaryFile
from threading import RLock
from time import time
from subprocess import DEVNULL, run  # nosec
from typing import Any, Callable, List, Optional

from cylc.flow import LOG, iter_entry_points
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.cylc_subproc import procopen
from cylc.flow.exceptions import PlatformLookupError
from cylc.flow.hostuserutil import is_remote_host
from cylc.flow.platforms import (
    log_platform_event,
    get_platform,
)
from cylc.flow.task_events_mgr import TaskJobLogsRetrieveContext
from cylc.flow.task_proxy import TaskProxy
from cylc.flow.wallclock import get_current_time_string

_XTRIG_MOD_CACHE: dict = {}
_XTRIG_FUNC_CACHE: dict = {}


def _killpg(proc, signal):
    """Kill a process group."""
    try:
        os.killpg(proc.pid, signal)
    except ProcessLookupError:
        # process group has already exited
        return False
    except PermissionError:
        # process group may contain zombie processes which will result in
        # PermissionError on some systems, not sure what happens on others
        #
        # we could go through the processes in the group and call waitpid on
        # them but waitpid is blocking and this would be a messy solution for a
        # problem that shouldn't happen (it's really a bug in the Cylc subproc)
        LOG.error(
            f'Could not kill process group: {proc.pid}'
            f'\nCommand: {" ".join(proc.args)}'
        )
        return False
    return True


def get_xtrig_mod(mod_name, src_dir):
    """Find, cache, and return a named xtrigger module.

    Locations checked in this order:
    - <src_dir>/lib/python (prepend to sys.path)
    - $CYLC_PYTHONPATH (already in sys.path)
    - `cylc.xtriggers` entry point

    (Check entry point last so users can override with local implementations).

    Workflow source dir passed in - this executes in an independent subprocess.

    Raises:
        ImportError, if the module is not found

    """
    if mod_name in _XTRIG_MOD_CACHE:
        # Found and cached already.
        return _XTRIG_MOD_CACHE[mod_name]

    # First look in <src-dir>/lib/python.
    sys.path.insert(0, os.path.join(src_dir, 'lib', 'python'))
    try:
        _XTRIG_MOD_CACHE[mod_name] = __import__(mod_name, fromlist=[mod_name])
    except ImportError:
        # Then entry point.
        for entry_point in iter_entry_points('cylc.xtriggers'):
            if mod_name == entry_point.name:
                _XTRIG_MOD_CACHE[mod_name] = entry_point.load()
                return _XTRIG_MOD_CACHE[mod_name]
        # Still unable to find anything so abort
        raise

    return _XTRIG_MOD_CACHE[mod_name]


def get_xtrig_func(mod_name, func_name, src_dir):
    """Find, cache, and return a function from an xtrigger module.

    Raises:
        ImportError, if the module is not found
        AttributeError, if the function is not found in the module

    """
    if (mod_name, func_name) in _XTRIG_FUNC_CACHE:
        return _XTRIG_FUNC_CACHE[(mod_name, func_name)]

    mod = get_xtrig_mod(mod_name, src_dir)

    _XTRIG_FUNC_CACHE[(mod_name, func_name)] = getattr(mod, func_name)

    return _XTRIG_FUNC_CACHE[(mod_name, func_name)]


def run_function(func_name, json_args, json_kwargs, src_dir):
    """Run a Python function in the process pool.

    func_name(*func_args, **func_kwargs)

    The function is presumed to be in a module of the same name.

    Redirect any function stdout to stderr (and workflow log in debug mode).
    Return value printed to stdout as a JSON string - allows use of the
    existing process pool machinery as-is. src_dir is for local modules.

    """
    func_args = json.loads(json_args)
    func_kwargs = json.loads(json_kwargs)

    # Find and import then function.
    func = get_xtrig_func(func_name, func_name, src_dir)

    # Redirect stdout to stderr.
    orig_stdout = sys.stdout
    sys.stdout = sys.stderr
    res = func(*func_args, **func_kwargs)

    # Restore stdout.
    sys.stdout = orig_stdout

    # Write function return value as JSON to stdout.
    sys.stdout.write(json.dumps(res))


class SubProcPool:
    """Manage queueing and pooling of subprocesses.

    Mainly used by the main loop of the scheduler, although
    the SubProcPool.run_command can be used as a standalone utility function
    to run the command in a cylc.flow.subprocctx.SubProcContext.

    A command to run under a subprocess in the pool is expected to be wrapped
    using a cylc.flow.subprocctx.SubProcContext object. The caller will add the
    context object using the SubProcPool.put_command method. A callback can
    be specified to notify the caller on exit of the subprocess.

    A command launched by the pool is expected to write to STDOUT and STDERR.
    These are captured while the command runs and/or when the command exits.
    The contents are appended to the `.out` and `.err` attributes of the
    SubProcContext object as they are read. STDIN can also be specified for the
    command. This is currently fed into the command using a temporary file.

    Note: For a cylc command that uses
    `cylc.flow.option_parsers.CylcOptionParser`, the default logging handler
    writes to the STDERR via a StreamHandler. Therefore, log messages will
    only be written to the workflow log by the callback function when the
    command exits (and only if the callback function has the logic to do so).

    """

    ERR_WORKFLOW_STOPPING = 'workflow stopping, command not run'
    JOBS_SUBMIT = 'jobs-submit'
    POLLREAD = select.POLLIN | select.POLLPRI
    RET_CODE_WORKFLOW_STOPPING = 999

    def __init__(self):
        self.size = glbl_cfg().get(['scheduler', 'process pool size'])
        self.proc_pool_timeout = glbl_cfg().get(
            ['scheduler', 'process pool timeout'])
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
        """Return whether .stopping is True or not.

        Returns:
            bool: Whether the pool is stopping or not.
        """
        with self.stopping_lock:
            return self.stopping

    def _proc_exit(
        self, proc, err_xtra, ctx,
        callback, callback_args, bad_hosts=None,
        callback_255=None, callback_255_args=None
    ):
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
        self._run_command_exit(
            ctx, bad_hosts=bad_hosts,
            callback=callback, callback_args=callback_args,
            callback_255=callback_255, callback_255_args=callback_255_args
        )

    def process(self):
        """Process done child processes and submit more."""
        # Handle child processes that are done
        runnings = []
        for running in self.runnings:
            (
                proc, ctx, bad_hosts,
                callback, callback_args,
                callback_255, callback_255_args
            ) = running
            # Command completed/exited
            if proc.poll() is not None:
                self._proc_exit(
                    proc, "", ctx,
                    callback=callback, callback_args=callback_args,
                    bad_hosts=bad_hosts,
                    callback_255=callback_255,
                    callback_255_args=callback_255_args
                )
                continue
            # Command timed out, kill it
            if time() > ctx.timeout:
                err_xtra = ""
                if _killpg(proc, SIGKILL):
                    err_xtra = (
                        f"\nkilled on timeout ({self.proc_pool_timeout})"
                    )
                self._proc_exit(
                    proc, err_xtra, ctx,
                    callback=callback,
                    callback_args=callback_args,
                    bad_hosts=bad_hosts
                )
                continue
            # Command still running, see if STDOUT/STDERR are readable or not
            runnings.append([
                proc, ctx, bad_hosts, callback, callback_args, None, None])
            # Unblock proc's STDOUT/STDERR if necessary. Otherwise, a full
            # STDOUT or STDERR may stop command from proceeding.
            self._poll_proc_pipes(proc, ctx)

        # Update list of running items
        self.runnings[:] = runnings
        # Create more child processes, if items in queue and space in pool
        stopping = self._is_stopping()
        while self.queuings and len(self.runnings) < self.size:
            (
                ctx, bad_hosts, callback, callback_args,
                callback_255, callback_255_args
            ) = self.queuings.popleft()
            if stopping and ctx.cmd_key == self.JOBS_SUBMIT:
                ctx.err = self.ERR_WORKFLOW_STOPPING
                ctx.ret_code = self.RET_CODE_WORKFLOW_STOPPING
                self._run_command_exit(ctx)
            else:
                proc = self._run_command_init(
                    ctx, bad_hosts, callback, callback_args,
                    callback_255, callback_255_args
                )
                if proc is not None:
                    ctx.timeout = time() + self.proc_pool_timeout
                    self.runnings.append([
                        proc, ctx, bad_hosts, callback, callback_args,
                        callback_255, callback_255_args
                    ])

    def put_command(
        self, ctx, bad_hosts=None, callback=None, callback_args=None,
        callback_255=None, callback_255_args=None
    ):
        """Queue a new shell command to execute.

        Arguments:
            ctx (cylc.flow.subprocctx.SubProcContext):
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
            ctx.err = self.ERR_WORKFLOW_STOPPING
            ctx.ret_code = self.RET_CODE_WORKFLOW_STOPPING
            self._run_command_exit(
                ctx, bad_hosts=bad_hosts,
                callback=callback, callback_args=callback_args,
                callback_255=callback_255, callback_255_args=callback_255_args
            )
        else:
            self.queuings.append(
                [
                    ctx, bad_hosts, callback, callback_args,
                    callback_255, callback_255_args
                ]
            )

    @classmethod
    def run_command(cls, ctx):
        """Execute command in ctx and capture its output and exit status.

        Arguments:
            ctx (cylc.flow.subprocctx.SubProcContext):
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
            ctx.err = self.ERR_WORKFLOW_STOPPING
            ctx.ret_code = self.RET_CODE_WORKFLOW_STOPPING
            self._run_command_exit(ctx)
        # Kill remaining processes
        for value in self.runnings:
            proc = value[0]
            if proc:
                _killpg(proc, SIGKILL)
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
            received_data = []
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
                received_data.append(data != '')
                if fileno == proc.stdout.fileno():
                    if ctx.out is None:
                        ctx.out = ''
                    ctx.out += data
                elif fileno == proc.stderr.fileno():
                    if ctx.err is None:
                        ctx.err = ''
                    ctx.err += data
            if received_data and not all(received_data):
                # if no data was pushed down the pipe exit the polling loop,
                # we can always re-enter the polling loop later if there is
                # more data
                # NOTE: this suppresses an infinite polling-loop observed
                # on darwin see:
                # https://github.com/cylc/cylc-flow/issues/3535
                # https://github.com/cylc/cylc-flow/pull/3543
                return
        self.pipepoller.unregister(proc.stdout.fileno())
        self.pipepoller.unregister(proc.stderr.fileno())

    @classmethod
    def _run_command_init(
        cls, ctx, bad_hosts=None, callback=None, callback_args=None,
        callback_255=None, callback_255_args=None
    ):
        """Prepare and launch shell command in ctx."""
        try:
            if ctx.cmd_kwargs.get('stdin_files'):
                if len(ctx.cmd_kwargs['stdin_files']) > 1:
                    stdin_file = cls.get_temporary_file()
                    for file_ in ctx.cmd_kwargs['stdin_files']:
                        if hasattr(file_, 'read'):
                            stdin_file.write(file_.read())
                        else:
                            with open(file_, 'rb') as openfile:
                                stdin_file.write(openfile.read())
                    stdin_file.seek(0)
                elif hasattr(ctx.cmd_kwargs['stdin_files'][0], 'read'):
                    stdin_file = ctx.cmd_kwargs['stdin_files'][0]
                else:
                    stdin_file = open(  # noqa: SIM115
                        # (nasty use of file handles, should avoid in future)
                        ctx.cmd_kwargs['stdin_files'][0], 'rb'
                    )
            elif ctx.cmd_kwargs.get('stdin_str'):
                stdin_file = cls.get_temporary_file()
                stdin_file.write(ctx.cmd_kwargs.get('stdin_str').encode())
                stdin_file.seek(0)
            else:
                stdin_file = DEVNULL
            proc = procopen(
                ctx.cmd, stdin=stdin_file, stdoutpipe=True, stderrpipe=True,
                # Execute command as a process group leader,
                # so we can use "os.killpg" to kill the whole group.
                preexec_fn=os.setpgrp,
                env=ctx.cmd_kwargs.get('env'),
                usesh=ctx.cmd_kwargs.get('shell'))
            # calls to open a shell are aggregated in cylc_subproc.procopen()
            # with logging for what is calling it and the commands given
        except OSError as exc:
            if exc.filename is None:
                exc.filename = ctx.cmd[0]
            LOG.exception(exc)
            ctx.ret_code = 1
            ctx.err = str(exc)
            cls._run_command_exit(
                ctx, bad_hosts=bad_hosts,
                callback=callback, callback_args=callback_args,
                callback_255=callback_255, callback_255_args=callback_255_args
            )
            return None
        else:
            LOG.debug(ctx.cmd)
            return proc

    @classmethod
    def _run_command_exit(
        cls, ctx, bad_hosts=None,
        callback: Optional[Callable] = None,
        callback_args: Optional[List[Any]] = None,
        callback_255: Optional[Callable] = None,
        callback_255_args: Optional[List[Any]] = None
    ) -> None:
        """Process command completion.

        If task has failed with a 255 error, run an alternative callback if
        one is provided.

        Args:
            ctx: SubProcContext object for this task.
            callback: Function to run on command exit.
            callback_args: Arguments to provide to callback
            callback_255: Function to run if command exits with a 255
                error - usually associated with ssh being unable to
                contact a remote host.
            callback_255_args: Arguments for the 255 callback function.

        """
        def _run_callback(callback, args_=None):
            if callable(callback):
                if not args_:
                    args_ = []
                callback(ctx, *args_)
            else:
                return False
        ctx.timestamp = get_current_time_string()

        # If cmd is fileinstall, which uses rsync, get a platform so
        # that you can use that platform's ssh command.
        platform_name = None
        platform = None
        if isinstance(ctx.cmd_key, TaskJobLogsRetrieveContext):
            try:
                platform = get_platform(ctx.cmd_key.platform_name)
            except PlatformLookupError:
                log_platform_event(
                    'Unable to retrieve job logs.',
                    {'name': ctx.cmd_key.platform_name},
                    level='warning',
                )
        elif callback_args:
            platform = callback_args[0]
            if not (
                isinstance(platform, dict)
                and 'ssh command' in platform
                and 'name' in platform
            ):
                # the first argument is not a platform
                platform = None
                # Backup, get a platform name from the config:
                for arg in callback_args:
                    if isinstance(arg, TaskProxy):
                        platform_name = arg.tdef.rtconfig['platform']
                    elif (
                        isinstance(arg, list)
                        and isinstance(arg[0], TaskProxy)
                    ):
                        platform_name = arg[0].tdef.rtconfig['platform']

        if cls.ssh_255_fail(ctx) or cls.rsync_255_fail(ctx, platform) is True:
            # Job log retrieval passes a special object as a command key
            # Extra logic to provide sensible strings for logging.
            if isinstance(ctx.cmd_key, TaskJobLogsRetrieveContext):
                cmd_key = ctx.cmd_key.key
            else:
                cmd_key = ctx.cmd_key
            log_platform_event(
                # NOTE: the failure of the command should be logged elsewhere
                (
                    f'Could not connect to {ctx.host}.'
                    f'\n* {ctx.host} has been added to the list of'
                    ' unreachable hosts'
                    f'\n* {cmd_key} will retry if another host is available.'
                ),
                platform or {'name': platform_name},
                level='warning',
            )

            # If callback_255 takes the same args as callback, we don't
            # want to spec those args:
            if callable(callback_255) and callback_255_args is None:
                callback_255_args = callback_args

            # Run Callback
            if bad_hosts is not None:
                bad_hosts.add(ctx.host)

            res = _run_callback(callback_255, callback_255_args)
            if res is False:
                _run_callback(callback, callback_args)
        else:
            # For every other return code run default callback.
            _run_callback(callback, callback_args)

    @staticmethod
    def ssh_255_fail(ctx) -> bool:
        """Test context for ssh command failing with a 255 error."""
        ssh_255_fail = False
        if (
            ctx.cmd[0] == 'ssh'
            and ctx.ret_code == 255
        ):
            ssh_255_fail = True
        return ssh_255_fail

    @staticmethod
    def rsync_255_fail(ctx, platform=None) -> bool:
        """Tests context for rsync failing to communicate with a host.

        If there has been a failure caused by rsync being unable to connect
        try a test of ssh connectivity. Necessary because loss of connectivity
        may cause different rsync failures depending on version, and some of
        the failures may be caused by other problems.
        """
        rsync_255_fail = False
        platform_rsync_cmd = (
            platform['rsync command']
            if platform is not None
            else 'rsync'
        )
        rsync_cmd = shlex.split(platform_rsync_cmd)
        if (
            ctx.cmd[0] == rsync_cmd[0]
            and ctx.ret_code not in [0, 255]
            and is_remote_host(ctx.host)
        ):
            ssh_cmd = (
                platform['ssh command']
                if platform is not None
                else 'ssh'
            )
            ssh_test_cmd = shlex.split(f'{ssh_cmd} {ctx.host} true')
            LOG.info(
                f'testing connectivity for {ctx.host} using {ssh_test_cmd}'
            )
            ssh_test = run(
                shlex.split(f'{ssh_cmd} {ctx.host} true'),  # nosec B603 *
                capture_output=True
            )
            # * (command is trusted input)
            if ssh_test.returncode == 255:
                rsync_255_fail = True
        elif (
            ctx.cmd[0] == rsync_cmd[0]
            and ctx.ret_code == 255
        ):
            rsync_255_fail = True
        return rsync_255_fail
