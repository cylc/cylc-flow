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

from metomi.isodatetime.data import CALENDAR
from cylc.flow.wallclock import (
    get_unix_time_from_time_string,
    get_current_time_string,
)


@pytest.mark.parametrize(
    'time_str,time_sec',
    [
        ('2016-09-08T09:09:00+01', 1473322140),
        ('2016-09-08T08:09:00Z', 1473322140),
        ('2016-09-07T20:09:00-12', 1473322140),
    ]
)
def test_get_unix_time_from_time_string(time_str, time_sec):
    assert get_unix_time_from_time_string(time_str) == time_sec


@pytest.mark.parametrize(
    'time_str,time_sec',
    [
        ('2016-09-08T09:09:00+01', 1473322140),
        ('2016-09-08T08:09:00Z', 1473322140),
        ('2016-09-07T20:09:00-12', 1473322140),
        ('2016-08-31T18:09:00+01', 1472663340),
    ]
)
def test_get_unix_time_from_time_string_360(time_str, time_sec):
    mode = CALENDAR.mode
    CALENDAR.set_mode(CALENDAR.MODE_360)
    try:
        assert get_unix_time_from_time_string(time_str) == time_sec
    finally:
        CALENDAR.set_mode(mode)


@pytest.mark.parametrize(
    'value,error',
    [
        (None, TypeError),
        (42, TypeError)
    ]
)
def test_get_unix_time_from_time_string_error(value, error):
    with pytest.raises(error):
        get_unix_time_from_time_string(value)


def test_get_current_time_string(set_timezone):
    """It reacts to local time zone changes.

    https://github.com/cylc/cylc-flow/issues/6701
    """
    set_timezone()
    res = get_current_time_string()
    assert res[-6:] == '+19:17'
