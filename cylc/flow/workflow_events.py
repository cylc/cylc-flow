# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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
"""Workflow event handler."""

from collections import namedtuple
import os
from shlex import quote

from cylc.flow import LOG
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.exceptions import WorkflowEventError
from cylc.flow.hostuserutil import get_host, get_user
from cylc.flow.log_diagnosis import run_reftest
from cylc.flow.subprocctx import SubProcContext


WorkflowEventContext = namedtuple(
    "WorkflowEventContext",
    ["event", "reason", "workflow", "uuid_str", "owner", "host", "port"])


class WorkflowEventHandler():
    """Workflow event handler."""

    EVENT_STARTUP = 'startup'
    EVENT_SHUTDOWN = 'shutdown'
    EVENT_ABORTED = 'abort'
    EVENT_TIMEOUT = 'timeout'
    EVENT_INACTIVITY_TIMEOUT = 'inactivity timeout'
    EVENT_STALL = 'stall'
    EVENT_STALL_TIMEOUT = 'stall timeout'

    WORKFLOW_EVENT_HANDLER = 'workflow-event-handler'
    WORKFLOW_EVENT_MAIL = 'workflow-event-mail'

    def __init__(self, proc_pool):
        self.proc_pool = proc_pool

    @staticmethod
    def get_events_conf(config, key, default=None):
        """Return a named [scheduler][[events]] configuration."""
        # Mail doesn't have any defaults in workflow.py
        if 'mail' in config.cfg['scheduler']:
            getters = [
                config.cfg['scheduler']['events'],
                config.cfg['scheduler']['mail'],
                glbl_cfg().get(['scheduler', 'events']),
                glbl_cfg().get(['scheduler', 'mail'])
            ]
        else:
            getters = [
                config.cfg['scheduler']['events'],
                glbl_cfg().get(['scheduler', 'events']),
                glbl_cfg().get(['scheduler', 'mail'])
            ]
        value = None
        for getter in getters:
            if key in getter:
                value = getter[key]
            if value is not None:
                return value
        return default

    def handle(self, config, ctx):
        """Handle a workflow event."""
        self._run_event_mail(config, ctx)
        self._run_event_custom_handlers(config, ctx)
        if config.options.reftest and ctx.event == self.EVENT_SHUTDOWN:
            run_reftest(config, ctx)

    def _run_event_mail(self, config, ctx):
        """Helper for "run_event_handlers", do mail notification."""
        if ctx.event in self.get_events_conf(config, 'mail events', []):
            # SMTP server
            env = dict(os.environ)
            mail_smtp = self.get_events_conf(config, 'smtp')
            if mail_smtp:
                env['smtp'] = mail_smtp
            subject = '[workflow %(event)s] %(workflow)s' % {
                'workflow': ctx.workflow, 'event': ctx.event}
            stdin_str = ''
            for name, value in [
                    ('workflow event', ctx.event),
                    ('reason', ctx.reason),
                    ('workflow', ctx.workflow),
                    ('host', ctx.host),
                    ('port', ctx.port),
                    ('owner', ctx.owner)]:
                if value:
                    stdin_str += '%s: %s\n' % (name, value)
            mail_footer_tmpl = self.get_events_conf(config, 'footer')
            if mail_footer_tmpl:
                # BACK COMPAT: "suite" deprecated
                # url:
                #     https://github.com/cylc/cylc-flow/pull/4174
                # from:
                #     Cylc 8
                # remove at:
                #     Cylc 9
                try:
                    stdin_str_footer = (mail_footer_tmpl + '\n') % {
                        'host': ctx.host,
                        'port': ctx.port,
                        'owner': ctx.owner,
                        'suite': ctx.workflow,  # deprecated
                        'workflow': ctx.workflow}
                except KeyError:
                    LOG.warning(
                        "Ignoring bad mail footer template: %s" % (
                            mail_footer_tmpl))
                else:
                    stdin_str += stdin_str_footer
            proc_ctx = SubProcContext(
                (self.WORKFLOW_EVENT_HANDLER, ctx.event),
                [
                    'mail',
                    '-s', subject,
                    '-r', self.get_events_conf(
                        config,
                        'from', 'notifications@' + get_host()),
                    self.get_events_conf(config, 'to', get_user()),
                ],
                env=env,
                stdin_str=stdin_str)
            if self.proc_pool.closed:
                # Run command in foreground if process pool is closed
                self.proc_pool.run_command(proc_ctx)
                self._run_event_handlers_callback(proc_ctx)
            else:
                # Run command using process pool otherwise
                self.proc_pool.put_command(
                    proc_ctx, callback=self._run_event_mail_callback)

    def _run_event_custom_handlers(self, config, ctx):
        """Helper for "run_event_handlers", custom event handlers."""
        # Look for event handlers
        # 1. Handlers for specific event
        # 2. General handlers
        handlers = self.get_events_conf(config, '%s handler' % ctx.event)
        if not handlers and (
                ctx.event in
                self.get_events_conf(config, 'handler events', [])):
            handlers = self.get_events_conf(config, 'handlers')
        if not handlers:
            return
        for i, handler in enumerate(handlers):
            cmd_key = ('%s-%02d' % (self.WORKFLOW_EVENT_HANDLER, i), ctx.event)
            # Handler command may be a string for substitution
            abort_on_error = self.get_events_conf(
                config, 'abort if %s handler fails' % ctx.event)
            # BACK COMPAT: suite, suite_uuid are deprecated
            # url:
            #     https://github.com/cylc/cylc-flow/pull/4174
            # from:
            #     Cylc 8
            # remove at:
            #     Cylc 9
            try:
                handler_data = {
                    'event': quote(ctx.event),
                    'message': quote(ctx.reason),
                    'workflow': quote(ctx.workflow),
                    'workflow_uuid': quote(ctx.uuid_str),
                    'suite': quote(ctx.workflow),  # deprecated
                    'suite_uuid': quote(ctx.uuid_str),  # deprecated
                }
                if config.cfg['meta']:
                    for key, value in config.cfg['meta'].items():
                        if key == "URL":
                            handler_data["workflow_url"] = quote(value)
                            handler_data["suite_url"] = quote(value)
                        handler_data[key] = quote(value)
                cmd = handler % (handler_data)
            except KeyError as exc:
                message = "%s bad template: %s" % (cmd_key, exc)
                LOG.error(message)
                if abort_on_error:
                    raise WorkflowEventError(message)
                continue
            if cmd == handler:
                # Nothing substituted, assume classic interface
                cmd = "%s '%s' '%s' '%s'" % (
                    handler, ctx.event, ctx.workflow, ctx.reason)
            proc_ctx = SubProcContext(
                cmd_key, cmd, env=dict(os.environ), shell=True)
            if abort_on_error or self.proc_pool.closed:
                # Run command in foreground if abort on failure is set or if
                # process pool is closed
                self.proc_pool.run_command(proc_ctx)
                self._run_event_handlers_callback(
                    proc_ctx, abort_on_error=abort_on_error)
            else:
                # Run command using process pool otherwise
                self.proc_pool.put_command(
                    proc_ctx, callback=self._run_event_handlers_callback)

    @staticmethod
    def _run_event_handlers_callback(proc_ctx, abort_on_error=False):
        """Callback on completion of a workflow event handler."""
        if proc_ctx.ret_code:
            msg = '%s EVENT HANDLER FAILED' % proc_ctx.cmd_key[1]
            LOG.error(str(proc_ctx))
            LOG.error(msg)
            if abort_on_error:
                raise WorkflowEventError(msg)
        else:
            LOG.info(str(proc_ctx))

    @staticmethod
    def _run_event_mail_callback(proc_ctx):
        """Callback the mail command for notification of a workflow event."""
        if proc_ctx.ret_code:
            LOG.warning(str(proc_ctx))
        else:
            LOG.info(str(proc_ctx))
