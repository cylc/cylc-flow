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

import datetime
import threading
import time

import cylc.flags
from cylc.suite_logging import LOG

from cylc.network import get_client_info, get_client_connection_denied


class CommsClientReporter(object):
    """For logging cylc client requests with identifying information."""

    _INSTANCE = None
    CLIENT_FORGET_SEC = 60
    CLIENT_ID_MIN_REPORT_RATE = 1.0  # 1 Hz
    CLIENT_ID_REPORT_SECONDS = 3600  # Report every 1 hour.
    LOG_COMMAND_TMPL = '[client-command] %s %s@%s:%s %s'
    LOG_IDENTIFY_TMPL = '[client-identify] %d id requests in PT%dS'
    LOG_SIGNOUT_TMPL = '[client-sign-out] %s@%s:%s %s'
    LOG_FORGET_TMPL = '[client-forget] %s'
    LOG_CONNECT_DENIED_TMPL = "[client-connect] DENIED %s@%s:%s %s"
    LOG_CONNECT_ALLOWED_TMPL = "[client-connect] %s@%s:%s privilege='%s' %s"

    @classmethod
    def get_inst(cls):
        """Return a singleton instance."""
        if cls._INSTANCE is None:
            cls._INSTANCE = cls()
        return cls._INSTANCE

    def __init__(self):
        self.clients = {}  # {uuid: time-of-last-connect}
        self._id_start_time = time.time()  # Start of id requests measurement.
        self._num_id_requests = 0  # Number of client id requests.

    def report(self, request, server_obj):
        """Log client requests with identifying information.

        In debug mode log all requests including task messages. Otherwise log
        all user commands, and just the first info request from each client.

        """
        if threading.current_thread().__class__.__name__ == '_MainThread':
            # Server methods may be called internally as well as by clients.
            return
        auth_user, prog_name, user, host, uuid, priv_level = get_client_info()
        name = server_obj.__class__.__name__
        log_me = (
            cylc.flags.debug or
            name in ["SuiteCommandServer",
                     "ExtTriggerServer",
                     "BroadcastServer"] or
            (name not in ["SuiteIdServer", "TaskMessageServer"] and
             uuid not in self.clients))
        if log_me:
            LOG.debug(
                self.__class__.LOG_CONNECT_ALLOWED_TMPL % (
                    user, host, prog_name, priv_level, uuid)
            )
            LOG.info(
                self.__class__.LOG_COMMAND_TMPL % (
                    request, user, host, prog_name, uuid))
        if name == "SuiteIdServer":
            self._num_id_requests += 1
            self.report_id_requests()
        self.clients[uuid] = datetime.datetime.utcnow()
        self._housekeep()

    def report_id_requests(self):
        """Report the frequency of identification (scan) requests."""
        current_time = time.time()
        interval = current_time - self._id_start_time
        if interval > self.CLIENT_ID_REPORT_SECONDS:
            rate = float(self._num_id_requests) / interval
            if rate > self.CLIENT_ID_MIN_REPORT_RATE:
                LOG.warning(
                    self.__class__.LOG_IDENTIFY_TMPL % (
                        self._num_id_requests, interval)
                )
            elif cylc.flags.debug:
                LOG.info(
                    self.__class__.LOG_IDENTIFY_TMPL % (
                        self._num_id_requests, interval)
                )
            self._id_start_time = current_time
            self._num_id_requests = 0

    def report_connection_if_denied(self):
        """Log an (un?)successful connection attempt."""
        try:
            (auth_user, prog_name, user, host, uuid,
             priv_level) = get_client_info()
        except Exception:
            LOG.warn(
                self.__class__.LOG_CONNECT_DENIED_TMPL % (
                    "unknown", "unknown", "unknown", "unknown")
            )
            return
        connection_denied = get_client_connection_denied()
        if connection_denied:
            LOG.warn(
                self.__class__.LOG_CONNECT_DENIED_TMPL % (
                    user, host, prog_name, uuid)
            )

    def signout(self, server_obj):
        """Force forget this client (for use by GUI etc.)."""

        caller = server_obj.getLocalStorage().caller
        LOG.info(
            self.__class__.LOG_SIGNOUT_TMPL % (
                caller.user, caller.host, caller.prog_name, caller.uuid))
        try:
            del self.clients[caller.uuid]
        except:
            # Already forgotten.
            pass
        self._housekeep()

    def _housekeep(self):
        """Forget inactive clients."""

        for uuid in self.clients.keys():
            dtime = self.clients[uuid]
            if (self._total_seconds(datetime.datetime.utcnow() - dtime) >
                    self.__class__.CLIENT_FORGET_SEC):
                del self.clients[uuid]
                LOG.debug(
                    self.__class__.LOG_FORGET_TMPL % uuid)

    def _total_seconds(self, td):
        """Return total seconds as a datetime.timedelta object.

        For back compat - timedelta.total_seconds() in Pyton >= 2.7.

        """
        return (td.microseconds + (
                td.seconds + td.days * 24 * 3600) * 10 ** 6) / 10 ** 6
