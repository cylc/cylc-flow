# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (C) 2013-2019 British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# ----------------------------------------------------------------------------
"""Test isodatetime.parsers."""

import pytest

from isodatetime.parsers import TimePointParser


def test_invalid_components():
    parser = TimePointParser()
    for date, invalid in {
        '2000-01-01T00:00:60': ['second_of_minute=60'],
        '2000-01-01T00:60:00': ['minute_of_hour=60'],
        '2000-01-01T60:00:00': ['hour_of_day=60'],
        '2000-01-32T00:00:00': ['day_of_month=32'],
        '2000-13-00T00:00:00': ['month_of_year=13'],
        '2000-13-32T60:60:60': ['month_of_year=13',
                                'day_of_month=32',
                                'hour_of_day=60',
                                'minute_of_hour=60',
                                'second_of_minute=60']
    }.items():
        with pytest.raises(ValueError) as exc:
            parser.parse(date)
        for item in invalid:
            assert item in str(exc)
