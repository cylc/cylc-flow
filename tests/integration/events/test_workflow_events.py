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
from cylc.flow.workflow_events import WorkflowEventHandler

import pytest


TEMPLATES = [
    # perfectly valid
    pytest.param('%(workflow)s', id='good'),
    # no template variable of that name
    pytest.param('%(no_such_variable)s', id='bad'),
    # missing the 's'
    pytest.param('%(broken_syntax)', id='ugly'),
]


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
        'cylc.flow.workflow_events.WorkflowEventHandler._send_mail'
    )

    # configure Cylc to send an email on startup with the configured footer
    mock_glbl_cfg(
        'cylc.flow.workflow_events.glbl_cfg',
        f'''
            [scheduler]
                [[mail]]
                    footer = 'footer={template}'
                [[events]]
                    mail events = startup
        ''',
    )

    # start the workflow and get it to send an email
    async with start(mod_one) as one_log:
        one_log.clear()  # clear previous log messages
        mod_one.workflow_event_handler.handle(
            mod_one,
            WorkflowEventHandler.EVENT_STARTUP,
            'event message'
        )

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


@pytest.mark.parametrize('template', TEMPLATES)
async def test_custom_event_handler_template(
    mod_one,  # use the same scheduler for each test
    start,
    mock_glbl_cfg,
    log_filter,
    template,
):
    """It should handle templating issues with custom event handlers."""
    # configure Cylc to send an email on startup with the configured footer
    mock_glbl_cfg(
        'cylc.flow.workflow_events.glbl_cfg',
        f'''
            [scheduler]
                [[events]]
                    startup handlers = echo "{template}"
        '''
    )

    # start the workflow and get it to send an email
    async with start(mod_one) as one_log:
        one_log.clear()  # clear previous log messages
        mod_one.workflow_event_handler.handle(
            mod_one,
            WorkflowEventHandler.EVENT_STARTUP,
            'event message'
        )

    # warnings should appear only when the template is invalid
    should_log = 'workflow' not in template

    # check that template issues are handled correctly
    assert bool(log_filter(
        contains='bad template',
    )) == should_log
    assert bool(log_filter(
        contains=template,
    )) == should_log
