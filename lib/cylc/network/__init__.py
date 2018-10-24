#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & Contributors.
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

"""Package for network interfaces to cylc suite server objects."""

import random
import socket

from ..cfgspec.glbl_cfg import glbl_cfg

# Dummy passphrase for client access from users without the suite passphrase.
NO_PASSPHRASE = 'the quick brown fox'

# Ordered privilege levels for authenticated users.
PRIV_IDENTITY = 'identity'
PRIV_DESCRIPTION = 'description'
PRIV_STATE_TOTALS = 'state-totals'
PRIV_FULL_READ = 'full-read'
PRIV_SHUTDOWN = 'shutdown'
PRIV_FULL_CONTROL = 'full-control'
PRIVILEGE_LEVELS = [
    PRIV_IDENTITY,
    PRIV_DESCRIPTION,
    PRIV_STATE_TOTALS,
    PRIV_FULL_READ,
    PRIV_SHUTDOWN,  # (Not used yet - for the post-passphrase era.)
    PRIV_FULL_CONTROL,
]


def get_free_port(host):
    # get a random pool of ports that we can use to connect
    ok_ports = glbl_cfg().get(['suite servers', 'run ports'])
    random.shuffle(ok_ports)

    # Check on specified host for free port
    for port in ok_ports:
        sock_check = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock_check.settimeout(1)
            sock_check.connect((host, port))
            sock_check.close()
        except socket.error:
            return port

    raise Exception("No available ports")
