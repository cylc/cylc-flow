#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA
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
"""Task events manager.

This module provides logic to:
* Manage task messages (incoming or internal).
* Set up retries on task job failures (submission or execution).
* Generate task event handlers.
  * Retrieval of log files for completed remote jobs.
  * Email notification.
  * Custom event handlers.
* Manage invoking and retrying of task event handlers.
"""

from collections import namedtuple
from logging import getLevelName, CRITICAL, ERROR, WARNING, INFO, DEBUG
import os
from pipes import quote
import re
import shlex
from time import time
import traceback

from parsec.config import ItemNotFoundError

from cylc.broadcast_mgr import BroadcastMgr
from cylc.cfgspec.glbl_cfg import glbl_cfg
import cylc.flags
from cylc.mp_pool import SuiteProcContext
from cylc.suite_logging import ERR, LOG
from cylc.hostuserutil import get_host, get_user
from cylc.task_action_timer import TaskActionTimer
from cylc.task_message import TaskMessage
from cylc.task_state import (
    TASK_STATUS_READY, TASK_STATUS_SUBMITTED, TASK_STATUS_SUBMIT_RETRYING,
    TASK_STATUS_SUBMIT_FAILED, TASK_STATUS_RUNNING, TASK_STATUS_RETRYING,
    TASK_STATUS_FAILED, TASK_STATUS_SUCCEEDED)
from cylc.task_outputs import (
    TASK_OUTPUT_SUBMITTED, TASK_OUTPUT_STARTED, TASK_OUTPUT_SUCCEEDED,
    TASK_OUTPUT_FAILED)
from cylc.wallclock import (
    get_current_time_string, RE_DATE_TIME_FORMAT_EXTENDED)


CustomTaskEventHandlerContext = namedtuple(
    "CustomTaskEventHandlerContext",
    ["key", "ctx_type", "cmd"])


TaskEventMailContext = namedtuple(
    "TaskEventMailContext",
    ["key", "ctx_type", "mail_from", "mail_to", "mail_smtp"])


TaskJobLogsRetrieveContext = namedtuple(
    "TaskJobLogsRetrieveContext",
    ["key", "ctx_type", "user_at_host", "max_size"])


