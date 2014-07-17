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
import subprocess
from multiprocessing import Value
import multiprocessing.pool

import flags
 
"""Process or thread pool to execute shell commands."""

# Command type flags.
CMD_TYPE_JOB_SUBMISSION=0
CMD_TYPE_JOB_POLL_KILL=1
CMD_TYPE_EVENT_HANDLER=2

# Shared memory flag
TRUE=1
FALSE=0
POOL_CLOSED = Value('i',FALSE)

# Job omission flag
JOB_NOT_SUBMITTED=999

def execute_shell_command(cmd_spec, current_process, job_sub_method=None):
    """Execute a shell command and capture its output and exit status."""

    cmd_type, cmd_string = cmd_spec
    cmd_result = {
            'CMD': cmd_string,
            'EXIT': None,
            'OUT': None,
            'ERR': None}

    if POOL_CLOSED.value == TRUE and cmd_type == CMD_TYPE_JOB_SUBMISSION:
        # Stop job submission commands if pool closed but continue others
        # till done (call pool.terminate() to stop all work immediately).
        if flags.debug:
            print "[%s] omitting: %s" % (current_process().name, cmd_string)
        cmd_result['ERR'] = "job not submitted (pool closed)"
        cmd_result['EXIT'] = JOB_NOT_SUBMITTED
        return cmd_result
    elif flags.debug:
        print "[%s] executing: %s" % ( current_process().name, cmd_string)

    # FOR TESTING PURPOSES try making command execution take a long time:
    # time.sleep(5)

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
        else:
            cmd_result['EXIT'] = p.wait()
            if cmd_result['EXIT'] is not None:
                cmd_result['OUT'], cmd_result['ERR'] = p.communicate()
    return cmd_result


class mp_pool(object):
    """Use a process or thread pool to execute shell commands."""

    def __init__(self, pool_config):
        self.type = pool_config['pool type']
        if self.type == 'process':
            pool_cls = multiprocessing.Pool 
            if pool_config['process pool size'] is None:
                # (Pool class does this anyway, but the result is not
                # exposed via its public interface).
                self.poolsize = multiprocessing.cpu_count()
            else:
                self.poolsize = pool_config['process pool size']
            self.current_process = multiprocessing.current_process
        else:
            pool_cls = multiprocessing.pool.ThreadPool
            self.poolsize = pool_config['thread pool size']
            self.current_process = multiprocessing.dummy.current_process

        self.pool = pool_cls( processes=self.poolsize )
        if flags.debug:
            print "Initialized %s pool, size %d" % (
                    self.type, self.get_pool_size())
        self.unhandled_results = []

    def put_command(self, cmd_spec, callback, job_sub_method=None):
        """Queue a new shell command to execute."""
        cmd_type, cmd_string = cmd_spec
        try:
            result = self.pool.apply_async(
                execute_shell_command,(cmd_spec, self.current_process, job_sub_method))
        except AssertionError:
            if flags.debug:
                print "rejecting (pool closed): %s" % cmd_string
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

    def close(self):
        """Wrap pool closure.

        This closes the pool to all new commands and stops job
        submissions, but it does not stop other commands).
        """
        if not (self.is_dead() or self.is_closed()):
            if flags.debug:
                print "closing %s pool" % self.type
            self.pool.close()
            # Tell the workers to stop job submissions.
            POOL_CLOSED.value = TRUE

    def terminate(self):
        """Wrap pool termination."""
        if not self.is_dead():
            if flags.debug:
                print "terminating %s pool" % self.type
            self.pool.terminate()

    def join(self):
        """Wrap pool joining."""
        if flags.debug:
            print "joining %s pool" % self.type
        self.pool.join()

    def get_pool_size(self):
        """Return number of workers."""
        return self.poolsize

    def is_closed(self):
        """Is the pool closed?"""
        # ACCESSES POOL INTERNAL STATE
        return self.pool._state == multiprocessing.pool.CLOSE

    def is_dead(self):
        """Have all my workers exited yet?"""
        # ACCESSES POOL INTERNAL STATE
        for p in self.pool._pool:
            if p.is_alive():
                return False
        return True


if __name__ == '__main__':
    """manual test playground"""

    flags.debug = True

    def print_result(result):
        if result['OUT']:
            print 'RESULT>', result['OUT'].strip()
        if result['ERR']:
            print 'COMMAND FAILED:', result['CMD']
            print result['ERR'].strip()

    pool_config = {
            'pool type' : 'process',
            'thread pool size' : 3,
            'process pool size' : 3
            }
    pool = mp_pool(pool_config)

    for i in range(0,3):
        com = "sleep 5 && echo Hello from JOB " + str(i)
        pool.put_command((CMD_TYPE_JOB_SUBMISSION,com), print_result)
        com = "sleep 5 && echo Hello from POLL " + str(i)
        pool.put_command((CMD_TYPE_JOB_POLL_KILL,com), print_result)
        com = "sleep 5 && echo Hello from HANDLER " + str(i)
        pool.put_command((CMD_TYPE_EVENT_HANDLER,com), print_result)
        com = "sleep 5 && echo Hello from HANDLER && badcommand"
        pool.put_command((CMD_TYPE_EVENT_HANDLER,com), print_result)

    print '  sleeping'
    time.sleep(3)
    pool.handle_results_async()
    print '  sleeping'
    time.sleep(3)
    pool.close()
    #pool.terminate()
    pool.handle_results_async()
    print '  sleeping'
    time.sleep(3)
    pool.join()
    pool.handle_results_async()

