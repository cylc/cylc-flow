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
"""Process pool to execute shell commands for the suite daemon.

In debug mode, commands are printed to stdout before execution.

Some notes:
 * To print worker process ID, call multiprocessing.current_process()
 * To use a thread pool instead of a process pool:
   - use multiprocessing.pool.ThreadPool instead of pool.Pool
   - use multiprocessing.dummy.current_process() for current_process()
   - note that lsof logic may be required to ensure job scripts are
     closed properly after writing (see jobfile.py prior to cylc-6).
  (early versions of this module gave a choice of process or thread).
"""

import time
import logging
from pipes import quote
from subprocess import Popen, PIPE
import multiprocessing

from cylc.batch_sys_manager import BATCH_SYS_MANAGER
from cylc.cfgspec.globalcfg import GLOBAL_CFG
import cylc.flags
from cylc.wallclock import get_current_time_string


def _run_command(ctx):
    """Execute a shell command and capture its output and exit status."""

    if cylc.flags.debug:
        if ctx.cmd_kwargs.get('shell'):
            print ctx.cmd
        else:
            print ' '.join([quote(cmd_str) for cmd_str in ctx.cmd])

    if (SuiteProcPool.STOP_JOB_SUBMISSION.value
            and ctx.cmd_type == SuiteProcPool.JOB_SUBMIT):
        ctx.err = "job submission skipped (suite stopping)"
        ctx.ret_code = SuiteProcPool.JOB_SKIPPED_FLAG
        ctx.timestamp = get_current_time_string()
        return ctx

    try:
        stdin_file = None
        if ctx.cmd_kwargs.get('stdin_file_path'):
            stdin_file = open(ctx.cmd_kwargs['stdin_file_path'])
        elif ctx.cmd_kwargs.get('stdin_str'):
            stdin_file = PIPE
        proc = Popen(
            ctx.cmd, stdin=stdin_file, stdout=PIPE, stderr=PIPE,
            env=ctx.cmd_kwargs.get('env'), shell=ctx.cmd_kwargs.get('shell'))
    except (IOError, OSError) as exc:
        ctx.ret_code = 1
        ctx.err = str(exc)
    else:
        # Does this command behave like a background job submit where:
        # 1. The process should print its job ID to STDOUT.
        # 2. The process should then continue in background.
        if ctx.cmd_kwargs.get('is_bg_submit'):
            # Capture just the echoed PID then move on.
            # N.B. Some hosts print garbage to STDOUT when going through a
            # login shell, so we want to try a few lines
            ctx.ret_code = 0
            ctx.out = ""
            for _ in range(10):  # Try 10 lines
                line = proc.stdout.readline()
                ctx.out += line
                if line.startswith(BATCH_SYS_MANAGER.CYLC_BATCH_SYS_JOB_ID):
                    break
            # Check if submission is OK or not
            if not ctx.out.rstrip():
                ret_code = proc.poll()
                if ret_code is not None:
                    ctx.out, ctx.err = proc.communicate()
                    ctx.ret_code = ret_code
        else:
            ctx.out, ctx.err = proc.communicate(
                ctx.cmd_kwargs.get('stdin_str'))
            ctx.ret_code = proc.wait()

    ctx.timestamp = get_current_time_string()
    return ctx


class SuiteProcContext(object):
    """Represent the context of a command to run."""

    # Format string for single line output
    JOB_LOG_FMT_1 = "%(timestamp)s [%(cmd_type)s %(attr)s] %(mesg)s"
    # Format string for multi-line output
    JOB_LOG_FMT_M = "%(timestamp)s [%(cmd_type)s %(attr)s]\n\n%(mesg)s\n"

    def __init__(self, cmd_type, cmd, **cmd_kwargs):
        self.timestamp = get_current_time_string()
        self.cmd_type = cmd_type
        self.cmd = cmd
        self.cmd_kwargs = cmd_kwargs

        self.err = cmd_kwargs.get('err')
        self.ret_code = cmd_kwargs.get('ret_code')
        self.out = cmd_kwargs.get('out')

    def __str__(self):
        ret = ""
        for attr in "cmd", "ret_code", "out", "err":
            value = getattr(self, attr, None)
            if value is not None and str(value).strip():
                if attr == "cmd" and isinstance(value, list):
                    mesg = " ".join(quote(item) for item in value)
                else:
                    mesg = str(value).strip()
                if attr == "cmd":
                    if self.cmd_kwargs.get("stdin_file_path"):
                        mesg += " <%s" % quote(
                            self.cmd_kwargs.get("stdin_file_path"))
                    elif self.cmd_kwargs.get("stdin_str"):
                        mesg += " <<<%s" % quote(
                            self.cmd_kwargs.get("stdin_str"))
                if len(mesg.splitlines()) > 1:
                    fmt = self.JOB_LOG_FMT_M
                else:
                    fmt = self.JOB_LOG_FMT_1
                if not mesg.endswith("\n"):
                    mesg += "\n"
                ret += fmt % {
                    "timestamp": self.timestamp,
                    "cmd_type": self.cmd_type,
                    "attr": attr,
                    "mesg": mesg}
        return ret

