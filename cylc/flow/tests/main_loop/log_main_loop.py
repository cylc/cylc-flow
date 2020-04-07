from collections import deque
from pathlib import Path

import pytest

from cylc.flow.main_loop.log_main_loop import (
    _transpose,
    _normalise,
    _dump,
    _plot
)


@pytest.fixture()
def test_data():
    return {
        'foo': {
            'timings': deque([(1, 'a'), (2, 'b'), (3, 'c')]),
            'some other var': None
        },
        'bar': {
            'timings': deque()
        },
        'baz': {
            'timings': deque([(4, 'd')])
        }
    }


def test_transpose(test_data):
    """Ensure we can orient the data around main-loop-time/plugin-time."""
    assert _transpose(test_data) == {
        'baz': ((4,), ('d',)),
        'foo': ((1, 2, 3), ('a', 'b', 'c'))
    }


def test_normalise(test_data):
    """Ensure we correctly normalise the timings against the earliest time."""
    assert _normalise(_transpose(test_data)) == {
        'baz': ((3,), ('d',)),
        'foo': ((0, 1, 2), ('a', 'b', 'c'))
    }


def test_dump(test_data, tmp_path):
    """Ensure the data is serialiseable."""
    assert _dump(_transpose(test_data), tmp_path)
    assert list(tmp_path.iterdir()) == [
        Path(tmp_path, 'cylc.flow.main_loop.log_main_loop.json')
    ]


def test_plot(test_data, tmp_path):
    """Ensure the plotting mechanism doesn't raise errors."""
    assert _plot(_transpose(test_data), tmp_path)
    assert list(tmp_path.iterdir()) == [
        Path(tmp_path, 'cylc.flow.main_loop.log_main_loop.pdf')
    ]
