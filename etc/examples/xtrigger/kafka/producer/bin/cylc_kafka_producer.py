#!/usr/bin/env python3
"""
A generic Kafka producer for use as a Cylc event handler.

Hilary Oliver, October 2017.

"""

import sys
import json
from inspect import cleandoc
from kafka import KafkaProducer


def main():
    """
    A generic Kafka producer for use as a Cylc event handler.

    USAGE:
       cylc_kafka_producer.py <HOST:PORT> <TOPIC> key1=val1 key2=val2 ...
    serializes {key1: val1, key2: val2, ...} to TOPIC at Kafka on HOST:PORT.

    This is generic in that a JSON message schema is defined by the received
    command line keyword arguments. To enforce compliance to a particular
    schema, copy and modify as needed.

    Can be partnered with the generic cylc_kafka_consumer external trigger
    function, for triggering downstream suites.

    """

    if 'help' in sys.argv[1]:
        print(cleandoc(main.__doc__))
        sys.exit(0)

    # TODO exception handling for bad inputs etc.
    kafka_server = sys.argv[1]
    kafka_topic = sys.argv[2]
    # Construct a message dict from kwargs.
    dmsg = {k.split('=') for k in sys.argv[3:]}

    producer = KafkaProducer(
        bootstrap_servers=kafka_server,
        value_serializer=lambda msg: json.dumps(msg).encode('utf-8'))

    producer.send(kafka_topic, dmsg)
    producer.flush()


if __name__ == "__main__":
    main()
