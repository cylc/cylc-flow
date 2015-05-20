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
from time import sleep 
from Queue import Queue, Empty
import Pyro.errors
import cylc.flags
from cylc.network.pyro_base import PyroClient, PyroServer
from cylc.network.suite_broadcast import BroadcastServer
from cylc.task_id import TaskID


PYRO_EXT_TRIG_OBJ_NAME = 'ext-trigger-interface'


class ExtTriggerServer(PyroServer):
    """Server-side external trigger interface."""

    _INSTANCE = None

    @classmethod
    def get_inst(cls):
        """Return a singleton instance."""
        if cls._INSTANCE is None:
            cls._INSTANCE = cls()
        return cls._INSTANCE

    def __init__(self):
        super(ExtTriggerServer, self).__init__()
        self.queue = Queue()
 
    def put(self, event_message, event_id):
        self.queue.put((event_message, event_id))
        return (True, 'event queued')

    def retrieve(self, itask):
        """Match external triggers for a waiting task proxy."""

        # Note this has to allow multiple same-message triggers to be queued
        # and only used one at a time.

        if self.queue.empty():
            return
        if len(itask.external_triggers) == 0:
            return
        bcast = BroadcastServer.get_inst()
        queued = []
        while True:
            try:
                queued.append(self.queue.get_nowait())
            except Empty:
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
                        bcast.put(
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
                self.queue.put(q)


class ExtTriggerClient(PyroClient):
    """Client-side external trigger interface."""

    target_server_object = PYRO_EXT_TRIG_OBJ_NAME

    MAX_N_TRIES = 5
    RETRY_INTVL_SECS = 10.0

    MSG_CLIENT_REPORT = '"%s" %s'
    MSG_SEND_FAILED = "Send message: try %s of %s failed"
    MSG_SEND_RETRY = "Retrying in %s seconds, timeout is %s"
    MSG_SEND_SUCCEED = "Send message: try %s of %s succeeded"

    def put(self, event_message, event_id):
        self._report(self.__class__.MSG_CLIENT_REPORT % (
            event_message, event_id))
        return self.pyro_proxy.put(event_message, event_id)

    def send_retry(self, event_message, event_id,
                   max_n_tries, retry_intvl_secs):
        """CLI external trigger interface."""

        max_n_tries = int(max_n_tries or self.__class__.MAX_N_TRIES)
        retry_intvl_secs = float(
            retry_intvl_secs or self.__class__.RETRY_INTVL_SECS)

        sent = False
        i_try = 0
        while not sent and i_try < max_n_tries:
            i_try += 1
            try:
                self.put(event_message, event_id)
            except Pyro.errors.NamingError as exc:
                print >> sys.stderr, exc
                print self.__class__.MSG_SEND_FAILED % (
                    i_try,
                    max_n_tries,
                )
                break
            except Exception as exc:
                print >> sys.stderr, exc
                print self.__class__.MSG_SEND_FAILED % (
                    i_try,
                    max_n_tries,
                )
                if i_try >= max_n_tries:
                    break
                print self.__class__.MSG_SEND_RETRY % (
                    retry_intvl_secs,
                    self.pyro_timeout
                )
                sleep(retry_intvl_secs)
            else:
                if i_try > 1:
                    print self.__class__.MSG_SEND_SUCCEEDED % (
                        i_try,
                        max_n_tries
                    )
                sent = True
                break
        if not sent:
            sys.exit('ERROR: send failed')
        return sent


        #try:
        #    self._report(log_msg)
        #    success, msg = self.pyro_proxy.put(event_message, event_id)
        #except Exception as exc:
        #    if cylc.flags.debug:
        #        raise
        #    sys.exit(exc)
        #if success:
        #    print msg
        #else:
        #    sys.exit(msg)
