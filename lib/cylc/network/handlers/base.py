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

"""Base handlers"""

import ast
import inspect
import re
from time import time
from uuid import uuid4

from cylc import LOG
import tornado.escape
import tornado.web
from tornado_http_auth import DigestAuthMixin
from .. import PRIVILEGE_LEVELS, PRIV_IDENTITY
from ... import flags
from ...version import CYLC_VERSION
from ...wallclock import RE_DATE_TIME_FORMAT_EXTENDED
from ...cfgspec.glbl_cfg import glbl_cfg


class BaseHandler(DigestAuthMixin, tornado.web.RequestHandler):
    """
    Base Handler for all handlers in Cylc Suite Server program.
    """

    CLIENT_FORGET_SEC = 60
    CLIENT_ID_MIN_REPORT_RATE = 1.0  # 1 Hz
    CLIENT_ID_REPORT_SECONDS = 3600  # Report every 1 hour.
    CONNECT_DENIED_PRIV_TMPL = (
        "[client-connect] DENIED (privilege '%s' < '%s') %s@%s:%s %s")
    LOG_COMMAND_TMPL = '[client-command] %s %s@%s:%s %s'
    LOG_IDENTIFY_TMPL = '[client-identify] %d id requests in PT%dS'
    LOG_FORGET_TMPL = '[client-forget] %s'
    LOG_CONNECT_ALLOWED_TMPL = "[client-connect] %s@%s:%s privilege='%s' %s"
    LOG_CONNECT_DENIED_TMPL = "[client-connect] DENIED %s@%s:%s %s"
    RE_MESSAGE_TIME = re.compile(
        r'\A(.+) at (' + RE_DATE_TIME_FORMAT_EXTENDED + r')\Z', re.DOTALL)
    data = None

    def prepare(self):
        """
        Called before get/post, used to prepare the process of the request
        with things like authentication/authorization
        """
        get_user_func = self.application.get_user

        realm = "Protected"
        try:
            self.authenticate_user(realm=realm,
                                   check_credentials_func=get_user_func)
        except self.SendChallenge:
            self.send_auth_challenge(realm,
                                     self.request.remote_ip,
                                     self.get_time())

    def write_error(self, status_code, **kwargs):
        self._report_connection_if_denied()
        if "exc_info" in kwargs:
            LOG.exception(kwargs["exc_info"])
        super(BaseHandler, self).write_error(status_code, **kwargs)

    def _report_connection_if_denied(self):
        """Log an (un?)successful connection attempt."""
        if self.get_status() not in [401, 403]:
            return
        prog_name, user, host, uuid = self._get_client_info()[1:]
        LOG.warning(self.__class__.LOG_CONNECT_DENIED_TMPL % (
            user, host, prog_name, uuid))

    def set_default_headers(self):
        """
        Set default headers
        """
        self.set_header("Content-Type", 'application/json')

    def _get_client_info(self):
        """Return information about the most recent request, if any."""
        auth_user = self.current_user
        info = self.request.headers
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
        uuid = origin_props.get("uuid", uuid4())
        if info.get("From") and "@" in info["From"]:
            user, host = info["From"].split("@")
        else:
            user, host = ("Unknown", "Unknown")
        return auth_user, prog_name, user, host, uuid

    def _access_priv_ok(self, required_privilege_level):
        """Return True if a client has enough privilege for given level.

        The required privilege level is compared to the level granted to the
        client by the connection validator (held in thread local storage).

        """
        try:
            return self._check_access_priv(required_privilege_level)
        except tornado.web.HTTPError:
            return False

    def _report_id_requests(self):
        """Report the frequency of identification (scan) requests."""
        self.application.num_id_requests += 1
        now = time()
        interval = now - self.application.id_start_time
        if interval > self.CLIENT_ID_REPORT_SECONDS:
            rate = float(self.application.num_id_requests) / interval
            log = None
            if rate > self.CLIENT_ID_MIN_REPORT_RATE:
                log = LOG.warning
            elif flags.debug:
                log = LOG.info
            if log:
                log(self.__class__.LOG_IDENTIFY_TMPL % (
                    self.application.num_id_requests, interval))
            self.application.id_start_time = now
            self.application.num_id_requests = 0
        uuid = self._get_client_info()[4]
        self.application.clients.setdefault(uuid, {})
        self.application.clients[uuid]['time'] = now
        self._housekeep()

    def _get_priv_level(self, auth_user):
        """Get the privilege level for this authenticated user."""
        if auth_user == "cylc":
            return PRIVILEGE_LEVELS[-1]
        elif self.application.scheduler.\
                config.cfg['cylc']['authentication']['public']:
            return self.application.scheduler.\
                config.cfg['cylc']['authentication']['public']
        else:
            return glbl_cfg().get(['authentication', 'public'])

    def _housekeep(self):
        """Forget inactive clients."""
        for uuid, client_info in self.application.clients.copy().items():
            if time() - client_info['time'] > self.CLIENT_FORGET_SEC:
                try:
                    del self.application.clients[uuid]
                except KeyError:
                    pass
                LOG.debug(self.LOG_FORGET_TMPL % uuid)

    def _check_access_priv(self, required_privilege_level):
        """Raise an exception if client privilege is insufficient.

        (See the documentation above for the boolean version of this function).

        """
        auth_user, prog_name, user, host, uuid = self._get_client_info()
        priv_level = self._get_priv_level(auth_user)
        if (PRIVILEGE_LEVELS.index(priv_level) <
                PRIVILEGE_LEVELS.index(required_privilege_level)):
            err = self.CONNECT_DENIED_PRIV_TMPL % (
                priv_level, required_privilege_level,
                user, host, prog_name, uuid)
            LOG.warning(err)
            # Raise an exception to be sent back to the client.
            self.clear()
            self.set_status(403)
            self.finish(err)
        return True

    def _check_access_priv_and_report(
            self, required_privilege_level, log_info=True):
        """Check access privilege and log requests with identifying info.

        In debug mode log all requests including task messages. Otherwise log
        all user commands, and just the first info command from each client.

        Return:
            dict: containing the client session

        """
        self._check_access_priv(required_privilege_level)
        command = inspect.currentframe().f_back.f_code.co_name
        auth_user, prog_name, user, host, uuid = self._get_client_info()
        priv_level = self._get_priv_level(auth_user)
        LOG.debug(self.__class__.LOG_CONNECT_ALLOWED_TMPL % (
            user, host, prog_name, priv_level, uuid))
        if flags.debug or uuid not in self.application.clients and log_info:
            LOG.info(self.__class__.LOG_COMMAND_TMPL % (
                command, user, host, prog_name, uuid))
        self.application.clients.setdefault(uuid, {})
        self.application.clients[uuid]['time'] = time()
        self._housekeep()
        return self.application.clients[uuid]

    def _literal_eval(self, key, value, default=None):
        """Wrap ast.literal_eval if value is basestring.

        On SyntaxError or ValueError, return default is default is not None.
        Otherwise, raise HTTPError 400.
        """
        if isinstance(value, basestring):
            try:
                return ast.literal_eval(value)
            except (SyntaxError, ValueError):
                if default is not None:
                    return default
                raise tornado.web.HTTPError(
                    400, r'Bad argument value: %s=%s' % (key, value))
        else:
            return value


class ApiVersionHandler(BaseHandler):

    def get(self):
        self.api_version()

    def api_version(self):
        r = tornado.escape.json_encode(str(self.application.API))
        self.write(r)


class SignoutHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.signout()

    def signout(self):
        """Forget client, where possible."""
        uuid = self._get_client_info()[4]
        try:
            del self.application.clients[uuid]
        except KeyError:
            r = tornado.escape.json_encode(False)
            self.write(r)
        else:
            LOG.debug(self.LOG_FORGET_TMPL % uuid)
            r = tornado.escape.json_encode(True)
            self.write(r)


class GetCylcVersionHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self):
        self.get_cylc_version()

    def get_cylc_version(self):
        """Return the cylc version running this suite."""
        self._check_access_priv_and_report(PRIV_IDENTITY)
        r = tornado.escape.json_encode(CYLC_VERSION)
        self.write(r)


default_handlers = [
    (r"/apiversion", ApiVersionHandler),
    (r"/signout", SignoutHandler),
    (r"/get_cylc_version", GetCylcVersionHandler),
]
