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

try:
    import Pyro.core
except ImportError, x:
    raise SystemExit("ERROR: Pyro is not installed")

import os
import sys
from time import sleep
from uuid import uuid4

import cylc.flags
from cylc.suite_host import get_hostname
from cylc.owner import user, user_at_host
from cylc.port_file import port_retriever
from cylc.network.client_reporter import PyroClientReporter


class PyroServer(Pyro.core.ObjBase):
    """Base class for server-side suite object interfaces."""

    def __init__(self):
        Pyro.core.ObjBase.__init__(self)
        self.client_reporter = PyroClientReporter.get_inst()

    def signout(self, uuid, info):
        self.client_reporter.signout(uuid, info)

    def report(self, command, uuid, info, multi):
        self.client_reporter.report(command, uuid, info, multi)


class PyroClient(object):
    """Base class for client-side suite object interfaces."""

    target_server_object = None

    def __init__(
        self, suite, pphrase, owner=user, host=get_hostname(),
        pyro_timeout=None, port=None, my_uuid=None):

        self.suite = suite
        self.host = host
        self.owner = owner
        if pyro_timeout is not None:
            pyro_timeout = float(pyro_timeout)
        self.pyro_timeout = pyro_timeout
        self.pphrase = pphrase
        self.hard_port = port
        self.pyro_proxy = None
        # Multi-client programs (cylc-gui) can give their own client ID:
        self.my_uuid = my_uuid or uuid4()
        # Possibly non-unique client info:
        self.my_info = {
            'user_at_host': user_at_host,
            'name': os.path.basename(sys.argv[0])
        }
        self.multi = False

    def get_client_uuid(self):
        return self.my_uuid

    def set_multi(self):
        """Declare this to be a multi-connect client (GUI, monitor)."""
        self.multi = True

    def reset(self):
        """Cause _get_proxy() to start from scratch."""
        self.pyro_proxy = None

    def _get_proxy(self):
        """Get the Pyro proxy if we don't already have it."""
        if self.pyro_proxy is None:
            # The following raises a PortFileError if the port file is not found.
            port = (self.hard_port or
                    port_retriever(self.suite, self.host, self.owner).get())
            objname = "%s.%s.%s" % (self.owner, self.suite, self.__class__.target_server_object)
            uri = "PYROLOC://%s:%s/%s" % (self.host, str(port), objname)
            # The following only fails for unknown hosts.
            # No connection is made until an RPC call is attempted.
            self.pyro_proxy = Pyro.core.getProxyForURI(uri)
            self.pyro_proxy._setTimeout(self.pyro_timeout)
            self.pyro_proxy._setIdentification(self.pphrase)

    def signout(self):
        """Multi-connect clients should call this on exit."""
        try:
            self._get_proxy()
            try:
                self.pyro_proxy.signout(self.my_uuid, self.my_info)
            except AttributeError:
                # Back compat.
                pass
        except Exception:
            # Suite may have stopped before the client exits.
            pass

    def _report(self, command):
        self._get_proxy()
        try:
            self.pyro_proxy.report(
                command.replace(' ', '_'), self.my_uuid, self.my_info, self.multi)
        except AttributeError:
            # Back compat.
            pass
