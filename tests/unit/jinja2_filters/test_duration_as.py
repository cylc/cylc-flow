# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) 2008-2019 NIWA
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

from cylc.flow.jinja.filters.duration_as import duration_as

import pytest


@pytest.mark.parametrize(
    'duration,fmt,result',
    [
        pytest.param('PT1H', 's', 3600, id='PT1H->s'),
        pytest.param('PT1H', 'm', 60, id='PT1H->m'),
        pytest.param('PT1H', 'h', 1, id='PT1H->h'),
        pytest.param('PT1H', 'd', 1 / 24, id='PT1H->d'),
        pytest.param('PT1H', 'w', 1 / (24 * 7), id='PT1H->w'),
        pytest.param('P7D', 'd', 7, id='P7D->d'),
        pytest.param('P7D', 's', 604800, id='P7D->s'),
    ]
)
def test_all(duration, fmt, result):
    assert duration_as(duration, fmt) == result
