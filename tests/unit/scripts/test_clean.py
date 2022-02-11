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

from typing import Callable, List

import pytest

from cylc.flow.scripts.clean import CleanOptions, scan, run


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
