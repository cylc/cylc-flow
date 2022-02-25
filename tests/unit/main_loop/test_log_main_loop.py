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

from collections import deque
from pathlib import Path

import pytest

from cylc.flow.main_loop.log_main_loop import (
    _normalise,
    _dump,
    _plot
)


@pytest.fixture()
def test_data():
    return {
        # (plugin_name, coro_name): deque([(start_time, duration), ...])
        ('foo', 'bar'): deque([(2, 1), (3, 2), (4, 3)]),
        ('baz', 'pub'): deque([(1, 4), (2, 5), (3, 6)]),
    }


def test_normalise(test_data):
    """Ensure we correctly normalise the timings against the earliest time."""
    assert _normalise(test_data) == {
        'foo': [(1, 1), (2, 2), (3, 3)],
        'baz': [(0, 4), (1, 5), (2, 6)],
    }


def test_dump(test_data, tmp_path):
    """Ensure the data is serialisable."""
    assert _dump(_normalise(test_data), tmp_path)
    assert list(tmp_path.iterdir()) == [
        Path(tmp_path, 'cylc.flow.main_loop.log_main_loop.json')
    ]


def test_plot(test_data, tmp_path):
    """Ensure the plotting mechanism doesn't raise errors."""
    assert _plot(_normalise(test_data), tmp_path)
    assert list(tmp_path.iterdir()) == [
        Path(tmp_path, 'cylc.flow.main_loop.log_main_loop.pdf')
    ]
