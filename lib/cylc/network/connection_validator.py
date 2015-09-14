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
import logging
import os
import sys

from Pyro.protocol import DefaultConnValidator
import Pyro.constants
import Pyro.errors
import hmac
try:
    import hashlib
    md5 = hashlib.md5
except ImportError:
    import md5
    md5 = md5.md5

from cylc.network import NO_PASSPHRASE, PRIVILEGE_LEVELS
from cylc.config import SuiteConfig
from cylc.suite_host import is_remote_host
from cylc.owner import user, host


# Access for users without the suite passphrase: encrypting the "no passphrase"
# passphrase is unnecessary, but doing so allows common passphrase handling.
NO_PASSPHRASE_MD5 = md5(NO_PASSPHRASE).hexdigest()

CONNECT_DENIED_TMPL = "[client-connect] DENIED %s@%s:%s %s"
CONNECT_ALLOWED_TMPL = "[client-connect] %s@%s:%s privilege='%s' %s"


class ConnValidator(DefaultConnValidator):
    """Custom Pyro connection validator for user authentication."""

    def set_pphrase(self, pphrase):
        """Store encrypted suite passphrase (called by the server)."""
        self.pphrase = md5(pphrase).hexdigest()

    def acceptIdentification(self, daemon, connection, token, challenge):
        """Authorize client login."""

        logger = logging.getLogger('main')
        is_old_daemon = False
        # Processes the token returned by createAuthToken.
        try:
            user, host, uuid, prog_name, proc_passwd = token.split(':', 4)
        except ValueError as exc:
            # Back compat for old suite client (passphrase only)
            # (Allows old scan to see new suites.)
            proc_passwd = token
            is_old_daemon = True

        # Check username and password, and set privilege level accordingly.
        # The auth token has a binary hash that needs conversion to ASCII.
        if hmac.new(challenge,
                    self.pphrase.decode("hex")).digest() == proc_passwd:
            # The client has the suite passphrase.
            # Access granted at highest privilege level.
            priv_level = PRIVILEGE_LEVELS[-1]
        elif is_old_daemon:
            # These won't support NO_PASSPHRASE and aren't worth logging.
            return (0, Pyro.constants.DENIED_SECURITY)
        elif (hmac.new(
                 challenge,
                 NO_PASSPHRASE_MD5.decode("hex")).digest() == proc_passwd):
            # The client does not have the suite passphrase.
            # Public access granted at level determined by global/suite config.
            config = SuiteConfig.get_inst()
            priv_level = config.cfg['cylc']['authentication']['public']
        else:
            # Access denied.
            logger.warn(CONNECT_DENIED_TMPL % (
                        user, host, prog_name, uuid))
            return (0, Pyro.constants.DENIED_SECURITY)

        # Store client details for use in the connection thread.
        connection.user = user
        connection.host = host
        connection.prog_name = prog_name
        connection.uuid = uuid
        connection.privilege_level = priv_level
        logger.debug(CONNECT_ALLOWED_TMPL % (
                     user, host, prog_name, priv_level, uuid))
        return (1, 0)

    def createAuthToken(self, authid, challenge, peeraddr, URI, daemon):
        """Return a secure auth token based on the server challenge string.

        Argument authid is what's returned by mungeIdent().

        """
        return ":".join(
            list(authid[:4]) + [hmac.new(challenge, authid[4]).digest()])

    def mungeIdent(self, ident):
        """Receive (uuid, passphrase) from client. Encrypt the passphrase.

        Also pass client identification info to server for logging:
        (user, host, prog name).

        """
        uuid, passphrase = ident
        prog_name = os.path.basename(sys.argv[0])
        if passphrase is None:
            passphrase = NO_PASSPHRASE
        return (user, host, str(uuid), prog_name, md5(passphrase).digest())
