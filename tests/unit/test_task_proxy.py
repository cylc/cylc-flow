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

import pytest
from pytest import param
from typing import Callable, Optional
from unittest.mock import Mock

from cylc.flow.cycling import PointBase
from cylc.flow.cycling.iso8601 import ISO8601Point
from cylc.flow.task_proxy import TaskProxy


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
