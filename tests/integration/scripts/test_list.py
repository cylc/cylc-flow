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

"""Test the "cylc list" command."""

import pytest

from cylc.flow.exceptions import InputError
from cylc.flow.option_parsers import Options
from cylc.flow.scripts.list import (
    get_option_parser,
    _main,
)


ListOptions = Options(get_option_parser())


@pytest.fixture(scope='module')
async def cylc_list(mod_flow, mod_scheduler, mod_start):
    id_ = mod_flow(
        {
            'scheduling': {
                # NOTE: all "a*" tasks are in the graph, but not "b*" tasks
                'initial cycle point': 1,
                'cycling mode': 'integer',
                'graph': {'P1': 'a12 & a111 & a112 & a121 & a2'},
            },
            'runtime': {
                'A': {'meta': {'title': 'Title For A'}},
                'A1': {'inherit': 'A'},
                'A11': {'inherit': 'A1', 'meta': {'title': 'Title For A11'}},
                'A12': {'inherit': 'A1'},
                'a2': {'inherit': 'A'},
                'a12': {'inherit': 'A1'},
                'a111': {'inherit': 'A11'},
                'a112': {'inherit': 'A11'},
                'a121': {'inherit': 'A12'},
                'B': {},
                'b1': {'inherit': 'B'},
            },
        }
    )
    schd = mod_scheduler(id_)

    async def _list(capsys, **kwargs):
        nonlocal schd
        capsys.readouterr()
        await _main(ListOptions(**kwargs), schd.workflow)
        out, err = capsys.readouterr()
        return out.splitlines()

    async with mod_start(schd):
        yield _list


@pytest.fixture
def supports_utf8(monkeypatch):
    monkeypatch.setenv('LANG', 'C.utf-8')


@pytest.fixture
def does_not_support_utf8(monkeypatch):
    monkeypatch.setenv('LANG', 'C')


async def test_plain(cylc_list, supports_utf8, capsys):
    """Test the default output format."""
    assert await cylc_list(capsys) == [
        'a111',
        'a112',
        'a12',
        'a121',
        'a2',
    ]

    assert await cylc_list(capsys, all_tasks=True) == [
        'a111',
        'a112',
        'a12',
        'a121',
        'a2',
        'b1',  # <= in the runtime but not in the graph
    ]

    assert await cylc_list(capsys, all_namespaces=True) == [
        'A',
        'A1',
        'A11',
        'A12',
        'B',
        'a111',
        'a112',
        'a12',
        'a121',
        'a2',
        'b1',
        'root',
    ]

    with pytest.raises(InputError):
        await cylc_list(capsys, all_tasks=True, all_namespaces=True)


async def test_mro(cylc_list, supports_utf8, capsys):
    """Test the --mro option."""
    assert await cylc_list(capsys, mro=True) == [
        'a111  a111 A11 A1 A root',
        'a112  a112 A11 A1 A root',
        'a12   a12 A1 A root',
        'a121  a121 A12 A1 A root',
        'a2    a2 A root',
    ]

    assert await cylc_list(capsys, mro=True, all_tasks=True) == [
        'a111  a111 A11 A1 A root',
        'a112  a112 A11 A1 A root',
        'a12   a12 A1 A root',
        'a121  a121 A12 A1 A root',
        'a2    a2 A root',
        'b1    b1 B root',
    ]

    assert await cylc_list(capsys, mro=True, all_namespaces=True) == [
        'A     A root',
        'A1    A1 A root',
        'A11   A11 A1 A root',
        'A12   A12 A1 A root',
        'B     B root',
        'a111  a111 A11 A1 A root',
        'a112  a112 A11 A1 A root',
        'a12   a12 A1 A root',
        'a121  a121 A12 A1 A root',
        'a2    a2 A root',
        'b1    b1 B root',
        'root  root',
    ]

    with pytest.raises(InputError):
        await cylc_list(capsys, titles=True, mro=True)



