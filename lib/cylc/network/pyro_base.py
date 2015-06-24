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

import os
import sys
from uuid import uuid4

try:
    import Pyro.core
    import Pyro.errors
except ImportError, x:
    raise SystemExit("ERROR: Pyro is not installed")

import cylc.flags
from cylc.owner import user, host, user_at_host
from cylc.passphrase import get_passphrase, PassphraseError
from cylc.registration import localdb
from cylc.network.port_file import PortRetriever
from cylc.network.connection_validator import ConnValidator
from cylc.network.client_reporter import PyroClientReporter


class PyroServer(Pyro.core.ObjBase):
    """Base class for server-side suite object interfaces."""

    def __init__(self):
        Pyro.core.ObjBase.__init__(self)
        self.client_reporter = PyroClientReporter.get_inst()

    def signout(self):
        self.client_reporter.signout(self)

    def report(self, command):
        self.client_reporter.report(command, self)


class PyroClient(object):
    """Base class for client-side suite object interfaces."""

    target_server_object = None

    def __init__(self, suite, owner=user, host=host, pyro_timeout=None,
                 port=None, db=None, my_uuid=None, print_uuid=False):
        self.suite = suite
        self.host = host
        self.owner = owner
        if pyro_timeout is not None:
            pyro_timeout = float(pyro_timeout)
        self.pyro_timeout = pyro_timeout
        self.hard_port = port
        self.pyro_proxy = None
        self.my_uuid = my_uuid or uuid4()
        if print_uuid:
            print >> sys.stderr, 'Client UUID: %s' % my_uuid
        try:
            self.pphrase = get_passphrase(suite, owner, host, localdb(db))
        except PassphraseError:
            self.pphrase = None
         
    def call_server_func(self, fname, *fargs):
        """Call server_object.fname(*fargs)
        
        Get a Pyro proxy for the server object if we don't already have it,
        and handle back compat retry for older daemons.

        """
        self._get_proxy()
        func = getattr(self.pyro_proxy, fname)
        try:
            return func(*fargs)
        except Pyro.errors.ConnectionDeniedError:
            # Back compat for daemons <= 6.4.1: passphrase-only auth.
            if cylc.flags.debug:
                print >> sys.stderr, "Old daemon? - trying passphrases."
            self.pyro_proxy = None
            self._get_proxy_old()
            func = getattr(self.pyro_proxy, fname)
            return func(*fargs)

    def _set_uri(self):
        # Find the suite port number (fails if port file not found)
        port = (self.hard_port or
                PortRetriever(self.suite, self.host, self.owner).get())
        # Qualify the obj name with user and suite name (unnecessary but
        # can't change it until we break back-compat with older daemons).
        name = "%s.%s.%s" % (self.owner, self.suite,
                             self.__class__.target_server_object)
        self.uri = "PYROLOC://%s:%s/%s" % (self.host, str(port), name)

    def _get_proxy_common(self):
        if self.pyro_proxy is None:
            self._set_uri()
            # Fails only for unknown hosts (no connection till RPC call).
            self.pyro_proxy = Pyro.core.getProxyForURI(self.uri)
            self.pyro_proxy._setTimeout(self.pyro_timeout)

    def _get_proxy(self):
        self._get_proxy_common()
        self.pyro_proxy._setNewConnectionValidator(ConnValidator())
        self.pyro_proxy._setIdentification((self.my_uuid, self.pphrase))

    def _get_proxy_old(self):
        """Back compat: passphrase-only daemons (<= 6.4.1)."""
        self._get_proxy_common()
        self.pyro_proxy._setIdentification(self.pphrase)

    def reset(self):
        self.pyro_proxy = None

    def signout(self):
        """Multi-connect clients should call this on exit."""
        try:
            self._get_proxy()
            try:
                self.pyro_proxy.signout()
            except AttributeError:
                # Back-compat for pre client reporting daemons <= 6.4.1.
                pass
        except Exception:
            # Suite may have stopped before the client exits.
            pass
