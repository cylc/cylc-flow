#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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

import sys
import time
import logging
import Queue
import Pyro.core
import Pyro.errors
import cylc.flags
import cylc.cylc_pyro_client
from cylc.task_id import TaskID
from cylc.passphrase import passphrase


PYRO_TARGET_NAME = 'external_event_broker'


class PyroClient(object):
    """Network client for sending external triggers to a suite."""

    MAX_TRIES = 5
    PYRO_TIMEOUT = 10
    RETRY_SECONDS = 10

    ERR_SEND_FAILED = "Send message: try %s of %s failed"
    STR_SEND_RETRY = "Retrying in %s seconds, timeout is %s"
    STR_SEND_SUCCEED = "Send message: try %s of %s succeeded"

    def __init__(
            self, suite, event_msg, host='localhost', owner=None,
            port=None, event_id=None, max_tries=None, pyro_timeout=None,
            retry_seconds=None):

        self.event_msg = event_msg
        self.event_id = event_id
        self.suite = suite
        self.host = host
        self.owner = owner
        self.port = port
        self.max_tries = max_tries or self.__class__.MAX_TRIES
        self.pyro_timeout = pyro_timeout or self.__class__.PYRO_TIMEOUT
        self.retry_seconds = retry_seconds or self.__class__.RETRY_SECONDS

        self.pphrase = passphrase(
            self.suite, self.owner, self.host).get(None, None)

        self.pyro_proxy = cylc.cylc_pyro_client.client(
            self.suite, self.pphrase, self.owner, self.host,
            self.pyro_timeout, self.port).get_proxy(PYRO_TARGET_NAME)

    def send(self):
        sent = False
        itry = 0
        while True:
            itry += 1
            try:
                # Get a proxy for the remote object and send the message.
                self.pyro_proxy.register(self.event_msg, self.event_id)
            except Pyro.errors.NamingError as exc:
                print >> sys.stderr, exc
                print self.__class__.ERR_SEND_FAILED % (
                    itry,
                    self.max_tries,
                )
                break
            except Exception as exc:
                print >> sys.stderr, exc
                print self.__class__.ERR_SEND_FAILED % (
                    itry,
                    self.max_tries,
                )
                if itry >= self.max_tries:
                    break
                print self.__class__.STR_SEND_RETRY % (
                    self.retry_seconds,
                    self.pyro_timeout
                )
                time.sleep(self.retry_seconds)
            else:
                if itry > 1:
                    print self.__class__.STR_SEND_SUCCEEDED % (
                        itry,
                        self.max_tries
                    )
                sent = True
                break
        if not sent:
            print >> sys.stderr, 'ERROR: event message send failed'
        return sent


class Broker(Pyro.core.ObjBase):
    """Receive and process all external event triggers for a suite."""

    _INSTANCE = None

    @classmethod
    def get_inst(cls, broadcaster=None):
        """Return a singleton instance.

        On 1st call, instantiate the singleton. The argument "broadcaster" is
        only relevant on 1st call.

        """
        if cls._INSTANCE is None:
            cls._INSTANCE = cls(broadcaster)
        return cls._INSTANCE

    def __init__(self, broadcaster):
        self.logger = logging.getLogger('main')
        self.queued = Queue.Queue()
        self.broadcaster = broadcaster
        Pyro.core.ObjBase.__init__(self)

    def register(self, message, event_id=None):
        """Register an external event with the suite."""
        trigger = message
        if event_id:
            trigger += ' (%s)' % event_id
        self.logger.log(
            logging.INFO, 'External trigger received\n%s' % trigger)
        self.queued.put((message, event_id))
        cylc.flags.pflag = True

    def retrieve(self, itask):
        """Match external triggers for a waiting task proxy."""

        # Note this has to allow multiple same-message triggers to be queued
        # and only used one at a time.

        if self.queued.empty():
            return
        if len(itask.external_triggers) == 0:
            return
        queued = []
        while True:
            try:
                queued.append(self.queued.get_nowait())
            except Queue.Empty:
                break
        used = []
        for trig, satisfied in itask.external_triggers.items():
            if satisfied:
                continue
            for qmsg, qid in queued:
                if trig == qmsg:
                    # Matched.
                    name, point_string = TaskID.split(itask.identity)
                    # Set trigger satisfied.
                    itask.external_triggers[trig] = True
                    cylc.flags.pflag = True
                    # Broadcast the event ID to the cycle point.
                    if qid is not None:
                        self.broadcaster.put(
                            [point_string],
                            ["root"],
                            [{
                                'environment': {
                                    'CYLC_EXT_TRIGGER_ID': qid
                                }
                            }]
                        )
                    used.append((qmsg, qid))
                    break
        for q in queued:
            if q not in used:
                self.queued.put(q)
