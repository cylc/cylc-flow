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

from enum import Enum
import os
from shlex import quote
from typing import Dict, Union, TYPE_CHECKING

from cylc.flow import LOG
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.hostuserutil import get_host, get_user
from cylc.flow.log_diagnosis import run_reftest
from cylc.flow.subprocctx import SubProcContext

if TYPE_CHECKING:
    from cylc.flow.scheduler import Scheduler


class EventData(Enum):
    """The following variables are available to workflow event handlers.

    They can be templated into event handlers with Python percent style string
    formatting e.g:

    .. code-block:: none

       %(workflow)s is running on %(host)s

    .. note::

       Substitution patterns should not be quoted in the template strings.
       This is done automatically where required.

    For an explanation of the substitution syntax, see
    `String Formatting Operations in the Python documentation
    <https://docs.python.org/3/library/stdtypes.html
    #printf-style-string-formatting>`_.

    """

    Event = 'event'
    """The type of workflow event that has occurred e.g. ``stall``."""

    Message = 'message'
    """Additional information about the event."""

    Workflow = 'workflow'
    """The workflow ID"""

    Host = 'host'
    """The host where the workflow is running."""

    Port = 'port'
    """The port where the workflow is running."""

    Owner = 'owner'
    """The user account under which the workflow is running."""

    UUID = 'uuid'
    """The unique identification string for this workflow run.

    This string is preserved for the lifetime of the scheduler and is restored
    from the database on restart.
    """

    WorkflowURL = 'workflow_url'
    """The URL defined in :cylc:conf:`flow.cylc[meta]URL`."""

    # BACK COMPAT: "suite" deprecated
    # url:
    #     https://github.com/cylc/cylc-flow/pull/4724 (& 4714)
    # from:
    #     Cylc 8
    # remove at:
    #     Cylc 8.x
    Suite = 'suite'
    """The workflow ID

    .. deprecated:: 8.0.0

       Use "workflow".
    """

    # BACK COMPAT: "suite_uuid" deprecated
    # url:
    #     https://github.com/cylc/cylc-flow/pull/4724 (& 4714)
    # from:
    #     Cylc 8
    # remove at:
    #     Cylc 8.x
    Suite_UUID = 'suite_uuid'
    """The unique identification string for this workflow run.

    .. deprecated:: 8.0.0

       Use "uuid_str".
    """

    # BACK COMPAT: "suite_url" deprecated
    # url:
    #     https://github.com/cylc/cylc-flow/pull/4724 (& 4714)
    # from:
    #     Cylc 8
    # remove at:
    #     Cylc 8.x
    SuiteURL = 'suite_url'
    """The URL defined in :cylc:conf:`flow.cylc[meta]URL`.

    .. deprecated:: 8.0.0

       Use "workflow_url".
    """


def get_template_variables(
    schd: 'Scheduler',
    event: str,
    reason: str
) -> Dict[str, Union[str, int]]:
    """Return a dictionary of template varaibles for a workflow event."""
    workflow_url: str = schd.config.cfg['meta'].get('URL', '')
    return {
        # scheduler properties
        EventData.Event.value:
            event,
        EventData.Message.value:
            reason,
        EventData.Workflow.value:
            schd.workflow,
        EventData.Host.value:
            schd.host,
        EventData.Port.value:
            (schd.server.port if schd.server else -1),
        EventData.Owner.value:
            schd.owner,
        EventData.UUID.value:
            schd.uuid_str,
        EventData.WorkflowURL.value:
            workflow_url,

        # BACK COMPAT: "suite", "suite_uuid", "suite_url"
        # url:
        #     https://github.com/cylc/cylc-flow/pull/4724 (&4714)
        # from:
        #     Cylc 8
        # remove at:
        #     Cylc 8.x
        EventData.Suite.value:
            schd.workflow,
        EventData.Suite_UUID.value:
            schd.uuid_str,
        EventData.SuiteURL.value:
            workflow_url,

        # workflow metadata
        **{
            key: quote(value)
            for key, value in schd.config.cfg['meta'].items()
            if key != 'URL'
        },  # noqa: E122
    }


def process_mail_footer(
    mail_footer_tmpl: str,
    template_vars,
) -> str:
    """Process mail footer for workflow or task events.

    Returns an empty string if issues occur in processing.
    """
    try:
        return (mail_footer_tmpl + '\n') % template_vars
    except (KeyError, ValueError):
        LOG.warning(
            f'Ignoring bad mail footer template: {mail_footer_tmpl}'
        )
    return ''


