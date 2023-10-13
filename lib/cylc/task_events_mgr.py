#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
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
* Manage task messages (internal, polled or received).
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
import shlex
from time import time

from parsec.config import ItemNotFoundError

from cylc import LOG
from cylc.cfgspec.glbl_cfg import glbl_cfg
from cylc.hostuserutil import get_host, get_user
from cylc.subprocctx import SubProcContext
from cylc.task_action_timer import TaskActionTimer
from cylc.task_job_logs import (
    get_task_job_log, get_task_job_activity_log, JOB_LOG_OUT, JOB_LOG_ERR)
from cylc.task_message import (
    ABORT_MESSAGE_PREFIX, FAIL_MESSAGE_PREFIX, VACATION_MESSAGE_PREFIX)
from cylc.task_state import (
    TASK_STATUSES_ACTIVE, TASK_STATUS_HELD,
    TASK_STATUS_READY, TASK_STATUS_SUBMITTED, TASK_STATUS_SUBMIT_RETRYING,
    TASK_STATUS_SUBMIT_FAILED, TASK_STATUS_RUNNING, TASK_STATUS_RETRYING,
    TASK_STATUS_FAILED, TASK_STATUS_SUCCEEDED)
from cylc.task_outputs import (
    TASK_OUTPUT_SUBMITTED, TASK_OUTPUT_STARTED, TASK_OUTPUT_SUCCEEDED,
    TASK_OUTPUT_FAILED, TASK_OUTPUT_SUBMIT_FAILED, TASK_OUTPUT_EXPIRED)
from cylc.wallclock import (
    get_current_time_string, get_seconds_as_interval_string as intvl_as_str)

CustomTaskEventHandlerContext = namedtuple(
    "CustomTaskEventHandlerContext",
    ["key", "ctx_type", "cmd"])


TaskEventMailContext = namedtuple(
    "TaskEventMailContext",
    ["key", "ctx_type", "mail_from", "mail_to", "mail_smtp"])


TaskJobLogsRetrieveContext = namedtuple(
    "TaskJobLogsRetrieveContext",
    ["key", "ctx_type", "user_at_host", "max_size"])


def log_task_job_activity(ctx, suite, point, name, submit_num=None):
    """Log an activity for a task job."""
    ctx_str = str(ctx)
    if not ctx_str:
        return
    if isinstance(ctx.cmd_key, tuple):  # An event handler
        submit_num = ctx.cmd_key[-1]
    job_activity_log = get_task_job_activity_log(
        suite, point, name, submit_num)
    try:
        with open(job_activity_log, "ab") as handle:
            handle.write(ctx_str + '\n')
    except IOError as exc:
        # This happens when there is no job directory, e.g. if job host
        # selection command causes an submission failure, there will be no job
        # directory. In this case, just send the information to the suite log.
        LOG.exception(exc)
        LOG.info(ctx_str)
    if ctx.cmd and ctx.ret_code:
        LOG.error(ctx_str)
    elif ctx.cmd:
        LOG.debug(ctx_str)


