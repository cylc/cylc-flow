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

import time
import logging
import subprocess
import multiprocessing

from cylc.cfgspec.globalcfg import GLOBAL_CFG
import flags

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

CMD_TYPE_JOB_SUBMISSION=0
CMD_TYPE_JOB_POLL_KILL=1
CMD_TYPE_EVENT_HANDLER=2

TRUE=1
FALSE=0
JOB_SKIPPED_FLAG = 999

# Shared memory flag.
STOP_JOB_SUBMISSION = multiprocessing.Value('i',FALSE)


def execute_shell_command(cmd_spec, job_sub_method=None):
    """Execute a shell command and capture its output and exit status."""

    cmd_type, cmd_string = cmd_spec
    cmd_result = {
            'CMD': cmd_string,
            'EXIT': None,
            'OUT': None,
            'ERR': None}

    if flags.debug:
        print cmd_string

    if (STOP_JOB_SUBMISSION.value == TRUE
            and cmd_type == CMD_TYPE_JOB_SUBMISSION):
        cmd_result['OUT'] = "job submission skipped (suite stopping)"
        cmd_result['EXIT'] = JOB_SKIPPED_FLAG
        return cmd_result

    try:
        p = subprocess.Popen(cmd_string, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, shell=True)
    except Exception as e:
        cmd_result['EXIT'] = 1
        cmd_result['ERR' ] = str(e)
    else:
        if job_sub_method == "background":
            # Capture just the echoed PID then move on.
            cmd_result['EXIT'] = 0
            cmd_result['OUT'] = p.stdout.readline().rstrip()
            # Check if submission is OK or not
            if not cmd_result['OUT']:
                ret_code = p.poll()
                if ret_code is not None:
                    cmd_result['OUT'], cmd_result['ERR'] = p.communicate()
                    cmd_result['EXIT'] = ret_code
        else:
            cmd_result['EXIT'] = p.wait()
            if cmd_result['EXIT'] is not None:
                cmd_result['OUT'], cmd_result['ERR'] = p.communicate()

    return cmd_result


class mp_pool(object):
    """Use a process pool to execute shell commands."""

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

    def put_command(self, cmd_spec, callback, job_sub_method=None):
        """Queue a new shell command to execute."""
        cmd_type, cmd_string = cmd_spec
        try:
            result = self.pool.apply_async(
                execute_shell_command,(cmd_spec, job_sub_method))
        except AssertionError as e:
            self.log.warning("%s\n  %s\n %s" % (
                str(e),
                "Rejecting command (pool closed)",
                cmd_string))
        else:
            if callback:
                self.unhandled_results.append((result,callback))

    def handle_results_async(self):
        """Pass any available results to their associated callback."""
        still_to_do = []
        for item in self.unhandled_results:
            res, callback = item
            if res.ready():
                val=res.get()
                callback(val)
            else:
                still_to_do.append((res,callback))
        self.unhandled_results = still_to_do

    def stop_job_submission(self):
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
        for p in self.pool._pool:
            if p.is_alive():
                return False
        return True


if __name__ == '__main__':
    """Manual test playground."""

    import sys
    log = logging.getLogger("main")
    log.setLevel(logging.INFO) # or logging.DEBUG
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    log.addHandler(handler)

    def print_result(result):
        if result['OUT']:
            log.info( 'result> ' + result['OUT'].strip() )
        if result['ERR']:
            log.info( 'FAILED> ' + result['CMD'] )
            log.info( result['ERR'].strip() )

    pool = mp_pool(3)

    for i in range(0,3):
        com = "sleep 5 && echo Hello from JOB " + str(i)
        pool.put_command((CMD_TYPE_JOB_SUBMISSION,com), print_result)
        com = "sleep 5 && echo Hello from POLL " + str(i)
        pool.put_command((CMD_TYPE_JOB_POLL_KILL,com), print_result)
        com = "sleep 5 && echo Hello from HANDLER " + str(i)
        pool.put_command((CMD_TYPE_EVENT_HANDLER,com), print_result)
        com = "sleep 5 && echo Hello from HANDLER && badcommand"
        pool.put_command((CMD_TYPE_EVENT_HANDLER,com), print_result)

    log.info( '  sleeping' )
    time.sleep(3)
    pool.handle_results_async()
    log.info( '  sleeping' )
    time.sleep(3)
    pool.close()
    #pool.terminate()
    pool.handle_results_async()
    log.info( '  sleeping' )
    time.sleep(3)
    pool.join()
    pool.handle_results_async()
