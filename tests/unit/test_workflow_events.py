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

from cylc.flow.workflow_events import WorkflowEventHandler


@pytest.mark.parametrize(
    'key, expected, scheduler_mail_defined',
    [
        ('handlers', ['stall'], True),
        ('hotel', None, True),
        ('from', 'highway@mixture', True),
        ('abort on timeout', True, True),
        ('handlers', ['stall'], False),
        ('hotel', None, False),
        ('abort on timeout', True, False),
    ]
)
def test_get_events_handler(
    mock_glbl_cfg, key, expected, scheduler_mail_defined
):
    # It checks that method returns sensible answers.
    if scheduler_mail_defined is True:
        mock_glbl_cfg(
            'cylc.flow.workflow_events.glbl_cfg',
            '''
            [scheduler]
                [[mail]]
                    from = highway@mixture
                [[events]]
                    abort on timeout = True
            '''
        )
    else:
        mock_glbl_cfg(
            'cylc.flow.workflow_events.glbl_cfg',
            '''
            [scheduler]
                [[events]]
                    abort on timeout = True
            '''
        )

    config = SimpleNamespace()
    config.cfg = {
        'scheduler': {
            'events': {
                'handlers': ['stall']
            },
        }
    }
    assert WorkflowEventHandler.get_events_conf(config, key) == expected
