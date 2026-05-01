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

from typing import Callable, Optional
from unittest.mock import Mock

import pytest
from pytest import param

from cylc.flow.cycling import PointBase
from cylc.flow.cycling.integer import IntegerPoint
from cylc.flow.cycling.iso8601 import ISO8601Point
from cylc.flow.flow_mgr import FlowNums
from cylc.flow.id import Tokens
from cylc.flow.task_proxy import TaskProxy
from cylc.flow.taskdef import TaskDef


def test_get_point_as_seconds_cached():
    """Already-computed value is returned immediately."""
    mock_itask = Mock(point_as_seconds=42)
    assert TaskProxy.get_point_as_seconds(mock_itask) == 42


def test_get_point_as_seconds_known_tz(set_cycling_type):
    """Cycle point with explicit UTC timezone."""
    set_cycling_type(ISO8601Point.TYPE)
    mock_itask = Mock(
        point=ISO8601Point('19700101T00Z').standardise(),
        point_as_seconds=None,
    )
    assert TaskProxy.get_point_as_seconds(mock_itask) == 0


def test_get_point_as_seconds_unknown_tz(monkeypatch):
    """Cycle point without timezone triggers local-tz offset adjustment."""
    # Mock point_parse to return a timepoint with unknown timezone
    mock_timepoint = Mock(
        seconds_since_unix_epoch=3600,
        time_zone=Mock(unknown=True),
    )
    monkeypatch.setattr(
        'cylc.flow.task_proxy.point_parse',
        lambda _: mock_timepoint,
    )
    # Pretend local timezone is UTC+5:30
    monkeypatch.setattr(
        'cylc.flow.task_proxy.get_local_time_zone',
        lambda: (5, 30),
    )
    mock_itask = Mock(
        point='19700101T01',
        point_as_seconds=None,
    )
    result = TaskProxy.get_point_as_seconds(mock_itask)
    # 3600 + (5*3600 + 30*60) = 3600 + 19800 = 23400
    assert result == 23400


@pytest.mark.parametrize(
    'itask_point, offset_str, expected',
    [
        param(  # date -u -d 19700101 "+%s"
            ISO8601Point('19700101T00Z'), 'PT0M', 0, id="zero epoch"
        ),
        param(  # 2025 is not a leap year: Jan 1 + P2M = P59D
            ISO8601Point('20250101T00Z'), 'PT0M', 1735689600, id="nonleap base"
        ),
        param(
            ISO8601Point('20250101T00Z'), 'P59D', 1740787200, id="nonleap off1"
        ),
        param(
            ISO8601Point('20250101T00Z'), 'P2M', 1740787200, id="nonleap off2"
        ),
        param(  # 2024 is a leap year: Jan 1 + P2M = P60D
            ISO8601Point('20240101T00Z'), 'PT0M', 1704067200, id="leap base"
        ),
        param(
            ISO8601Point('20240101T00Z'), 'P60D', 1709251200, id="leap off1"
        ),
        param(
            ISO8601Point('20240101T00Z'), 'P2M', 1709251200, id="leap off2"
        ),
    ]
)
def test_get_clock_trigger_time(
    itask_point: PointBase,
    offset_str: str,
    expected: int,
    set_cycling_type: Callable
) -> None:
    """Test get_clock_trigger_time() for exact and inexact offsets."""
    set_cycling_type(itask_point.TYPE)
    mock_itask = Mock(
        point=itask_point.standardise(),
        clock_trigger_times={}
    )
    assert TaskProxy.get_clock_trigger_time(
        mock_itask, mock_itask.point, offset_str) == expected


def test_is_ready_to_run_held():
    """A held task is not ready to run."""
    mock_itask = Mock(state=Mock(is_held=True))
    assert TaskProxy.is_ready_to_run(mock_itask) is False


