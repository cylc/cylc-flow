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

from Queue import Queue
from cylc.network import check_access_priv
from cylc.network.https.base_server import BaseCommsServer

import cherrypy


class TaskMessageServer(BaseCommsServer):
    """Server-side task messaging interface"""

    def __init__(self, suite):
        self.queue = Queue()
        super(TaskMessageServer, self).__init__()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def put(self, task_id, priority, message):
        """Notify the suite daemon of a task message.

        Example URL:

        * /put?task_id=foo.1&priority=NORMAL&message=foo.1+succeeded

        Args:

        * task_id - string
            task_id should be the task that originates the message.
        * priority - string
            priority should be NORMAL, WARNING, or CRITICAL
        * message - string
            message should usually be a known output message for the
            task (e.g. to indicate that the task succeeded). It can
            also be a custom message.

        """
        check_access_priv(self, 'full-control')
        self.report('task_message')
        self.queue.put((task_id, priority, str(message)))
        return 'Message queued'

    def get_queue(self):
        return self.queue
