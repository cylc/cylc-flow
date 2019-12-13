# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
# Tests for the platform lookup.

import pytest
from cylc.flow.platform_lookup import forward_lookup
from cylc.flow.exceptions import PlatformLookupError

PLATFORMS_STANDARD = {
    'suite server platform': None,
    'desktop[0-9][0-9]|laptop[0-9][0-9]': None,
    'sugar': {
        'login hosts': 'localhost',
        'batch system': 'slurm'
    },
    'hpc': {
        'login hosts': ['hpc1', 'hpc2'],
        'batch system': 'pbs'
    },
    'hpc1-bg': {
        'login hosts': 'hpc1',
        'batch system': 'background'
    },
    'hpc2-bg': {
        'login hosts': 'hpc2',
        'batch system': 'background'
    }
}

PLATFORMS_NO_UNIQUE = {
    'sugar': {
        'login hosts': 'localhost',
        'batch system': 'slurm'
    },
    'pepper': {
        'login hosts': ['hpc1', 'hpc2'],
        'batch system': 'slurm'
    },

}

PLATFORMS_WITH_RE = {
    'hpc.*': {'login hosts': 'hpc1', 'batch system': 'background'},
    'h.*': {'login hosts': 'hpc3'},
    r'vld\d{2,3}': None,
    'nu.*': {'batch system': 'slurm'}
}


@pytest.mark.parametrize(
    "PLATFORMS, platform, expected",
    [(PLATFORMS_WITH_RE, 'nutmeg', 'nutmeg'),
     (PLATFORMS_WITH_RE, 'vld798', 'vld798'),
     (PLATFORMS_WITH_RE, 'vld56', 'vld56'),
     (PLATFORMS_NO_UNIQUE, 'sugar', 'sugar'),
     (PLATFORMS_STANDARD, None, 'localhost'),
     (PLATFORMS_STANDARD, 'laptop22', 'laptop22'),
     (PLATFORMS_STANDARD, 'hpc1-bg', 'hpc1-bg'),
     (PLATFORMS_WITH_RE, 'hpc2', 'hpc2')
     ]
)
def test_basic(PLATFORMS, platform, expected):
    assert forward_lookup(PLATFORMS, platform) == expected


def test_platform_not_there():
    with pytest.raises(PlatformLookupError):
        forward_lookup(PLATFORMS_STANDARD, 'moooo')


def test_similar_but_not_exact_match():
    with pytest.raises(PlatformLookupError):
        forward_lookup(PLATFORMS_WITH_RE, 'vld1')
