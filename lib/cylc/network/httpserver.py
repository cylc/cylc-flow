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
"""HTTP(S) server, and suite runtime API service facade exposed.

Implementation currently via Tornado.
"""

from time import time

import handlers
import tornado.escape
import tornado.httpserver
import tornado.web

from graphene_tornado.tornado_graphql_handler import TornadoGraphQLHandler
from .schema import schema

from cylc import LOG
from cylc.network import NO_PASSPHRASE
from cylc.cfgspec.glbl_cfg import glbl_cfg
from cylc.exceptions import CylcError
from cylc.suite_srv_files_mgr import (
    SuiteSrvFilesManager, SuiteServiceFileError)


class HttpApplication(tornado.web.Application):
    """
    Tornado web application for the suite server program.
    """

    API = 2

    def __init__(self, suite, scheduler):
        """
        Create a new Tornado web application.
        :param suite: a reference to a Cylc Suite
        :param scheduler: a reference to the Cylc Scheduler
        """
        self.suite = suite
        self.scheduler = scheduler
        self.srv_files_mgr = SuiteSrvFilesManager()

        self.users = {}
        self.ssl_context = None
        self.handlers = []
        self.settings = {}
        self.clients = {}
        self.id_start_time = time()
        self.num_id_requests = 0

        self.init_auth()
        self.init_mappings()
        self.init_settings()
        self.init_ssl()

        tornado.web.Application.__init__(self, self.handlers, self.settings)

    def init_auth(self):
        self.users['cylc'] = self.srv_files_mgr.get_auth_item(
            self.srv_files_mgr.FILE_BASE_PASSPHRASE,
            self.suite, content=True)
        self.users['anon'] = NO_PASSPHRASE

    def get_user(self, username):
        """
        Exposed via tornado-auth as the argument for `check_credentials_func`
        See the BaseHandler for more in base.py
        :param username: user name
        :type username: str
        :return: password|None
        :rtype: str
        """
        return self.users.get(username)

    def init_mappings(self):
        """
        Initialize handlers
        :return:
        """
        h = []
        # Cylc's previous HTTP server would listen to requests coming through
        # / and /id. So we will just duplicate every handler to allow the /id
        for handler in handlers.default_handlers:
            h.append((r"/id{}".format(handler[0]), handler[1]))
        h.extend(handlers.default_handlers)
        h.append((r"/graphiql", TornadoGraphQLHandler, dict(graphiql=True, schema=schema)))
        # we can prepend other things to the url's here if necessary
        # e.g. /api/v2/....
        self.handlers = h

    def init_settings(self):
        """
        Initialize application settings
        :return: a dictionary with settings for Tornado
        :rtype: dict
        """
        s = dict(
            template_path=None,
            static_path=None,
            debug=False,
            cookie_secret="cylc",
            login_url=None,
            xsrf_cookies=True,
            autoescape=None,
        )
        self.settings = s

    def init_ssl(self):
        # here we are dropping SHA1 support, and using only the default
        # md5 (weaker). But in the future we may change this communication
        # way altogether
        # communication_options = glbl_cfg().get(['communication', 'options'])
        communication_method = glbl_cfg().get(['communication', 'method'])
        if communication_method is None or communication_method == 'https':
            try:
                certificate = self.srv_files_mgr.get_auth_item(
                    self.srv_files_mgr.FILE_BASE_SSL_CERT, self.suite)
                private_key = self.srv_files_mgr.get_auth_item(
                    self.srv_files_mgr.FILE_BASE_SSL_PEM, self.suite)
                self.ssl_context = {"certfile": certificate,
                                    "keyfile": private_key}
            except SuiteServiceFileError as e:
                LOG.error("no HTTPS/OpenSSL support. Aborting...")
                LOG.exception(e)
                raise CylcError("No HTTPS support. "
                                "Configure user's global.rc to use HTTP.")
