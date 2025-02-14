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
"""Tests for utilities supporting simulation and skip modes
"""
import pytest
from pytest import param

from cylc.flow.cycling.integer import IntegerPoint
from cylc.flow.cycling.iso8601 import ISO8601Point
from cylc.flow.run_modes.simulation import (
    disable_platforms,
    get_simulated_run_len,
    parse_fail_cycle_points,
    sim_task_failed,
)


@pytest.mark.parametrize(
    'execution_time_limit, speedup_factor, default_run_length',
    (
        param(None, None, 'PT1H', id='default-run-length'),
        param(None, 10, 'PT1H', id='speedup-factor-alone'),
        param('PT1H', None, 'PT1H', id='execution-time-limit-alone'),
        param('P1D', 24, 'PT1M', id='speed-up-and-execution-tl'),
    )
)
def test_get_simulated_run_len(
    execution_time_limit, speedup_factor, default_run_length
):
    """Test the logic of the presence or absence of config items.

    Avoid testing the correct workign of DurationParser.
    """
    rtc = {
        'execution time limit': execution_time_limit,
        'simulation': {
            'speedup factor': speedup_factor,
            'default run length': default_run_length,
            'time limit buffer': 'PT0S',
        }
    }
    assert get_simulated_run_len(rtc) == 3600


@pytest.mark.parametrize(
    'rtc, expect', (
        ({'platform': 'skarloey'}, 'localhost'),
        ({'remote': {'host': 'rheneas'}}, 'localhost'),
        ({'job': {'batch system': 'loaf'}}, 'localhost'),
    )
)
def test_disable_platforms(rtc, expect):
    """A sampling of items FORBIDDEN_WITH_PLATFORMS are removed from a
    config passed to this method.
    """
    disable_platforms(rtc)
    assert rtc['platform'] == expect
    subdicts = [v for v in rtc.values() if isinstance(v, dict)]
    for subdict in subdicts:
        for k, val in subdict.items():
            if k != 'platform':
                assert val is None


@pytest.mark.parametrize(
    'args, cycling, fallback',
    (
        param((['2', '4'], ['']), 'integer', False, id='int.valid'),
        param((['garbage'], []), 'integer', True, id='int.invalid'),
        param((['20200101T0000Z'], []), 'iso8601', False, id='iso.valid'),
        param((['garbage'], []), 'iso8601', True, id='iso.invalid'),
    ),
)
def test_parse_fail_cycle_points(
    caplog, set_cycling_type, args, cycling, fallback
):
    """Tests for parse_fail_cycle points.
    """
    set_cycling_type(cycling)
    if fallback:
        expect = args[1]
        check_log = True
    else:
        expect = args[0]
        check_log = False

    if cycling == 'integer':
        assert parse_fail_cycle_points(*args) == [
            IntegerPoint(i) for i in expect
        ]
    else:
        assert parse_fail_cycle_points(*args) == [
            ISO8601Point(i) for i in expect
        ]
    if check_log:
        assert "Incompatible" in caplog.messages[0]
        assert cycling in caplog.messages[0].lower()


@pytest.mark.parametrize(
    'conf, point, try_, expect',
    (
        param(
            {'fail cycle points': [], 'fail try 1 only': True},
            ISO8601Point('1'),
            1,
            False,
            id='defaults'
        ),
        param(
            {'fail cycle points': None, 'fail try 1 only': False},
            ISO8601Point('1066'),
            1,
            True,
            id='fail-all'
        ),
        param(
            {
                'fail cycle points': [
                    ISO8601Point('1066'), ISO8601Point('1067')],
                'fail try 1 only': False
            },
            ISO8601Point('1067'),
            1,
            True,
            id='point-in-failCP'
        ),
        param(
            {
                'fail cycle points': [
                    ISO8601Point('1066'), ISO8601Point('1067')],
                'fail try 1 only': True
            },
            ISO8601Point('1000'),
            1,
            False,
            id='point-notin-failCP'
        ),
        param(
            {'fail cycle points': None, 'fail try 1 only': True},
            ISO8601Point('1066'),
            2,
            False,
            id='succeed-attempt2'
        ),
        param(
            {'fail cycle points': None, 'fail try 1 only': False},
            ISO8601Point('1066'),
            7,
            True,
            id='fail-attempt7'
        ),
    )
)
def test_sim_task_failed(
    conf, point, try_, expect, set_cycling_type
):
    set_cycling_type('iso8601')
    assert sim_task_failed(conf, point, try_) == expect
