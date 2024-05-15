#!/usr/bin/env python3

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

from typing import Callable, List, Type, Union

import pytest

from cylc.flow.exceptions import InputError
from cylc.flow.scripts.clean import (
    CleanOptions, _main, parse_timeout, scan, run
)


async def test_scan(tmp_run_dir):
    """It should scan the filesystem to expand partial IDs."""
    # regular workflows pass straight through
    tmp_run_dir('foo')
    workflows, multi_mode = await scan(['foo'], False)
    assert workflows == ['foo']
    assert multi_mode is False

    # hierarchies, however, get expanded
    tmp_run_dir('bar/run1')
    workflows, multi_mode = await scan(['bar'], False)
    assert workflows == ['bar/run1']
    assert multi_mode is True  # because an expansion has happened

    tmp_run_dir('bar/run2')
    workflows, multi_mode = await scan(['bar'], False)
    assert workflows == ['bar/run1', 'bar/run2']
    assert multi_mode is True


@pytest.fixture
def mute(monkeypatch: pytest.MonkeyPatch) -> List[str]:
    """Stop cylc clean from doing anything and log all init_clean calls."""
    items = []

    def _clean(id_, *_):
        nonlocal items
        items.append(id_)

    monkeypatch.setattr('cylc.flow.scripts.clean.init_clean', _clean)
    monkeypatch.setattr('cylc.flow.scripts.clean.prompt', lambda x: None)

    return items


async def test_multi(tmp_run_dir: Callable, mute: List[str]):
    """It supports cleaning multiple workflows."""
    # cli opts
    opts = CleanOptions()

    # create three dummy workflows
    tmp_run_dir('bar/pub/beer')
    tmp_run_dir('baz/run1')
    tmp_run_dir('foo')

    # an explicit workflow ID goes straight through
    mute.clear()
    await run('foo', opts=opts)
    assert mute == ['foo']

    # a partial hierarchical ID gets expanded to all workflows contained
    # in the hierarchy (note runs are a special case of hierarchical ID)
    mute.clear()
    await run('bar', opts=opts)
    assert mute == ['bar/pub/beer']

    # test a mixture of explicit and partial IDs
    mute.clear()
    await run('bar', 'baz', 'foo', opts=opts)
    assert mute == ['bar/pub/beer', 'baz/run1', 'foo']

    # test a glob
    mute.clear()
    await run('*', opts=opts)
    assert mute == ['bar/pub/beer', 'baz/run1', 'foo']


@pytest.mark.parametrize(
    'timeout, expected',
    [('100', '100'),
     ('PT1M2S', '62'),
     ('', ''),
     ('oopsie', InputError),
     (' ', InputError)]
)
def test_parse_timeout(
    timeout: str,
    expected: Union[str, Type[InputError]]
):
    """It should accept ISO 8601 format or number of seconds."""
    opts = CleanOptions(remote_timeout=timeout)

    if expected is InputError:
        with pytest.raises(expected):
            parse_timeout(opts)
    else:
        parse_timeout(opts)
        assert opts.remote_timeout == expected


@pytest.mark.parametrize(
    'opts, expected_msg',
    [
        ({'local_only': True, 'remote_only': True}, "mutually exclusive"),
        ({'remote_timeout': 'oops'}, "Invalid timeout"),
    ]
)
def test_bad_user_input(opts: dict, expected_msg: str, mute):
    """It should raise an InputError for bad user input."""
    with pytest.raises(InputError) as exc_info:
        _main(CleanOptions(**opts), 'blah')
    assert expected_msg in str(exc_info.value)
