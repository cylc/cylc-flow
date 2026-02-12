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

import pytest

try:
    from cylc.flow.main_loop.log_data_store import (
        _dump,
        _plot,
        _iter_data_store
    )
except ModuleNotFoundError as exc:
    if exc.name == 'pympler':
        pytest.skip(
            'pympler required for these tests',
            allow_module_level=True
        )
    else:
        raise


@pytest.fixture()
def test_data():
    return {
        'times': [1, 2, 3],
        'objects': {
            'foo': [4, 5, 6]
        },
        'size': {
            'foo': [7, 8, 9]
        }
    }


def test_dump(test_data, tmp_path):
    """Ensure the data is serialiseable."""
    assert _dump(test_data, tmp_path)
    assert list(tmp_path.iterdir()) == [
        Path(tmp_path, 'cylc.flow.main_loop.log_data_store.json')
    ]


def test_plot_no_data(tmp_path):
    """Ensure plotting skips if data insufficient."""
    assert not _plot({'times': [1]}, tmp_path)


def test_plot(test_data, tmp_path):
    """Ensure the plotting mechanism doesn't raise errors."""
    pytest.importorskip('matplotlib', reason='requires matplotlib')
    assert _plot(test_data, tmp_path)
    assert list(tmp_path.iterdir()) == [
        Path(tmp_path, 'cylc.flow.main_loop.log_data_store.pdf')
    ]


def test_iter_data_store():
    class DataStore:
        tracker = {'this': 'that'}
        data = {'x': {'a': 1, 'workflow': 2, 'c': 3}}
    ds = DataStore()
    assert (
        list(_iter_data_store(ds))
    ) == [
        ('data_store_mgr (total)', ds),
        ('tracker', {'this': 'that'}),
        ('data.a', 1),
        ('data.workflow', [2]),
        ('data.c', 3)
    ]
