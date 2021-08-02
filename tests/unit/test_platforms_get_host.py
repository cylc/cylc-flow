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
#
# Tests for the get_host_from_platform lookup.

import pytest

from cylc.flow.platforms import get_host_from_platform, NoHostsError
from cylc.flow.exceptions import CylcError


TEST_PLATFORM = {
    'name': 'Elephant',
    'hosts': ['nellie', 'dumbo', 'jumbo'],
    'host selection method': 'definition order'
}


@pytest.mark.parametrize(
    'badhosts, expect',
    [
        pytest.param(None, 'nellie'),
        pytest.param({'nellie', 'dumbo'}, 'jumbo')
    ]
)
def test_get_host_from_platform(badhosts, expect):
    platform = TEST_PLATFORM
    assert get_host_from_platform(platform, badhosts) == expect


def test_get_host_from_platform_fails_no_goodhosts():
    platform = TEST_PLATFORM
    with pytest.raises(NoHostsError) as err:
        get_host_from_platform(platform, {'nellie', 'dumbo', 'jumbo'})
    assert err.exconly() == (
        'cylc.flow.exceptions.NoHostsError: '
        'Unable to find valid host for Elephant'
    )


def test_get_host_from_platform_fails_bad_method():
    platform = TEST_PLATFORM.copy()
    platform['host selection method'] = 'roulette'
    with pytest.raises(CylcError) as err:
        get_host_from_platform(platform, {'Elephant'})
    assert err.exconly() == (
        'cylc.flow.exceptions.CylcError: method "roulette" is not a '
        'supported host selection method.'
    )
