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
import cylc.flags

class PyroClientReporter(object):
    """Log commands from cylc clients with identifying information.
    
    For single-connect clients (e.g. CLI commands), log each command.

    For multi-connect clients (e.g. cylc-gui, cylc-monitor) only sign-in and
    sign-out are logged, except in debug mode. If no explicit sign-out is
    received the client is forgotten after a time (any subsequent connect is
    another sign-on). Individual commands are not logged except in debug mode.

    Note that a client program can contain multiple Pyro client interfaces;
    these can be a mix of single and multi-connect clients; and can all share
    the same UUID.
    """

    _INSTANCE = None
    CLIENT_FORGET_SEC = 60
    LOG_TMPL = 'Client: %s (%s %s %s)'

    @classmethod
    def get_inst(cls):
        """Return a singleton instance."""
        if cls._INSTANCE is None:
            cls._INSTANCE = cls()
        return cls._INSTANCE

    def __init__(self):
        self.log = logging.getLogger("main")
        # {uuid: (info, datetime)}
        self.clients = {}

    def report(self, command, uuid, info, multi):
        now = datetime.datetime.utcnow()
        if multi:
            if uuid not in self.clients:
                self.log.info(
                    self.__class__.LOG_TMPL % (
                        'sign-in', info['name'], info['user_at_host'], uuid))
            self.clients[uuid] = (info, now)
        if not multi or cylc.flags.debug:
            self.log.info(
                self.__class__.LOG_TMPL % (
                    command,
                    info['name'], info['user_at_host'], uuid))
        self._housekeep()

    def signout(self, uuid, info):
        """Forget this client."""
        self.log.info(
            self.__class__.LOG_TMPL % (
                'sign-out', info['name'], info['user_at_host'], uuid))
        try:
            del self.clients[uuid]
        except:
            # In case of multiple calls from a multi-client program.
            pass
        self._housekeep()

    def _housekeep(self):
        """Forget inactive clients."""
        now = datetime.datetime.utcnow()
        for uuid in self.clients.keys():
            info, dtime = self.clients[uuid]
            if (self._total_seconds(now - dtime) >
                    self.__class__.CLIENT_FORGET_SEC):
                del self.clients[uuid]
                self.log.info(
                    self.__class__.LOG_TMPL % (
                        'forget', info['name'], info['user_at_host'], uuid))
 
    def _total_seconds(self, td):
        """Return total seconds in a datetime.timedelta object.

        Back compat Python 2.6.x; timedelta.total_seconds() introduced in 2.7.
        """
        return (td.microseconds + (
                td.seconds + td.days * 24 * 3600) * 10**6) / 10**6 
