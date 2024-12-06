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
"""
tests for functions in cylc.flow.workflow_events.py
"""

import pytest

from types import SimpleNamespace

from cylc.flow.workflow_events import (
    WorkflowEventHandler,
    get_template_variables,
    process_mail_footer,
)


@pytest.mark.parametrize(
    'key, workflow_cfg, glbl_cfg, expected',
    [
        ('handlers', True, True, ['stall']),
        ('handlers', False, True, None),
        ('handlers', False, False, None),
        ('mail events', True, True, []),
        ('mail events', False, True, ['abort']),
        ('mail events', False, False, None),
        ('from', True, True, 'docklands@railway'),
        ('from', False, True, 'highway@mixture'),
        ('from', False, False, None),
        ('abort on workflow timeout', True, True, True),
        ('abort on workflow timeout', False, True, True),
        ('abort on workflow timeout', False, False, False),
    ]
)
def test_get_events_handler(
    mock_glbl_cfg, key, workflow_cfg, glbl_cfg, expected
):
    """Test order of precedence for getting event handler configuration."""
    if glbl_cfg:
        mock_glbl_cfg(
            'cylc.flow.workflow_events.glbl_cfg',
            '''
            [scheduler]
                [[mail]]
                    from = highway@mixture
                [[events]]
                    abort on workflow timeout = True
                    mail events = abort
            '''
        )

    config = SimpleNamespace()
    config.cfg = {
        'scheduler': {
            'events': {'handlers': ['stall'], 'mail events': []},
            'mail': {'from': 'docklands@railway'},
        } if workflow_cfg else {'events': {}}
    }
    assert WorkflowEventHandler.get_events_conf(config, key) == expected


def test_process_mail_footer(caplog, log_filter):
    schd = SimpleNamespace(
        config=SimpleNamespace(cfg={'meta': {}}),
        host='myhost',
        owner='me',
        server=SimpleNamespace(port=42),
        uuid_str=None,
        workflow='my_workflow',
    )
    template_vars = get_template_variables(schd, '', '')

    # test all variables
    assert process_mail_footer(
        '%(host)s|%(port)s|%(owner)s|%(suite)s|%(workflow)s', template_vars
    ) == 'myhost|42|me|my_workflow|my_workflow\n'
    assert not log_filter(caplog, contains='Ignoring bad mail footer template')

    # test invalid variable
    assert process_mail_footer('%(invalid)s', template_vars) == ''
    assert log_filter(caplog, contains='Ignoring bad mail footer template')

    # test broken template
    caplog.clear()
    assert process_mail_footer('%(invalid)s', template_vars) == ''
    assert log_filter(caplog, contains='Ignoring bad mail footer template')
