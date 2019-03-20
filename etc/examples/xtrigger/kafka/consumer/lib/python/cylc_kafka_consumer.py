#!/usr/bin/env python3
"""
A generic Kakfa consumer for use as a Cylc external trigger function.

A NOTE ON OVERHEADS of checking Kafka for an external trigger condition at
intervals, vs a persistent consumer looking for all suite trigger messages:

 1) Every unique trigger has to check Kafka separately for its own specific
 message, at intervals until the message is found.
 2) Every call has connection and authentication overheads.
 3) The first call for each unique trigger has to consume messages from the
 start of the topic - required in case messages are checked for out of order.
 Subsequent checks for the same message do not need to start from the beginning
 of the topic. This is achieved by giving each trigger a unique consumer group
 ID.

"""

import re
import json

from kafka import KafkaConsumer

from cylc import LOG

# Time out after 1 second if we reach the end of the topic.
CONSUMER_TIMEOUT_MS = 1000


def _match_msg(cylc_msg, kafka_msg):
    all_msg_items_matched = True
    result = {}
    for ckey, cval in cylc_msg.items():
        if ckey not in kafka_msg.value:
            all_msg_items_matched = False
            break
        elif cval.startswith('<') and cval.endswith('>'):
            m = re.match(cval[1:-1], kafka_msg.value[ckey])
            # TODO: check regex; and num match groups should be one.
            if m:
                result[ckey] = m.group(0)
            else:
                all_msg_items_matched = False
                break
        elif kafka_msg.value[ckey] != cval:
            all_msg_items_matched = False
            break
        else:
            # exact match this field
            result[ckey] = cval
    if all_msg_items_matched:
        return result
    else:
        return {}


def cylc_kafka_consumer(kafka_server, kafka_topic, group_id, message, debug):
    r"""Look for a matching message in a Kafka topic.

    ARGUMENTS:
     * kafka_server - Kafka server URL, e.g. "localhost:9092".
     * kafka_topic - the Kafka topic to check, e.g. "data-avail".
     * group_id - determines Kafka offset ownership (see below).
     * message - string-ified dict with optional pattern elements (see below).
     * debug - boolean; set by daemon debug mode; prints to suite err log.

    The topic is first consumed from the beginning, then from the previous
    committed offset. If the message is not found by end of topic, commit the
    offset and return (to will try again later). If found, return the result.

    Kafka commits offsets per "consumer group" so the group_id argument
    must be unique per distinct trigger in the suite - this allows each trigger
    to separately consume the topic from the beginning, looking for its own
    messages (otherwise, with shared offsets, one trigger could move the offset
    beyond the messages of another trigger). This goes for successive instances
    of an external-triggered cycling task too, because out-of-order triggering
    could be required sometimes. So this argument should typically be, e.g.:

        group_id=x%(id)s  # id ID of the dependent task

    where "x" is an arbitrary string you can use to change the group name if
    you need to re-run the suite, and the messages, from the start again,
    without re-running the producer suite. Note this also serves to make the
    function signature cycle-point-specific for Cylc even if the message does
    not contain the cycle point (although it probably should).

    The "message" argument is a stringified dict, e.g.:
        {'system': 'prod', 'point': '2025', 'data': '<nwp.*\.nc>'}
    should be represented as:
        "system:prod point:2025 data:<nwp.*\.nc>"

    A match occurs Kafka if all message dict items match, and the result
    returned is the sub-dict of the actual values of items containing
    angle-bracket-delineated regex patterns. E.g. above {'data': 'nwp-2025.nc'}

    """

    consumer = KafkaConsumer(kafka_topic, bootstrap_servers=[kafka_server],
                             value_deserializer=json.loads,
                             consumer_timeout_ms=CONSUMER_TIMEOUT_MS,
                             auto_offset_reset='earliest',
                             group_id=group_id)

    # Construct a dict from the message argument "key1=val1 key2=val2 ...".
    cylc_msg = dict(m.split(':') for m in message.split())

    result = (False, {})
    n_cons = 0
    for kafka_msg in consumer:
        n_cons += 1
        m = _match_msg(cylc_msg, kafka_msg)
        if m:
            result = (True, m)
            break
        # (else consume and compare next message)
    consumer.commit()
    # Unsubscribe before exit, otherwise next call will be slow while
    # Kafka times out waiting for this original consumer connection.
    consumer.unsubscribe()
    if debug:
        if result[0]:
            res = "\n  MATCHED: %s" % result[1]
        else:
            res = "no match."
        LOG.debug('Kafka: "%s" (consumed %d) ... %s', message, n_cons, res)
    return result
