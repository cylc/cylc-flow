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

"""Package for network interfaces to cylc suite server objects."""

import threading
from logging import getLogger

# Names for network-connected objects.
# WARNING: these names are don't have consistent formatting, but changing them
# will break backward compatibility with older cylc clients!
COMMS_SUITEID_OBJ_NAME = 'id'
COMMS_EXT_TRIG_OBJ_NAME = 'ext-trigger'
COMMS_BCAST_OBJ_NAME = 'broadcast'
COMMS_CMD_OBJ_NAME = 'command'
COMMS_INFO_OBJ_NAME = 'info'
COMMS_LOG_OBJ_NAME = 'log'
COMMS_STATE_OBJ_NAME = 'state'
COMMS_TASK_MESSAGE_OBJ_NAME = 'message'

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


class ConnectionDeniedError(Exception):

    """An error raised when the client is not permitted to connect."""

    MESSAGE = "Not authorized: %s: %s: access type '%s'"

    def __str__(self):
        return self.MESSAGE % (self.args[0], self.args[1], self.args[2])


def access_priv_ok(server_obj, required_privilege_level):
    """Return True if a client is allowed access to info from server_obj.

    The required privilege level is compared to the level granted to the
    client by the connection validator (held in thread local storage).

    """
    if threading.current_thread().__class__.__name__ == '_MainThread':
        # Server methods may be called internally as well as by clients.
        return True
    import cherrypy
    user = cherrypy.request.login
    priv_level = get_priv_level(user)
    return (PRIVILEGE_LEVELS.index(priv_level) >=
            PRIVILEGE_LEVELS.index(required_privilege_level))


def check_access_priv(server_obj, required_privilege_level):
    """Raise an exception if client privilege is insufficient for server_obj.

    (See the documentation above for the boolean version of this function).

    """
    if threading.current_thread().__class__.__name__ == '_MainThread':
        # Server methods may be called internally as well as by clients.
        return
    auth_user, prog_name, user, host, uuid, priv_level = get_client_info()
    if not (PRIVILEGE_LEVELS.index(priv_level) >=
            PRIVILEGE_LEVELS.index(required_privilege_level)):
        err = CONNECT_DENIED_PRIV_TMPL % (
            priv_level, required_privilege_level,
            user, host, prog_name, uuid
        )
        getLogger("log").warn(err)
        # Raise an exception to be sent back to the client.
        raise Exception(err)


def get_client_info():
    """Return information about the most recent cherrypy request, if any."""
    import cherrypy
    import uuid
    auth_user = cherrypy.request.login
    info = cherrypy.request.headers
    origin_string = info.get("User-Agent", "")
    origin_props = {}
    if origin_string:
        try:
            origin_props = dict(
                [_.split("/", 1) for _ in origin_string.split()]
            )
        except ValueError:
            pass
    prog_name = origin_props.get("prog_name", "Unknown")
    uuid = origin_props.get("uuid", uuid.uuid4())
    if info.get("From") and "@" in info["From"]:
        user, host = info["From"].split("@")
    else:
        user, host = ("Unknown", "Unknown")
    priv_level = get_priv_level(auth_user)
    return auth_user, prog_name, user, host, uuid, priv_level


def get_client_connection_denied():
    """Return whether a connection was denied."""
    import cherrypy
    if "Authorization" not in cherrypy.request.headers:
        # Probably just the initial HTTPS handshake.
        return False
    status = cherrypy.response.status
    if isinstance(status, basestring):
        return cherrypy.response.status.split()[0] in ["401", "403"]
    return cherrypy.response.status in [401, 403]


def get_priv_level(user):
    """Get the privilege level for this authenticated user."""
    if user == "cylc":
        return PRIVILEGE_LEVELS[-1]
    from cylc.config import SuiteConfig
    config = SuiteConfig.get_inst()
    return config.cfg['cylc']['authentication']['public']


def handle_proxies():
    """Unset proxies if the configuration matches this."""
    from cylc.cfgspec.globalcfg import GLOBAL_CFG
    if not GLOBAL_CFG.get(['communication', 'proxies on']):
        import os
        os.environ.pop("http_proxy", None)
        os.environ.pop("https_proxy", None)
