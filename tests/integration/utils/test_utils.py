# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
"""Tests to ensure the tests are working - very meta.

https://github.com/cylc/cylc-flow/pull/2740#discussion_r206086008

And yes, these are unit-tests inside a functional test framework thinggy.

"""

from pathlib import Path

import pytest

from . import (
    _rm_if_empty,
    _poll_file,
    _expanduser
)


def test_rm_if_empty(tmp_path):
    """It should remove dirs if empty and suppress exceptions otherwise."""
    path1 = Path(tmp_path, 'foo')
    path2 = Path(path1, 'bar')
    path2.mkdir(parents=True)
    _rm_if_empty(path1)
    assert path2.exists()
    _rm_if_empty(path2)
    assert not path2.exists()
    _rm_if_empty(path1)
    assert not path1.exists()


@pytest.mark.asyncio
async def test_poll_file(tmp_path):
    """It should return if the condition is met."""
    path = tmp_path / 'file'
    await _poll_file(path, exists=False)
    path.touch()
    await _poll_file(path, exists=True)


def test_expanduser():
    """It should expand ~ and $HOME."""
    assert _expanduser('a/~/b') == Path('a/~/b').expanduser()
    assert _expanduser('a/$HOME/b') == Path('a/~/b').expanduser()
    assert _expanduser('a/${HOME}/b') == Path('a/~/b').expanduser()