def test_is_ready_to_run_try_timer():
    """A task with an active try timer delegates to is_delay_done()."""
    mock_timer = Mock()
    mock_timer.is_delay_done.return_value = True
    mock_itask = Mock(
        state=Mock(is_held=False, status='submission-failed'),
        try_timers={'submission-failed': mock_timer},
    )
    assert TaskProxy.is_ready_to_run(mock_itask) is True
    mock_timer.is_delay_done.assert_called_once()


@pytest.mark.parametrize(
    'is_waiting, prereqs, ext_trigs, xtrigs, expected',
    [
        param(True, True, True, True, True, id="all-satisfied"),
        param(False, True, True, True, False, id="not-waiting"),
        param(True, False, True, True, False, id="prereqs-unsatisfied"),
        param(True, True, False, True, False, id="ext-trigs-unsatisfied"),
        param(True, True, True, False, False, id="xtrigs-unsatisfied"),
    ]
)
def test_is_ready_to_run_conditions(
    is_waiting, prereqs, ext_trigs, xtrigs, expected
):
    """Test the final return with various combinations of conditions."""
    mock_itask = Mock(
        state=Mock(is_held=False, status='waiting'),
        try_timers={},
    )
    mock_itask.state.return_value = is_waiting
    mock_itask.prereqs_are_satisfied = Mock(return_value=prereqs)
    mock_itask.state.external_triggers_all_satisfied.return_value = ext_trigs
    mock_itask.state.xtriggers_all_satisfied.return_value = xtrigs
    assert TaskProxy.is_ready_to_run(mock_itask) is expected


@pytest.mark.parametrize(
    'name_str, expected',
    [('beer', True),
     ('FAM', True),
     ('root', True),
     ('horse', False),
     ('F*', True),
     ('*', True)]
)
def test_name_match(name_str: str, expected: bool):
    """Test TaskProxy.name_match().

    For a task named "beer" in family "FAM".
    """
    mock_tdef = Mock(namespace_hierarchy=['root', 'FAM', 'beer'])
    mock_tdef.name = 'beer'
    mock_itask = Mock(tdef=mock_tdef)

    assert TaskProxy.name_match(mock_itask, name_str) is expected


@pytest.mark.parametrize(
    'status_str, expected',
    [param('waiting', True, id="Basic"),
     param('w*', False, id="Globs don't work"),
     param(None, True, id="None always matches")]
)
def test_status_match(status_str: Optional[str], expected: bool):
    """Test TaskProxy.status_match().

    For a task with status "waiting".
    """
    mock_itask = Mock(state=Mock(status='waiting'))

    assert TaskProxy.status_match(mock_itask, status_str) is expected


@pytest.mark.parametrize('itask_flow_nums, flow_nums, expected', [
    param({1, 2}, {2}, {2}, id="subset"),
    param({2}, {1, 2}, {2}, id="superset"),
    param({1, 2}, {3, 4}, set(), id="disjoint"),
    param({1, 2}, set(), {1, 2}, id="all-matches-num"),
    param(set(), {1, 2}, set(), id="num-doesnt-match-none"),
    param(set(), set(), set(), id="all-doesnt-match-none"),
])
def test_match_flows(
    itask_flow_nums: FlowNums, flow_nums: FlowNums, expected: FlowNums
):
    mock_itask = Mock(flow_nums=itask_flow_nums)
    assert TaskProxy.match_flows(mock_itask, flow_nums) == expected


def test_match_flows_copy():
    """Test that this method does not return the same reference as
    itask.flow_nums, otherwise you could end up unexpectedly mutating
    itask.flow_nums."""
    mock_itask = Mock(flow_nums={1, 2})
    result = TaskProxy.match_flows(mock_itask, set())
    assert result == mock_itask.flow_nums
    assert result is not mock_itask.flow_nums


def test_job_tokens():
    itask = TaskProxy(
        Tokens('wflow'),
        TaskDef('foo', {}, None, None),
        IntegerPoint('10'),
        submit_num=3,
    )
    assert str(itask.job_tokens) == 'wflow//10/foo/03'
