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
    id_keys = [((None, 'failed'), '1', 'a', 1)]
    async with start(mod_one) as one_log:
        mod_one.task_events_mgr._process_event_email(mod_one, ctx, id_keys)

    # warnings should appear only when the template is invalid
    should_log = 'workflow' not in template

    # check that template issues are handled correctly
    assert bool(log_filter(
        one_log,
        contains='Ignoring bad mail footer template',
    )) == should_log
    assert bool(log_filter(
        one_log,
        contains=template,
    )) == should_log

    # check that the mail is sent even if there are issues with the footer
    assert len(mail_calls) == 1


# NOTE: we do not test custom event handlers here because these are tested
# as a part of workflow validation (now also performed by cylc play)
