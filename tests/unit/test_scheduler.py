# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
"""Tests for Cylc scheduler server."""

import pytest

from types import SimpleNamespace
from unittest.mock import patch, create_autospec

from cylc.flow.scheduler import Scheduler


@pytest.mark.parametrize(
    'options, expected',
    [
        (
            {
                'self.is_restart': True,
                'self.options.stopcp': 'ignore',
            },
            '2000'
        ),
        (
            {
                'self.options.stopcp': '1066'
            },
            '1066'
        ),
        (
            {
                'self.options.stopcp': None
            },
            '1991'
        ),
        (
            {
                'self.pool.stop_point': '1998',
                'self.options.stopcp': False
            },
            '1998'
        ),
        (
            {
                'self.config.cfg': {
                    'scheduling': {
                        'stop after cycle point': '1995'
                    }
                },
                'self.options.stopcp': False,
                'self.pool.stop_point': False
            },
            '1995'
        )
    ]
)
@patch('cylc.flow.scheduler.get_point')
def test_process_cylc_stop_point(get_point, options, expected):
    # Mock the get_point function - we don't care here
    get_point.return_value = None
    inputs = {
        'self.is_restart': False,
        'self.options.stopcp': '1990',
        'self.pool.stop_point': '1991',
        'self.config.final_point': '2000',
        "self.config.cfg": '1993',
    }
    for key, value in options.items():
        inputs[key] = value

    # Create a mock scheduler object and assign values to it.
    scheduler = create_autospec(Scheduler)

    # Add the method we want to test to our mock Scheduler class
    scheduler.process_cylc_stop_point = Scheduler.process_cylc_stop_point

    # Add various options to our scheduler.
    scheduler.is_restart = inputs['self.is_restart']
    # Set-up a fake options object.
    scheduler.options = SimpleNamespace(
        stopcp=inputs['self.options.stopcp']
    )
    # Set-up fake config object
    scheduler.config = SimpleNamespace(
        final_point=inputs['self.config.final_point'],
        cfg=inputs['self.config.cfg']
    )
    # Set up fake taskpool
    scheduler.pool = SimpleNamespace(
        stop_point=inputs['self.pool.stop_point'],
        set_stop_point=lambda x: x
    )

    scheduler.process_cylc_stop_point(scheduler)
    assert scheduler.options.stopcp == expected
