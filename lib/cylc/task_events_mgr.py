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

import os
import shlex
from time import time
import traceback

from cylc.cfgspec.globalcfg import GLOBAL_CFG
import cylc.flags
from cylc.mp_pool import SuiteProcContext
from cylc.suite_logging import ERR, LOG
from cylc.task_proxy import TaskProxy
from cylc.task_state import TASK_STATUS_SUCCEEDED


class TaskEventsManager(object):
    """Task events manager."""

    def __init__(self, proc_pool, mail_interval, mail_footer):
        self.proc_pool = proc_pool
        self.mail_interval = mail_interval
        self.mail_footer = mail_footer
        self.next_mail_time = None
        self.event_timers = {}

    def add_event_timers(self, itasks):
        """Add event timers by removing them from itasks."""
        for itask in itasks:
            while itask.event_handler_try_timers:
                key, timer = itask.event_handler_try_timers.popitem()
                if timer.ctx is not None:
                    key1, submit_num = key
                    id_key = (
                        key1, str(itask.point), itask.tdef.name, submit_num)
                    self.event_timers[id_key] = (itask, timer)

    def process_events(self, schd_ctx):
        """Process task events."""
        ctx_groups = {}
        now = time()
        for id_key, (_, timer) in self.event_timers.copy().items():
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
                    self._custom_handler_callback, [id_key])
            else:
                # Group together built-in event handlers, where possible
                if timer.ctx not in ctx_groups:
                    ctx_groups[timer.ctx] = []
                # "itask.submit_num" may have moved on at this point
                ctx_groups[timer.ctx].append(id_key)

        next_mail_time = now + self.mail_interval
        for ctx, id_keys in ctx_groups.items():
            if ctx.ctx_type == TaskProxy.EVENT_MAIL:
                # Set next_mail_time if any mail sent
                self.next_mail_time = next_mail_time
                self._process_event_email(schd_ctx, ctx, id_keys)
            elif ctx.ctx_type == TaskProxy.JOB_LOGS_RETRIEVE:
                self._process_job_logs_retrieval(schd_ctx, ctx, id_keys)

    def _custom_handler_callback(self, ctx, id_key):
        """Callback when a custom event handler is done."""
        itask, timer = self.event_timers[id_key]
        itask.command_log(ctx)
        if ctx.ret_code == 0:
            del self.event_timers[id_key]
        else:
            timer.unset_waiting()

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
        mail_footer_tmpl = self.mail_footer
        if mail_footer_tmpl:
            stdin_str += (mail_footer_tmpl + "\n") % {
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
            self._event_email_callback)

    def _event_email_callback(self, proc_ctx):
        """Call back when email notification command exits."""
        for id_key in proc_ctx.cmd_kwargs["id_keys"]:
            key1 = id_key[0]
            submit_num = id_key[-1]
            try:
                itask, timer = self.event_timers[id_key]
                if proc_ctx.ret_code == 0:
                    del self.event_timers[id_key]
                    log_ctx = SuiteProcContext((key1, submit_num), None)
                    log_ctx.ret_code = 0
                    itask.command_log(log_ctx)
                else:
                    timer.unset_waiting()
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
            self._job_logs_retrieval_callback)

    def _job_logs_retrieval_callback(self, proc_ctx):
        """Call back when log job retrieval completes."""
        for id_key in proc_ctx.cmd_kwargs["id_keys"]:
            key1 = id_key[0]
            submit_num = id_key[-1]
            try:
                itask, timer = self.event_timers[id_key]
                # All completed jobs are expected to have a "job.out".
                fnames = ["job.out"]
                # Failed jobs are expected to have a "job.err".
                if itask.state.status != TASK_STATUS_SUCCEEDED:
                    fnames.append("job.err")
                fname_oks = {}
                for fname in fnames:
                    fname_oks[fname] = os.path.exists(itask.get_job_log_path(
                        TaskProxy.HEAD_MODE_LOCAL, submit_num, fname))
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
                    timer.unset_waiting()
                itask.command_log(log_ctx)
            except KeyError:
                if cylc.flags.debug:
                    ERR.debug(traceback.format_exc())
