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

from types import SimpleNamespace

from .test_workflow_events import TEMPLATES

from cylc.flow.id import Tokens
from cylc.flow.task_events_mgr import EventKey

import pytest


@pytest.mark.parametrize('template', TEMPLATES)
async def test_mail_footer_template(
    mod_one,  # use the same scheduler for each test
    start,
    mock_glbl_cfg,
    log_filter,
    capcall,
    template,
):
    """It should handle templating issues with the mail footer."""
    # prevent emails from being sent
    mail_calls = capcall(
        'cylc.flow.task_events_mgr.TaskEventsManager._send_mail'
    )

    # configure mail footer
    mock_glbl_cfg(
        'cylc.flow.workflow_events.glbl_cfg',
        f'''
            [scheduler]
                [[mail]]
                    footer = 'footer={template}'
        ''',
    )

    # start the workflow and get it to send an email
    ctx = SimpleNamespace(mail_to=None, mail_from=None)
    id_keys = [EventKey('none', 'failed', 'failed', Tokens('//1/a'))]
    async with start(mod_one):
        mod_one.task_events_mgr._process_event_email(mod_one, ctx, id_keys)

    # warnings should appear only when the template is invalid
    should_log = 'workflow' not in template

    # check that template issues are handled correctly
    assert bool(log_filter(
        contains='Ignoring bad mail footer template',
    )) == should_log
    assert bool(log_filter(
        contains=template,
    )) == should_log

    # check that the mail is sent even if there are issues with the footer
    assert len(mail_calls) == 1


async def test_event_email_body(
    mod_one,
    start,
    capcall,
):
    """It should send an email with the event context."""
    mail_calls = capcall(
        'cylc.flow.task_events_mgr.TaskEventsManager._send_mail'
    )

    # start the workflow and get it to send an email
    ctx = SimpleNamespace(mail_to=None, mail_from=None)
    async with start(mod_one):
        # send a custom task message with the warning severity level
        id_keys = [EventKey('none', 'warning', 'warning message', Tokens('//1/a/01'))]
        mod_one.task_events_mgr._process_event_email(mod_one, ctx, id_keys)

    # test the email which would have been sent for this message
    email_body = mail_calls[0][0][3]
    assert 'event: warning'
    assert 'job: 1/a/01' in email_body
    assert 'message: warning message' in email_body
    assert f'workflow: {mod_one.tokens["workflow"]}' in email_body
    assert f'host: {mod_one.host}' in email_body
    assert f'port: {mod_one.server.port}' in email_body
    assert f'owner: {mod_one.owner}' in email_body

# NOTE: we do not test custom event handlers here because these are tested
# as a part of workflow validation (now also performed by cylc play)
