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

import logging
import multiprocessing
from pipes import quote
from subprocess import Popen, PIPE
import sys
from tempfile import TemporaryFile
import time
import traceback

from cylc.cfgspec.globalcfg import GLOBAL_CFG
import cylc.flags
from cylc.suite_logging import LOG
from cylc.wallclock import get_current_time_string


def _run_command(ctx):
    """Execute a shell command and capture its output and exit status."""

    LOG.debug(ctx)

    if (SuiteProcPool.STOP_JOB_SUBMISSION.value and
            ctx.cmd_key == SuiteProcPool.JOBS_SUBMIT):
        ctx.err = "job submission skipped (suite stopping)"
        ctx.ret_code = SuiteProcPool.JOB_SKIPPED_FLAG
        ctx.timestamp = get_current_time_string()
        return ctx

    try:
        stdin_file = None
        if ctx.cmd_kwargs.get('stdin_file_paths'):
            stdin_file = TemporaryFile()
            for file_path in ctx.cmd_kwargs['stdin_file_paths']:
                for line in open(file_path):
                    stdin_file.write(line)
            stdin_file.seek(0)
        elif ctx.cmd_kwargs.get('stdin_str'):
            stdin_file = PIPE
        proc = Popen(
            ctx.cmd, stdin=stdin_file, stdout=PIPE, stderr=PIPE,
            env=ctx.cmd_kwargs.get('env'), shell=ctx.cmd_kwargs.get('shell'))
    except IOError as exc:
        if cylc.flags.debug:
            traceback.print_exc()
        ctx.ret_code = 1
        ctx.err = str(exc)
    except OSError as exc:
        if exc.filename is None:
            exc.filename = ctx.cmd[0]
        if cylc.flags.debug:
            traceback.print_exc()
        ctx.ret_code = 1
        ctx.err = str(exc)
    else:
        ctx.out, ctx.err = proc.communicate(ctx.cmd_kwargs.get('stdin_str'))
        ctx.ret_code = proc.wait()

    ctx.timestamp = get_current_time_string()
    return ctx


class SuiteProcContext(object):
    """Represent the context of a command to run."""

    # Format string for single line output
    JOB_LOG_FMT_1 = "[%(cmd_key)s %(attr)s] %(mesg)s"
    # Format string for multi-line output
    JOB_LOG_FMT_M = "[%(cmd_key)s %(attr)s]\n%(mesg)s"

    def __init__(self, cmd_key, cmd, **cmd_kwargs):
        self.timestamp = get_current_time_string()
        self.cmd_key = cmd_key
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
                mesg = ""
                if attr == "cmd" and self.cmd_kwargs.get("stdin_file_paths"):
                    mesg += "cat"
                    for file_path in self.cmd_kwargs.get("stdin_file_paths"):
                        mesg += " " + quote(file_path)
                    mesg += " | "
                if attr == "cmd" and isinstance(value, list):
                    mesg += " ".join(quote(item) for item in value)
                else:
                    mesg = str(value).strip()
                if attr == "cmd" and self.cmd_kwargs.get("stdin_str"):
                    mesg += " <<<%s" % quote(self.cmd_kwargs.get("stdin_str"))
                if len(mesg.splitlines()) > 1:
                    fmt = self.JOB_LOG_FMT_M
                else:
                    fmt = self.JOB_LOG_FMT_1
                if not mesg.endswith("\n"):
                    mesg += "\n"
                ret += fmt % {
                    "cmd_key": self.cmd_key,
                    "attr": attr,
                    "mesg": mesg}
        return ret.rstrip()


class SuiteProcPool(object):
    """Use a process pool to execute shell commands."""

    JOBS_SUBMIT = "jobs-submit"
    JOB_SKIPPED_FLAG = 999
    # Shared memory flag.
    STOP_JOB_SUBMISSION = multiprocessing.Value('i', 0)

    def __init__(self, pool_size=None):
        self.pool_size = (
            pool_size or
            GLOBAL_CFG.get(["process pool size"]) or
            multiprocessing.cpu_count())
        # (The Pool class defaults to cpu_count anyway, but does not
        # expose the result via its public interface).
        LOG.debug(
            "Initializing process pool, size %d" % self.pool_size)
        self.pool = multiprocessing.Pool(processes=self.pool_size)
        self.results = {}

    def close(self):
        """Close the pool to new commands."""
        if not (self.is_dead() or self.is_closed()):
            LOG.debug("Closing process pool")
            self.pool.close()

    def handle_results_async(self):
        """Pass any available results to their associated callback."""
        for key, (result, callback, callback_args) in self.results.items():
            if result.ready():
                self.results.pop(key)
                value = result.get()
                if callable(callback):
                    if not callback_args:
                        callback_args = []
                    callback(value, *callback_args)

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

    def join(self):
        """Join after workers have exited. Close or terminate first."""
        LOG.debug("Joining process pool")
        try:
            self.pool.join()
        except AssertionError:
            # multiprocessing.Pool.join may raise this error. We want to ignore
            # this so suite shutdown can continue.
            pass

    def put_command(self, ctx, callback, callback_args=None):
        """Queue a new shell command to execute."""
        try:
            result = self.pool.apply_async(_run_command, [ctx])
        except AssertionError as exc:
            LOG.warning("%s\n  %s\n %s" % (
                str(exc),
                "Rejecting command (pool closed)",
                ctx.cmd))
        else:
            self.results[id(result)] = (result, callback, callback_args)

    @staticmethod
    def run_command(ctx):
        """Execute a shell command and capture its output and exit status."""
        return _run_command(ctx)

    @classmethod
    def stop_job_submission(cls):
        """Set STOP_JOB_SUBMISSION flag."""
        cls.STOP_JOB_SUBMISSION.value = 1

    def terminate(self):
        """Kill all worker processes immediately."""
        if not self.is_dead():
            LOG.debug("Terminating process pool")
            self.pool.terminate()


def main():
    """Manual test playground."""

    log = logging.getLogger(LOG)
    log.setLevel(logging.INFO)  # or logging.DEBUG
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    log.addHandler(handler)

    def print_result(result):
        """Print result"""
        if result['OUT']:
            LOG.info('result> ' + result['OUT'].strip())
        if result['ERR']:
            LOG.info('FAILED> ' + result['CMD'])
            LOG.info(result['ERR'].strip())

    pool = SuiteProcPool(3)

    for i in range(3):
        com = "sleep 5 && echo Hello from JOB " + str(i)
        pool.put_command(SuiteProcPool.JOBS_SUBMIT, com, print_result)
        com = "sleep 5 && echo Hello from POLL " + str(i)
        pool.put_command("poll", com, print_result)
        com = "sleep 5 && echo Hello from HANDLER " + str(i)
        pool.put_command("event-handler", com, print_result)
        com = "sleep 5 && echo Hello from HANDLER && badcommand"
        pool.put_command("event-handler", com, print_result)

    LOG.info('  sleeping')
    time.sleep(3)
    pool.handle_results_async()
    LOG.info('  sleeping')
    time.sleep(3)
    pool.close()
    # pool.terminate()
    pool.handle_results_async()
    LOG.info('  sleeping')
    time.sleep(3)
    pool.join()
    pool.handle_results_async()


if __name__ == '__main__':
    main()
