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
"""Tests for utilities supporting run modes.
"""

import pytest

from cylc.flow.run_modes import RunMode


def test_run_mode_desc():
    """All run mode labels have descriptions."""
    for mode in RunMode:
        assert mode.describe()


def test_get_default_live():
    """RunMode.get() => live"""
    assert RunMode.get({}) == RunMode.LIVE


@pytest.mark.parametrize('str_', ('LIVE', 'Dummy', 'SkIp', 'siMuLATioN'))
def test__missing_(str_):
    """The RunMode enumeration works when fed a string in the wrong case"""
    assert RunMode(str_).value == str_.lower()
