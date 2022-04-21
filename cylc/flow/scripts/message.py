#!/usr/bin/env python3

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
r"""cylc message [OPTIONS] -- ARGS

Record task job messages.

Send task job messages to:
- The job stdout/stderr.
- The job status file, if there is one.
- The scheduler, if communication is possible.

Task jobs use this command to record and report status such as success and
failure. Applications run by task jobs can use this command to report messages
and to report registered task outputs.

Messages can be specified as arguments. A '-' indicates that the command should
read messages from STDIN. When reading from STDIN, multiple messages are
separated by empty lines.

Examples:
  # Single message as an argument:
  $ cylc message -- "${CYLC_WORKFLOW_ID}" "${CYLC_TASK_JOB}" 'Hello world!'

  # Multiple messages as arguments:
  $ cylc message -- "${CYLC_WORKFLOW_ID}" "${CYLC_TASK_JOB}" \
  >     'Hello world!' 'Hi' 'WARNING:Hey!'

  # Multiple messages on STDIN:
  $ cylc message -- "${CYLC_WORKFLOW_ID}" "${CYLC_TASK_JOB}" - <<'__STDIN__'
  > Hello
  > world!
  >
  > Hi
  >
  > WARNING:Hey!
  >__STDIN__

Note "${CYLC_WORKFLOW_ID}" and "${CYLC_TASK_JOB}" are available in task job
environments - you do not need to write their actual values in task scripting.

Each message can be prefixed with a severity level using the syntax 'SEVERITY:
MESSAGE' (colons cannot be used unless such a prefix is provided).

The default message severity is INFO. The --severity=SEVERITY option can be
used to set the default severity level for all unprefixed messages.

Note: to abort a job script with a custom error message, use cylc__job_abort:
  cylc__job_abort 'message...'
(For technical reasons this is a shell function, not a cylc sub-command.)

For backward compatibility, if number of arguments is less than or equal to 2,
the command assumes the classic interface, where all arguments are messages.
Otherwise, the first 2 arguments are assumed to be workflow name and task job
identifier.
"""


from logging import getLevelName, INFO
import os
import sys
from typing import TYPE_CHECKING

from cylc.flow.id_cli import parse_id
from cylc.flow.option_parsers import (
    WORKFLOW_ID_ARG_DOC,
    CylcOptionParser as COP
)
from cylc.flow.task_message import record_messages
from cylc.flow.terminal import cli_function
from cylc.flow.exceptions import InputError
from cylc.flow.unicode_rules import TaskMessageValidator

if TYPE_CHECKING:
    from optparse import Values


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        comms=True,
        argdoc=[
            # TODO
            COP.optional(WORKFLOW_ID_ARG_DOC),
            COP.optional(
                ('TASK-JOB', 'Task job identifier CYCLE/TASK_NAME/SUBMIT_NUM')
            ),
            COP.optional(
                ('[SEVERITY:]MESSAGE ...', 'Messages')
            )
        ]
    )

    parser.add_option(
        '-s', '--severity', '-p', '--priority',
        metavar='SEVERITY',
        help='Set severity levels for messages that do not have one',
        action='store', dest='severity')

    return parser


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', *args: str) -> None:
    """CLI."""
    if not args:
        return parser.error('No message supplied')
    if len(args) <= 2:
        # BACK COMPAT: args <= 2
        # from:
        #     7.6?
        # remove at:
        #     9.0?
        # (As of Dec 2020 some functional tests still use the classic
        # two arg interface)
        workflow_id = os.getenv('CYLC_WORKFLOW_ID')
        task_job = os.getenv('CYLC_TASK_JOB')
        message_strs = list(args)
    else:
        workflow_id, task_job, *message_strs = args
        workflow_id, *_ = parse_id(
            workflow_id,
            constraint='workflows',
        )
    # Read messages from STDIN
    if '-' in message_strs:
        current_message_str = ''
        while True:  # Note: `for line in sys.stdin:` can hang
            message_str = sys.stdin.readline()
            if message_str.strip():
                # non-empty line
                current_message_str += message_str
            elif message_str:
                # empty line, start next message
                if current_message_str:
                    message_strs.append(current_message_str)
                current_message_str = ''  # reset
            else:
                # end of file
                if current_message_str:
                    message_strs.append(current_message_str)
                break
    # Separate "severity: message"
    messages = []  # [(severity, message_str), ...]
    for message_str in message_strs:
        if message_str == '-':
            pass
        elif ':' in message_str:
            valid, err_msg = TaskMessageValidator.validate(message_str)
            if not valid:
                raise InputError(
                    f'Invalid task message "{message_str}" - {err_msg}')
            messages.append(
                [item.strip() for item in message_str.split(':', 1)])
        elif options.severity:
            messages.append([options.severity, message_str.strip()])
        else:
            messages.append([getLevelName(INFO), message_str.strip()])
    record_messages(workflow_id, task_job, messages)
