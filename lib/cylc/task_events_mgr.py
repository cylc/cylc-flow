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
"""Task events manager."""

from logging import getLevelName, CRITICAL, ERROR, WARNING, INFO, DEBUG
import os
import re
import shlex
from time import time
import traceback

from cylc.cfgspec.globalcfg import GLOBAL_CFG
import cylc.flags
from cylc.mp_pool import SuiteProcContext
from cylc.suite_logging import ERR, LOG
from cylc.task_message import TaskMessage
from cylc.task_proxy import TaskProxy
from cylc.task_state import (
    TASK_STATUSES_ACTIVE,
    TASK_STATUS_READY, TASK_STATUS_SUBMITTED, TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_RUNNING, TASK_STATUS_FAILED)
from cylc.task_outputs import (
    TASK_OUTPUT_STARTED, TASK_OUTPUT_SUCCEEDED, TASK_OUTPUT_FAILED)
from cylc.wallclock import (
    get_current_time_string,
    get_unix_time_from_time_string,
    RE_DATE_TIME_FORMAT_EXTENDED)


class TaskEventsManager(object):
    """Task events manager."""

    INCOMING_FLAG = ">"
    LOGGING_LVL_OF = {
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
        '\A(.+) at (' + RE_DATE_TIME_FORMAT_EXTENDED + ')\Z')

    def __init__(self, proc_pool):
        self.proc_pool = proc_pool
        self.mail_interval = 0.0
        self.mail_footer = None
        self.next_mail_time = None
        self.event_timers = {}

    def events_from_tasks(self, pool):
        """Get task events from all tasks in pool.

        Strip event timers from tasks to self.event_timers.
        """
        for itask in pool.get_all_tasks():
            while itask.event_handler_try_timers:
                key, timer = itask.event_handler_try_timers.popitem()
                if timer.ctx is not None:
                    key1, submit_num = key
                    id_key = (
                        key1, str(itask.point), itask.tdef.name, submit_num)
                    self.event_timers[id_key] = timer

    def get_task_job_activity_log(
            self, suite, point, name, submit_num=None):
        """Shorthand for get_task_job_log(..., tail="job-activity.log")."""
        return self.get_task_job_log(
            suite, point, name, submit_num, "job-activity.log")

    def get_task_job_log(
            self, suite, point, name, submit_num=None, tail=None):
        """Return the job log path."""
        args = [
            GLOBAL_CFG.get_derived_host_item(suite, "suite job log directory"),
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
        """Process task events."""
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
                timer.ctx.ctx_type == TaskProxy.EVENT_MAIL and
                not schd_ctx.stop_mode and
                self.next_mail_time is not None and
                self.next_mail_time > now
            ):
                continue

            timer.set_waiting()
            if timer.ctx.ctx_type == TaskProxy.CUSTOM_EVENT_HANDLER:
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
            if ctx.ctx_type == TaskProxy.EVENT_MAIL:
                # Set next_mail_time if any mail sent
                self.next_mail_time = next_mail_time
                self._process_event_email(schd_ctx, ctx, id_keys)
            elif ctx.ctx_type == TaskProxy.JOB_LOGS_RETRIEVE:
                self._process_job_logs_retrieval(schd_ctx, ctx, id_keys)

    def process_message(self, itask, priority, message, poll_event_time=None,
                        is_incoming=False):
        """Parse an incoming task message and update task state.

        Incoming is e.g. "succeeded at <TIME>".

        Correctly handle late (out of order) message which would otherwise set
        the state backward in the natural order of events.

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
        itask.log(self.LOGGING_LVL_OF.get(priority, INFO), log_message)

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

        # Failed tasks do not send messages unless declared resurrectable
        if itask.state.status == TASK_STATUS_FAILED:
            if itask.tdef.rtconfig['enable resurrection']:
                itask.log(
                    WARNING,
                    'message received while in the failed state:' +
                    ' I am returning from the dead!')
            else:
                itask.log(
                    WARNING,
                    'message rejected while in the failed state:\n  %s' %
                    message)
                return

        # Check registered outputs.
        if itask.state.outputs.exists(message):
            if not itask.state.outputs.is_completed(message):
                cylc.flags.pflag = True
                itask.state.outputs.set_completed(message)
                itask.db_events_insert(
                    event="output completed", message=message)
            elif not is_polled:
                # This output has already been reported complete. Not an error
                # condition - maybe the network was down for a bit. Ok for
                # polling as multiple polls *should* produce the same result.
                itask.log(WARNING, (
                    "Unexpected output (already completed):\n  %s" % message))

        if is_polled and itask.state.status not in TASK_STATUSES_ACTIVE:
            # A poll result can come in after a task finishes.
            itask.log(WARNING, "Ignoring late poll result: task is not active")
            return

        if priority == TaskMessage.WARNING:
            itask.setup_event_handlers('warning', message, db_update=False)

        if (message == TASK_OUTPUT_STARTED and
                itask.state.status in [
                    TASK_STATUS_READY, TASK_STATUS_SUBMITTED,
                    TASK_STATUS_SUBMIT_FAILED]):
            self._process_message_started(itask, event_time)
        elif (message == TASK_OUTPUT_SUCCEEDED and
                itask.state.status in [
                    TASK_STATUS_READY, TASK_STATUS_SUBMITTED,
                    TASK_STATUS_SUBMIT_FAILED, TASK_STATUS_RUNNING,
                    TASK_STATUS_FAILED]):
            self._process_message_succeeded(itask, event_time, is_polled)
        elif (message == TASK_OUTPUT_FAILED and
                itask.state.status in [
                    TASK_STATUS_READY, TASK_STATUS_SUBMITTED,
                    TASK_STATUS_SUBMIT_FAILED, TASK_STATUS_RUNNING]):
            # (submit- states in case of very fast submission and execution).
            self._process_message_failed(itask, event_time)
        elif message == "submission failed":
            self._process_message_submit_failed(itask, event_time)
        elif message == "submission succeeded":
            self._process_message_submitted(itask, event_time)
        elif message.startswith(TaskMessage.FAIL_MESSAGE_PREFIX):
            # capture and record signals sent to task proxy
            itask.db_events_insert(event="signaled", message=message)
            signal = message.replace(TaskMessage.FAIL_MESSAGE_PREFIX, "")
            itask.db_updates_map[itask.TABLE_TASK_JOBS].append(
                {"run_signal": signal})
        elif message.startswith(TaskMessage.VACATION_MESSAGE_PREFIX):
            cylc.flags.pflag = True
            itask.state.set_state(TASK_STATUS_SUBMITTED)
            itask.db_events_insert(event="vacated", message=message)
            itask.state.execution_timer_timeout = None
            itask.set_event_time('started')
            itask.try_timers[itask.KEY_SUBMIT].num = 0
            itask.job_vacated = True
        else:
            # Unhandled messages. These include:
            #  * general non-output/progress messages
            #  * poll messages that repeat previous results
            # Note that all messages are logged already at the top.
            itask.log(DEBUG, '(current: %s) unhandled: %s' % (
                itask.state.status, message))
            if priority in [CRITICAL, ERROR, WARNING, INFO, DEBUG]:
                priority = getLevelName(priority)
            itask.db_events_insert(
                event=("message %s" % str(priority).lower()), message=message)

    def _custom_handler_callback(self, ctx, schd_ctx, id_key):
        """Callback when a custom event handler is done."""
        _, point, name, submit_num = id_key
        self.log_task_job_activity(
            ctx, schd_ctx.suite, point, name, submit_num)
        if ctx.ret_code == 0:
            del self.event_timers[id_key]
        else:
            self.event_timers[id_key].unset_waiting()

    def _process_event_email(self, schd_ctx, ctx, id_keys):
        """Process event notification, by email."""
        if len(id_keys) == 1:
            # 1 event from 1 task
            (_, event), point, name, submit_num = id_keys[0]
            subject = "[%s/%s/%02d %s] %s" % (
                point, name, submit_num, event, schd_ctx.suite)
        else:
            event_set = set([id_key[0][1] for id_key in id_keys])
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

    def _process_job_logs_retrieval(self, schd_ctx, ctx, id_keys):
        """Process retrieval of task job logs from remote user@host."""
        if ctx.user_at_host and "@" in ctx.user_at_host:
            s_user, s_host = ctx.user_at_host.split("@", 1)
        else:
            s_user, s_host = (None, ctx.user_at_host)
        ssh_str = str(GLOBAL_CFG.get_host_item("ssh command", s_host, s_user))
        rsync_str = str(GLOBAL_CFG.get_host_item(
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
        cmd.append(ctx.user_at_host + ":" + GLOBAL_CFG.get_derived_host_item(
            schd_ctx.suite, "suite job log directory", s_host, s_user) + "/")
        # Local target
        cmd.append(GLOBAL_CFG.get_derived_host_item(
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

    def _process_message_failed(self, itask, event_time):
        """Helper for process_message, handle a failed message."""
        if event_time is None:
            event_time = get_current_time_string()
        itask.set_event_time('finished', event_time)
        itask.db_updates_map[itask.TABLE_TASK_JOBS].append({
            "run_status": 1,
            "time_run_exit": itask.summary['finished_time_string'],
        })
        itask.state.execution_timer_timeout = None
        if itask.try_timers[itask.KEY_EXECUTE].next() is None:
            # No retry lined up: definitive failure.
            # Note the TASK_STATUS_FAILED output is only added if needed.
            cylc.flags.pflag = True
            itask.state.set_execution_failed()
            itask.setup_event_handlers("failed", 'job failed')
        else:
            # There is a retry lined up
            timeout_str = itask.try_timers[itask.KEY_EXECUTE].timeout_as_str()
            delay_msg = "retrying in %s" % (
                itask.try_timers[itask.KEY_EXECUTE].delay_as_seconds())
            msg = "failed, %s (after %s)" % (delay_msg, timeout_str)
            itask.log(INFO, "job(%02d) " % itask.submit_num + msg)
            itask.summary['latest_message'] = msg
            itask.setup_event_handlers(
                "retry", "job failed, " + delay_msg, db_msg=delay_msg)
            itask.state.set_execution_retry()

    def _process_message_started(self, itask, event_time):
        """Helper for process_message, handle a started message."""
        if itask.job_vacated:
            itask.job_vacated = False
            itask.log(WARNING, "Vacated job restarted")
        cylc.flags.pflag = True
        itask.state.set_state(TASK_STATUS_RUNNING)
        itask.set_event_time('started', event_time)
        itask.db_updates_map[itask.TABLE_TASK_JOBS].append({
            "time_run": itask.summary['started_time_string']})
        if itask.summary['execution_time_limit']:
            execution_timeout = itask.summary['execution_time_limit']
        else:
            execution_timeout = itask._get_events_conf('execution timeout')
        try:
            itask.state.execution_timer_timeout = (
                itask.summary['started_time'] + float(execution_timeout))
        except (TypeError, ValueError):
            itask.state.execution_timer_timeout = None

        # submission was successful so reset submission try number
        itask.try_timers[itask.KEY_SUBMIT].num = 0
        itask.setup_event_handlers('started', 'job started')
        itask.set_next_poll_time(itask.KEY_EXECUTE)

    def _process_message_succeeded(self, itask, event_time, is_polled=False):
        """Helper for process_message, handle a succeeded message."""
        itask.state.execution_timer_timeout = None
        cylc.flags.pflag = True
        itask.set_event_time('finished', event_time)
        itask.db_updates_map[itask.TABLE_TASK_JOBS].append({
            "run_status": 0,
            "time_run_exit": itask.summary['finished_time_string'],
        })
        # Update mean elapsed time only on task succeeded.
        if itask.summary['started_time'] is not None:
            itask.tdef.elapsed_times.append(
                itask.summary['finished_time'] -
                itask.summary['started_time'])
        itask.setup_event_handlers("succeeded", "job succeeded")
        warnings = itask.state.set_execution_succeeded(is_polled)
        for warning in warnings:
            itask.log(WARNING, warning)

    def _process_message_submit_failed(self, itask, event_time):
        """Helper for process_message, handle a submit-failed message."""
        itask.state.submission_timer_timeout = None
        itask.log(ERROR, 'submission failed')
        if event_time is None:
            event_time = get_current_time_string()
        itask.db_updates_map[itask.TABLE_TASK_JOBS].append({
            "time_submit_exit": get_current_time_string(),
            "submit_status": 1,
        })
        try:
            del itask.summary['submit_method_id']
        except KeyError:
            pass
        if itask.try_timers[itask.KEY_SUBMIT].next() is None:
            # No submission retry lined up: definitive failure.
            itask.set_event_time('finished', event_time)
            cylc.flags.pflag = True
            # See github #476.
            itask.setup_event_handlers(
                'submission failed', 'job submission failed')
            itask.state.set_submit_failed()
        else:
            # There is a submission retry lined up.
            timeout_str = itask.try_timers[itask.KEY_SUBMIT].timeout_as_str()

            delay_msg = "submit-retrying in %s" % (
                itask.try_timers[itask.KEY_SUBMIT].delay_as_seconds())
            msg = "submission failed, %s (after %s)" % (delay_msg, timeout_str)
            itask.log(INFO, "job(%02d) " % itask.submit_num + msg)
            itask.summary['latest_message'] = msg
            itask.db_events_insert(
                event="submission failed", message=delay_msg)
            # TODO - is this insert redundant with setup_event_handlers?
            itask.db_events_insert(
                event="submission failed",
                message="submit-retrying in " + str(
                    itask.try_timers[itask.KEY_SUBMIT].delay))
            itask.setup_event_handlers(
                "submission retry", "job submission failed, " + delay_msg)
            itask.state.set_submit_retry()

    def _process_message_submitted(self, itask, event_time):
        """Helper for process_message, handle a submit-succeeded message."""
        if itask.summary.get('submit_method_id') is not None:
            itask.log(
                INFO, 'submit_method_id=' + itask.summary['submit_method_id'])
        itask.db_updates_map[itask.TABLE_TASK_JOBS].append({
            "time_submit_exit": get_unix_time_from_time_string(event_time),
            "submit_status": 0,
            "batch_sys_job_id": itask.summary.get('submit_method_id')})

        if itask.tdef.run_mode == 'simulation':
            # Simulate job execution at this point.
            itask.set_event_time('started', event_time)
            itask.state.set_state(TASK_STATUS_RUNNING)
            itask.state.outputs.set_completed(TASK_OUTPUT_STARTED)
            return

        itask.set_event_time('submitted', event_time)
        itask.set_event_time('started')
        itask.set_event_time('finished')
        itask.summary['latest_message'] = TASK_STATUS_SUBMITTED
        itask.setup_event_handlers(
            "submitted", 'job submitted', db_event='submission succeeded')

        if itask.state.set_submit_succeeded():
            try:
                itask.state.submission_timer_timeout = (
                    itask.summary['submitted_time'] +
                    float(itask._get_events_conf('submission timeout')))
            except (TypeError, ValueError):
                itask.state.submission_timer_timeout = None
            itask.set_next_poll_time(itask.KEY_SUBMIT)
