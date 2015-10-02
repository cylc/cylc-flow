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

import logging
import datetime
import threading
import cylc.flags


class PyroClientReporter(object):
    """For logging cylc client requests with identifying information."""

    _INSTANCE = None
    CLIENT_FORGET_SEC = 60
    LOG_COMMAND_TMPL = '[client-command] %s %s@%s:%s %s'
    LOG_SIGNOUT_TMPL = '[client-sign-out] %s@%s:%s %s'
    LOG_FORGET_TMPL = '[client-forget] %s'

    @classmethod
    def get_inst(cls):
        """Return a singleton instance."""
        if cls._INSTANCE is None:
            cls._INSTANCE = cls()
        return cls._INSTANCE

    def __init__(self):
        self.clients = {}  # {uuid: time-of-last-connect}

    def report(self, request, server_obj):
        """Log client requests with identifying information.

        In debug mode log all requests including task messages. Otherwise log
        all user commands, and just the first info request from each client.

        """
        if threading.current_thread().__class__.__name__ == '_MainThread':
            # Server methods may be called internally as well as by clients.
            return
        name = server_obj.__class__.__name__
        caller = server_obj.getLocalStorage().caller
        log_me = (
            cylc.flags.debug or
            name in ["SuiteCommandServer",
                     "ExtTriggerServer",
                     "BroadcastServer"] or
            (name not in ["SuiteIdServer", "TaskMessageServer"] and
             caller.uuid not in self.clients))
        if log_me:
            logging.getLogger("main").info(
                self.__class__.LOG_COMMAND_TMPL % (
                    request, caller.user, caller.host, caller.prog_name,
                    caller.uuid))
        self.clients[caller.uuid] = datetime.datetime.utcnow()
        self._housekeep()

    def signout(self, server_obj):
        """Force forget this client (for use by GUI etc.)."""

        caller = server_obj.getLocalStorage().caller
        logging.getLogger("main").info(
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
                logging.getLogger("main").debug(
                    self.__class__.LOG_FORGET_TMPL % uuid)

    def _total_seconds(self, td):
        """Return total seconds as a datetime.timedelta object.

        For back compat - timedelta.total_seconds() in Pyton >= 2.7.

        """
        return (td.microseconds + (
                td.seconds + td.days * 24 * 3600) * 10**6) / 10**6
