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
from typing import Optional, Tuple

from cylc.flow.task_pool import TaskPool


@pytest.mark.parametrize(
    'item, expected',
    [('foo', (None, 'foo', None)),
     ('foo.*', ('*', 'foo', None)),
     ('foo.*:failed', ('*', 'foo', 'failed')),
     ('foo:failed', (None, 'foo', 'failed')),
     ('3/foo:failed', ('3', 'foo', 'failed'))]
)
def test_parse_task_item(
    item: str, expected: Tuple[Optional[str], str, Optional[str]]
) -> None:
    assert TaskPool._parse_task_item(item) == expected
