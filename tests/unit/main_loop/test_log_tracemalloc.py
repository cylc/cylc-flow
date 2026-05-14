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

from types import SimpleNamespace
from cylc.flow.main_loop.log_tracemalloc import take_snapshot, init, close_log

import pytest


# find the number of the MARKER line in this file
MARKER_LINE = None
with open(__file__, 'r') as this_file:
    for line_number, line in enumerate(this_file):
        print('$', line.strip())
        print('#', line[-7:].strip())
        if line[-7:] == 'MARKER\n':
            MARKER_LINE = line_number + 1
            break


@pytest.fixture
async def state(tmp_path):
    """A clean state object for this plugin."""
    state = {}
    await init(SimpleNamespace(workflow_run_dir=tmp_path), state)
    return state


async def test_tracemalloc(tmp_path, state):
    """Test the tracemalloc plugin functionality."""
    out_dir = tmp_path / 'tracemalloc'

    # test the empty state object
    assert state['itt'] == 0
    assert len(list(out_dir.iterdir())) == 1  # the tracemalloc folder
    assert state['log'].closed is False  # the log file is open

    # take a snapshot
    await take_snapshot(None, state, diff_filter=None)
    assert state['itt'] == 1, 'the iteration has been incremented'
    assert len(list(out_dir.iterdir())) == 2, 'dump file has been written'

    # allocate some memory
    _memory = [x for x in range(100)]  # MARKER

    # take another snapshot
    await take_snapshot(None, state, diff_filter=None)
    assert state['itt'] == 2, 'the iteration has been incremented'
    assert len(list(out_dir.iterdir())) == 3, 'dump file has been written'

    # close the log file
    await close_log(None, state)
    assert state['log'].closed is True, 'log file has been closed'

    # ensure the allocated memory appears in the log file
    with open(out_dir / 'log', 'r') as tracemalloc_file:
        tracemalloc_log = tracemalloc_file.read()
        assert f'{__file__}:{MARKER_LINE}' in tracemalloc_log

    del _memory  # make linters happy
