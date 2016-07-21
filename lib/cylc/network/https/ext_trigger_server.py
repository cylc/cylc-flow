#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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

import cherrypy

from Queue import Queue, Empty
import cylc.flags
from cylc.network.https.base_server import BaseCommsServer
from cylc.network.https.suite_broadcast_server import BroadcastServer
from cylc.network import check_access_priv
from cylc.task_id import TaskID


class ExtTriggerServer(BaseCommsServer):
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

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def put(self, event_message, event_id):
        """Server-side external event trigger interface."""

        check_access_priv(self, 'full-control')
        self.report("ext_trigger")
        self.queue.put((event_message, event_id))
        return (True, 'event queued')

    def retrieve(self, itask):
        """Match external triggers for a waiting task proxy."""

        # Note this has to allow multiple same-message triggers to be queued
        # and only used one at a time.

        if self.queue.empty():
            return
        if len(itask.state.external_triggers) == 0:
            return
        bcast = BroadcastServer.get_inst()
        queued = []
        while True:
            try:
                queued.append(self.queue.get_nowait())
            except Empty:
                break
        used = []
        for trig, satisfied in itask.state.external_triggers.items():
            if satisfied:
                continue
            for qmsg, qid in queued:
                if trig == qmsg:
                    # Matched.
                    name, point_string = TaskID.split(itask.identity)
                    # Set trigger satisfied.
                    itask.state.external_triggers[trig] = True
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
                            }],
                            not_from_client=True
                        )
                    used.append((qmsg, qid))
                    break
        for q in queued:
            if q not in used:
                self.queue.put(q)
