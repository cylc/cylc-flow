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
from cylc.flow.cycling.integer import IntegerPoint
from cylc.flow.cycling.iso8601 import ISO8601Point
from cylc.flow.task_proxy import TaskProxy


@pytest.mark.parametrize(
    'itask_point, point_str, expected',
    [param(IntegerPoint(5), '5', True, id="Integer, basic"),
     param(IntegerPoint(5), '*', True, id="Integer, glob"),
     param(IntegerPoint(5), None, True, id="None same as glob(*)"),
     param(ISO8601Point('2012'), '2012-01-01', True, id="ISO, basic"),
     param(ISO8601Point('2012'), '2012*', True, id="ISO, glob"),
     param(ISO8601Point('2012'), '2012-*', False,
           id="ISO, bad glob (must use short datetime format)")]
)
def test_point_match(
    itask_point: PointBase, point_str: Optional[str], expected: bool,
    set_cycling_type: Callable
) -> None:
    """Test TaskProxy.point_match()."""
    set_cycling_type(itask_point.TYPE)
    mock_itask = Mock(point=itask_point.standardise())

    assert TaskProxy.point_match(mock_itask, point_str) is expected


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
