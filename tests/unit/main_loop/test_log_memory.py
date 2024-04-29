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

from pathlib import Path
from unittest.mock import Mock

import pytest


try:
    from cylc.flow.main_loop.log_memory import (
        _compute_sizes,
        _transpose,
        _dump,
        _plot
    )
except ModuleNotFoundError as exc:
    if exc.name == 'pympler':
        pytest.skip(
            'pympler required for these tests',
            allow_module_level=True
        )
    else:
        raise


def test_compute_sizes():
    """Test the interface for the calculation of instance attribute sizes."""
    keys = {
        'a': [],
        'b': 42,
        'c': 'beef wellington'
    }
    test_object = Mock(**keys)
    # no fields should be larger than 10kb
    sizes = _compute_sizes(test_object, 10000)
    sizes.pop('total')
    assert sizes == {}
    # all fields should be larger than 0kb
    ret = _compute_sizes(test_object, 0)
    assert {
        key
        for key, value in ret.items()
        # filter out mock fields
        if not key.startswith('_')
        and key not in ('method_calls', 'total')
    } == set(keys)


@pytest.fixture()
def test_data():
    return [
        (5, {'a': 1, 'b': 2, 'c': 3}),
        (6, {'a': 2, 'c': 4}),
        (7, {'a': 5, 'c': 2})
    ]


def test_transpose(test_data):
    """Test transposing the data from bin to series orientated."""
    assert _transpose(test_data) == (
        {
            # the keys are sorted by their last entry
            'a': [1, 2, 5],
            'c': [3, 4, 2],
            'b': [2, -1, -1]  # missing values become -1
        },
        [0, 1, 2]
    )


def test_dump(test_data, tmp_path):
    """Ensure the data is serialiseable."""
    _dump(test_data, tmp_path)
    assert list(tmp_path.iterdir()) == [
        Path(tmp_path, 'cylc.flow.main_loop.log_memory.json')
    ]


def test_plot(test_data, tmp_path):
    """Ensure the plotting mechanism doesn't raise errors."""
    fields, times = _transpose(test_data)
    _plot(fields, times, tmp_path)
    assert list(tmp_path.iterdir()) == [
        Path(tmp_path, 'cylc.flow.main_loop.log_memory.pdf')
    ]
