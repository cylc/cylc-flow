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

"""Test cycling utils."""
import pytest

from cylc.flow.cycling.util import add_offset


def test_add_offset():
    """Test socket start."""
    orig_point = '20200202T0000Z'
    plus_offset = '+PT02H02M'
    assert str(add_offset(orig_point, plus_offset)) == '20200202T0202Z'
    minus_offset = '-P1MT22H59M'
    assert str(add_offset(orig_point, minus_offset)) == '20200101T0101Z'
    assert str(
        add_offset(orig_point, minus_offset, dmp_fmt="CCYY-MM-DDThh:mmZ")
    ) == '2020-01-01T01:01Z'
    bad_offset = '+foo'
    with pytest.raises(ValueError, match=r'ERROR, bad offset format'):
        add_offset(orig_point, bad_offset)