class TaskEventsManager(object):
    """Task events manager.

    This class does the following:
    * Manage task messages (received or otherwise).
    * Set up task (submission) retries on job (submission) failures.
    * Generate and manage task event handlers.
    """
    EVENT_FAILED = TASK_OUTPUT_FAILED
    EVENT_LATE = "late"
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
    FLAG_INTERNAL = "(internal)"
    FLAG_RECEIVED = "(received)"
    FLAG_RECEIVED_IGNORED = "(received-ignored)"
    FLAG_POLLED = "(polled)"
    KEY_EXECUTE_TIME_LIMIT = 'execution_time_limit'
    LEVELS = {
        "INFO": INFO,
        "NORMAL": INFO,
        "WARNING": WARNING,
        "ERROR": ERROR,
        "CRITICAL": CRITICAL,
        "DEBUG": DEBUG,
    }
    NON_UNIQUE_EVENTS = ('warning', 'critical', 'custom')

    def __init__(self, suite, proc_pool, suite_db_mgr, broadcast_mgr):
        self.suite = suite
        self.suite_url = None
        self.suite_cfg = {}
        self.uuid_str = None
        self.proc_pool = proc_pool
        self.suite_db_mgr = suite_db_mgr
        self.broadcast_mgr = broadcast_mgr
        self.mail_interval = 0.0
        self.mail_footer = None
        self.next_mail_time = None
        # NOTE: do not mutate directly
        # use {add,remove,unset_waiting}_event_timers methods
        self._event_timers = {}
        # NOTE: flag for DB use
        self.event_timers_updated = True
        # Set pflag = True to stimulate task dependency negotiation whenever a
        # task changes state in such a way that others could be affected. The
        # flag should only be turned off again after use in
        # Scheduler.process_tasks, to ensure that dependency negotiation occurs
        # when required.
        self.pflag = False

    @staticmethod
    def check_poll_time(itask, now=None):
        """Set the next task execution/submission poll time.

        If now is set, set the timer only if the previous delay is done.
        Return the next delay.
        """
        if itask.state.status not in TASK_STATUSES_ACTIVE:
            # Reset, task not active
            itask.timeout = None
            itask.poll_timer = None
            return None
        ctx = (itask.submit_num, itask.state.status)
        if itask.poll_timer is None or itask.poll_timer.ctx != ctx:
            # Reset, timer no longer relevant
            itask.timeout = None
            itask.poll_timer = None
            return None
        if now is not None and not itask.poll_timer.is_delay_done(now):
            return False
        if itask.poll_timer.num is None:
            itask.poll_timer.num = 0
        itask.poll_timer.next(no_exhaust=True)
        return True

    def check_job_time(self, itask, now):
        """Check/handle job timeout and poll timer"""
        can_poll = self.check_poll_time(itask, now)
        if itask.timeout is None or now <= itask.timeout:
            return can_poll
        # Timeout reached for task, emit event and reset itask.timeout
        if itask.state.status == TASK_STATUS_RUNNING:
            time_ref = itask.summary['started_time']
            event = 'execution timeout'
        elif itask.state.status == TASK_STATUS_SUBMITTED:
            time_ref = itask.summary['submitted_time']
            event = 'submission timeout'
        msg = event
        try:
            msg += ' after %s' % intvl_as_str(itask.timeout - time_ref)
        except (TypeError, ValueError):
            # Badness in time_ref?
            pass
        itask.timeout = None  # emit event only once
        if msg and event:
            LOG.warning('[%s] -%s', itask, msg)
            self.setup_event_handlers(itask, event, msg)
            return True
        else:
            return can_poll

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

    def process_events(self, schd_ctx):
        """Process task events that were created by "setup_event_handlers".

        schd_ctx is an instance of "Scheduler" in "cylc.scheduler".
        """
        ctx_groups = {}
        now = time()
        for id_key, timer in self._event_timers.copy().items():
            key1, point, name, submit_num = id_key
            if timer.is_waiting:
                continue
            # Set timer if timeout is None.
            if not timer.is_timeout_set():
                if timer.next() is None:
                    LOG.warning("%s/%s/%02d %s failed" % (
                        point, name, submit_num, key1))
                    self.remove_event_timer(id_key)
                    continue
                # Report retries and delayed 1st try
                tmpl = None
                if timer.num > 1:
                    tmpl = "%s/%s/%02d %s failed, retrying in %s"
                elif timer.delay:
                    tmpl = "%s/%s/%02d %s will run after %s"
                if tmpl:
                    LOG.debug(tmpl % (
                        point, name, submit_num, key1,
                        timer.delay_timeout_as_str()))
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
                    SubProcContext(
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

    def process_message(
        self,
        itask,
        severity,
        message,
        event_time=None,
        flag=FLAG_INTERNAL,
        submit_num=None,
    ):
        """Parse an task message and update task state.

        Incoming, e.g. "succeeded at <TIME>", may be from task job or polling.

        It is possible for the current state of a task to be inconsistent with
        a message (whether internal, received or polled) e.g. due to a late
        poll result, or a network outage, or manual state reset. To handle
        this, if a message would take the task state backward, issue a poll to
        confirm instead of changing state - then always believe the next
        message. Note that the next message might not be the result of this
        confirmation poll, in the unlikely event that a job emits a succession
        of messages very quickly, but this is the best we can do without
        somehow uniquely associating each poll with its result message.

        Arguments:
            itask (cylc.task_proxy.TaskProxy):
                The task proxy object relevant for the message.
            severity (str or int):
                Message severity, should be a recognised logging level.
            message (str):
                Message content.
            event_time (str):
                Event time stamp. Expect ISO8601 date time string.
                If not specified, use current time.
            flag (str):
                If specified, can be:
                    FLAG_INTERNAL (default):
                        To indicate an internal message.
                    FLAG_RECEIVED:
                        To indicate a message received from a job or an
                        external source.
                    FLAG_POLLED:
                        To indicate a message resulted from a poll.
            submit_num (int):
                The submit number of the task relevant for the message.
                If not specified, use latest submit number.

        Return:
            None: in normal circumstances.
            True: if polling is required to confirm a reversal of status.

        """
        # Log messages
        if event_time is None:
            event_time = get_current_time_string()
        if submit_num is None:
            submit_num = itask.submit_num
        logfmt = r'[%s] status=%s: %s%s at %s for job(%02d)'
        if flag == self.FLAG_RECEIVED and submit_num != itask.submit_num:
            LOG.warning(
                logfmt + r' != current job(%02d)',
                itask, itask.state, self.FLAG_RECEIVED_IGNORED, message,
                event_time, submit_num, itask.submit_num)
            return
        LOG.log(
            self.LEVELS.get(severity, INFO),
            logfmt, itask, itask.state, flag, message, event_time, submit_num)

        # always update the suite state summary for latest message
        if flag == self.FLAG_POLLED:
            itask.set_summary_message('%s %s' % (message, self.FLAG_POLLED))
        else:
            itask.set_summary_message(message)

        # Satisfy my output, if possible, and record the result.
        completed_trigger = itask.state.outputs.set_msg_trg_completion(
            message=message, is_completed=True)

        if message == TASK_OUTPUT_STARTED:
            if (flag == self.FLAG_RECEIVED
                    and itask.state.is_gt(TASK_STATUS_RUNNING)):
                return True
            self._process_message_started(itask, event_time)
        elif message == TASK_OUTPUT_SUCCEEDED:
            self._process_message_succeeded(itask, event_time)
        elif message == TASK_OUTPUT_FAILED:
            if (flag == self.FLAG_RECEIVED
                    and itask.state.is_gt(TASK_STATUS_FAILED)):
                return True
            self._process_message_failed(itask, event_time, self.JOB_FAILED)
        elif message == self.EVENT_SUBMIT_FAILED:
            if (flag == self.FLAG_RECEIVED
                    and itask.state.is_gt(TASK_STATUS_SUBMIT_FAILED)):
                return True
            self._process_message_submit_failed(itask, event_time)
        elif message == TASK_OUTPUT_SUBMITTED:
            if (flag == self.FLAG_RECEIVED
                    and itask.state.is_gt(TASK_STATUS_SUBMITTED)):
                return True
            self._process_message_submitted(itask, event_time)
        elif message.startswith(FAIL_MESSAGE_PREFIX):
            # Task received signal.
            if (flag == self.FLAG_RECEIVED
                    and itask.state.is_gt(TASK_STATUS_FAILED)):
                return True
            signal = message[len(FAIL_MESSAGE_PREFIX):]
            self._db_events_insert(itask, "signaled", signal)
            self.suite_db_mgr.put_update_task_jobs(
                itask, {"run_signal": signal})
            self._process_message_failed(itask, event_time, self.JOB_FAILED)
        elif message.startswith(ABORT_MESSAGE_PREFIX):
            # Task aborted with message
            if (flag == self.FLAG_RECEIVED
                    and itask.state.is_gt(TASK_STATUS_FAILED)):
                return True
            aborted_with = message[len(ABORT_MESSAGE_PREFIX):]
            self._db_events_insert(itask, "aborted", message)
            self.suite_db_mgr.put_update_task_jobs(
                itask, {"run_signal": aborted_with})
            self._process_message_failed(itask, event_time, aborted_with)
        elif message.startswith(VACATION_MESSAGE_PREFIX):
            # Task job pre-empted into a vacation state
            self._db_events_insert(itask, "vacated", message)
            itask.set_summary_time('started')  # unset
            if TASK_STATUS_SUBMIT_RETRYING in itask.try_timers:
                itask.try_timers[TASK_STATUS_SUBMIT_RETRYING].num = 0
            itask.job_vacated = True
            # Believe this and change state without polling (could poll?).
            self.pflag = True
            itask.state.reset_state(TASK_STATUS_SUBMITTED)
            self._reset_job_timers(itask)
            # We should really have a special 'vacated' handler, but given that
            # this feature can only be used on the deprecated loadleveler
            # system, we should probably aim to remove support for job vacation
            # instead. Otherwise, we should have:
            # self.setup_event_handlers(itask, 'vacated', message)
        elif completed_trigger:
            # Message of an as-yet unreported custom task output.
            # No state change.
            self.pflag = True
            self.suite_db_mgr.put_update_task_outputs(itask)
            self.setup_event_handlers(itask, completed_trigger, message)
        else:
            # Unhandled messages. These include:
            #  * general non-output/progress messages
            #  * poll messages that repeat previous results
            # Note that all messages are logged already at the top.
            # No state change.
            LOG.debug(
                '[%s] status=%s: unhandled: %s',
                itask, itask.state.status, message)
            if severity in [CRITICAL, ERROR, WARNING, INFO, DEBUG]:
                severity = getLevelName(severity)
            self._db_events_insert(
                itask, ("message %s" % str(severity).lower()), message)
        lseverity = str(severity).lower()
        if lseverity in self.NON_UNIQUE_EVENTS:
            itask.non_unique_events.setdefault(lseverity, 0)
            itask.non_unique_events[lseverity] += 1
            self.setup_event_handlers(itask, lseverity, message)

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

    def _custom_handler_callback(self, ctx, schd_ctx, id_key):
        """Callback when a custom event handler is done."""
        _, point, name, submit_num = id_key
        log_task_job_activity(ctx, schd_ctx.suite, point, name, submit_num)
        if ctx.ret_code == 0:
            self.remove_event_timer(id_key)
        else:
            self.unset_waiting_event_timer(id_key)

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
            SubProcContext(
                ctx, cmd, env=env, stdin_str=stdin_str, id_keys=id_keys,
            ),
            self._event_email_callback, [schd_ctx])

    def _event_email_callback(self, proc_ctx, schd_ctx):
        """Call back when email notification command exits."""
        for id_key in proc_ctx.cmd_kwargs["id_keys"]:
            key1, point, name, submit_num = id_key
            try:
                if proc_ctx.ret_code == 0:
                    self.remove_event_timer(id_key)
                    log_ctx = SubProcContext((key1, submit_num), None)
                    log_ctx.ret_code = 0
                    log_task_job_activity(
                        log_ctx, schd_ctx.suite, point, name, submit_num)
                else:
                    self.unset_waiting_event_timer(id_key)
            except KeyError as exc:
                LOG.exception(exc)

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
        if LOG.isEnabledFor(DEBUG):
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
        remote_source = (ctx.user_at_host +
                         ":" +
                         glbl_cfg().get_derived_host_item(
                             schd_ctx.suite, "suite job log directory",
                             s_host, s_user
                         ) +
                         "/").replace("$HOME/", "")
        cmd.append(remote_source)
        # Local target
        cmd.append(glbl_cfg().get_derived_host_item(
            schd_ctx.suite, "suite job log directory") + "/")
        self.proc_pool.put_command(
            SubProcContext(ctx, cmd, env=dict(os.environ), id_keys=id_keys),
            self._job_logs_retrieval_callback, [schd_ctx])

    def _job_logs_retrieval_callback(self, proc_ctx, schd_ctx):
        """Call back when log job retrieval completes."""
        if proc_ctx.ret_code:
            LOG.error(proc_ctx)
        else:
            LOG.debug(proc_ctx)
        for id_key in proc_ctx.cmd_kwargs["id_keys"]:
            key1, point, name, submit_num = id_key
            try:
                # All completed jobs are expected to have a "job.out".
                fnames = [JOB_LOG_OUT]
                try:
                    if key1[1] not in 'succeeded':
                        fnames.append(JOB_LOG_ERR)
                except TypeError:
                    pass
                fname_oks = {}
                for fname in fnames:
                    fname_oks[fname] = os.path.exists(get_task_job_log(
                        schd_ctx.suite, point, name, submit_num, fname))
                # All expected paths must exist to record a good attempt
                log_ctx = SubProcContext((key1, submit_num), None)
                if all(fname_oks.values()):
                    log_ctx.ret_code = 0
                    self.remove_event_timer(id_key)
                else:
                    log_ctx.ret_code = 1
                    log_ctx.err = "File(s) not retrieved:"
                    for fname, exist_ok in sorted(fname_oks.items()):
                        if not exist_ok:
                            log_ctx.err += " %s" % fname
                    self.unset_waiting_event_timer(id_key)
                log_task_job_activity(
                    log_ctx, schd_ctx.suite, point, name, submit_num)
            except KeyError as exc:
                LOG.exception(exc)

    def _process_message_failed(self, itask, event_time, message):
        """Helper for process_message, handle a failed message."""
        if event_time is None:
            event_time = get_current_time_string()
        itask.set_summary_time('finished', event_time)
        self.suite_db_mgr.put_update_task_jobs(itask, {
            "run_status": 1,
            "time_run_exit": event_time,
        })
        if (TASK_STATUS_RETRYING not in itask.try_timers or
                itask.try_timers[TASK_STATUS_RETRYING].next() is None):
            # No retry lined up: definitive failure.
            self.pflag = True
            if itask.state.reset_state(TASK_STATUS_FAILED):
                self.setup_event_handlers(itask, "failed", message)
            LOG.critical(
                "[%s] -job(%02d) %s", itask, itask.submit_num, "failed")
        elif itask.state.reset_state(
            TASK_STATUS_RETRYING,
            respect_hold_swap=True,
        ):
            delay_msg = "retrying in %s" % (
                itask.try_timers[TASK_STATUS_RETRYING].delay_timeout_as_str())
            if itask.state.status == TASK_STATUS_HELD:
                delay_msg = "%s (%s)" % (TASK_STATUS_HELD, delay_msg)
            msg = "failed, %s" % (delay_msg)
            LOG.info("[%s] -job(%02d) %s", itask, itask.submit_num, msg)
            itask.set_summary_message(msg)
            self.setup_event_handlers(
                itask, "retry", "%s, %s" % (self.JOB_FAILED, delay_msg))
        self._reset_job_timers(itask)

    def _process_message_started(self, itask, event_time):
        """Helper for process_message, handle a started message."""
        if itask.job_vacated:
            itask.job_vacated = False
            LOG.warning("[%s] -Vacated job restarted", itask)
        self.pflag = True
        if itask.state.reset_state(TASK_STATUS_RUNNING):
            self.setup_event_handlers(itask, 'started', 'job started')
        itask.set_summary_time('started', event_time)
        self._reset_job_timers(itask)
        self.suite_db_mgr.put_update_task_jobs(itask, {
            "time_run": itask.summary['started_time_string']})

        # submission was successful so reset submission try number
        if TASK_STATUS_SUBMIT_RETRYING in itask.try_timers:
            itask.try_timers[TASK_STATUS_SUBMIT_RETRYING].num = 0

    def _process_message_succeeded(self, itask, event_time):
        """Helper for process_message, handle a succeeded message."""
        self.pflag = True
        itask.set_summary_time('finished', event_time)
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
            msg = ""
            for output in itask.state.outputs.get_not_completed():
                if output not in [TASK_OUTPUT_EXPIRED,
                                  TASK_OUTPUT_SUBMIT_FAILED,
                                  TASK_OUTPUT_FAILED]:
                    msg += "\n  " + output
            if msg:
                LOG.info(
                    "[%s] -Succeeded with outputs not completed: %s",
                    itask, msg)
        if itask.state.reset_state(TASK_STATUS_SUCCEEDED):
            self.setup_event_handlers(itask, "succeeded", "job succeeded")
        self._reset_job_timers(itask)

    def _process_message_submit_failed(self, itask, event_time):
        """Helper for process_message, handle a submit-failed message."""
        LOG.error('[%s] -%s', itask, self.EVENT_SUBMIT_FAILED)
        if event_time is None:
            event_time = get_current_time_string()
        self.suite_db_mgr.put_update_task_jobs(itask, {
            "time_submit_exit": event_time,
            "submit_status": 1,
        })
        itask.summary['submit_method_id'] = None
        if (TASK_STATUS_SUBMIT_RETRYING not in itask.try_timers or
                itask.try_timers[TASK_STATUS_SUBMIT_RETRYING].next() is None):
            # No submission retry lined up: definitive failure.
            self.pflag = True
            # See github #476.
            if itask.state.reset_state(TASK_STATUS_SUBMIT_FAILED):
                self.setup_event_handlers(
                    itask, self.EVENT_SUBMIT_FAILED,
                    'job %s' % self.EVENT_SUBMIT_FAILED)
        elif itask.state.reset_state(
            TASK_STATUS_SUBMIT_RETRYING,
            respect_hold_swap=True,
        ):
            # There is a submission retry lined up.
            timer = itask.try_timers[TASK_STATUS_SUBMIT_RETRYING]
            delay_msg = "submit-retrying in %s" % timer.delay_timeout_as_str()
            if itask.state.status == TASK_STATUS_HELD:
                delay_msg = "%s (%s)" % (TASK_STATUS_HELD, delay_msg)
            msg = "%s, %s" % (self.EVENT_SUBMIT_FAILED, delay_msg)
            LOG.info("[%s] -job(%02d) %s", itask, itask.submit_num, msg)
            itask.set_summary_message(msg)
            self.setup_event_handlers(
                itask, self.EVENT_SUBMIT_RETRY,
                "job %s, %s" % (self.EVENT_SUBMIT_FAILED, delay_msg))
        self._reset_job_timers(itask)

    def _process_message_submitted(self, itask, event_time):
        """Helper for process_message, handle a submit-succeeded message."""
        try:
            LOG.info(
                '[%s] -job[%02d] submitted to %s:%s[%s]',
                itask,
                itask.summary['submit_num'],
                itask.summary['host'],
                itask.summary['batch_sys_name'],
                itask.summary['submit_method_id'])
        except KeyError:
            pass
        self.suite_db_mgr.put_update_task_jobs(itask, {
            "time_submit_exit": event_time,
            "submit_status": 0,
            "batch_sys_job_id": itask.summary.get('submit_method_id')})

        if itask.tdef.run_mode == 'simulation':
            # Simulate job execution at this point.
            itask.set_summary_time('submitted', event_time)
            itask.set_summary_time('started', event_time)
            itask.state.reset_state(TASK_STATUS_RUNNING)
            itask.state.outputs.set_completion(TASK_OUTPUT_STARTED, True)
            return

        itask.set_summary_time('submitted', event_time)
        # Unset started and finished times in case of resubmission.
        itask.set_summary_time('started')
        itask.set_summary_time('finished')
        itask.set_summary_message(TASK_OUTPUT_SUBMITTED)

        self.pflag = True
        if itask.state.status == TASK_STATUS_READY:
            # The job started message can (rarely) come in before the submit
            # command returns - in which case do not go back to 'submitted'.
            if itask.state.reset_state(TASK_STATUS_SUBMITTED):
                self.setup_event_handlers(
                    itask, TASK_OUTPUT_SUBMITTED, 'job submitted')
            self._reset_job_timers(itask)

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
                id_key in self._event_timers):
            return
        retry_delays = self.get_host_conf(
            itask, "retrieve job logs retry delays")
        if not retry_delays:
            retry_delays = [0]
        self.add_event_timer(
            id_key,
            TaskActionTimer(
                TaskJobLogsRetrieveContext(
                    self.HANDLER_JOB_LOGS_RETRIEVE,  # key
                    self.HANDLER_JOB_LOGS_RETRIEVE,  # ctx_type
                    user_at_host,
                    self.get_host_conf(itask, "retrieve job logs max size"),
                ),
                retry_delays
            )
        )

    def _setup_event_mail(self, itask, event):
        """Set up task event notification, by email."""
        if event in self.NON_UNIQUE_EVENTS:
            key1 = (
                self.HANDLER_MAIL,
                '%s-%d' % (event, itask.non_unique_events.get(event, 1)))
        else:
            key1 = (self.HANDLER_MAIL, event)
        id_key = (key1, str(itask.point), itask.tdef.name, itask.submit_num)
        if (id_key in self._event_timers or
                event not in self._get_events_conf(itask, "mail events", [])):
            return
        retry_delays = self._get_events_conf(itask, "mail retry delays")
        if not retry_delays:
            retry_delays = [0]
        self._event_timers[id_key] = TaskActionTimer(
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
            if event in self.NON_UNIQUE_EVENTS:
                key1 = (
                    '%s-%02d' % (self.HANDLER_CUSTOM, i),
                    '%s-%d' % (event, itask.non_unique_events.get(event, 1)))
            else:
                key1 = ('%s-%02d' % (self.HANDLER_CUSTOM, i), event)
            id_key = (
                key1, str(itask.point), itask.tdef.name, itask.submit_num)
            if id_key in self._event_timers:
                continue
            # Note: user@host may not always be set for a submit number, e.g.
            # on late event or if host select command fails. Use null string to
            # prevent issues in this case.
            user_at_host = itask.summary['job_hosts'].get(itask.submit_num, '')
            if user_at_host and '@' not in user_at_host:
                # (only has 'user@' on the front if user is not suite owner).
                user_at_host = '%s@%s' % (get_user(), user_at_host)
            # Custom event handler can be a command template string
            # or a command that takes 4 arguments (classic interface)
            # Note quote() fails on None, need str(None).
            try:
                handler_data = {
                    "event": quote(event),
                    "suite": quote(self.suite),
                    'suite_uuid': quote(str(self.uuid_str)),
                    "point": quote(str(itask.point)),
                    "name": quote(itask.tdef.name),
                    "submit_num": itask.submit_num,
                    "try_num": itask.get_try_num(),
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
            LOG.debug("[%s] -Queueing %s handler: %s", itask, event, cmd)
            self._event_timers[id_key] = (
                TaskActionTimer(
                    CustomTaskEventHandlerContext(
                        key1,
                        self.HANDLER_CUSTOM,
                        cmd,
                    ),
                    retry_delays))

    def add_event_timer(self, key, timer):
        """Add a new event timer.

        Args:
            key (str)
            timer (TaskActionTimer)

        """
        self._event_timers[key] = timer
        self.event_timers_updated = True

    def remove_event_timer(self, key):
        """Remove a new event timer.

        Args:
            key (str)

        """
        del self._event_timers[key]
        self.event_timers_updated = True

    def unset_waiting_event_timer(self, key):
        """Invoke unset_waiting on an event timer.

        Args:
            key (str)

        """
        self._event_timers[key].unset_waiting()
        self.event_timers_updated = True

    def _reset_job_timers(self, itask):
        """Set up poll timer and timeout for task."""
        if itask.state.status not in TASK_STATUSES_ACTIVE:
            # Reset, task not active
            itask.timeout = None
            itask.poll_timer = None
            return
        ctx = (itask.submit_num, itask.state.status)
        if itask.poll_timer and itask.poll_timer.ctx == ctx:
            return
        # Set poll timer
        # Set timeout
        timeref = None  # reference time, submitted or started time
        timeout = None  # timeout in setting
        if itask.state.status == TASK_STATUS_RUNNING:
            timeref = itask.summary['started_time']
            timeout_key = 'execution timeout'
            timeout = self._get_events_conf(itask, timeout_key)
            # delays - All polling times after start
            # timeout - Total time limit including all polling:
            delays = list(self.get_host_conf(
                itask, 'execution polling intervals', skey='job',
                default=[900]))  # Default 15 minute intervals
            if itask.summary[self.KEY_EXECUTE_TIME_LIMIT]:
                time_limit = itask.summary[self.KEY_EXECUTE_TIME_LIMIT]

                # Get execution time limit polling intervals or set to default:
                try:
                    host_conf = self.get_host_conf(itask, 'batch systems')
                    batch_sys_conf = host_conf[itask.summary['batch_sys_name']]
                except (TypeError, KeyError):
                    batch_sys_conf = {}
                time_limit_delays = batch_sys_conf.get(
                    'execution time limit polling intervals', [60, 120, 420])

                # Total timeout after adding execution time limit polling
                # intervals:
                timeout = (time_limit + sum(time_limit_delays))

                delays = self.process_execution_polling_delays(
                    delays, time_limit, time_limit_delays
                )

        else:  # if itask.state.status == TASK_STATUS_SUBMITTED:
            timeref = itask.summary['submitted_time']
            timeout_key = 'submission timeout'
            timeout = self._get_events_conf(itask, timeout_key)
            delays = list(self.get_host_conf(
                itask, 'submission polling intervals', skey='job',
                default=[900]))  # Default 15 minute intervals
        try:
            itask.timeout = timeref + float(timeout)
            time_limit_str = intvl_as_str(time_limit)
        except (TypeError, ValueError):
            itask.timeout = None
            time_limit_str = None

        itask.poll_timer = TaskActionTimer(ctx=ctx, delays=delays)

        # Log timeout and polling schedule
        message = 'health check settings: %s=%s' % (
            timeout_key, time_limit_str)
        # Attempt to group identical consecutive delays as N*DELAY,...
        if itask.poll_timer.delays:
            items = []  # [(number of item - 1, item), ...]
            for delay in itask.poll_timer.delays:
                if items and items[-1][1] == delay:
                    items[-1][0] += 1
                else:
                    items.append([0, delay])
            message += ', polling intervals='
            for num, item in items:
                if num:
                    message += '%d*' % (num + 1)
                message += '%s,' % intvl_as_str(item)
            message += '...'
        LOG.info('[%s] -%s', itask, message)
        # Set next poll time
        self.check_poll_time(itask)

    @staticmethod
    def process_execution_polling_delays(
        delays, time_limit, time_limit_delays
    ):
        """Create list of intervals after starting at which to poll a task.

        Args:
            delays: Input is Execution Polling intervals.
            time_limit_delays: Execution Time Limit Polling Intervals.
            time_limit: Execution Time Limit.

        Returns: List of delays from start of task.

        Examples:

            >>> this = TaskEventsManager.process_execution_polling_delays

            # Basic example:
            >>> this([40, 35], 100, [10])
            [40, 35, 35, 10]

            # Second 40 second delay gets lopped off the list because it's
            # after the execution time limit:
            >>> this([40, 40], 60, [10])
            [40, 30, 10]

            # Expand last item in exection polling intervals to fill the
            # execution time limit:
            >>> this([5, 20], 100, [10])
            [5, 20, 20, 20, 20, 25, 10]

            # There are no execution polling intervals set - polling starts
            # at execution time limit:
            >>> this([], 10, [5])
            [15, 5]

            # We have a list of execution time limit polling intervals,
            >>> this([10], 25, [5, 6, 7, 8])
            [10, 10, 10, 6, 7, 8]
        """
        if sum(delays) > time_limit:
            # Remove excessive polling before time limit
            while sum(delays) > time_limit:
                del delays[-1]
        elif delays:
            # But fill up the gap before time limit
            size = int((time_limit - sum(delays)) / delays[-1])
            delays.extend([delays[-1]] * size)

        # After the last delay before the execution time limit add the
        # delay to get to the execution_time_limit
        if len(time_limit_delays) > 1:
            time_limit_delays[0] += time_limit - sum(delays)
        else:
            delays.append(
                time_limit_delays[0] + time_limit - sum(delays))

        delays += time_limit_delays
        return delays
