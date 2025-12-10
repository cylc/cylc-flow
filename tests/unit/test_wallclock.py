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

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from metomi.isodatetime.data import CALENDAR
import pytest
from pytest import param

from cylc.flow.wallclock import (
    get_current_time_string,
    get_time_string,
    get_unix_time_from_time_string,
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


@pytest.mark.parametrize('tz_info', [
    pytest.param(None, id="naive"),
    pytest.param(timezone.utc, id="utc-tz-aware"),
    pytest.param(timezone(timedelta(hours=5)), id="custom-tz-aware"),
])
def test_get_time_string_tzinfo(tz_info, monkeypatch: pytest.MonkeyPatch):
    """Basic check it handles naive and timezone-aware datetime objects.

    Currently we just ignore the timezone information in the datetime object.
    """
    # Mock UTC time zone:
    monkeypatch.setattr(
        'cylc.flow.wallclock.TIME_ZONE_LOCAL_UTC_OFFSET', (0, 0)
    )
    for fmt in ('BASIC', 'EXTENDED'):
        monkeypatch.setattr(
            f'cylc.flow.wallclock.TIME_ZONE_STRING_LOCAL_{fmt}', 'Z'
        )

    assert get_time_string(
        datetime(2077, 2, 8, 13, 42, 39, 123456, tz_info)
    ) == '2077-02-08T13:42:39Z'


def test_get_current_time_string(set_timezone):
    """It reacts to local time zone changes.

    https://github.com/cylc/cylc-flow/issues/6701
    """
    set_timezone()
    res = get_current_time_string()
    assert res[-6:] == '+19:17'


@pytest.mark.parametrize(
    'arg, kwargs, expect',
    (
        param(
            datetime(2000, 12, 13, 15, 30, 12, 123456),
            {},
            '2000-12-14T10:47:12+19:17',
            id='good',
        ),
        param(
            datetime(2000, 12, 13, 15, 30, 12, 123456),
            {'date_time_is_local': True},
            '2000-12-13T15:30:12+19:17',
            id='dt_is_local',
        ),
        param(
            datetime(2000, 12, 13, 15, 30, 12, 123456),
            {
                'custom_time_zone_info': {
                    'hours': 0,
                    'minutes': -20,
                    'string_basic': 'XXX+00:20',
                },
                'use_basic_format': True
            },
            '20001213T151012XXX+00:20',
            id='custom_time_zone_info_string_basic',
        ),
        param(
            datetime(2000, 12, 13, 15, 30, 12, 123456),
            {
                'custom_time_zone_info': {
                    'hours': 0,
                    'minutes': -20,
                    'string_extended': ':UK/Exeter',
                },
                'use_basic_format': False
            },
            '2000-12-13T15:10:12:UK/Exeter',
            id='custom_time_zone_info_string_extended',
        ),
        param(
            datetime(2000, 12, 13, 15, 30, 12, 123456),
            {
                'custom_time_zone_info': {
                    'hours': 0,
                    'minutes': -20,
                    'string_extended': ':UK/Exeter',
                },
                'use_basic_format': False,
                'date_time_is_local': True,
            },
            '2000-12-12T19:53:12:UK/Exeter',
            id='date_time_is_local',
        ),
    ),
)
def test_get_time_string(set_timezone, arg, kwargs, expect):
    set_timezone()
    assert get_time_string(arg, **kwargs) == expect