async def test_tree(cylc_list, supports_utf8, capsys):
    """Test the --tree option."""
    assert (
        await cylc_list(capsys, tree=True)
        # NOTE: the --all-tasks and --all-namespaces opts should be ignored
        == await cylc_list(capsys, tree=True, all_tasks=True)
        == await cylc_list(capsys, tree=True, all_namespaces=True)
        == [
            'root ',
            ' `-A ',
            '   |-A1 ',
            '   | |-A11 ',
            '   | | |-a111 ',
            '   | | `-a112 ',
            '   | |-A12 ',
            '   | | `-a121 ',
            '   | `-a12 ',
            '   `-a2 ',
        ]
    )

    assert (
        await cylc_list(capsys, tree=True, box=True)
        == await cylc_list(capsys, box=True)  # --tree implicit with --box
        == [
            'root ',
            ' └─A ',
            '   ├─A1 ',
            '   │ ├─A11 ',
            '   │ │ ├─a111 ',
            '   │ │ └─a112 ',
            '   │ ├─A12 ',
            '   │ │ └─a121 ',
            '   │ └─a12 ',
            '   └─a2 ',
        ]
    )

    assert await cylc_list(capsys, tree=True, titles=True) == [
        'root          ',
        ' `-A          ',
        '   |-A1       ',
        '   | |-A11    ',
        '   | | |-a111 Title For A11',
        '   | | `-a112 Title For A11',
        '   | |-A12    ',
        '   | | `-a121 Title For A',
        '   | `-a12    Title For A',
        '   `-a2       Title For A',
    ]

    assert await cylc_list(capsys, tree=True, box=True, titles=True) == [
        'root          ',
        ' └─A          ',
        '   ├─A1       ',
        '   │ ├─A11    ',
        '   │ │ ├─a111 Title For A11',
        '   │ │ └─a112 Title For A11',
        '   │ ├─A12    ',
        '   │ │ └─a121 Title For A',
        '   │ └─a12    Title For A',
        '   └─a2       Title For A',
    ]


async def test_box_with_lang_c(cylc_list, does_not_support_utf8, capsys):
    """It falls back to plain output if unicode support isn't there."""
    assert await cylc_list(capsys, tree=True, box=True) == [
        'a111',
        'a112',
        'a12',
        'a121',
        'a2',
    ]


async def test_titles(cylc_list, supports_utf8, capsys):
    """Test the --titles option."""
    assert await cylc_list(capsys, titles=True) == [
        'a111  Title For A11',
        'a112  Title For A11',
        'a12   Title For A',
        'a121  Title For A',
        'a2    Title For A',
    ]

    assert await cylc_list(capsys, titles=True, all_tasks=True) == [
        'a111  Title For A11',
        'a112  Title For A11',
        'a12   Title For A',
        'a121  Title For A',
        'a2    Title For A',
        'b1    ',
    ]

    assert await cylc_list(capsys, titles=True, all_namespaces=True) == [
        'A     Title For A',
        'A1    Title For A',
        'A11   Title For A11',
        'A12   Title For A',
        'B     ',
        'a111  Title For A11',
        'a112  Title For A11',
        'a12   Title For A',
        'a121  Title For A',
        'a2    Title For A',
        'b1    ',
        'root  ',
    ]


async def test_points(cylc_list, supports_utf8, capsys):
    """Test the --points option."""
    # specify start and stop points
    assert await cylc_list(capsys, prange='1,2') == [
        '1/a111',
        '1/a112',
        '1/a12',
        '1/a121',
        '1/a2',
        '2/a111',
        '2/a112',
        '2/a12',
        '2/a121',
        '2/a2',
    ]

    # leave start and stop points implicit
    assert await cylc_list(capsys, prange=',') == [
        '1/a111',
        '1/a112',
        '1/a12',
        '1/a121',
        '1/a2',
        '2/a111',
        '2/a112',
        '2/a12',
        '2/a121',
        '2/a2',
        '3/a111',
        '3/a112',
        '3/a12',
        '3/a121',
        '3/a2',
    ]

    # leave start point implicit
    assert await cylc_list(capsys, prange=',2') == [
        '1/a111',
        '1/a112',
        '1/a12',
        '1/a121',
        '1/a2',
        '2/a111',
        '2/a112',
        '2/a12',
        '2/a121',
        '2/a2',
    ]

    # leave stop point implicit
    assert await cylc_list(capsys, prange='4,') == [
        '4/a111',
        '4/a112',
        '4/a12',
        '4/a121',
        '4/a2',
        '5/a111',
        '5/a112',
        '5/a12',
        '5/a121',
        '5/a2',
        '6/a111',
        '6/a112',
        '6/a12',
        '6/a121',
        '6/a2',
    ]

    with pytest.raises(InputError):
        await cylc_list(capsys, prange='1,2', all_tasks=True)

    with pytest.raises(InputError):
        await cylc_list(capsys, prange='1,2', all_namespaces=True)
