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
"""Tests for Cylc scheduler server."""

import logging
import pytest
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import create_autospec, Mock, patch

from cylc.flow import CYLC_LOG
from cylc.flow.scheduler import Scheduler

Fixture = Any


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


@pytest.mark.parametrize(
    'opts, is_restart, expected_set_opts, expected_warnings',
    [
        pytest.param(
            {}, False, {}, [], id="No opts"
        ),
        pytest.param(
            {'icp': 'ignore'}, True, {'icp': 'ignore'}, [],
            id="opt=ignore on restart"
        ),
        pytest.param(
            {'icp': 3, 'startcp': 5}, True, {'icp': None, 'startcp': None},
            [("Ignoring option: --icp=3. The only valid "
              "value for a restart is 'ignore'."),
             ("Ignoring option: --startcp=5. The only valid "
              "value for a restart is 'ignore'.")],
            id="icp & startcp on restart"
        ),
        pytest.param(
            {'icp': 'ignore'}, False, {'icp': None},
            [("Ignoring option: --icp=ignore. The value cannot be 'ignore' "
              "unless restarting the workflow.")],
            id="opt=ignore on first start"
        ),
        pytest.param(
            {'icp': '22', 'stopcp': 'ignore'}, False,
            {'icp': '22', 'stopcp': None},
            [("Ignoring option: --stopcp=ignore. The value cannot be 'ignore' "
              "unless restarting the workflow.")],
            id="mixed opts on first start"
        )
    ]
)
def test_process_cycle_point_opts(
        opts: Dict[str, Optional[str]],
        is_restart: bool,
        expected_set_opts: Dict[str, Optional[str]],
        expected_warnings: List[str],
        caplog: Fixture):
    """Test Scheduler.process_cycle_point_opts()"""
    caplog.set_level(logging.WARNING, CYLC_LOG)
    mocked_scheduler = Mock()
    mocked_scheduler.options = Mock(spec=[], **opts)
    mocked_scheduler.is_restart = is_restart

    Scheduler.process_cycle_point_opts(mocked_scheduler)
    for opt, value in expected_set_opts.items():
        assert getattr(mocked_scheduler.options, opt) == value
    actual_warnings: List[str] = [rec.message for rec in caplog.records]
    assert sorted(actual_warnings) == sorted(expected_warnings)
