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
    assert _compute_sizes(test_object, 10000) == {}
    # all fields should be larger than 0kb
    ret = _compute_sizes(test_object, 0)
    assert {
        key
        for key, value in ret.items()
        # filter out mock fields
        if not key.startswith('_')
        and key != 'method_calls'
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
