#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
"""Suite event handler."""

from collections import namedtuple
import os
from shlex import quote

from cylc import LOG
from cylc.cfgspec.glbl_cfg import glbl_cfg
from cylc.exceptions import SuiteEventError
from cylc.hostuserutil import get_host, get_user
from cylc.subprocctx import SubProcContext


SuiteEventContext = namedtuple(
    "SuiteEventContext",
    ["event", "reason", "suite", "uuid_str", "owner", "host", "port"])


class SuiteEventHandler(object):
    """Suite event handler."""

    EVENT_STARTUP = 'startup'
    EVENT_SHUTDOWN = 'shutdown'
    EVENT_TIMEOUT = 'timeout'
    EVENT_INACTIVITY_TIMEOUT = 'inactivity'
    EVENT_STALLED = 'stalled'

    SUITE_EVENT_HANDLER = 'suite-event-handler'
    SUITE_EVENT_MAIL = 'suite-event-mail'

    def __init__(self, proc_pool):
        self.proc_pool = proc_pool

    @staticmethod
    def get_events_conf(config, key, default=None):
        """Return a named [cylc][[events]] configuration."""
        for getter in [
                config.cfg['cylc']['events'],
                glbl_cfg().get(['cylc', 'events'])]:
            try:
                value = getter[key]
            except KeyError:
                pass
            else:
                if value is not None:
                    return value
        return default

    def handle(self, config, ctx):
        """Handle a suite event."""
        self._run_event_mail(config, ctx)
        self._run_event_custom_handlers(config, ctx)

    def _run_event_mail(self, config, ctx):
        """Helper for "run_event_handlers", do mail notification."""
        if ctx.event in self.get_events_conf(config, 'mail events', []):
            # SMTP server
            env = dict(os.environ)
            mail_smtp = self.get_events_conf(config, 'mail smtp')
            if mail_smtp:
                env['smtp'] = mail_smtp
            subject = '[suite %(event)s] %(suite)s' % {
                'suite': ctx.suite, 'event': ctx.event}
            stdin_str = ''
            for name, value in [
                    ('suite event', ctx.event),
                    ('reason', ctx.reason),
                    ('suite', ctx.suite),
                    ('host', ctx.host),
                    ('port', ctx.port),
                    ('owner', ctx.owner)]:
                if value:
                    stdin_str += '%s: %s\n' % (name, value)
            mail_footer_tmpl = self.get_events_conf(config, 'mail footer')
            if mail_footer_tmpl:
                stdin_str += (mail_footer_tmpl + '\n') % {
                    'host': ctx.host,
                    'port': ctx.port,
                    'owner': ctx.owner,
                    'suite': ctx.suite}
            proc_ctx = SubProcContext(
                (self.SUITE_EVENT_HANDLER, ctx.event),
                [
                    'mail',
                    '-s', subject,
                    '-r', self.get_events_conf(
                        config,
                        'mail from', 'notifications@' + get_host()),
                    self.get_events_conf(config, 'mail to', get_user()),
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
                    proc_ctx, self._run_event_mail_callback)

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
            cmd_key = ('%s-%02d' % (self.SUITE_EVENT_HANDLER, i), ctx.event)
            # Handler command may be a string for substitution
            abort_on_error = self.get_events_conf(
                config, 'abort if %s handler fails' % ctx.event)
            try:
                handler_data = {
                    'event': quote(ctx.event),
                    'message': quote(ctx.reason),
                    'suite': quote(ctx.suite),
                    'suite_uuid': quote(str(ctx.uuid_str)),
                }
                if config.cfg['meta']:
                    for key, value in config.cfg['meta'].items():
                        if key == "URL":
                            handler_data["suite_url"] = quote(value)
                        handler_data[key] = quote(value)
                cmd = handler % (handler_data)
            except KeyError as exc:
                message = "%s bad template: %s" % (cmd_key, exc)
                LOG.error(message)
                if abort_on_error:
                    raise SuiteEventError(message)
                continue
            if cmd == handler:
                # Nothing substituted, assume classic interface
                cmd = "%s '%s' '%s' '%s'" % (
                    handler, ctx.event, ctx.suite, ctx.reason)
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
                    proc_ctx, self._run_event_handlers_callback)

    @staticmethod
    def _run_event_handlers_callback(proc_ctx, abort_on_error=False):
        """Callback on completion of a suite event handler."""
        if proc_ctx.ret_code:
            msg = '%s EVENT HANDLER FAILED' % proc_ctx.cmd_key[1]
            LOG.error(str(proc_ctx))
            LOG.error(msg)
            if abort_on_error:
                raise SuiteEventError(msg)
        else:
            LOG.info(str(proc_ctx))

    @staticmethod
    def _run_event_mail_callback(proc_ctx):
        """Callback the mail command for notification of a suite event."""
        if proc_ctx.ret_code:
            LOG.warning(str(proc_ctx))
        else:
            LOG.info(str(proc_ctx))
