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
from subprocess import TimeoutExpired
from typing import Any, Dict, List, Union, TYPE_CHECKING

from cylc.flow import LOG
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.hostuserutil import get_host, get_user
from cylc.flow.log_diagnosis import run_reftest
from cylc.flow.parsec.config import DefaultList
from cylc.flow.subprocctx import SubProcContext

if TYPE_CHECKING:
    from cylc.flow.config import WorkflowConfig
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

       Use "uuid".
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


def construct_mail_cmd(
    subject: str, from_address: str, to_address: str
) -> List[str]:
    """Construct a mail command."""
    return [
        'mail',
        '-s', subject,
        '-r', from_address,
        to_address
    ]


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
    except (KeyError, TypeError, ValueError):
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
    EVENT_RESTART_TIMEOUT = 'restart timeout'

    WORKFLOW_EVENT_HANDLER = 'workflow-event-handler'
    WORKFLOW_EVENT_MAIL = 'workflow-event-mail'

    def __init__(self, proc_pool):
        self.proc_pool = proc_pool
        self.proc_timeout = (
            glbl_cfg().get(['scheduler', 'process pool timeout']))

    @staticmethod
    def get_events_conf(
        config: 'WorkflowConfig', key: str, default: Any = None
    ) -> Any:
        """Return a named [scheduler][[events]] configuration."""
        for getter in (
            config.cfg['scheduler']['events'],
            config.cfg['scheduler'].get('mail', {}),
            glbl_cfg().get(['scheduler', 'events']),
            glbl_cfg().get(['scheduler', 'mail'])
        ):
            value = getter.get(key)
            if value is not None and not isinstance(value, DefaultList):
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

    def _send_mail(
        self,
        event: str,
        subject: str,
        message: str,
        schd: 'Scheduler',
        env: Dict[str, str]
    ) -> None:
        proc_ctx = SubProcContext(
            (self.WORKFLOW_EVENT_HANDLER, event),
            construct_mail_cmd(
                subject,
                from_address=self.get_events_conf(
                    schd.config, 'from', f'notifications@{get_host()}'
                ),
                to_address=self.get_events_conf(schd.config, 'to', get_user())
            ),
            env=env,
            stdin_str=message
        )
        self._run_cmd(proc_ctx, callback=self._run_event_mail_callback)

    def _run_cmd(self, ctx, callback):
        """Queue or directly run a command and its callback.

        Queue the command to the subprocess pool if possible, or otherwise
        run it in the foreground but subject to the subprocess pool timeout.

        """
        if not self.proc_pool.closed:
            # Queue it to the subprocess pool.
            self.proc_pool.put_command(ctx, callback=callback)
        else:
            # Run it in the foreground, but use the subprocess pool timeout.
            try:
                self.proc_pool.run_command(ctx, float(self.proc_timeout))
            except TimeoutExpired:
                ctx.ret_code = 124
                ctx.err = f"killed on timeout ({self.proc_timeout})"
            callback(ctx)

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
            except (KeyError, TypeError, ValueError) as exc:
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
            self._run_cmd(proc_ctx, self._run_event_handlers_callback)

    @staticmethod
    def _run_event_handlers_callback(proc_ctx):
        """Callback on completion of a workflow event handler."""
        if proc_ctx.ret_code:
            LOG.error(str(proc_ctx))
            LOG.error(f'{proc_ctx.cmd_key[1]} EVENT HANDLER FAILED')
        else:
            LOG.info(str(proc_ctx))

    @staticmethod
    def _run_event_mail_callback(proc_ctx):
        """Callback the mail command for notification of a workflow event."""
        if proc_ctx.ret_code:
            LOG.warning(str(proc_ctx))
        else:
            LOG.info(str(proc_ctx))