class SuiteProcPool(object):
    """Use a process pool to execute shell commands."""

    JOB_SUBMIT = "job-submit"
    JOB_SKIPPED_FLAG = 999
    # Shared memory flag.
    STOP_JOB_SUBMISSION = multiprocessing.Value('i', 0)

    _INSTANCE = None

    @classmethod
    def get_inst(cls, pool_size=None):
        """Return a singleton instance.

        On 1st call, instantiate the singleton. The argument "pool_size" is
        only relevant on 1st call.

        """
        if cls._INSTANCE is None:
            cls._INSTANCE = cls(pool_size)
        return cls._INSTANCE

    def __init__(self, pool_size=None):
        self.pool_size = (
            pool_size or
            GLOBAL_CFG.get(["process pool size"]) or
            multiprocessing.cpu_count())
        # (The Pool class defaults to cpu_count anyway, but does not
        # expose the result via its public interface).
        self.log = logging.getLogger("main")
        self.log.debug(
            "Initializing process pool, size %d" % self.pool_size)
        self.pool = multiprocessing.Pool(processes=self.pool_size)
        self.results = {}

    def put_command(self, ctx, callback):
        """Queue a new shell command to execute."""
        try:
            result = self.pool.apply_async(_run_command, [ctx])
        except AssertionError as exc:
            self.log.warning("%s\n  %s\n %s" % (
                str(exc),
                "Rejecting command (pool closed)",
                ctx.cmd))
        else:
            self.results[id(result)] = (result, callback)

    def handle_results_async(self):
        """Pass any available results to their associated callback."""
        for result_id, item in self.results.items():
            result, callback = item
            if result.ready():
                self.results.pop(result_id)
                value = result.get()
                if callable(callback):
                    callback(value)

    @classmethod
    def stop_job_submission(cls):
        """Set STOP_JOB_SUBMISSION flag."""
        cls.STOP_JOB_SUBMISSION.value = 1

    def close(self):
        """Close the pool to new commands."""
        if not (self.is_dead() or self.is_closed()):
            self.log.debug("Closing process pool")
            self.pool.close()

    def terminate(self):
        """Kill all worker processes immediately."""
        if not self.is_dead():
            self.log.debug("Terminating process pool")
            self.pool.terminate()

    def join(self):
        """Join after workers have exited. Close or terminate first."""
        self.log.debug("Joining process pool")
        self.pool.join()

    def is_closed(self):
        """Is the pool closed?"""
        # Warning: accesses multiprocessing.Pool internal state
        return self.pool._state == multiprocessing.pool.CLOSE

    def is_dead(self):
        """Have all my workers exited yet?"""
        # Warning: accesses multiprocessing.Pool internal state
        for pool in self.pool._pool:
            if pool.is_alive():
                return False
        return True


def main():
    """Manual test playground."""

    log = logging.getLogger("main")
    log.setLevel(logging.INFO)  # or logging.DEBUG
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    log.addHandler(handler)

    def print_result(result):
        """Print result"""
        if result['OUT']:
            log.info('result> ' + result['OUT'].strip())
        if result['ERR']:
            log.info('FAILED> ' + result['CMD'])
            log.info(result['ERR'].strip())

    pool = mp_pool(3)

    for i in range(3):
        com = "sleep 5 && echo Hello from JOB " + str(i)
        pool.put_command(SuiteProcPool.JOB_SUBMIT, com, print_result)
        com = "sleep 5 && echo Hello from POLL " + str(i)
        pool.put_command("poll", com, print_result)
        com = "sleep 5 && echo Hello from HANDLER " + str(i)
        pool.put_command("event-handler", com, print_result)
        com = "sleep 5 && echo Hello from HANDLER && badcommand"
        pool.put_command("event-handler", com, print_result)

    log.info('  sleeping')
    time.sleep(3)
    pool.handle_results_async()
    log.info('  sleeping')
    time.sleep(3)
    pool.close()
    #pool.terminate()
    pool.handle_results_async()
    log.info('  sleeping')
    time.sleep(3)
    pool.join()
    pool.handle_results_async()


if __name__ == '__main__':
    import sys
    main()
