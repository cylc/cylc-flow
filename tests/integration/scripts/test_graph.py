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

from cylc.flow.option_parsers import Options
from cylc.flow.scripts.graph import _main, get_option_parser


Opts = Options(get_option_parser())


@pytest.fixture
def disable_graph_open(monkeypatch):
    """Prevent "cylc graph" from trying to pop open the image."""
    monkeypatch.setattr(
        'cylc.flow.scripts.graph.open_image',
        lambda *_a, **_k: None,
    )


async def test_blank_graph(one, disable_graph_open, capsys):
    """It should inform the user if there are no tasks to display."""
    # graph with one task
    await _main(Opts(color='never'), one.tokens.id)
    out, err = capsys.readouterr()
    assert 'Graph rendered to' in out

    # graph with no tasks (the only task is in cycle "1")
    await _main(Opts(color='never'), one.tokens.id, '5')
    out, err = capsys.readouterr()
    assert 'No tasks to display' in err
    assert 'Try changing the start and stop values' in err
