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
"""Wrap HTTPS daemon for a suite."""

import binascii
import os
import socket
import sys
import traceback

from cylc.cfgspec.globalcfg import GLOBAL_CFG
from cylc.network import NO_PASSPHRASE
from cylc.network.https.client_reporter import CommsClientReporter
from cylc.owner import USER
from cylc.registration import RegistrationDB, PassphraseError
from cylc.suite_host import get_hostname

import cherrypy


class CommsDaemon(object):
    """Wrap HTTPS daemon for a suite."""

    def __init__(self, suite, suite_dir):
        # Suite only needed for back-compat with old clients (see below):
        self.suite = suite

        # Figure out the ports we are allowed to use.
        base_port = GLOBAL_CFG.get(
            ['communication', 'base port'])
        max_ports = GLOBAL_CFG.get(
            ['communication', 'maximum number of ports'])
        self.ok_ports = range(
            int(base_port),
            int(base_port) + int(max_ports)
        )

        comms_options = GLOBAL_CFG.get(['communication', 'options'])
        # HTTP Digest Auth uses MD5 - pretty secure in this use case.
        # Extending it with extra algorithms is allowed, but won't be
        # supported by most browsers. requests and urllib2 are OK though.
        self.hash_algorithm = "MD5"
        if "SHA1" in comms_options:
            # Note 'SHA' rather than 'SHA1'.
            self.hash_algorithm = "SHA"

        self.reg_db = RegistrationDB()
        try:
            self.cert = self.reg_db.load_item(
                suite, USER, None, "certificate", create_ok=True)
            self.pkey = self.reg_db.load_item(
                suite, USER, None, "private_key", create_ok=True)
        except PassphraseError:
            # No OpenSSL installed.
            self.cert = None
            self.pkey = None
        self.suite = suite
        passphrase = self.reg_db.load_passphrase(suite, USER, None)
        userpassdict = {'cylc': passphrase, 'anon': NO_PASSPHRASE}
        get_ha1 = cherrypy.lib.auth_digest.get_ha1_dict_plain(
            userpassdict, algorithm=self.hash_algorithm)
        self.get_ha1 = get_ha1
        del passphrase
        del userpassdict
        self.client_reporter = CommsClientReporter.get_inst()
        self.start()

    def start(self):
        _ws_init(self)

    def shutdown(self):
        """Shutdown the daemon."""
        if hasattr(self, "engine"):
            self.engine.exit()
            self.engine.block()

    def connect(self, obj, name):
        """Connect obj and name to the daemon."""
        import cherrypy
        cherrypy.tree.mount(obj, "/" + name)

    def disconnect(self, obj):
        """Disconnect obj from the daemon."""
        pass

    def get_port(self):
        """Return the daemon port."""
        return self.port

    def report_connection_if_denied(self):
        self.client_reporter.report_connection_if_denied()


def can_ssl():
    """Return whether we can run HTTPS under cherrypy on this machine."""
    try:
        from OpenSSL import SSL
        from OpenSSL import crypto
    except ImportError:
        return False
    return True


def _ws_init(service_inst, *args, **kwargs):
    """Start quick web service."""
    # cherrypy.config["tools.encode.on"] = True
    # cherrypy.config["tools.encode.encoding"] = "utf-8"
    cherrypy.config["server.socket_host"] = '0.0.0.0'
    cherrypy.config["engine.autoreload.on"] = False
    if can_ssl():
        cherrypy.config['server.ssl_module'] = 'pyopenSSL'
        cherrypy.config['server.ssl_certificate'] = service_inst.cert
        cherrypy.config['server.ssl_private_key'] = service_inst.pkey
    else:
        sys.stderr.write("WARNING: no HTTPS support: cannot import OpenSSL\n")
    cherrypy.config['log.screen'] = None
    key = binascii.hexlify(os.urandom(16))
    cherrypy.config.update({
        'tools.auth_digest.on': True,
        'tools.auth_digest.realm': service_inst.suite,
        'tools.auth_digest.get_ha1': service_inst.get_ha1,
        'tools.auth_digest.key': key,
        'tools.auth_digest.algorithm': service_inst.hash_algorithm
    })
    cherrypy.tools.connect_log = cherrypy.Tool(
        'on_end_resource', service_inst.report_connection_if_denied)
    cherrypy.config['tools.connect_log.on'] = True
    host = get_hostname()
    service_inst.engine = cherrypy.engine
    for port in service_inst.ok_ports:
        my_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            my_socket.bind((host, port))
        except socket.error:
            # Host busy.
            my_socket.close()
            continue
        my_socket.close()
        cherrypy.config["server.socket_port"] = port
        try:
            cherrypy.engine.start()
            cherrypy.engine.wait(cherrypy.engine.states.STARTED)
            if cherrypy.engine.state != cherrypy.engine.states.STARTED:
                continue
        except (socket.error, IOError):
            pass
        except:
            import traceback
            traceback.print_exc()
        else:
            service_inst.port = port
            return
        # We need to reinitialise the httpserver for each port attempt.
        cherrypy.server.httpserver = None
    raise Exception("No available ports")
