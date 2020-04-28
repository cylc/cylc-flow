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

"""Tests for cylc.flow.network.schema"""

import asyncio
from types import AsyncGeneratorType

from cylc.flow.network.schema import to_subscription


def test_to_subscription():
    """Test to_subscription function."""
    async def async_callable():
        return []

    assert asyncio.iscoroutine(async_callable())

    async_generator = to_subscription(async_callable)

    assert not asyncio.iscoroutine(async_generator())
    assert isinstance(async_generator(), AsyncGeneratorType)
