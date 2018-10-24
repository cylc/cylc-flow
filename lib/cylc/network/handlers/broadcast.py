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

"""Broadcast handlers"""

import tornado.escape
import tornado.web
from .base import BaseHandler
from .. import PRIV_FULL_READ, PRIV_FULL_CONTROL
from ...unicode_util import utf8_enforce


class ClearBroadcastHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.clear_broadcast()

    def clear_broadcast(self):
        """
        Clear settings globally, or for listed namespaces and/or points.

        Return a tuple (modified_settings, bad_options), where:
        * modified_settings is similar to the return value of the "put" method,
          but for removed settings.
        * bad_options is a dict in the form:
              {"point_strings": ["20020202", ..."], ...}
          The dict is only populated if there are options not associated with
          previous broadcasts. The keys can be:
          * point_strings: a list of bad point strings.
          * namespaces: a list of bad namespaces.
          * cancel: a list of tuples. Each tuple contains the keys of a bad
            setting.
        """
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        data = {}
        if self.request.body:
            data.update(tornado.escape.json_decode(self.request.body))
        point_strings = utf8_enforce(
            data.get('point_strings',
                     self.get_argument('point_strings', None)))
        namespaces = utf8_enforce(
            data.get('namespaces',
                     self.get_argument('namespaces', None)))
        cancel_settings = utf8_enforce(
            data.get('cancel_settings',
                     self.get_argument('cancel_settings', None)))
        r = tornado.escape.json_encode(
            self.application.scheduler.task_events_mgr.broadcast_mgr
                .clear_broadcast(point_strings, namespaces, cancel_settings)
        )
        self.write(r)


class ExpireBroadcastHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.expire_broadcast()

    def expire_broadcast(self):
        """Clear all settings targeting cycle points earlier than cutoff."""
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        cutoff = self.get_argument('cutoff', None)
        r = tornado.escape.json_encode(
            self.application.scheduler
                .task_events_mgr.broadcast_mgr.expire_broadcast(cutoff)
        )
        self.write(r)


class GetBroadcastHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self):
        self.get_broadcast()

    def get_broadcast(self):
        """Retrieve all broadcast variables that target a given task ID."""
        self._check_access_priv_and_report(PRIV_FULL_READ)
        task_id = self.get_argument('task_id', None)
        r = tornado.escape.json_encode(
            self.application.scheduler
                .task_events_mgr.broadcast_mgr.get_broadcast(task_id)
        )
        self.write(r)


class PutBroadcastHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.put_broadcast()

    def put_broadcast(self):
        """Add new broadcast settings (server side interface).

        Return a tuple (modified_settings, bad_options) where:
          modified_settings is list of modified settings in the form:
            [("20200202", "foo", {"command scripting": "true"}, ...]
          bad_options is as described in the docstring for self.clear().
        """
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        data = {}
        if self.request.body:
            data.update(tornado.escape.json_decode(self.request.body))
        point_strings = utf8_enforce(
            data.get('point_strings',
                     self.get_argument('point_strings', None)))
        namespaces = utf8_enforce(
            data.get('namespaces',
                     self.get_argument('namespaces', None)))
        settings = utf8_enforce(
            data.get('settings',
                     self.get_argument('settings', None)))
        r = tornado.escape.json_encode(
            self.application.scheduler
                .task_events_mgr.broadcast_mgr.put_broadcast(
                 point_strings, namespaces, settings)
        )
        self.write(r)


default_handlers = [
    (r"/clear_broadcast", ClearBroadcastHandler),
    (r"/expire_broadcast", ExpireBroadcastHandler),
    (r"/get_broadcast", GetBroadcastHandler),
    (r"/put_broadcast", PutBroadcastHandler),
]
