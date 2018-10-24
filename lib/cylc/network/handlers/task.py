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

"""Task and Task Pool handlers"""

import tornado.escape
import tornado.web
from .base import BaseHandler
from .. import PRIV_FULL_CONTROL, PRIV_FULL_READ
from ...unicode_util import utf8_enforce


class DryRunTasksHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.dry_run_tasks()

    def dry_run_tasks(self):
        """
        Prepare job file for a task.

        items[0] is an identifier for matching a task proxy.
        """
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        items = self.get_argument('items')
        if not isinstance(items, list):
            items = [items]
        check_syntax = self._literal_eval(
            'check_syntax', self.get_argument('check_syntax', True))
        self.application.scheduler \
            .command_queue.put(('dry_run_tasks', (items,),
                                {'check_syntax': check_syntax}))
        r = tornado.escape.json_encode((True, 'Command queued'))
        self.write(r)


class GetTaskInfoHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self):
        self.get_task_info()

    def get_task_info(self):
        """Return info of a task."""
        self._check_access_priv_and_report(PRIV_FULL_READ)
        names = self.get_argument('names')
        if not isinstance(names, list):
            names = [names]
        r = tornado.escape.json_encode(
            self.application.scheduler.info_get_task_info(names)
        )
        self.write(r)


class GetTaskJobfilePathHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self):
        self.get_task_jobfile_path()

    def get_task_jobfile_path(self):
        """Return task job file path."""
        self._check_access_priv_and_report(PRIV_FULL_READ)
        task_id = self.get_argument('task_id')
        r = tornado.escape.json_encode(
            self.application.scheduler.info_get_task_jobfile_path(task_id)
        )
        self.write(r)


class GetTaskRequisitesHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self):
        self.get_task_requisites()

    def get_task_requisites(self):
        """Return prerequisites of a task."""
        self._check_access_priv_and_report(PRIV_FULL_READ)
        items = self.get_argument('items', None)
        if not isinstance(items, list):
            items = [items]
        list_prereqs = self.get_argument('list_prereqs', False)
        r = tornado.escape.json_encode(
            self.application.scheduler.info_get_task_requisites(
                items, list_prereqs=(list_prereqs in [True, 'True']))
        )
        self.write(r)


class HoldTasksHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.hold_tasks()

    def hold_tasks(self):
        """Hold tasks.

        items is a list of identifiers for matching task proxies.
        """
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        items = self.get_argument('items')
        if not isinstance(items, list):
            items = [items]
        self.application.scheduler \
            .command_queue.put(("hold_tasks", (items,), {}))
        r = tornado.escape.json_encode((True, 'Command queued'))
        self.write(r)


class InsertTasksHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.insert_tasks()

    def insert_tasks(self):
        """Insert task proxies.

        items is a list of identifiers of (families of) task instances.
        """
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        items = self.get_argument('items')
        if not isinstance(items, list):
            items = [items]
        stop_point_string = self.get_argument('stop_point_string', None)
        if stop_point_string == "None":
            stop_point_string = None
        no_check = self.get_argument('no_check', False)
        self.application.scheduler.command_queue.put((
            "insert_tasks",
            (items,),
            {"stop_point_string": stop_point_string,
             "no_check": no_check in ['True', True]}))
        r = tornado.escape.json_encode((True, 'Command queued'))
        self.write(r)


class KillTasksHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.kill_tasks()

    def kill_tasks(self):
        """Kill task jobs.

        items is a list of identifiers for matching task proxies.
        """
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        items = self.get_argument('items')
        if not isinstance(items, list):
            items = [items]
        self.application.scheduler \
            .command_queue.put(("kill_tasks", (items,), {}))
        r = tornado.escape.json_encode((True, 'Command queued'))
        self.write(r)


class PingTaskHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self):
        self.ping_task()

    def ping_task(self):
        """Return True if task_id exists (and running)."""
        self._check_access_priv_and_report(PRIV_FULL_READ)
        task_id = self.get_argument('task_id')
        exists_only = self._literal_eval(
            'exists_only',
            self.get_argument('exists_only', False))
        r = tornado.escape.json_encode(
            self.application
                .scheduler.info_ping_task(task_id, exists_only=exists_only)
        )
        self.write(r)


class PollTasksHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.poll_tasks()

    def poll_tasks(self):
        """Poll task jobs.

        items is a list of identifiers for matching task proxies.
        """
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        items = self.get_argument('items', None)
        if not isinstance(items, list):
            items = [items]
        poll_succ = self.get_argument('poll_succ', False)
        self.application.scheduler.command_queue.put(
            ("poll_tasks", (items,),
             {"poll_succ": poll_succ in ['True', True]}))
        r = tornado.escape.json_encode((True, 'Command queued'))
        self.write(r)


class PutMessageHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.put_message()

    def put_message(self):
        """(Compat) Put task message."""
        self._check_access_priv_and_report(PRIV_FULL_CONTROL, log_info=False)
        message = self.get_argument('message')
        match = self.RE_MESSAGE_TIME.match(message)
        event_time = None
        if match:
            message, event_time = match.groups()
        self.application.scheduler.message_queue.put(
            (self.get_argument('task_id'),
             event_time,
             self.get_argument('severity'),
             message))
        r = tornado.escape.json_encode((True, 'Message queued'))
        self.write(r)


class PutMessagesHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.put_messages()

    def put_messages(self):
        """Put task messages in queue for processing later by the main loop."""
        self._check_access_priv_and_report(PRIV_FULL_CONTROL, log_info=False)
        data = {}
        if self.request.body:
            data.update(tornado.escape.json_decode(self.request.body))
        task_job = utf8_enforce(
            data.get('task_job', self.get_argument('task_job', None)))
        event_time = utf8_enforce(
            data.get('event_time', self.get_argument('event_time', None)))
        messages = utf8_enforce(
            data.get('messages', self.get_argument('messages', None)))
        for severity, message in messages:
            self.application.scheduler.message_queue.put(
                (task_job, event_time, severity, message))
        r = tornado.escape.json_encode(
            (True, 'Messages queued: %d' % len(messages))
        )
        self.write(r)


class ReleaseTasksHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.release_tasks()

    def release_tasks(self):
        """Unhold tasks.

        items is a list of identifiers for matching task proxies.
        """
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        items = self.get_argument('items')
        if not isinstance(items, list):
            items = [items]
        self.application.scheduler \
            .command_queue.put(("release_tasks", (items,), {}))
        r = tornado.escape.json_encode((True, 'Command queued'))
        self.write(r)


class RemoveCycleHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.remove_cycle()

    def remove_cycle(self):
        """Remove tasks in a cycle from task pool."""
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        spawn = self._literal_eval('spawn', self.get_argument('spawn', False))
        self.application.scheduler.command_queue.put(
            ("remove_tasks",
             ('%s/*' % self.get_argument('point_string'),),
             {"spawn": spawn}))
        r = tornado.escape.json_encode((True, 'Command queued'))
        self.write(r)


class RemoveTasksHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.remove_tasks()

    def remove_tasks(self):
        """Remove tasks from task pool.

        items is a list of identifiers for matching task proxies.
        """
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        spawn = self._literal_eval('spawn', self.get_argument('spawn', False))
        items = self.get_argument('items')
        if not isinstance(items, list):
            items = [items]
        self.application.scheduler.command_queue.put(
            ("remove_tasks", (items,), {"spawn": spawn}))
        r = tornado.escape.json_encode((True, 'Command queued'))
        self.write(r)


class ResetTaskStatesHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.reset_task_states()

    def reset_task_states(self):
        """Reset statuses tasks.

        items is a list of identifiers for matching task proxies.
        """
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        items = self.get_argument('items')
        if not isinstance(items, list):
            items = [items]
        outputs = self.get_argument('outputs', None)
        if not isinstance(outputs, list):
            outputs = [outputs]
        self.application.scheduler.command_queue.put((
            "reset_task_states",
            (items,), {"state": self.get_argument('state', False),
                       "outputs": outputs}))
        r = tornado.escape.json_encode((True, 'Command queued'))
        self.write(r)


class SpawnTasksHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.spawn_tasks()

    def spawn_tasks(self):
        """Spawn tasks.

        items is a list of identifiers for matching task proxies.
        """
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        items = self.get_argument('items')
        if not isinstance(items, list):
            items = [items]
        self.application.scheduler \
            .command_queue.put(("spawn_tasks", (items,), {}))
        r = tornado.escape.json_encode((True, 'Command queued'))
        self.write(r)


class TakeCheckpointsHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.take_checkpoints()

    def take_checkpoints(self):
        """Checkpoint current task pool.

        items[0] is the name of the checkpoint.
        """
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        items = self.get_argument('items')
        if not isinstance(items, list):
            items = [items]
        self.application.scheduler \
            .command_queue.put(("take_checkpoints", (items,), {}))
        r = tornado.escape.json_encode((True, 'Command queued'))
        self.write(r)


class TriggerTasksHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        self.trigger_tasks()

    def trigger_tasks(self):
        """Trigger submission of task jobs where possible.

        items is a list of identifiers for matching task proxies.
        """
        self._check_access_priv_and_report(PRIV_FULL_CONTROL)
        back_out = self._literal_eval('back_out',
                                      self.get_argument('back_out', False))
        items = self.get_argument('items')
        if not isinstance(items, list):
            items = [items]
        items = [str(item) for item in items]
        self.application.scheduler.command_queue.put(
            ("trigger_tasks", (items,), {"back_out": back_out}))
        r = tornado.escape.json_encode((True, 'Command queued'))
        self.write(r)


default_handlers = [
    (r"/dry_run_tasks", DryRunTasksHandler),
    (r"/get_task_info", GetTaskInfoHandler),
    (r"/get_task_jobfile_path", GetTaskJobfilePathHandler),
    (r"/get_task_requisites", GetTaskRequisitesHandler),
    (r"/hold_tasks", HoldTasksHandler),
    (r"/insert_tasks", InsertTasksHandler),
    (r"/kill_tasks", KillTasksHandler),
    (r"/ping_task", PingTaskHandler),
    (r"/poll_tasks", PollTasksHandler),
    (r"/put_message", PutMessageHandler),
    (r"/put_messages", PutMessagesHandler),
    (r"/release_tasks", ReleaseTasksHandler),
    (r"/remove_cycle", RemoveCycleHandler),
    (r"/remove_tasks", RemoveTasksHandler),
    (r"/reset_task_states", ResetTaskStatesHandler),
    (r"/spawn_tasks", SpawnTasksHandler),
    (r"/take_checkpoints", TakeCheckpointsHandler),
    (r"/trigger_tasks", TriggerTasksHandler),
]