class WorkflowEventHandler():
    """Workflow event handler."""

    EVENT_STARTUP = 'startup'
    EVENT_SHUTDOWN = 'shutdown'
    EVENT_ABORTED = 'abort'
    EVENT_WORKFLOW_TIMEOUT = 'workflow timeout'
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
                value = getter.get(key)
            if value is not None and value != []:
                return value
        return default

    def handle(self, schd: 'Scheduler', event: str, reason: str) -> None:
        """Handle a workflow event."""
        template_variables = get_template_variables(schd, event, reason)
        self._run_event_mail(schd, template_variables, event)
        self._run_event_custom_handlers(schd, template_variables, event)
        if schd.config.options.reftest and event == self.EVENT_SHUTDOWN:
            run_reftest(schd)

    def _run_event_mail(self, schd, template_variables, event):
        """Helper for "run_event_handlers", do mail notification."""
        if event in self.get_events_conf(schd.config, 'mail events', []):
            # SMTP server
            env = dict(os.environ)
            mail_smtp = self.get_events_conf(schd.config, 'smtp')
            if mail_smtp:
                env['smtp'] = mail_smtp
            subject = (
                f'[workflow %({EventData.Event.value})s]'
                f' %({EventData.Workflow.value})s' % (
                    template_variables
                )
            )
            stdin_str = ''
            for key in (
                EventData.Event.value,
                EventData.Message.value,
                EventData.Workflow.value,
                EventData.Host.value,
                EventData.Port.value,
                EventData.Owner.value,
            ):
                value = template_variables.get(key, None)
                if value:
                    stdin_str += '%s: %s\n' % (key, value)
            mail_footer_tmpl = self.get_events_conf(schd.config, 'footer')
            if mail_footer_tmpl:
                stdin_str += process_mail_footer(
                    mail_footer_tmpl,
                    template_variables,
                )
            self._send_mail(event, subject, stdin_str, schd, env)

    def _send_mail(self, event, subject, message, schd, env):
        proc_ctx = SubProcContext(
            (self.WORKFLOW_EVENT_HANDLER, event),
            [
                'mail',
                '-s', subject,
                '-r', self.get_events_conf(
                    schd.config,
                    'from', 'notifications@' + get_host()),
                self.get_events_conf(schd.config, 'to', get_user()),
            ],
            env=env,
            stdin_str=message)
        if self.proc_pool.closed:
            # Run command in foreground if process pool is closed
            self.proc_pool.run_command(proc_ctx)
            self._run_event_handlers_callback(proc_ctx)
        else:
            # Run command using process pool otherwise
            self.proc_pool.put_command(
                proc_ctx, callback=self._run_event_mail_callback)

    def _run_event_custom_handlers(self, schd, template_variables, event):
        """Helper for "run_event_handlers", custom event handlers."""
        # Look for event handlers
        # 1. Handlers for specific event
        # 2. General handlers
        config = schd.config
        handlers = self.get_events_conf(config, '%s handlers' % event)
        if not handlers and (
            event in
            self.get_events_conf(config, 'handler events', [])
        ):
            handlers = self.get_events_conf(config, 'handlers')
        if not handlers:
            return
        for i, handler in enumerate(handlers):
            cmd_key = ('%s-%02d' % (self.WORKFLOW_EVENT_HANDLER, i), event)
            try:
                cmd = handler % (template_variables)
            except KeyError as exc:
                message = f'{cmd_key} bad template: {handler}\n{exc}'
                LOG.error(message)
                continue
            if cmd == handler:
                # Nothing substituted, assume classic interface
                cmd = (
                    f"%(handler)s"
                    f" '%({EventData.Event.value})s'"
                    f" '%({EventData.Workflow.value})s'"
                    f" '%({EventData.Message.value})s'"
                ) % (
                    {'handler': handler, **template_variables}
                )
            proc_ctx = SubProcContext(
                cmd_key,
                cmd,
                env=dict(os.environ),
                shell=True  # nosec (designed to run user defined code)
            )
            if self.proc_pool.closed:
                # Run command in foreground if abort on failure is set or if
                # process pool is closed
                self.proc_pool.run_command(proc_ctx)
                self._run_event_handlers_callback(proc_ctx)
            else:
                # Run command using process pool otherwise
                self.proc_pool.put_command(
                    proc_ctx, callback=self._run_event_handlers_callback)

    @staticmethod
    def _run_event_handlers_callback(proc_ctx):
        """Callback on completion of a workflow event handler."""
        if proc_ctx.ret_code:
            msg = '%s EVENT HANDLER FAILED' % proc_ctx.cmd_key[1]
            LOG.error(str(proc_ctx))
            LOG.error(msg)
        else:
            LOG.info(str(proc_ctx))

    @staticmethod
    def _run_event_mail_callback(proc_ctx):
        """Callback the mail command for notification of a workflow event."""
        if proc_ctx.ret_code:
            LOG.warning(str(proc_ctx))
        else:
            LOG.info(str(proc_ctx))
