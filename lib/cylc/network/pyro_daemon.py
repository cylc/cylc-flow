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
import socket
try:
    import Pyro
except ImportError:
    sys.exit("ERROR: Pyro is not installed")

from cylc.owner import user
from cylc.network.connection_validator import ConnValidator
from cylc.cfgspec.globalcfg import GLOBAL_CFG


class PyroDaemon(object):
    def __init__(self, suite):

        Pyro.config.PYRO_MULTITHREADED = 1
        # Use dns names instead of fixed ip addresses from /etc/hosts
        # (see the Userguide "Networking Issues" section).
        Pyro.config.PYRO_DNS_URI = True

        # Base Pyro socket number.
        Pyro.config.PYRO_PORT = GLOBAL_CFG.get(['pyro', 'base port'])
        # Max number of sockets starting at base.
        Pyro.config.PYRO_PORT_RANGE = GLOBAL_CFG.get(
            ['pyro', 'maximum number of ports'])

        Pyro.core.initServer()
        self.daemon = None
        # Suite only needed for back-compat with old clients (see below):
        self.suite = suite

    def set_auth(self, passphrase):
        self.daemon = Pyro.core.Daemon()
        cval = ConnValidator()
        cval.set_pphrase(passphrase)
        self.daemon.setNewConnectionValidator(cval)

    def shutdown(self):
        self.daemon.shutdown(True)
        # If a suite shuts down via 'stop --now' or # Ctrl-C, etc.,
        # any existing client end connections will hang for a long time
        # unless we do the following (or cylc clients set a timeout,
        # presumably) which daemon.shutdown() does not do (why not?):

        try:
            self.daemon.sock.shutdown(socket.SHUT_RDWR)
        except socket.error, x:
            print >> sys.stderr, x

    def connect(self, obj, name):
        if not obj.__class__.__name__ == 'SuiteIdServer':
            # Qualify the obj name with user and suite name (unnecessary but
            # can't change it until we break back-compat with older daemons).
            name = "%s.%s.%s" % (user, self.suite, name)
        uri = self.daemon.connect(obj, name)

    def disconnect(self, obj):
        self.daemon.disconnect(obj)

    def handleRequests(self, timeout=None):
        self.daemon.handleRequests(timeout)

    def get_port(self):
        return self.daemon.port
