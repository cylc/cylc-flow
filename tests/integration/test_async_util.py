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
from shutil import rmtree

import pytest

from cylc.flow.async_util import scandir


@pytest.fixture()
def directory(tmp_path):
    """A directory with two files and a symlink."""
    (tmp_path / 'a').touch()
    (tmp_path / 'b').touch()
    (tmp_path / 'c').symlink_to(tmp_path / 'b')
    yield tmp_path
    rmtree(tmp_path)


async def test_scandir(directory):
    """It should list directory contents (including symlinks)."""
    assert sorted(await scandir(directory)) == [
        Path(directory, 'a'),
        Path(directory, 'b'),
        Path(directory, 'c')
    ]
