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
"""Base classes for Pyro servers and clients."""

import os
import shlex
from subprocess import Popen, PIPE
import sys
import traceback
from uuid import uuid4

import Pyro.core
import Pyro.errors

from cylc.cfgspec.globalcfg import GLOBAL_CFG
from cylc.exceptions import PortFileError
import cylc.flags
from cylc.network.client_reporter import PyroClientReporter
from cylc.network.connection_validator import ConnValidator, OK_HASHES
from cylc.owner import is_remote_user, USER
from cylc.registration import RegistrationDB
from cylc.suite_host import get_hostname, is_remote_host
from cylc.suite_env import CylcSuiteEnv, CylcSuiteEnvLoadError


class PyroServer(Pyro.core.ObjBase):
    """Base class for server-side suite object interfaces."""

    def __init__(self):
        Pyro.core.ObjBase.__init__(self)
        self.client_reporter = PyroClientReporter.get_inst()

    def signout(self):
        """Wrap client_reporter.signout."""
        self.client_reporter.signout(self)

    def report(self, command):
        """Wrap client_reporter.report."""
        self.client_reporter.report(command, self)


class PyroClient(object):
    """Base class for client-side suite object interfaces."""

    target_server_object = None

    def __init__(self, suite, owner=USER, host=None, pyro_timeout=None,
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
        self.uri = None
        if print_uuid:
            print >> sys.stderr, '%s' % self.my_uuid
        self.reg_db = RegistrationDB(db)
        self.pphrase = None

    def call_server_func(self, fname, *fargs):
        """Call server_object.fname(*fargs)

        Get a Pyro proxy for the server object if we don't already have it,
        and handle back compat retry for older daemons.

        """
        items = [
            {},
            {"reset": True, "cache_ok": False},
            {"reset": True, "cache_ok": False, "old": True},
        ]
        for hash_name in OK_HASHES[1:]:
            items.append(
                {"reset": True, "cache_ok": False, "hash_name": hash_name})
        for i, proxy_kwargs in enumerate(items):
            func = getattr(self._get_proxy(**proxy_kwargs), fname)
            try:
                ret = func(*fargs)
                break
            except Pyro.errors.ProtocolError:
                if i + 1 == len(items):  # final attempt
                    raise
        self.reg_db.cache_passphrase(
            self.suite, self.owner, self.host, self.pphrase)
        return ret

    def _set_uri(self):
        """Set Pyro URI.

        Determine host and port using content in port file, unless already
        specified.

        """
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
                ret_code = proc.wait()
                if ret_code:
                    if cylc.flags.debug:
                        print >> sys.stderr, {
                            "code": ret_code,
                            "command": command,
                            "stdout": out,
                            "stderr": err}
                    raise PortFileError(
                        "Port file '%s:%s' not found - suite not running?." %
                        (user_at_host, r_port_file_path))
            else:
                try:
                    out = open(port_file_path).read()
                except IOError:
                    raise PortFileError(
                        "Port file '%s' not found - suite not running?." %
                        (port_file_path))
            lines = out.splitlines()
            try:
                if self.port is None:
                    self.port = int(lines[0])
            except (IndexError, ValueError):
                raise PortFileError(
                    "ERROR, bad content in port file: %s" % port_file_path)
            if self.host is None:
                if len(lines) >= 2:
                    self.host = lines[1].strip()
                else:
                    self.host = get_hostname()

        # Qualify the obj name with user and suite name (unnecessary but
        # can't change it until we break back-compat with older daemons).
        self.uri = (
            'PYROLOC://%(host)s:%(port)s/%(owner)s.%(suite)s.%(target)s' % {
                "host": self.host,
                "port": self.port,
                "suite": self.suite,
                "owner": self.owner,
                "target": self.target_server_object})

    def _get_proxy(self, reset=True, hash_name=None, cache_ok=True, old=False):
        """Get a Pyro proxy."""
        if reset or self.pyro_proxy is None:
            self._set_uri()
            self.pphrase = self.reg_db.load_passphrase(
                self.suite, self.owner, self.host, cache_ok)
            # Fails only for unknown hosts (no connection till RPC call).
            self.pyro_proxy = Pyro.core.getProxyForURI(self.uri)
            self.pyro_proxy._setTimeout(self.pyro_timeout)
            if old:
                self.pyro_proxy._setIdentification(self.pphrase)
            else:
                conn_val = ConnValidator()
                if hash_name is None:
                    hash_name = getattr(self, "_hash_name", None)
                if hash_name is not None and hash_name in OK_HASHES:
                    conn_val.set_default_hash(hash_name)
                self.pyro_proxy._setNewConnectionValidator(conn_val)
                self.pyro_proxy._setIdentification(
                    (self.my_uuid, self.pphrase))
        return self.pyro_proxy

    def reset(self):
        """Reset pyro_proxy."""
        self.pyro_proxy = None

    def signout(self):
        """Multi-connect clients should call this on exit."""
        try:
            self._get_proxy().signout()
        except Exception:
            # Suite may have stopped before the client exits.
            pass
