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
"""Wrap HTTPS daemon for a suite."""

import binascii
import os
import random
import traceback

import cherrypy
from cylc.cfgspec.globalcfg import GLOBAL_CFG
from cylc.exceptions import CylcError
import cylc.flags
from cylc.network import NO_PASSPHRASE
from cylc.network.server import SuiteRuntimeService
from cylc.network.server_util import get_client_info
from cylc.suite_host import get_suite_host
from cylc.suite_logging import ERR, LOG
from cylc.suite_srv_files_mgr import (
    SuiteSrvFilesManager, SuiteServiceFileError)


class HTTPServer(object):
    """HTTP(S) server for suite runtime services."""

    LOG_CONNECT_DENIED_TMPL = "[client-connect] DENIED %s@%s:%s %s"

    def __init__(self, suite):
        # Suite only needed for back-compat with old clients (see below):
        self.suite = suite

        # Figure out the ports we are allowed to use.
        base_port = GLOBAL_CFG.get(['communication', 'base port'])
        max_ports = GLOBAL_CFG.get(
            ['communication', 'maximum number of ports'])
        self.ok_ports = range(int(base_port), int(base_port) + int(max_ports))
        random.shuffle(self.ok_ports)

        comms_options = GLOBAL_CFG.get(['communication', 'options'])

        # HTTP Digest Auth uses MD5 - pretty secure in this use case.
        # Extending it with extra algorithms is allowed, but won't be
        # supported by most browsers. requests and urllib2 are OK though.
        self.hash_algorithm = "MD5"
        if "SHA1" in comms_options:
            # Note 'SHA' rather than 'SHA1'.
            self.hash_algorithm = "SHA"

        self.srv_files_mgr = SuiteSrvFilesManager()
        self.comms_method = GLOBAL_CFG.get(['communication', 'method'])
        self.get_ha1 = cherrypy.lib.auth_digest.get_ha1_dict_plain(
            {
                'cylc': self.srv_files_mgr.get_auth_item(
                    self.srv_files_mgr.FILE_BASE_PASSPHRASE,
                    suite, content=True),
                'anon': NO_PASSPHRASE
            },
            algorithm=self.hash_algorithm)
        if self.comms_method == 'http':
            self.cert = None
            self.pkey = None
        else:  # if self.comms_method in [None, 'https']:
            try:
                self.cert = self.srv_files_mgr.get_auth_item(
                    self.srv_files_mgr.FILE_BASE_SSL_CERT, suite)
                self.pkey = self.srv_files_mgr.get_auth_item(
                    self.srv_files_mgr.FILE_BASE_SSL_PEM, suite)
            except SuiteServiceFileError:
                ERR.error("no HTTPS/OpenSSL support. Aborting...")
                raise CylcError("No HTTPS support. "
                                "Configure user's global.rc to use HTTP.")
        self.start()

    def shutdown(self):
        """Shutdown the daemon."""
        if hasattr(self, "engine"):
            self.engine.exit()
            self.engine.block()

    @staticmethod
    def connect(schd):
        """Connect suite schedular object to the daemon."""
        cherrypy.tree.mount(SuiteRuntimeService(schd), '/')
        # For back-compat with "scan"
        cherrypy.tree.mount(SuiteRuntimeService(schd), '/id')

    @staticmethod
    def disconnect(schd):
        """Disconnect obj from the daemon."""
        del cherrypy.tree.apps['/%s/%s' % (schd.owner, schd.suite)]

    def get_port(self):
        """Return the daemon port."""
        return self.port

    def start(self):
        """Start quick web service."""
        # cherrypy.config["tools.encode.on"] = True
        # cherrypy.config["tools.encode.encoding"] = "utf-8"
        cherrypy.config["server.socket_host"] = get_suite_host()
        cherrypy.config["engine.autoreload.on"] = False

        if self.comms_method == "https":
            # Setup SSL etc. Otherwise fail and exit.
            # Require connection method to be the same e.g HTTP/HTTPS matching.
            cherrypy.config['server.ssl_module'] = 'pyopenSSL'
            cherrypy.config['server.ssl_certificate'] = self.cert
            cherrypy.config['server.ssl_private_key'] = self.pkey

        cherrypy.config['log.screen'] = None
        key = binascii.hexlify(os.urandom(16))
        cherrypy.config.update({
            'tools.auth_digest.on': True,
            'tools.auth_digest.realm': self.suite,
            'tools.auth_digest.get_ha1': self.get_ha1,
            'tools.auth_digest.key': key,
            'tools.auth_digest.algorithm': self.hash_algorithm
        })
        cherrypy.tools.connect_log = cherrypy.Tool(
            'on_end_resource', self._report_connection_if_denied)
        cherrypy.config['tools.connect_log.on'] = True
        self.engine = cherrypy.engine
        for port in self.ok_ports:
            cherrypy.config["server.socket_port"] = port
            try:
                cherrypy.engine.start()
                cherrypy.engine.wait(cherrypy.engine.states.STARTED)
            except cherrypy.process.wspbus.ChannelFailures:
                if cylc.flags.debug:
                    traceback.print_exc()
                # We need to reinitialise the httpserver for each port attempt.
                cherrypy.server.httpserver = None
            else:
                if cherrypy.engine.state == cherrypy.engine.states.STARTED:
                    self.port = port
                    return
        raise Exception("No available ports")

    @staticmethod
    def _get_client_connection_denied():
        """Return whether a connection was denied."""
        if "Authorization" not in cherrypy.request.headers:
            # Probably just the initial HTTPS handshake.
            return False
        status = cherrypy.response.status
        if isinstance(status, basestring):
            return cherrypy.response.status.split()[0] in ["401", "403"]
        return cherrypy.response.status in [401, 403]

    def _report_connection_if_denied(self):
        """Log an (un?)successful connection attempt."""
        prog_name, user, host, uuid = get_client_info()[1:]
        connection_denied = self._get_client_connection_denied()
        if connection_denied:
            LOG.warning(self.__class__.LOG_CONNECT_DENIED_TMPL % (
                user, host, prog_name, uuid))
