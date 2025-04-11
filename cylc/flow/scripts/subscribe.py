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

"""cylc subscribe [OPTIONS] ARGS

(This command is for internal use.)

Invoke workflow subscriber to receive published workflow output.
"""

import json
import sys
import time

from google.protobuf.json_format import MessageToDict

from cylc.flow.exceptions import ClientError
from cylc.flow.option_parsers import (
    WORKFLOW_ID_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow.network import get_location
from cylc.flow.network.subscriber import WorkflowSubscriber, process_delta_msg
from cylc.flow.terminal import cli_function
from cylc.flow.data_store_mgr import DELTAS_MAP

INTERNAL = True


def print_message(topic, data, subscriber=None, once=False):
    """Print protobuf message."""
    print(f'Received: {topic}')
    if topic == 'shutdown':
        print(data.decode('utf-8'))
        subscriber.stop()
        return
    sys.stdout.write(
        json.dumps(MessageToDict(data), indent=4) + '\n')
    if once and subscriber is not None:
        subscriber.stop()


def get_option_parser() -> COP:
    """Augment options parser to current context."""
    parser = COP(
        __doc__,
        argdoc=[WORKFLOW_ID_ARG_DOC],
        comms=True
    )

    delta_keys = list(DELTAS_MAP)
    pb_topics = ("Directly published data-store topics include: '" +
                 ("', '").join(delta_keys[:-1]) +
                 "' and '" + delta_keys[-1] + "'.")
    parser.add_option(
        "-T", "--topics",
        help="Specify a comma delimited list of subscription topics. "
        + pb_topics,
        action="store", dest="topics", default='workflow')

    parser.add_option(
        "-o", "--once",
        help="Show a single publish then exit.",
        action="store_true", default=False, dest="once")

    return parser


@cli_function(get_option_parser)
def main(_, options, *args):
    workflow_id = args[0]

    try:
        while True:
            try:
                host, _, port, _ = get_location(workflow_id)
            except (ClientError, IOError, TypeError, ValueError) as exc:
                print(exc)
                time.sleep(3)
                continue
            break
    except KeyboardInterrupt:
        sys.exit()

    print(f'Connecting to tcp://{host}:{port}')
    topic_set = set()
    topic_set.add(b'shutdown')
    for topic in options.topics.split(','):
        topic_set.add(topic.encode('utf-8'))

    subscriber = WorkflowSubscriber(
        workflow_id,
        host=host,
        port=port,
        topics=topic_set
    )

    subscriber.loop.create_task(
        subscriber.subscribe(
            process_delta_msg,
            func=print_message,
            subscriber=subscriber,
            once=options.once
        )
    )

    # run Python run
    try:
        subscriber.loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        print('\nDisconnecting')
        subscriber.stop()
        sys.exit()
