#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.
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


CMD_TYPE_JOB_SUBMISSION = 0
CMD_TYPE_JOB_POLL_KILL = 1
CMD_TYPE_EVENT_HANDLER = 2

TRUE = 1
FALSE = 0
JOB_SKIPPED_FLAG = 999

# Shared memory flag.
STOP_JOB_SUBMISSION = multiprocessing.Value('i', FALSE)


def _run_command(
        cmd_type, cmd, is_bg_submit=None, stdin_file_path=None, env=None,
        shell=False):
    """Execute a shell command and capture its output and exit status."""

    cmd_result = {'CMD': cmd, 'EXIT': None, 'OUT': None, 'ERR': None}

    if cylc.flags.debug:
        if shell:
            print cmd
        else:
            print ' '.join([quote(cmd_str) for cmd_str in cmd])

    if (STOP_JOB_SUBMISSION.value == TRUE
            and cmd_type == CMD_TYPE_JOB_SUBMISSION):
        cmd_result['OUT'] = "job submission skipped (suite stopping)"
        cmd_result['EXIT'] = JOB_SKIPPED_FLAG
        return cmd_result

    try:
        stdin_file = None
        if stdin_file_path:
            stdin_file = open(stdin_file_path)
        proc = Popen(
            cmd, stdin=stdin_file, stdout=PIPE, stderr=PIPE,
            env=env, shell=shell)
    except (IOError, OSError) as exc:
        cmd_result['EXIT'] = 1
        cmd_result['ERR'] = str(exc)
    else:
        # Does this command behave like a background job submit where:
        # 1. The process should print its job ID to STDOUT.
        # 2. The process should then continue in background.
        if is_bg_submit:  # behave like background job submit?
            # Capture just the echoed PID then move on.
            # N.B. Some hosts print garbage to STDOUT when going through a
            # login shell, so we want to try a few lines
            cmd_result['EXIT'] = 0
            cmd_result['OUT'] = ""
            for _ in range(10):  # Try 10 lines
                line = proc.stdout.readline()
                cmd_result['OUT'] += line
                if line.startswith(BATCH_SYS_MANAGER.CYLC_BATCH_SYS_JOB_ID):
                    break
            # Check if submission is OK or not
            if not cmd_result['OUT'].rstrip():
                ret_code = proc.poll()
                if ret_code is not None:
                    cmd_result['OUT'], cmd_result['ERR'] = proc.communicate()
                    cmd_result['EXIT'] = ret_code
        else:
            cmd_result['EXIT'] = proc.wait()
            if cmd_result['EXIT'] is not None:
                cmd_result['OUT'], cmd_result['ERR'] = proc.communicate()

    return cmd_result


class SuiteProcPool(object):
    """Use a process pool to execute shell commands."""

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
        self.unhandled_results = []

    def put_command(
            self, cmd_type, cmd, callback, is_bg_submit=False,
            stdin_file_path=None, env=None, shell=False):
        """Queue a new shell command to execute."""
        try:
            result = self.pool.apply_async(
                _run_command,
                (cmd_type, cmd, is_bg_submit, stdin_file_path, env, shell))
        except AssertionError as exc:
            self.log.warning("%s\n  %s\n %s" % (
                str(exc),
                "Rejecting command (pool closed)",
                cmd))
        else:
            if callback:
                self.unhandled_results.append((result, callback))

    def handle_results_async(self):
        """Pass any available results to their associated callback."""
        still_to_do = []
        for item in self.unhandled_results:
            res, callback = item
            if res.ready():
                val = res.get()
                callback(val)
            else:
                still_to_do.append((res, callback))
        self.unhandled_results = still_to_do

    @classmethod
    def stop_job_submission(cls):
        """Set STOP_JOB_SUBMISSION flag."""
        STOP_JOB_SUBMISSION.value = TRUE

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
        pool.put_command(CMD_TYPE_JOB_SUBMISSION, com, print_result)
        com = "sleep 5 && echo Hello from POLL " + str(i)
        pool.put_command(CMD_TYPE_JOB_POLL_KILL, com, print_result)
        com = "sleep 5 && echo Hello from HANDLER " + str(i)
        pool.put_command(CMD_TYPE_EVENT_HANDLER, com, print_result)
        com = "sleep 5 && echo Hello from HANDLER && badcommand"
        pool.put_command(CMD_TYPE_EVENT_HANDLER, com, print_result)

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