class TaskEventsManager(object):
    """Task events manager.

    This class does the following:
    * Manage task messages (incoming or otherwise).
    * Set up task (submission) retries on job (submission) failures.
    * Generate and manage task event handlers.
    """
    EVENT_FAILED = TASK_OUTPUT_FAILED
    EVENT_RETRY = "retry"
    EVENT_STARTED = TASK_OUTPUT_STARTED
    EVENT_SUBMITTED = TASK_OUTPUT_SUBMITTED
    EVENT_SUBMIT_FAILED = "submission failed"
    EVENT_SUBMIT_RETRY = "submission retry"
    EVENT_SUCCEEDED = TASK_OUTPUT_SUCCEEDED
    HANDLER_CUSTOM = "event-handler"
    HANDLER_MAIL = "event-mail"
    JOB_FAILED = "job failed"
    HANDLER_JOB_LOGS_RETRIEVE = "job-logs-retrieve"
    INCOMING_FLAG = ">"
    LEVELS = {
        "INFO": INFO,
        "NORMAL": INFO,
        "WARNING": WARNING,
        "ERROR": ERROR,
        "CRITICAL": CRITICAL,
        "DEBUG": DEBUG,
    }
    NN = "NN"
    POLLED_INDICATOR = "(polled)"
    RE_MESSAGE_TIME = re.compile(
        '\A(.+) at (' + RE_DATE_TIME_FORMAT_EXTENDED + ')\Z', re.DOTALL)

    def __init__(self, suite, proc_pool, suite_db_mgr, broadcast_mgr=None):
        self.suite = suite
        self.suite_url = None
        self.suite_cfg = {}
        self.proc_pool = proc_pool
        self.suite_db_mgr = suite_db_mgr
        if broadcast_mgr is None:
            broadcast_mgr = BroadcastMgr(self.suite_db_mgr)
        self.broadcast_mgr = broadcast_mgr
        self.mail_interval = 0.0
        self.mail_footer = None
        self.next_mail_time = None
        self.event_timers = {}
        # Set pflag = True to stimulate task dependency negotiation whenever a
        # task changes state in such a way that others could be affected. The
        # flag should only be turned off again after use in
        # Scheduler.process_tasks, to ensure that dependency negotation occurs
        # when required.
        self.pflag = False

    def get_host_conf(self, itask, key, default=None, skey="remote"):
        """Return a host setting from suite then global configuration."""
        overrides = self.broadcast_mgr.get_broadcast(itask.identity)
        if skey in overrides and overrides[skey].get(key) is not None:
            return overrides[skey][key]
        elif itask.tdef.rtconfig[skey].get(key) is not None:
            return itask.tdef.rtconfig[skey][key]
        else:
            try:
                return glbl_cfg().get_host_item(
                    key, itask.task_host, itask.task_owner)
            except (KeyError, ItemNotFoundError):
                pass
        return default

    def get_task_job_activity_log(
            self, suite, point, name, submit_num=None):
        """Shorthand for get_task_job_log(..., tail="job-activity.log")."""
        return self.get_task_job_log(
            suite, point, name, submit_num, "job-activity.log")

    def get_task_job_log(
            self, suite, point, name, submit_num=None, tail=None):
        """Return the job log path."""
        args = [
            glbl_cfg().get_derived_host_item(suite, "suite job log directory"),
            self.get_task_job_id(point, name, submit_num)]
        if tail:
            args.append(tail)
        return os.path.join(*args)

    def get_task_job_id(self, point, name, submit_num=None):
        """Return the job log path."""
        try:
            submit_num = "%02d" % submit_num
        except TypeError:
            submit_num = self.NN
        return os.path.join(str(point), name, submit_num)

    def log_task_job_activity(self, ctx, suite, point, name, submit_num=NN):
        """Log an activity for a task job."""
        ctx_str = str(ctx)
        if not ctx_str:
            return
        if isinstance(ctx.cmd_key, tuple):  # An event handler
            submit_num = ctx.cmd_key[-1]
        job_activity_log = self.get_task_job_activity_log(
            suite, point, name, submit_num)
        try:
            with open(job_activity_log, "ab") as handle:
                handle.write(ctx_str + '\n')
        except IOError as exc:
            LOG.warning("%s: write failed\n%s" % (job_activity_log, exc))
        if ctx.cmd and ctx.ret_code:
            LOG.error(ctx_str)
        elif ctx.cmd:
            LOG.debug(ctx_str)

    def process_events(self, schd_ctx):
        """Process task events that were created by "setup_event_handlers".

        schd_ctx is an instance of "Schduler" in "cylc.scheduler".
        """
        ctx_groups = {}
        now = time()
        for id_key, timer in self.event_timers.copy().items():
            key1, point, name, submit_num = id_key
            if timer.is_waiting:
                continue
            # Set timer if timeout is None.
            if not timer.is_timeout_set():
                if timer.next() is None:
                    LOG.warning("%s/%s/%02d %s failed" % (
                        point, name, submit_num, key1))
                    del self.event_timers[id_key]
                    continue
                # Report retries and delayed 1st try
                tmpl = None
                if timer.num > 1:
                    tmpl = "%s/%s/%02d %s failed, retrying in %s (after %s)"
                elif timer.delay:
                    tmpl = "%s/%s/%02d %s will run after %s (after %s)"
                if tmpl:
                    LOG.debug(tmpl % (
                        point, name, submit_num, key1,
                        timer.delay_as_seconds(),
                        timer.timeout_as_str()))
            # Ready to run?
            if not timer.is_delay_done() or (
                # Avoid flooding user's mail box with mail notification.
                # Group together as many notifications as possible within a
                # given interval.
                timer.ctx.ctx_type == self.HANDLER_MAIL and
                not schd_ctx.stop_mode and
                self.next_mail_time is not None and
                self.next_mail_time > now
            ):
                continue

            timer.set_waiting()
            if timer.ctx.ctx_type == self.HANDLER_CUSTOM:
                # Run custom event handlers on their own
                self.proc_pool.put_command(
                    SuiteProcContext(
                        (key1, submit_num),
                        timer.ctx.cmd, env=os.environ, shell=True,
                    ),
                    self._custom_handler_callback, [schd_ctx, id_key])
            else:
                # Group together built-in event handlers, where possible
                if timer.ctx not in ctx_groups:
                    ctx_groups[timer.ctx] = []
                ctx_groups[timer.ctx].append(id_key)

        next_mail_time = now + self.mail_interval
        for ctx, id_keys in ctx_groups.items():
            if ctx.ctx_type == self.HANDLER_MAIL:
                # Set next_mail_time if any mail sent
                self.next_mail_time = next_mail_time
                self._process_event_email(schd_ctx, ctx, id_keys)
            elif ctx.ctx_type == self.HANDLER_JOB_LOGS_RETRIEVE:
                self._process_job_logs_retrieval(schd_ctx, ctx, id_keys)

    def _poll_to_confirm(self, itask, status_gt, poll_func):
        """Poll itask to confirm an apparent state reversal."""
        if (itask.state.is_greater_than(status_gt) and not
                itask.state.confirming_with_poll):
            poll_func(self.suite, [itask],
                      msg="polling %s to confirm state" % itask.identity)
            itask.state.confirming_with_poll = True
            return True
        else:
            itask.state.confirming_with_poll = False
            return False

    def process_message(self, itask, severity, message, poll_func,
                        poll_event_time=None, is_incoming=False):
        """Parse an incoming task message and update task state.

        Incoming, e.g. "succeeded at <TIME>", may be from task job or polling.

        It is possible for my current state to be inconsistent with an incoming
        message (whether normal or polled) e.g. due to a late poll result, or a
        network outage, or manual state reset. To handle this, if a message
        would take the task state backward, issue a poll to confirm instead of
        changing state - then always believe the next message. Note that the
        next message might not be the result of this confirmation poll, in the
        unlikely event that a job emits a succession of messages very quickly,
        but this is the best we can do without somehow uniquely associating
        each poll with its result message.

        """

        is_polled = poll_event_time is not None
        # Log incoming messages with '>' to distinguish non-message log entries
        message_flag = ""
        if is_incoming:
            message_flag = self.INCOMING_FLAG
        log_message = '(current:%s)%s %s' % (
            itask.state.status, message_flag, message)
        if poll_event_time is not None:
            log_message += ' %s' % self.POLLED_INDICATOR
        LOG.log(self.LEVELS.get(severity, INFO), log_message, itask=itask)

        # Strip the "at TIME" suffix.
        event_time = poll_event_time
        if not event_time:
            match = self.RE_MESSAGE_TIME.match(message)
            if match:
                message, event_time = match.groups()
        if not event_time:
            event_time = get_current_time_string()

        # always update the suite state summary for latest message
        itask.summary['latest_message'] = message
        if is_polled:
            itask.summary['latest_message'] += " %s" % self.POLLED_INDICATOR
        cylc.flags.iflag = True

        # Satisfy my output, if possible, and record the result.
        an_output_was_satisfied = itask.state.outputs.set_msg_trg_completion(
            message=message, is_completed=True)

        if message == TASK_OUTPUT_STARTED:
            if self._poll_to_confirm(itask, TASK_STATUS_RUNNING, poll_func):
                return
            self._process_message_started(itask, event_time)
        elif message == TASK_OUTPUT_SUCCEEDED:
            if self._poll_to_confirm(itask, TASK_STATUS_SUCCEEDED, poll_func):
                return
            self._process_message_succeeded(itask, event_time)
        elif message == TASK_OUTPUT_FAILED:
            if self._poll_to_confirm(itask, TASK_STATUS_FAILED, poll_func):
                return
            self._process_message_failed(itask, event_time, self.JOB_FAILED)
        elif message == self.EVENT_SUBMIT_FAILED:
            if self._poll_to_confirm(itask,
                                     TASK_STATUS_SUBMIT_FAILED, poll_func):
                return
            self._process_message_submit_failed(itask, event_time)
        elif message == TASK_OUTPUT_SUBMITTED:
            if self._poll_to_confirm(itask, TASK_STATUS_SUBMITTED, poll_func):
                return
            self._process_message_submitted(itask, event_time)
        elif message.startswith(TaskMessage.FAIL_MESSAGE_PREFIX):
            # Task received signal.
            signal = message[len(TaskMessage.FAIL_MESSAGE_PREFIX):]
            self._db_events_insert(itask, "signaled", signal)
            self.suite_db_mgr.put_update_task_jobs(
                itask, {"run_signal": signal})
            if self._poll_to_confirm(itask, TASK_STATUS_FAILED, poll_func):
                return
            self._process_message_failed(itask, event_time, self.JOB_FAILED)
        elif message.startswith(TaskMessage.ABORT_MESSAGE_PREFIX):
            # Task aborted with message
            aborted_with = message[len(TaskMessage.ABORT_MESSAGE_PREFIX):]
            self._db_events_insert(itask, "aborted", message)
            self.suite_db_mgr.put_update_task_jobs(
                itask, {"run_signal": aborted_with})
            if self._poll_to_confirm(itask, TASK_STATUS_FAILED, poll_func):
                return
            self._process_message_failed(itask, event_time, aborted_with)
        elif message.startswith(TaskMessage.VACATION_MESSAGE_PREFIX):
            # Task job pre-empted into a vacation state
            self._db_events_insert(itask, "vacated", message)
            itask.set_event_time('started')  # reset
            if TASK_STATUS_SUBMIT_RETRYING in itask.try_timers:
                itask.try_timers[TASK_STATUS_SUBMIT_RETRYING].num = 0
            itask.job_vacated = True
            try:
                itask.timeout_timers[TASK_STATUS_SUBMITTED] = (
                    itask.summary['submitted_time'] +
                    float(self._get_events_conf(itask, 'submission timeout')))
            except (TypeError, ValueError):
                itask.timeout_timers[TASK_STATUS_SUBMITTED] = None
            # Believe this and change state without polling (could poll?).
            self.pflag = True
            itask.state.reset_state(TASK_STATUS_SUBMITTED)
        elif an_output_was_satisfied:
            # Message of an as-yet unreported custom task output.
            # No state change.
            self.pflag = True
            self.suite_db_mgr.put_update_task_outputs(itask)
        else:
            # Unhandled messages. These include:
            #  * general non-output/progress messages
            #  * poll messages that repeat previous results
            # Note that all messages are logged already at the top.
            # No state change.
            LOG.debug(
                '(current: %s) unhandled: %s' % (itask.state.status, message),
                itask=itask)
            if severity in [CRITICAL, ERROR, WARNING, INFO, DEBUG]:
                severity = getLevelName(severity)
            self._db_events_insert(
                itask, ("message %s" % str(severity).lower()), message)
        if severity == "CUSTOM":
            self.setup_event_handlers(itask, "custom", message)
        elif severity in [TaskMessage.WARNING, TaskMessage.CRITICAL]:
            self.setup_event_handlers(itask, severity.lower(), message)

    def setup_event_handlers(self, itask, event, message):
        """Set up handlers for a task event."""
        if itask.tdef.run_mode != 'live':
            return
        msg = ""
        if message != "job %s" % event:
            msg = message
        self._db_events_insert(itask, event, msg)
        self._setup_job_logs_retrieval(itask, event)
        self._setup_event_mail(itask, event)
        self._setup_custom_event_handlers(itask, event, message)

    @staticmethod
    def set_poll_time(itask, now=None):
        """Set the next task execution/submission poll time.

        If now is set, set the timer only if the previous delay is done.
        Return the next delay.
        """
        key = itask.state.status
        timer = itask.poll_timers.get(key)
        if timer is None:
            return
        if now is not None and not timer.is_delay_done(now):
            return
        if timer.num is None:
            timer.num = 0
        delay = timer.next(no_exhaust=True)
        if delay is not None:
            LOG.info(
                'next job poll in %s (after %s)' % (
                    timer.delay_as_seconds(), timer.timeout_as_str()),
                itask=itask)
        return delay

    def _custom_handler_callback(self, ctx, schd_ctx, id_key):
        """Callback when a custom event handler is done."""
        _, point, name, submit_num = id_key
        self.log_task_job_activity(
            ctx, schd_ctx.suite, point, name, submit_num)
        if ctx.ret_code == 0:
            del self.event_timers[id_key]
        else:
            self.event_timers[id_key].unset_waiting()

    def _db_events_insert(self, itask, event="", message=""):
        """Record an event to the DB."""
        self.suite_db_mgr.put_insert_task_events(itask, {
            "time": get_current_time_string(),
            "event": event,
            "message": message})

    def _process_event_email(self, schd_ctx, ctx, id_keys):
        """Process event notification, by email."""
        if len(id_keys) == 1:
            # 1 event from 1 task
            (_, event), point, name, submit_num = id_keys[0]
            subject = "[%s/%s/%02d %s] %s" % (
                point, name, submit_num, event, schd_ctx.suite)
        else:
            event_set = set(id_key[0][1] for id_key in id_keys)
            if len(event_set) == 1:
                # 1 event from n tasks
                subject = "[%d tasks %s] %s" % (
                    len(id_keys), event_set.pop(), schd_ctx.suite)
            else:
                # n events from n tasks
                subject = "[%d task events] %s" % (
                    len(id_keys), schd_ctx.suite)
        cmd = ["mail", "-s", subject]
        # From: and To:
        cmd.append("-r")
        cmd.append(ctx.mail_from)
        cmd.append(ctx.mail_to)
        # STDIN for mail, tasks
        stdin_str = ""
        for id_key in sorted(id_keys):
            (_, event), point, name, submit_num = id_key
            stdin_str += "%s: %s/%s/%02d\n" % (event, point, name, submit_num)
        # STDIN for mail, event info + suite detail
        stdin_str += "\n"
        for label, value in [
                ('suite', schd_ctx.suite),
                ("host", schd_ctx.host),
                ("port", schd_ctx.port),
                ("owner", schd_ctx.owner)]:
            if value:
                stdin_str += "%s: %s\n" % (label, value)
        if self.mail_footer:
            stdin_str += (self.mail_footer + "\n") % {
                "host": schd_ctx.host,
                "port": schd_ctx.port,
                "owner": schd_ctx.owner,
                "suite": schd_ctx.suite}
        # SMTP server
        env = dict(os.environ)
        mail_smtp = ctx.mail_smtp
        if mail_smtp:
            env["smtp"] = mail_smtp
        self.proc_pool.put_command(
            SuiteProcContext(
                ctx, cmd, env=env, stdin_str=stdin_str, id_keys=id_keys,
            ),
            self._event_email_callback, [schd_ctx])

    def _event_email_callback(self, proc_ctx, schd_ctx):
        """Call back when email notification command exits."""
        for id_key in proc_ctx.cmd_kwargs["id_keys"]:
            key1, point, name, submit_num = id_key
            try:
                if proc_ctx.ret_code == 0:
                    del self.event_timers[id_key]
                    log_ctx = SuiteProcContext((key1, submit_num), None)
                    log_ctx.ret_code = 0
                    self.log_task_job_activity(
                        log_ctx, schd_ctx.suite, point, name, submit_num)
                else:
                    self.event_timers[id_key].unset_waiting()
            except KeyError:
                if cylc.flags.debug:
                    ERR.debug(traceback.format_exc())

    def _get_events_conf(self, itask, key, default=None):
        """Return an events setting from suite then global configuration."""
        for getter in [
                self.broadcast_mgr.get_broadcast(itask.identity).get("events"),
                itask.tdef.rtconfig["events"],
                glbl_cfg().get()["task events"]]:
            try:
                value = getter.get(key)
            except (AttributeError, ItemNotFoundError, KeyError):
                pass
            else:
                if value is not None:
                    return value
        return default

    def _process_job_logs_retrieval(self, schd_ctx, ctx, id_keys):
        """Process retrieval of task job logs from remote user@host."""
        if ctx.user_at_host and "@" in ctx.user_at_host:
            s_user, s_host = ctx.user_at_host.split("@", 1)
        else:
            s_user, s_host = (None, ctx.user_at_host)
        ssh_str = str(glbl_cfg().get_host_item("ssh command", s_host, s_user))
        rsync_str = str(glbl_cfg().get_host_item(
            "retrieve job logs command", s_host, s_user))

        cmd = shlex.split(rsync_str) + ["--rsh=" + ssh_str]
        if cylc.flags.debug:
            cmd.append("-v")
        if ctx.max_size:
            cmd.append("--max-size=%s" % (ctx.max_size,))
        # Includes and excludes
        includes = set()
        for _, point, name, submit_num in id_keys:
            # Include relevant directories, all levels needed
            includes.add("/%s" % (point))
            includes.add("/%s/%s" % (point, name))
            includes.add("/%s/%s/%02d" % (point, name, submit_num))
            includes.add("/%s/%s/%02d/**" % (point, name, submit_num))
        cmd += ["--include=%s" % (include) for include in sorted(includes)]
        cmd.append("--exclude=/**")  # exclude everything else
        # Remote source
        cmd.append(ctx.user_at_host + ":" + glbl_cfg().get_derived_host_item(
            schd_ctx.suite, "suite job log directory", s_host, s_user) + "/")
        # Local target
        cmd.append(glbl_cfg().get_derived_host_item(
            schd_ctx.suite, "suite job log directory") + "/")
        self.proc_pool.put_command(
            SuiteProcContext(ctx, cmd, env=dict(os.environ), id_keys=id_keys),
            self._job_logs_retrieval_callback, [schd_ctx])

    def _job_logs_retrieval_callback(self, proc_ctx, schd_ctx):
        """Call back when log job retrieval completes."""
        for id_key in proc_ctx.cmd_kwargs["id_keys"]:
            key1, point, name, submit_num = id_key
            try:
                # All completed jobs are expected to have a "job.out".
                fnames = ["job.out"]
                try:
                    if key1[1] not in 'succeeded':
                        fnames.append("job.err")
                except TypeError:
                    pass
                fname_oks = {}
                for fname in fnames:
                    fname_oks[fname] = os.path.exists(self.get_task_job_log(
                        schd_ctx.suite, point, name, submit_num, fname))
                # All expected paths must exist to record a good attempt
                log_ctx = SuiteProcContext((key1, submit_num), None)
                if all(fname_oks.values()):
                    log_ctx.ret_code = 0
                    del self.event_timers[id_key]
                else:
                    log_ctx.ret_code = 1
                    log_ctx.err = "File(s) not retrieved:"
                    for fname, exist_ok in sorted(fname_oks.items()):
                        if not exist_ok:
                            log_ctx.err += " %s" % fname
                    self.event_timers[id_key].unset_waiting()
                self.log_task_job_activity(
                    log_ctx, schd_ctx.suite, point, name, submit_num)
            except KeyError:
                if cylc.flags.debug:
                    ERR.debug(traceback.format_exc())

    def _process_message_failed(self, itask, event_time, message):
        """Helper for process_message, handle a failed message."""
        if event_time is None:
            event_time = get_current_time_string()
        itask.set_event_time('finished', event_time)
        self.suite_db_mgr.put_update_task_jobs(itask, {
            "run_status": 1,
            "time_run_exit": event_time,
        })
        if (TASK_STATUS_RETRYING not in itask.try_timers or
                itask.try_timers[TASK_STATUS_RETRYING].next() is None):
            # No retry lined up: definitive failure.
            self.pflag = True
            itask.state.reset_state(TASK_STATUS_FAILED)
            self.setup_event_handlers(itask, "failed", message)
            LOG.critical("job(%02d) %s" % (
                itask.submit_num, "failed"), itask=itask)
        else:
            # There is a retry lined up
            timeout_str = (
                itask.try_timers[TASK_STATUS_RETRYING].timeout_as_str())
            delay_msg = "retrying in %s" % (
                itask.try_timers[TASK_STATUS_RETRYING].delay_as_seconds())
            msg = "failed, %s (after %s)" % (delay_msg, timeout_str)
            LOG.info("job(%02d) %s" % (itask.submit_num, msg), itask=itask)
            itask.summary['latest_message'] = msg
            self.setup_event_handlers(
                itask, "retry", "%s, %s" % (self.JOB_FAILED, delay_msg))
            itask.state.reset_state(TASK_STATUS_RETRYING)

    def _process_message_started(self, itask, event_time):
        """Helper for process_message, handle a started message."""
        if itask.job_vacated:
            itask.job_vacated = False
            LOG.warning("Vacated job restarted", itask=itask)
        self.pflag = True
        itask.state.reset_state(TASK_STATUS_RUNNING)
        itask.set_event_time('started', event_time)
        self.suite_db_mgr.put_update_task_jobs(itask, {
            "time_run": itask.summary['started_time_string']})
        if itask.summary['execution_time_limit']:
            execution_timeout = itask.summary['execution_time_limit']
        else:
            execution_timeout = self._get_events_conf(
                itask, 'execution timeout')
        try:
            itask.timeout_timers[TASK_STATUS_RUNNING] = (
                itask.summary['started_time'] + float(execution_timeout))
        except (TypeError, ValueError):
            itask.timeout_timers[TASK_STATUS_RUNNING] = None

        # submission was successful so reset submission try number
        if TASK_STATUS_SUBMIT_RETRYING in itask.try_timers:
            itask.try_timers[TASK_STATUS_SUBMIT_RETRYING].num = 0
        self.setup_event_handlers(itask, 'started', 'job started')
        self.set_poll_time(itask)

    def _process_message_succeeded(self, itask, event_time):
        """Helper for process_message, handle a succeeded message."""
        self.pflag = True
        itask.set_event_time('finished', event_time)
        self.suite_db_mgr.put_update_task_jobs(itask, {
            "run_status": 0,
            "time_run_exit": event_time,
        })
        # Update mean elapsed time only on task succeeded.
        if itask.summary['started_time'] is not None:
            itask.tdef.elapsed_times.append(
                itask.summary['finished_time'] -
                itask.summary['started_time'])
        if not itask.state.outputs.all_completed():
            message = "Succeeded with unreported outputs:"
            for output in itask.state.outputs.get_not_completed():
                message += "\n  " + output
            LOG.info(message, itask=itask)
        itask.state.reset_state(TASK_STATUS_SUCCEEDED)
        self.setup_event_handlers(itask, "succeeded", "job succeeded")

    def _process_message_submit_failed(self, itask, event_time):
        """Helper for process_message, handle a submit-failed message."""
        LOG.error(self.EVENT_SUBMIT_FAILED, itask=itask)
        if event_time is None:
            event_time = get_current_time_string()
        self.suite_db_mgr.put_update_task_jobs(itask, {
            "time_submit_exit": get_current_time_string(),
            "submit_status": 1,
        })
        itask.summary['submit_method_id'] = None
        if (TASK_STATUS_SUBMIT_RETRYING not in itask.try_timers or
                itask.try_timers[TASK_STATUS_SUBMIT_RETRYING].next() is None):
            # No submission retry lined up: definitive failure.
            itask.set_event_time('finished', event_time)
            self.pflag = True
            # See github #476.
            self.setup_event_handlers(
                itask, self.EVENT_SUBMIT_FAILED,
                'job %s' % self.EVENT_SUBMIT_FAILED)
            itask.state.reset_state(TASK_STATUS_SUBMIT_FAILED)
        else:
            # There is a submission retry lined up.
            timer = itask.try_timers[TASK_STATUS_SUBMIT_RETRYING]
            timeout_str = timer.timeout_as_str()
            delay_msg = "submit-retrying in %s" % timer.delay_as_seconds()
            msg = "%s, %s (after %s)" % (
                self.EVENT_SUBMIT_FAILED, delay_msg, timeout_str)
            LOG.info("job(%02d) %s" % (itask.submit_num, msg), itask=itask)
            itask.summary['latest_message'] = msg
            self.setup_event_handlers(
                itask, self.EVENT_SUBMIT_RETRY,
                "job %s, %s" % (self.EVENT_SUBMIT_FAILED, delay_msg))
            itask.state.reset_state(TASK_STATUS_SUBMIT_RETRYING)

    def _process_message_submitted(self, itask, event_time):
        """Helper for process_message, handle a submit-succeeded message."""
        try:
            LOG.info(
                ('job[%(submit_num)02d] submitted to'
                 ' %(host)s:%(batch_sys_name)s[%(submit_method_id)s]') %
                itask.summary,
                itask=itask)
        except KeyError:
            pass
        self.suite_db_mgr.put_update_task_jobs(itask, {
            "time_submit_exit": event_time,
            "submit_status": 0,
            "batch_sys_job_id": itask.summary.get('submit_method_id')})

        if itask.tdef.run_mode == 'simulation':
            # Simulate job execution at this point.
            itask.set_event_time('started', event_time)
            itask.state.reset_state(TASK_STATUS_RUNNING)
            itask.state.outputs.set_completion(TASK_OUTPUT_STARTED, True)
            return

        itask.set_event_time('submitted', event_time)
        itask.set_event_time('started')
        itask.set_event_time('finished')
        itask.summary['latest_message'] = TASK_OUTPUT_SUBMITTED
        self.setup_event_handlers(
            itask, TASK_OUTPUT_SUBMITTED, 'job submitted')

        self.pflag = True
        if itask.state.status == TASK_STATUS_READY:
            # In rare occassions, the submit command of a batch system has sent
            # the job to its server, and the server has started the job before
            # the job submit command returns.
            itask.state.reset_state(TASK_STATUS_SUBMITTED)
            try:
                itask.timeout_timers[TASK_STATUS_SUBMITTED] = (
                    itask.summary['submitted_time'] +
                    float(self._get_events_conf(itask, 'submission timeout')))
            except (TypeError, ValueError):
                itask.timeout_timers[TASK_STATUS_SUBMITTED] = None
            self.set_poll_time(itask)

    def _setup_job_logs_retrieval(self, itask, event):
        """Set up remote job logs retrieval.

        For a task with a job completion event, i.e. succeeded, failed,
        (execution) retry.
        """
        id_key = (
            (self.HANDLER_JOB_LOGS_RETRIEVE, event),
            str(itask.point), itask.tdef.name, itask.submit_num)
        if itask.task_owner:
            user_at_host = itask.task_owner + "@" + itask.task_host
        else:
            user_at_host = itask.task_host
        events = (self.EVENT_FAILED, self.EVENT_RETRY, self.EVENT_SUCCEEDED)
        if (event not in events or
                user_at_host in [get_user() + '@localhost', 'localhost'] or
                not self.get_host_conf(itask, "retrieve job logs") or
                id_key in self.event_timers):
            return
        retry_delays = self.get_host_conf(
            itask, "retrieve job logs retry delays")
        if not retry_delays:
            retry_delays = [0]
        self.event_timers[id_key] = TaskActionTimer(
            TaskJobLogsRetrieveContext(
                self.HANDLER_JOB_LOGS_RETRIEVE,  # key
                self.HANDLER_JOB_LOGS_RETRIEVE,  # ctx_type
                user_at_host,
                self.get_host_conf(itask, "retrieve job logs max size"),
            ),
            retry_delays)

    def _setup_event_mail(self, itask, event):
        """Set up task event notification, by email."""
        id_key = (
            (self.HANDLER_MAIL, event),
            str(itask.point), itask.tdef.name, itask.submit_num)
        if (id_key in self.event_timers or
                event not in self._get_events_conf(itask, "mail events", [])):
            return
        retry_delays = self._get_events_conf(itask, "mail retry delays")
        if not retry_delays:
            retry_delays = [0]
        self.event_timers[id_key] = TaskActionTimer(
            TaskEventMailContext(
                self.HANDLER_MAIL,  # key
                self.HANDLER_MAIL,  # ctx_type
                self._get_events_conf(  # mail_from
                    itask,
                    "mail from",
                    "notifications@" + get_host(),
                ),
                self._get_events_conf(itask, "mail to", get_user()),  # mail_to
                self._get_events_conf(itask, "mail smtp"),  # mail_smtp
            ),
            retry_delays)

    def _setup_custom_event_handlers(self, itask, event, message):
        """Set up custom task event handlers."""
        handlers = self._get_events_conf(itask, event + ' handler')
        if (handlers is None and
                event in self._get_events_conf(itask, 'handler events', [])):
            handlers = self._get_events_conf(itask, 'handlers')
        if handlers is None:
            return
        retry_delays = self._get_events_conf(
            itask,
            'handler retry delays',
            self.get_host_conf(itask, "task event handler retry delays"))
        if not retry_delays:
            retry_delays = [0]
        # There can be multiple custom event handlers
        for i, handler in enumerate(handlers):
            key1 = ("%s-%02d" % (self.HANDLER_CUSTOM, i), event)
            id_key = (
                key1, str(itask.point), itask.tdef.name, itask.submit_num)
            if id_key in self.event_timers:
                continue
            # Custom event handler can be a command template string
            # or a command that takes 4 arguments (classic interface)
            # Note quote() fails on None, need str(None).
            user_at_host = itask.summary['job_hosts'][itask.submit_num]
            if '@' not in user_at_host:
                # (only has 'user@' on the front if user is not suite owner).
                user_at_host = '%s@%s' % (get_user(), user_at_host)
            try:
                handler_data = {
                    "event": quote(event),
                    "suite": quote(self.suite),
                    "point": quote(str(itask.point)),
                    "name": quote(itask.tdef.name),
                    "submit_num": itask.submit_num,
                    "id": quote(itask.identity),
                    "message": quote(message),
                    "batch_sys_name": quote(
                        str(itask.summary['batch_sys_name'])),
                    "batch_sys_job_id": quote(
                        str(itask.summary['submit_method_id'])),
                    "submit_time": quote(
                        str(itask.summary['submitted_time_string'])),
                    "start_time": quote(
                        str(itask.summary['started_time_string'])),
                    "finish_time": quote(
                        str(itask.summary['finished_time_string'])),
                    "user@host": quote(user_at_host)
                }

                if self.suite_cfg:
                    for key, value in self.suite_cfg.items():
                        if key == "URL":
                            handler_data["suite_url"] = quote(value)
                        else:
                            handler_data["suite_" + key] = quote(value)

                if itask.tdef.rtconfig['meta']:
                    for key, value in itask.tdef.rtconfig['meta'].items():
                        if key == "URL":
                            handler_data["task_url"] = quote(value)
                        handler_data[key] = quote(value)

                cmd = handler % (handler_data)
            except KeyError as exc:
                message = "%s/%s/%02d %s bad template: %s" % (
                    itask.point, itask.tdef.name, itask.submit_num, key1, exc)
                LOG.error(message)
                continue

            if cmd == handler:
                # Nothing substituted, assume classic interface
                cmd = "%s '%s' '%s' '%s' '%s'" % (
                    handler, event, self.suite, itask.identity, message)
            LOG.debug("Queueing %s handler: %s" % (event, cmd), itask=itask)
            self.event_timers[id_key] = (
                TaskActionTimer(
                    CustomTaskEventHandlerContext(
                        key1,
                        self.HANDLER_CUSTOM,
                        cmd,
                    ),
                    retry_delays))
