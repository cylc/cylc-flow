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
import shlex
from subprocess import Popen, PIPE
import sys
import traceback
from uuid import uuid4

try:
    import Pyro.core
    import Pyro.errors
except ImportError, x:
    raise SystemExit("ERROR: Pyro is not installed")

from cylc.cfgspec.globalcfg import GLOBAL_CFG
from cylc.exceptions import PortFileError
import cylc.flags
from cylc.network.client_reporter import PyroClientReporter
from cylc.network.connection_validator import ConnValidator
from cylc.owner import is_remote_user, user, host, user_at_host
from cylc.passphrase import get_passphrase, PassphraseError
from cylc.registration import localdb
from cylc.suite_host import is_remote_host
from cylc.network.connection_validator import ConnValidator, OK_HASHES
from cylc.suite_env import CylcSuiteEnv, CylcSuiteEnvLoadError


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
        self.port = port
        self.pyro_proxy = None
        self.my_uuid = my_uuid or uuid4()
        if print_uuid:
            print >> sys.stderr, '%s' % self.my_uuid
        try:
            self.pphrase = get_passphrase(suite, owner, host, localdb(db))
        except PassphraseError:
            # No passphrase: public access client.
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
            try:
                return func(*fargs)
            except Pyro.errors.ConnectionClosedError:
                # Back compat for daemons <= 6.7.1.
                # Try alternate hashes.
                for alt_hash_name in OK_HASHES[1:]:
                    self.pyro_proxy = None
                    self._get_proxy(hash_name=alt_hash_name)
                    func = getattr(self.pyro_proxy, fname)
                    try:
                        return func(*fargs)
                    except Pyro.errors.ConnectionClosedError:
                        continue
                raise

    def _set_uri(self):
        """Set Pyro URI.

        Determine host and port using content in port file, unless already
        specified.

        """
        uri_data = {
            "host": self.host,
            "port": self.port,
            "suite": self.suite,
            "owner": self.owner,
            "target": self.target_server_object}

        if ((self.host is None or self.port is None) and
                'CYLC_SUITE_RUN_DIR' in os.environ):
            # Looks like we are in a running task job, so we should be able to
            # use "cylc-suite-env" file under the suite running directory
            try:
                suite_env = CylcSuiteEnv.load(
                    self.suite, os.environ['CYLC_SUITE_RUN_DIR'])
            except CylcSuiteEnvLoadError:
                if cylc.flags.debug:
                    traceback.print_exc()
            else:
                self.host = suite_env.suite_host
                self.port = suite_env.suite_port
                self.owner = suite_env.suite_owner
                uri_data['host'] = suite_env.suite_host
                uri_data['port'] = suite_env.suite_port
                uri_data['owner'] = suite_env.suite_owner

        if self.host is None or self.port is None:
            port_file_path = os.path.join(
                GLOBAL_CFG.get(['pyro', 'ports directory']), self.suite)
            if is_remote_host(self.host) or is_remote_user(self.owner):
                ssh_tmpl = str(GLOBAL_CFG.get_host_item(
                    'remote shell template', self.host, self.owner))
                ssh_tmpl = ssh_tmpl.replace(' %s', '')
                user_at_host = ''
                if self.owner:
                    user_at_host = self.owner + '@'
                if self.host:
                    user_at_host += self.host
                else:
                    user_at_host += 'localhost'
                r_port_file_path = port_file_path.replace(
                    os.environ['HOME'], '$HOME')
                command = shlex.split(ssh_tmpl) + [
                    user_at_host, 'cat', r_port_file_path]
                proc = Popen(command, stdout=PIPE, stderr=PIPE)
                out, err = proc.communicate()
                if proc.wait():
                    raise PortFileError(
                        "Port file '%s:%s' not found - suite not running?." %
                        (user_at_host, r_port_file_path))
            else:
                try:
                    out = open(port_file_path).read()
                except IOError as exc:
                    raise PortFileError(
                        "Port file '%s' not found - suite not running?." %
                        (port_file_path))
            lines = out.splitlines()
            try:
                if uri_data["port"] is None:
                    uri_data["port"] = int(lines[0])
                    self.port = uri_data["port"]
            except (IndexError, ValueError):
                raise PortFileError(
                    "ERROR, bad content in port file: %s" % port_file_path)
            if uri_data["host"] is None:
                if len(lines) >= 2:
                    uri_data["host"] = lines[1].strip()
                else:
                    uri_data["host"] = "localhost"
                self.host = uri_data["host"]

        # Qualify the obj name with user and suite name (unnecessary but
        # can't change it until we break back-compat with older daemons).
        self.uri = (
            'PYROLOC://%(host)s:%(port)s/%(owner)s.%(suite)s.%(target)s' %
            uri_data)

    def _get_proxy_common(self):
        if self.pyro_proxy is None:
            self._set_uri()
            # Fails only for unknown hosts (no connection till RPC call).
            self.pyro_proxy = Pyro.core.getProxyForURI(self.uri)
            self.pyro_proxy._setTimeout(self.pyro_timeout)

    def _get_proxy(self, hash_name=None):
        self._get_proxy_common()
        conn_val = ConnValidator()
        if hash_name is not None and hash_name in OK_HASHES:
            conn_val.set_default_hash(hash_name)
        self.pyro_proxy._setNewConnectionValidator(conn_val)
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
