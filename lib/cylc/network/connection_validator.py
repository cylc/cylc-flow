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

import Pyro.core
import hashlib
import os
import sys

from Pyro.protocol import DefaultConnValidator
import Pyro.constants
import Pyro.errors
import hmac

from cylc.cfgspec.globalcfg import GLOBAL_CFG
from cylc.network import NO_PASSPHRASE, PRIVILEGE_LEVELS
from cylc.config import SuiteConfig
from cylc.suite_host import get_hostname, is_remote_host
from cylc.suite_logging import LOG
from cylc.owner import USER


# Access for users without the suite passphrase: encrypting the "no passphrase"
# passphrase is unnecessary, but doing so allows common passphrase handling.

OK_HASHES = GLOBAL_CFG.get()['authentication']['hashes']
SCAN_HASH = GLOBAL_CFG.get()['authentication']['scan hash']
if SCAN_HASH not in OK_HASHES:
    OK_HASHES.append(SCAN_HASH)


CONNECT_DENIED_TMPL = "[client-connect] DENIED %s@%s:%s %s"
CONNECT_ALLOWED_TMPL = "[client-connect] %s@%s:%s privilege='%s' %s"


class ConnValidator(DefaultConnValidator):
    """Custom Pyro connection validator for user authentication."""

    HASHES = {}
    LENGTH_HASH_DIGESTS = {}
    NO_PASSPHRASE_HASHES = {}

    def set_pphrase(self, pphrase):
        """Store encrypted suite passphrase (called by the server)."""
        self.pphrase_hashes = {}
        for hash_name in OK_HASHES:
            hash_ = self._get_hash(hash_name)
            self.pphrase_hashes[hash_name] = hash_(pphrase).hexdigest()

    def set_default_hash(self, hash_name):
        """Configure a hash to use as the default."""
        self._default_hash_name = hash_name
        if None in self.HASHES:
            self.HASHES.pop(None)  # Pop default setting.

    def acceptIdentification(self, daemon, connection, token, challenge):
        """Authorize client login."""

        is_old_client = False
        # Processes the token returned by createAuthToken.
        try:
            user, host, uuid, prog_name, proc_passwd = token.split(':', 4)
        except ValueError:
            # Back compat for old suite client (passphrase only)
            # (Allows old scan to see new suites.)
            proc_passwd = token
            is_old_client = True
            user = "(user)"
            host = "(host)"
            uuid = "(uuid)"
            prog_name = "(OLD_CLIENT)"

        hash_name = self._get_hash_name_from_digest_length(proc_passwd)

        if hash_name not in OK_HASHES:
            return (0, Pyro.constants.DENIED_SECURITY)

        hash_ = self._get_hash(hash_name)

        # Access for users without the suite passphrase: encrypting the
        # no-passphrase is unnecessary, but doing so allows common handling.
        no_passphrase_hash = self._get_no_passphrase_hash(hash_name)

        # Check username and password, and set privilege level accordingly.
        # The auth token has a binary hash that needs conversion to ASCII.
        if self._compare_hmacs(
                hmac.new(challenge,
                         self.pphrase_hashes[hash_name].decode("hex"),
                         hash_).digest(),
                proc_passwd):
            # The client has the suite passphrase.
            # Access granted at highest privilege level.
            priv_level = PRIVILEGE_LEVELS[-1]
        elif not is_old_client and self._compare_hmacs(
                hmac.new(challenge,
                         no_passphrase_hash.decode("hex"),
                         hash_).digest(),
                proc_passwd):
            # The client does not have the suite passphrase.
            # Public access granted at level determined by global/suite config.
            config = SuiteConfig.get_inst()
            priv_level = config.cfg['cylc']['authentication']['public']
        else:
            # Access denied.
            if not is_old_client:
                # Avoid logging large numbers of denials from old scan clients
                # that try all passphrases available to them.
                LOG.warn(CONNECT_DENIED_TMPL % (user, host, prog_name, uuid))
            return (0, Pyro.constants.DENIED_SECURITY)

        # Store client details for use in the connection thread.
        connection.user = user
        connection.host = host
        connection.prog_name = prog_name
        connection.uuid = uuid
        connection.privilege_level = priv_level
        LOG.debug(CONNECT_ALLOWED_TMPL % (
                  user, host, prog_name, priv_level, uuid))
        return (1, 0)

    def createAuthToken(self, authid, challenge, peeraddr, URI, daemon):
        """Return a secure auth token based on the server challenge string.

        Argument authid is what's returned by mungeIdent().

        """
        hash_ = self._get_hash()
        return ":".join(
            list(authid[:4]) +
            [hmac.new(challenge, authid[4], hash_).digest()]
        )

    def mungeIdent(self, ident):
        """Receive (uuid, passphrase) from client. Encrypt the passphrase.

        Also pass client identification info to server for logging:
        (user, host, prog name).

        """
        hash_ = self._get_hash()
        uuid, passphrase = ident
        prog_name = os.path.basename(sys.argv[0])
        if passphrase is None:
            passphrase = NO_PASSPHRASE
        return (USER, get_hostname(), str(uuid), prog_name,
                hash_(passphrase).digest())

    def _compare_hmacs(self, hmac1, hmac2):
        """Compare hmacs as securely as possible."""
        try:
            return hmac.compare_hmacs(hmac1, hmac2)
        except AttributeError:
            # < Python 2.7.7.
            return (hmac1 == hmac2)

    def _get_default_hash_name(self):
        if hasattr(self, "_default_hash_name"):
            return self._default_hash_name
        return GLOBAL_CFG.get()['authentication']['hashes'][0]

    def _get_hash(self, hash_name=None):
        try:
            return self.HASHES[hash_name]
        except KeyError:
            pass

        hash_name_dest = hash_name
        if hash_name is None:
            hash_name = self._get_default_hash_name()

        self.HASHES[hash_name_dest] = getattr(hashlib, hash_name)
        return self.HASHES[hash_name_dest]

    def _get_hash_name_from_digest_length(self, digest):
        if len(digest) in self.LENGTH_HASH_DIGESTS:
            return self.LENGTH_HASH_DIGESTS[len(digest)]
        for hash_name in OK_HASHES:
            hash_ = self._get_hash(hash_name)
            len_hash = len(hash_("foo").digest())
            self.LENGTH_HASH_DIGESTS[len_hash] = hash_name
            if len_hash == len(digest):
                return hash_name

    def _get_no_passphrase_hash(self, hash_name=None):
        try:
            return self.NO_PASSPHRASE_HASHES[hash_name]
        except KeyError:
            hash_ = self._get_hash(hash_name)
            self.NO_PASSPHRASE_HASHES[hash_name] = (
                hash_(NO_PASSPHRASE).hexdigest())
        return self.NO_PASSPHRASE_HASHES[hash_name]
