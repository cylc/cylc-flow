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

import sys
import time
import subprocess
from multiprocessing import Value, current_process
from multiprocessing.pool import CLOSE
import flags
if flags.MP_USE_PROCESS_POOL:
    from multiprocessing.pool import Pool
else:
    from multiprocessing.pool import ThreadPool as Pool
 
"""Process or thread pool for shell commands executed by the suite daemon."""

class Enum(set):
    def __getattr__(self, name):
        if name in self:
            return name
        raise AttributeError

output_capture = Enum(['ALL_LINES', 'FIRST_LINE', 'NONE'])
command_types = Enum(['JOB_SUBMISSION', 'POLL_OR_KILL', 'EVENT_HANDLER' ])

# Shared memory flag to ignore already-queued job submission commands:
TRUE=1
FALSE=0
STOP_JOB_SUBMISSION = Value('i',FALSE)

def execute_shell_command(command_spec, capture_flag):
    """Called by pool workers to execute a shell command and optionally
    capture its output and exit status.
    """

    command_type, command_string = command_spec

    print current_process().name + ": " + command_type

    command_result = {
            'COMMAND' : command_string,
            'EXIT': None,
            'OUT': None,
            'ERR': None }

    if STOP_JOB_SUBMISSION.value == TRUE and \
            command_type == command_types.JOB_SUBMISSION:
        if flags.debug:
            print >> sys.stderr, '(process pool) ignoring:', command_string
        return command_result

    if capture_flag == output_capture.NONE:
        out_err = None
    else:
        out_err = subprocess.PIPE

    try:
        p = subprocess.Popen(command_string, stdout=out_err, stderr=out_err, shell=True)
    except Exception, e:
        command_result[ 'EXIT' ] = 1
        command_result[ 'ERR'  ] = str(e)
    else:
        if capture_flag == output_capture.FIRST_LINE:
            command_result['EXIT'] = 0
            command_result['OUT' ] = p.stdout.readline().rstrip()
        elif capture_flag == output_capture.ALL_LINES:
            command_result['EXIT'] = p.wait()
            if command_result['EXIT'] is not None:
                command_result['OUT'], command_result['ERR'] = p.communicate()

    return command_result


class mp_pool(object):
    """Uses multiprocessing.Pool to execute shell commands and
    optionally capture command exit status and output.
    """

    def __init__(self, nproc=flags.MP_NPROC):
        self.pool = Pool(processes=nproc)
        self.unprocessed_results = []

    def put_command(self, command_spec, callback_func=None, capture_first_line=False):
        """Queue a command, and capture results if a callback is given."""

        # If a callback is given capture command output, else don't.
        if callback_func is None:
            capture_flag = output_capture.NONE
        elif capture_first_line:
            capture_flag = output_capture.FIRST_LINE
        else:
            capture_flag = output_capture.ALL_LINES

        try:
            result = self.pool.apply_async(
                execute_shell_command,(command_spec,capture_flag))
        except AssertionError:
            print >> sys.stderr, "WARNING, ignoring command (process pool closed):", command_spec[1]
        else:
            if callback_func:
                self.unprocessed_results.append((result,callback_func))

    def handle_results_async(self):
        """Check for command results and pass them to the callback if given."""
        still_to_do = []
        for item in self.unprocessed_results:
            res, callback = item
            if res.ready():
                callback(res.get())
            else:
                still_to_do.append((res,callback))
        self.unprocessed_results = still_to_do

    def stop_job_submission(self):
        """Tell workers not to execute further job submission commands."""
        STOP_JOB_SUBMISSION.value = TRUE

    def close(self):
        """Close the process pool to new commands."""
        self.pool.close()

    def is_closed(self):
        return self.pool._state == CLOSE

    def terminate(self):
        """Terminate pool workers immediately."""
        self.pool.terminate()

    def join(self):
        self.pool.join()


if __name__ == '__main__':
    """manual unit test"""

    flags.debug = True

    def print_result(result):
        if result['OUT'] is None:
            return
        print 'RESULT:', result['OUT'].strip()

    pool = mp_pool(3)

    for i in range(0,3):
        com = "sleep 5 && echo JOB " + str(i)
        pool.put_command((command_types.JOB_SUBMISSION,com), print_result)
        com = "sleep 5 && echo POLL " + str(i)
        pool.put_command((command_types.POLL_OR_KILL,com), print_result)
        com = "sleep 5 && echo HANDLER " + str(i)
        pool.put_command((command_types.EVENT_HANDLER,com), print_result)

    print 'sleeping'
    time.sleep(3)
    pool.handle_results_async()
    print 'sleeping'
    time.sleep(3)
    pool.stop_job_submission()
    pool.close()
    #pool.terminate()
    pool.handle_results_async()
    print 'sleeping'
    time.sleep(3)
    pool.pool.join()
    pool.handle_results_async()

