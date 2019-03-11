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
"""Allow a task job to record its messages.

Send task job messages to:
- The stdout/stderr.
- The job status file, if there is one.
- The suite server program, if communication is possible.
"""

from logging import getLevelName, WARNING, ERROR, CRITICAL
import os
import sys


from cylc.cfgspec.glbl_cfg import glbl_cfg
import cylc.flags
from cylc.network.client import SuiteRuntimeClient
from cylc.task_outputs import TASK_OUTPUT_STARTED, TASK_OUTPUT_SUCCEEDED
from cylc.wallclock import get_current_time_string


CYLC_JOB_PID = "CYLC_JOB_PID"
CYLC_JOB_INIT_TIME = "CYLC_JOB_INIT_TIME"
CYLC_JOB_EXIT = "CYLC_JOB_EXIT"
CYLC_JOB_EXIT_TIME = "CYLC_JOB_EXIT_TIME"
CYLC_MESSAGE = "CYLC_MESSAGE"

ABORT_MESSAGE_PREFIX = "aborted/"
FAIL_MESSAGE_PREFIX = "failed/"
VACATION_MESSAGE_PREFIX = "vacated/"

STDERR_LEVELS = (getLevelName(level) for level in (WARNING, ERROR, CRITICAL))


def record_messages(suite, task_job, messages):
    """Record task job messages.

    Print the messages according to their severity.
    Write the messages in the job status file.
    Send the messages to the suite, if possible.

    Arguments:
        suite (str): Suite name.
        task_job (str): Task job identifier "CYCLE/TASK_NAME/SUBMIT_NUM".
        messages (list): List of messages "[[severity, message], ...]".
    """
    # Record the event time, in case the message is delayed in some way.
    event_time = get_current_time_string(
        override_use_utc=(os.getenv('CYLC_UTC') == 'True'))
    # Print to stdout/stderr
    for severity, message in messages:
        if severity in STDERR_LEVELS:
            handle = sys.stderr
        else:
            handle = sys.stdout
        handle.write('%s %s - %s\n' % (event_time, severity, message))
    handle.flush()
    # Write to job.status
    _append_job_status_file(suite, task_job, event_time, messages)
    # Send messages
    try:
        pclient = SuiteRuntimeClient(suite)
    except Exception:
        # Backward communication not possible
        if cylc.flags.debug:
            import traceback
            traceback.print_exc()
    pclient(
        'put_messages',
        {'task_job': task_job, 'event_time': event_time, 'messages': messages}
    )


def _append_job_status_file(suite, task_job, event_time, messages):
    """Write messages to job status file."""
    job_log_name = os.getenv('CYLC_TASK_LOG_ROOT')
    if not job_log_name:
        job_log_name = os.path.join(
            glbl_cfg().get_derived_host_item(suite, 'suite job log directory'),
            'job')
    try:
        job_status_file = open(job_log_name + '.status', 'a')
    except IOError:
        if cylc.flags.debug:
            import traceback
            traceback.print_exc()
        return
    for severity, message in messages:
        if message == TASK_OUTPUT_STARTED:
            job_id = os.getppid()
            if job_id > 1:
                # If os.getppid() returns 1, the original job process
                # is likely killed already
                job_status_file.write('%s=%s\n' % (CYLC_JOB_PID, job_id))
            job_status_file.write('%s=%s\n' % (CYLC_JOB_INIT_TIME, event_time))
        elif message == TASK_OUTPUT_SUCCEEDED:
            job_status_file.write(
                ('%s=%s\n' % (CYLC_JOB_EXIT, TASK_OUTPUT_SUCCEEDED.upper())) +
                ('%s=%s\n' % (CYLC_JOB_EXIT_TIME, event_time)))
        elif message.startswith(FAIL_MESSAGE_PREFIX):
            job_status_file.write(
                ('%s=%s\n' % (
                    CYLC_JOB_EXIT,
                    message[len(FAIL_MESSAGE_PREFIX):])) +
                ('%s=%s\n' % (CYLC_JOB_EXIT_TIME, event_time)))
        elif message.startswith(ABORT_MESSAGE_PREFIX):
            job_status_file.write(
                ('%s=%s\n' % (
                    CYLC_JOB_EXIT,
                    message[len(ABORT_MESSAGE_PREFIX):])) +
                ('%s=%s\n' % (CYLC_JOB_EXIT_TIME, event_time)))
        elif message.startswith(VACATION_MESSAGE_PREFIX):
            # Job vacated, remove entries related to current job
            job_status_file_name = job_status_file.name
            job_status_file.close()
            lines = []
            for line in open(job_status_file_name):
                if not line.startswith('CYLC_JOB_'):
                    lines.append(line)
            job_status_file = open(job_status_file_name, 'w')
            for line in lines:
                job_status_file.write(line)
            job_status_file.write('%s=%s|%s|%s\n' % (
                CYLC_MESSAGE, event_time, severity, message))
        else:
            job_status_file.write('%s=%s|%s|%s\n' % (
                CYLC_MESSAGE, event_time, severity, message))
    try:
        job_status_file.close()
    except IOError:
        if cylc.flags.debug:
            import traceback
            traceback.print_exc()
