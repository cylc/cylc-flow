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
"""Allow a task to record its messages.

Send messages to:
- The stdout/stderr.
- The job status file, if there is one.
- The scheduler, if communication is possible.
"""

from logging import (
    CRITICAL,
    ERROR,
    WARNING,
    getLevelName,
)
import os
import sys
from typing import (
    List,
    Optional,
    Tuple,
)

from cylc.flow.exceptions import WorkflowStopped
import cylc.flow.flags
from cylc.flow.network.client_factory import (
    CommsMeth,
    get_client,
    get_comms_method,
)
from cylc.flow.pathutil import get_workflow_run_job_dir
from cylc.flow.task_outputs import (
    TASK_OUTPUT_FAILED,
    TASK_OUTPUT_STARTED,
    TASK_OUTPUT_SUCCEEDED,
)
from cylc.flow.wallclock import get_current_time_string


CYLC_JOB_PID = "CYLC_JOB_PID"
CYLC_JOB_INIT_TIME = "CYLC_JOB_INIT_TIME"
CYLC_JOB_EXIT = "CYLC_JOB_EXIT"
CYLC_JOB_EXIT_TIME = "CYLC_JOB_EXIT_TIME"
CYLC_MESSAGE = "CYLC_MESSAGE"

ABORT_MESSAGE_PREFIX = "aborted"
FAIL_MESSAGE_PREFIX = TASK_OUTPUT_FAILED
VACATION_MESSAGE_PREFIX = "vacated"

STDERR_LEVELS = (getLevelName(level) for level in (WARNING, ERROR, CRITICAL))

MUTATION = '''
mutation (
  $wFlows: [WorkflowID]!,
  $taskJob: String!,
  $eventTime: String,
  $messages: [[String]]
) {
  message (
    workflows: $wFlows,
    taskJob: $taskJob,
    eventTime: $eventTime,
    messages: $messages
  ) {
    result
  }
}
'''


def split_run_signal(message: str) -> Tuple[str, Optional[str]]:
    """Get the run signal from a message.

    >>> split_run_signal('failed/ERR')
    ('failed', 'ERR')
    >>> split_run_signal('aborted/mission')
    ('aborted', 'mission')
    >>> split_run_signal('failed')
    ('failed', None)
    """
    prefix, *signal = message.split('/', 1)
    return prefix, signal[0] if signal else None


def record_messages(workflow: str, job_id: str, messages: List[list]) -> None:
    """Record task job messages.

    Print the messages according to their severity.
    Write the messages in the job status file.
    Send the messages to the workflow, if possible.

    Arguments:
        workflow: Workflow ID.
        job_id: Job identifier "CYCLE/TASK_NAME/SUBMIT_NUM".
        messages: List of messages "[[severity, message], ...]".
    """
    # Record the event time, in case the message is delayed in some way.
    event_time = get_current_time_string(
        override_use_utc=(os.getenv('CYLC_UTC') == 'True'))
    write_messages(workflow, job_id, messages, event_time)
    if get_comms_method() != CommsMeth.POLL:
        send_messages(workflow, job_id, messages, event_time)


def write_messages(workflow, job_id, messages, event_time):
    # Print to stdout/stderr
    for severity, message in messages:
        if severity in STDERR_LEVELS:
            handle = sys.stderr
        else:
            handle = sys.stdout
        handle.write('%s %s - %s\n' % (event_time, severity, message))
        handle.flush()
    # Write to job.status
    _append_job_status_file(workflow, job_id, event_time, messages)


def send_messages(
    workflow: str, job_id: str, messages: List[list], event_time: str
) -> None:
    workflow = os.path.normpath(workflow)
    try:
        pclient = get_client(workflow)
    except WorkflowStopped:
        # on a remote host this means the contact file is not present
        # either the workflow is stopped or the contact file is not present
        # on the job host (i.e. comms method is polling)
        # eitherway don't try messaging
        return
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        if cylc.flow.flags.verbosity > 1:
            import traceback
            traceback.print_exc()
        # cylc message shouldn't fail if the client can't initialize.
        return
    mutation_kwargs = {
        'request_string': MUTATION,
        'variables': {
            'wFlows': [workflow],
            'taskJob': job_id,
            'eventTime': event_time,
            'messages': messages,
        }
    }
    pclient('graphql', mutation_kwargs)


def _append_job_status_file(workflow, job_id, event_time, messages):
    """Write messages to job status file."""
    job_log_name = os.getenv('CYLC_TASK_LOG_ROOT')
    if not job_log_name:
        job_log_name = get_workflow_run_job_dir(workflow, job_id, 'job')
    try:
        job_status_file = open(job_log_name + '.status', 'a')  # noqa: SIM115
        # TODO: niceify read/write/appending messages to this file
    except IOError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        if cylc.flow.flags.verbosity > 1:
            import traceback
            traceback.print_exc()
        return
    for severity, message in messages:
        message_prefix, signal = split_run_signal(message)
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
        elif signal is not None and message_prefix in {
            FAIL_MESSAGE_PREFIX, ABORT_MESSAGE_PREFIX
        }:
            job_status_file.write(
                ('%s=%s\n' % (CYLC_JOB_EXIT, signal)) +
                ('%s=%s\n' % (CYLC_JOB_EXIT_TIME, event_time))
            )
        elif signal is not None and message_prefix == VACATION_MESSAGE_PREFIX:
            # Job vacated, remove entries related to current job
            job_status_file_name = job_status_file.name
            job_status_file.close()
            lines = []
            for line in open(job_status_file_name):  # noqa: SIM115
                if not line.startswith('CYLC_JOB_'):
                    lines.append(line)
            job_status_file = open(job_status_file_name, 'w')  # noqa: SIM115
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
        if cylc.flow.flags.verbosity > 1:
            import traceback
            traceback.print_exc()
