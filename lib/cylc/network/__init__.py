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

"""Package for network interfaces to cylc suite server objects."""

import threading
from logging import getLogger

# Names for network-connected objects.
# WARNING: these names are don't have consistent formatting, but changing them
# will break backward compatibility with older cylc clients!
PYRO_SUITEID_OBJ_NAME = 'cylcid'
PYRO_EXT_TRIG_OBJ_NAME = 'ext-trigger-interface'
PYRO_BCAST_OBJ_NAME = 'broadcast_receiver'
PYRO_CMD_OBJ_NAME = 'command-interface'
PYRO_INFO_OBJ_NAME = 'suite-info'
PYRO_LOG_OBJ_NAME = 'log'
PYRO_STATE_OBJ_NAME = 'state_summary'

# Ordered privilege levels for authenticated users.
PRIVILEGE_LEVELS = [
    "identity",
    "description",
    "state-totals",
    "full-read",
    "shutdown",  # (Not used yet - for the post-passhprase era.)
    "full-control"
]

CONNECT_DENIED_PRIV_TMPL = (
    "[client-connect] DENIED (privilege '%s' < '%s') %s@%s:%s %s")

# Dummy passphrase for client access from users without the suite passphrase.
NO_PASSPHRASE = 'the quick brown fox'


def access_priv_ok(server_obj, required_privilege_level):
    """Return True if a client is allowed access to info from server_obj.

    The required privilege level is compared to the level granted to the
    client by the connection validator (held in thread local storage).

    """
    if threading.current_thread().__class__.__name__ == '_MainThread':
        # Server methods may be called internally as well as by clients.
        return True
    caller = server_obj.getLocalStorage().caller
    client_privilege_level = caller.privilege_level
    return (PRIVILEGE_LEVELS.index(client_privilege_level) >=
            PRIVILEGE_LEVELS.index(required_privilege_level))


def check_access_priv(server_obj, required_privilege_level):
    """Raise an exception if client privilege is insufficient for server_obj.

    (See the documentation above for the boolean version of this function).

    """
    if threading.current_thread().__class__.__name__ == '_MainThread':
        # Server methods may be called internally as well as by clients.
        return
    caller = server_obj.getLocalStorage().caller
    client_privilege_level = caller.privilege_level
    if not (PRIVILEGE_LEVELS.index(client_privilege_level) >=
            PRIVILEGE_LEVELS.index(required_privilege_level)):
        err = CONNECT_DENIED_PRIV_TMPL % (
            client_privilege_level, required_privilege_level,
            caller.user, caller.host, caller.prog_name, caller.uuid)
        getLogger("main").warn(err)
        # Raise an exception to be sent back to the client.
        raise Exception(err)
