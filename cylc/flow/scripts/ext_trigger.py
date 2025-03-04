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

"""cylc ext-trigger [OPTIONS] ARGS

Report an external event message to a scheduler.

External triggers allow any program to send a message to the Cylc scheduler.
Cylc can use this message as a signal that an external prerequisite has been
satisfied and trigger the task accordingly.

The WORKFLOW argument should be unique to each external trigger event. When
an incoming message satisfies a task's external trigger the message TRIGGER_ID
is broadcast to all downstream tasks in the cycle point as
``$CYLC_EXT_TRIGGER_ID``.  Tasks can use ``$CYLC_EXT_TRIGGER_ID``, for example,
to identify a new data file that the external triggering system is responding
to.

Use the retry options in case the target workflow is down or out of contact.

Note: to manually trigger a task use 'cylc trigger', not this command.
"""

from time import sleep
from typing import TYPE_CHECKING

from cylc.flow import LOG
from cylc.flow.exceptions import CylcError, ClientError
from cylc.flow.id_cli import parse_id
from cylc.flow.network.client_factory import get_client
from cylc.flow.option_parsers import (
    WORKFLOW_ID_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow.terminal import cli_function

if TYPE_CHECKING:
    from optparse import Values


MAX_N_TRIES = 5
RETRY_INTVL_SECS = 10.0

MSG_SEND_FAILED = "Send message: try %s of %s failed"
MSG_SEND_RETRY = "Retrying in %s seconds, timeout is %s"
MSG_SEND_SUCCEED = "Send message: try %s of %s succeeded"

MUTATION = '''
mutation (
  $wFlows: [WorkflowID]!,
  $eventMsg: String!,
  $eventId: String!
) {
  extTrigger (
    workflows: $wFlows,
    message: $eventMsg,
    id: $eventId
  ) {
    result
  }
}
'''


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        comms=True,
        argdoc=[
            WORKFLOW_ID_ARG_DOC,
            ("MSG", "External trigger message"),
            ("TRIGGER_ID", "Unique trigger ID"),
        ],
    )

    parser.add_option(
        "--max-tries",
        help=r"Maximum number of send attempts (default: %default).",
        metavar="INT",
        action="store",
        default=MAX_N_TRIES,
        dest="max_n_tries"
    )

    parser.add_option(
        "--retry-interval",
        help=r"Delay in seconds before retrying (default: %default).",
        metavar="SEC",
        action="store",
        default=RETRY_INTVL_SECS,
        dest="retry_intvl_secs"
    )

    return parser


@cli_function(get_option_parser)
def main(
    parser: COP,
    options: 'Values',
    workflow_id: str,
    event_msg: str,
    event_id: str
) -> None:
    workflow_id, *_ = parse_id(
        workflow_id,
        constraint='workflows',
    )
    LOG.info(
        'Send to workflow %s: "%s" (%s)', workflow_id, event_msg, event_id
    )
    pclient = get_client(workflow_id, timeout=options.comms_timeout)

    max_n_tries = int(options.max_n_tries)
    retry_intvl_secs = float(options.retry_intvl_secs)

    mutation_kwargs = {
        'request_string': MUTATION,
        'variables': {
            'wFlows': [workflow_id],
            'eventMsg': event_msg,
            'eventId': event_id,
        }
    }

    for i_try in range(max_n_tries):
        try:
            pclient('graphql', mutation_kwargs)
        except ClientError as exc:
            LOG.exception(exc)
            LOG.info(MSG_SEND_FAILED, i_try + 1, max_n_tries)
            if i_try == max_n_tries - 1:  # final attempt
                raise CylcError('send failed') from None
            LOG.info(MSG_SEND_RETRY, retry_intvl_secs, options.comms_timeout)
            sleep(retry_intvl_secs)
        else:
            if i_try > 0:
                LOG.info(MSG_SEND_SUCCEED, i_try + 1, max_n_tries)
            break
