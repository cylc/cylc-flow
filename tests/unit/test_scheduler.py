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

import pytest
from types import SimpleNamespace
from typing import Any, List
from unittest.mock import create_autospec, Mock, patch

from cylc.flow.exceptions import UserInputError
from cylc.flow.scheduler import Scheduler
from cylc.flow.scheduler_cli import RunOptions

Fixture = Any
param = pytest.param

@pytest.mark.parametrize(
    'options, expected',
    [
        pytest.param(
            {
                'is_restart': True,
                'cli_stop_point': 'reload',
                'db_stop_point': '1991'  # DB value should be ignored
            },
            '1993',
            id="From cfg if --stopcp=reload on restart"
        ),
        pytest.param(
            {
                'cli_stop_point': '1066'
            },
            '1066',
            id="From CLI if --stopcp used"
        ),
        pytest.param(
            {
                'is_restart': True,
                'cli_stop_point': '1066',
                'db_stop_point': '1991'  # DB value should be ignored
            },
            '1066',
            id="From CLI if --stopcp used on restart"
        ),
        pytest.param(
            {
                'is_restart': True,
                'db_stop_point': '1991'
            },
            '1991',
            id="From DB on restart"
        ),
        pytest.param(
            {},
            '1993',
            id="From flow.cylc value by default"
        ),
        pytest.param(
            {
                'cfg': {
                    'scheduling': {}
                }
            },
            None,
            id="None if not set anywhere"
        )
    ]
)
@patch('cylc.flow.scheduler.get_point')
def test_process_stop_cycle_point(get_point, options, expected):
    # Mock the get_point function - we don't care here
    get_point.return_value = None
    inputs = {
        'is_restart': False,
        'cfg': {
            'scheduling': {
                'stop after cycle point': '1993'
            }
        },
        'final_point': '2000',
    }
    inputs.update(options)

    # Create a mock scheduler object and assign values to it.
    scheduler = create_autospec(Scheduler)
    scheduler.is_restart = inputs.get('is_restart')
    scheduler.options = RunOptions(stopcp=inputs.get('cli_stop_point'))
    # Set-up fake config object
    scheduler.config = SimpleNamespace(
        final_point=inputs.get('final_point'),
        cfg=inputs.get('cfg')
    )
    # Set up fake taskpool
    scheduler.pool = Mock(
        stop_point=inputs.get('db_stop_point')
    )

    Scheduler.process_stop_cycle_point(scheduler)
    assert scheduler.options.stopcp == expected


@pytest.mark.parametrize(
    'opts_to_test, is_restart, err_msg',
    [
        pytest.param(
            ['icp', 'startcp', 'starttask'],
            True,
            "option --{} is not valid for restart",
            id="start opts on restart"
        ),
        pytest.param(
            ['icp', 'startcp', 'starttask'],
            False,
            "option --{}=reload is not valid",
            id="start opts =reload"
        ),
        pytest.param(
            ['fcp', 'stopcp'],
            False,
            "option --{}=reload is only valid for restart",
            id="end opts =reload when not restart"
        ),
    ]
)
def test_check_startup_opts(
    opts_to_test: List[str],
    is_restart: bool,
    err_msg: str
) -> None:
    """Test Scheduler._check_startup_opts()"""
    for opt in opts_to_test:
        mocked_scheduler = Mock(is_restart=is_restart)
        mocked_scheduler.options = SimpleNamespace(**{opt: 'reload'})
        with pytest.raises(UserInputError) as excinfo:
            Scheduler._check_startup_opts(mocked_scheduler)
        assert(err_msg.format(opt) in str(excinfo))


@pytest.mark.parametrize(
    'input_, expect',
    [
        param(
            {
                'point': 'reload',
                'cycling_mode': 'integer'
            },
            None,
            id="Point==reload"
        ),
        param(
            {
                'point': '911',
                'cycling_mode': 'integer',
            },
            None,
            id="integer-cycling-valid"
        ),
        param(
            {
                'point': 'foo',
                'cycling_mode': 'integer'
            },
            'Not OK',
            id="integer-cycling-invalid"
        ),
        param(
            {
                'point': '2022',
                'cycling_mode': 'gregorian'
            },
            None,
            id="dt-cycling-valid"
        ),
        param(
            {
                'point': '2022boo',
                'cycling_mode': 'gergorian'
            },
            'Not OK',
            id="dt-cycling-invalid"
        )
    ]
)
def test_validate_cyclepoint_str(input_, expect):
    """Method correctly checks whether cyclepoint str is valid"""
    testthis = Scheduler.validate_cyclepoint_str
    if expect == None:
        assert testthis(**input_) == expect
    else:
        with pytest.raises(UserInputError, match='Invalid'):
            testthis(**input_)

