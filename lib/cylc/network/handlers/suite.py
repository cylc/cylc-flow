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

"""Suite handlers"""

import tornado.escape
import tornado.web
from .base import BaseHandler
from .. import PRIVILEGE_LEVELS, PRIV_FULL_CONTROL, PRIV_FULL_READ, \
    PRIV_IDENTITY, PRIV_SHUTDOWN, PRIV_DESCRIPTION


class GetGraphRawHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self):
        self.get_graph_raw()

    def get_graph_raw(self):
        """Return raw suite graph."""
        self._check_access_priv_and_report(PRIV_FULL_READ)
        start_point_string = self.get_argument('start_point_string')
        stop_point_string = self.get_argument('stop_point_string')
        group_nodes = self.get_argument('group_nodes', None)
        ungroup_nodes = self.get_argument('ungroup_nodes', None)
        ungroup_recursive = self.get_argument('ungroup_recursive', False)
        group_all = self.get_argument('group_all', False)
        ungroup_all = self.get_argument('ungroup_all', False)

        group_nodes = self._literal_eval(
            'group_nodes', group_nodes, [group_nodes])
        ungroup_nodes = self._literal_eval(
            'ungroup_nodes', ungroup_nodes, [ungroup_nodes])
        ungroup_recursive = self._literal_eval(
            'ungroup_recursive', ungroup_recursive)
        group_all = self._literal_eval('group_all', group_all)
        ungroup_all = self._literal_eval('ungroup_all', ungroup_all)
        # Ensure that a "None" str is converted to the None value.
        stop_point_string = self._literal_eval(
            'stop_point_string', stop_point_string, stop_point_string)
        if stop_point_string is not None:
            stop_point_string = str(stop_point_string)
        r = tornado.escape.json_encode(
            self.application.scheduler.info_get_graph_raw(
                start_point_string, stop_point_string,
                group_nodes=group_nodes,
                ungroup_nodes=ungroup_nodes,
                ungroup_recursive=ungroup_recursive,
                group_all=group_all,
                ungroup_all=ungroup_all)
        )
        self.write(r)


class GetLatestStateHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self):
        self.get_latest_state()

    def get_latest_state(self):
        """Return latest suite state (suitable for a GUI update)."""
        client_info = self._check_access_priv_and_report(PRIV_FULL_READ)
        full_mode = self._literal_eval(
            'full_mode',
            self.get_argument('full_mode', False))
        r = tornado.escape.json_encode(
            self.application.scheduler
                .info_get_latest_state(client_info, full_mode)
        )
        self.write(r)


class GetSuiteInfoHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self):
        self.get_suite_info()

    def get_suite_info(self):
        """Return a dict containing the suite title and description."""
        self._check_access_priv_and_report(PRIV_DESCRIPTION)
        r = tornado.escape.json_encode(
            self.application.scheduler.info_get_suite_info()
        )
        self.write(r)


class GetSuiteStateSummaryHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self):
        self.get_suite_state_summary()

    def get_suite_state_summary(self):
        """Return the global, task, and family summary data structures."""
        self._check_access_priv_and_report(PRIV_FULL_READ)
        r = tornado.escape.json_encode(
            self.application.scheduler.info_get_suite_state_summary()
        )
        self.write(r)


class HoldAfterPointStringHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.hold_after_point_string()

    def hold_after_point_string(self):
        """Set hold point of suite."""
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        point_string = self.get_argument('point_string')
        r = tornado.escape.json_encode(
            self.application.scheduler.command_queue.put(
                ("hold_after_point_string", (point_string,), {}))
        )
        self.write(r)


class HoldSuiteHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.hold_suite()

    def hold_suite(self):
        """Hold the suite."""
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        self.application.scheduler.command_queue.put(("hold_suite", (), {}))
        r = tornado.escape.json_encode((True, 'Command queued'))
        self.write(r)


class IdentifyHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self):
        self.identify()

    def identify(self):
        """Return suite identity, (description, (states))."""
        self._report_id_requests()
        privileges = []
        for privilege in PRIVILEGE_LEVELS[0:3]:
            if self._access_priv_ok(privilege):
                privileges.append(privilege)
        r = tornado.escape.json_encode(
            self.application.scheduler.info_get_identity(privileges)
        )
        self.write(r)


class NudgeHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.nudge()

    def nudge(self):
        """Tell suite to try task processing."""
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        self.application.scheduler.command_queue.put(("nudge", (), {}))
        r = tornado.escape.json_encode((True, 'Command queued'))
        self.write(r)


class PingSuiteHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self):
        self.ping_suite()

    def ping_suite(self):
        """Return True."""
        self._check_access_priv_and_report(PRIV_IDENTITY)
        r = tornado.escape.json_encode(True)
        self.write(r)


class PutExtTriggerHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.put_ext_trigger()

    def put_ext_trigger(self):
        """Server-side external event trigger interface."""
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        event_message = self.get_argument('event_message')
        event_id = self.get_argument('event_id')
        self.application.scheduler \
            .ext_trigger_queue.put((event_message, event_id))
        r = tornado.escape.json_encode((True, 'Event queued'))
        self.write(r)


class ReloadSuiteHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.reload_suite()

    def reload_suite(self):
        """Tell suite to reload the suite definition."""
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        self.application.scheduler.command_queue.put(("reload_suite", (), {}))
        r = tornado.escape.json_encode((True, 'Command queued'))
        self.write(r)


class ReleaseSuiteHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.release_suite()

    def release_suite(self):
        """Unhold suite."""
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        self.application.scheduler.command_queue.put(("release_suite", (), {}))
        r = tornado.escape.json_encode((True, 'Command queued'))
        self.write(r)


class SetStopAfterClockTimeHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.set_stop_after_clock_time()

    def set_stop_after_clock_time(self):
        """Set suite to stop after wallclock time."""
        self._check_access_priv_and_report(PRIV_SHUTDOWN)
        self.application.scheduler.command_queue.put(
            ("set_stop_after_clock_time",
             (self.get_argument('datetime_string'),),
             {}))
        r = tornado.escape.json_encode((True, 'Command queued'))
        self.write(r)


class SetStopAfterPointHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.set_stop_after_point()

    def set_stop_after_point(self):
        """Set suite to stop after cycle point."""
        self._check_access_priv_and_report(PRIV_SHUTDOWN)
        self.application.scheduler.command_queue.put(
            ("set_stop_after_point", (self.get_argument('point_string'),), {}))
        r = tornado.escape.json_encode((True, 'Command queued'))
        self.write(r)


class SetStopAfterTaskHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.set_stop_after_task()

    def set_stop_after_task(self):
        """Set suite to stop after an instance of a task."""
        self._check_access_priv_and_report(PRIV_SHUTDOWN)
        self.application.scheduler.command_queue.put(
            ("set_stop_after_task", (self.get_argument('task_id'),), {}))
        r = tornado.escape.json_encode((True, 'Command queued'))
        self.write(r)


class SetStopCleanlyHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.set_stop_cleanly()

    def set_stop_cleanly(self):
        """Set suite to stop cleanly or after kill active tasks."""
        self._check_access_priv_and_report(PRIV_SHUTDOWN)
        kill_active_tasks = self._literal_eval(
            'kill_active_tasks', self.get_argument('kill_active_tasks', False))
        self.application.scheduler.command_queue.put(
            ("set_stop_cleanly", (), {"kill_active_tasks": kill_active_tasks}))
        r = tornado.escape.json_encode((True, 'Command queued'))
        self.write(r)


class SetVerbosityHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.set_verbosity()

    def set_verbosity(self):
        """Set suite verbosity to new level."""
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        self.application.scheduler \
            .command_queue.put(("set_verbosity",
                                (self.get_argument('level'),),
                                {}))
        r = tornado.escape.json_encode((True, 'Command queued'))
        self.write(r)


class StopNowHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.stop_now()

    def stop_now(self):
        """Stop suite on event handler completion, or terminate right away."""
        self._check_access_priv_and_report(PRIV_SHUTDOWN)
        terminate = self._literal_eval(
            'terminate', self.get_argument('terminate', False))
        self.application.scheduler.command_queue \
            .put(("stop_now", (), {"terminate": terminate}))
        r = tornado.escape.json_encode((True, 'Command queued'))
        self.write(r)


default_handlers = [
    (r"/get_graph_raw", GetGraphRawHandler),
    (r"/get_latest_state", GetLatestStateHandler),
    (r"/get_suite_info", GetSuiteInfoHandler),
    (r"/get_suite_state_summary", GetSuiteStateSummaryHandler),
    (r"/hold_after_point_string", HoldAfterPointStringHandler),
    (r"/hold_suite", HoldSuiteHandler),
    (r"/identify", IdentifyHandler),
    (r"/nudge", NudgeHandler),
    (r"/ping_suite", PingSuiteHandler),
    (r"/put_ext_trigger", PutExtTriggerHandler),
    (r"/release_suite", ReleaseSuiteHandler),
    (r"/reload_suite", ReloadSuiteHandler),
    (r"/set_stop_after_clock_time", SetStopAfterClockTimeHandler),
    (r"/set_stop_after_point", SetStopAfterPointHandler),
    (r"/set_stop_after_task", SetStopAfterTaskHandler),
    (r"/set_stop_cleanly", SetStopCleanlyHandler),
    (r"/set_verbosity", SetVerbosityHandler),
    (r"/stop_now", StopNowHandler),
]
