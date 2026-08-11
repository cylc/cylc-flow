# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) Earth Sciences New Zealand & British Crown (Met Office)
# & Contributors.
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


async def test_flatten_icp(flow, tmp_path):
    """It should flatten out absolute dependencies in the ICP.

    Tests the "--flatten-icp" flag.
    """
    id_ = flow({
        'scheduler': {
            'cycle point format': 'CCYY',
        },
        'scheduling': {
            'initial cycle point': '2000',
            'final cycle point': '2004',
            'graph': {
                'R1': 'start',
                'P1Y': 'start[^] => foo => bar',  # ICP dep (^)
                'R1/2003': 'foo[2001] => pub',  # non-ICP ABS dep (2001)
            },
        },
    })
    graph_file = tmp_path / 'graph.dot'

    # test default behaviour (expanded ICP deps):
    await _main(
        Opts(output=str(graph_file), flatten_icp_dependence=False),
        id_,
        '2000',
        '2003',
    )
    with open(graph_file, 'r') as graph_file_:
        edges = {line.strip() for line in graph_file_ if '->' in line}

    assert edges == {
        '"2000/foo" -> "2000/bar"',
        '"2000/start" -> "2000/foo"',  # NOTE: inter-cycle ICP dep
        '"2000/start" -> "2001/foo"',  # NOTE: ICP dep
        '"2000/start" -> "2002/foo"',  # NOTE: ICP dep
        '"2000/start" -> "2003/foo"',  # NOTE: ICP dep
        '"2001/foo" -> "2001/bar"',
        '"2001/foo" -> "2003/pub"',
        '"2002/foo" -> "2002/bar"',
        '"2003/foo" -> "2003/bar"',
    }

    # test "--flatten-icp" behaviour:
    await _main(
        Opts(output=str(graph_file), flatten_icp_dependence=True),
        id_,
        '2000',
        '2003',
    )
    with open(graph_file, 'r') as graph_file_:
        edges = {line.strip() for line in graph_file_ if '->' in line}

    assert edges == {
        '"2000/foo" -> "2000/bar"',
        '"2000/start" -> "2000/foo"',
        '"2001/foo" -> "2001/bar"',
        '"2001/foo" -> "2003/pub"',  # NOTE: not flattened (non-ICP abs dep)
        '"2002/foo" -> "2002/bar"',
        '"2003/foo" -> "2003/bar"',
        '"R1.2001/start" -> "2001/foo"',  # NOTE: ICP dep flattened
        '"R1.2002/start" -> "2002/foo"',  # NOTE: ICP dep flattened
        '"R1.2003/start" -> "2003/foo"',  # NOTE: ICP dep flattened
    }
