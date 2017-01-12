#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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
"""Wrap Pyro daemon for a suite."""

import socket
import traceback

import Pyro
from cylc.cfgspec.globalcfg import GLOBAL_CFG
from cylc.network.connection_validator import ConnValidator
from cylc.owner import USER
from cylc.registration import RegistrationDB


class PyroDaemon(object):
    """Wrap Pyro daemon for a suite."""

    def __init__(self, suite, suite_dir):
        # Suite only needed for back-compat with old clients (see below):
        self.suite = suite

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
        self.daemon = Pyro.core.Daemon()
        cval = ConnValidator()
        self.daemon.setNewConnectionValidator(cval)
        cval.set_pphrase(RegistrationDB.load_passphrase_from_dir(suite_dir))

    def shutdown(self):
        """Shutdown the daemon."""
        self.daemon.shutdown(True)
        # If a suite shuts down via 'stop --now' or # Ctrl-C, etc.,
        # any existing client end connections will hang for a long time
        # unless we do the following (or cylc clients set a timeout,
        # presumably) which daemon.shutdown() does not do (why not?):

        try:
            self.daemon.sock.shutdown(socket.SHUT_RDWR)
        except socket.error:
            traceback.print_exc()

        # Force all Pyro threads to stop now, to prevent them from raising any
        # exceptions during Python interpreter shutdown - see GitHub #1890.
        self.daemon.closedown()

    def connect(self, obj, name):
        """Connect obj and name to the daemon."""
        if not obj.__class__.__name__ == 'SuiteIdServer':
            # Qualify the obj name with user and suite name (unnecessary but
            # can't change it until we break back-compat with older daemons).
            name = "%s.%s.%s" % (USER, self.suite, name)
        self.daemon.connect(obj, name)

    def disconnect(self, obj):
        """Disconnect obj from the daemon."""
        self.daemon.disconnect(obj)

    def handle_requests(self, timeout=None):
        """Handle Pyro requests."""
        self.daemon.handleRequests(timeout)

    def get_port(self):
        """Return the daemon port."""
        return self.daemon.port
