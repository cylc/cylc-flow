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

from Queue import Queue
from cylc.owner import user
from cylc.suite_host import get_hostname
from cylc.network.pyro_base import PyroClient, PyroServer


class TaskMessageServer(PyroServer):
    """Server-side task messaging interface"""

    def __init__(self):
        super(PyroServer, self).__init__()
        self.queue = Queue()

    def put(self, priority, message):
        self.queue.put((priority, message))
        return (True, 'Message queued')

    def get_queue(self):
        return self.queue


class TaskMessageClient(PyroClient):
    """Client-side task messaging interface"""

    def __init__(self, suite, task_id, pphrase, owner=user, host=get_hostname(),
                 pyro_timeout=None, port=None):
        self.__class__.target_server_object = task_id
        super(TaskMessageClient, self).__init__(suite, pphrase, owner, host,
                                                pyro_timeout, port)
    def put(self, *args):
        self._report('task_message')
        self.pyro_proxy.put(*args)
