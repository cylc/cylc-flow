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
from cylc.flow.platform_lookup import forward_lookup, reverse_lookup
from cylc.flow.exceptions import PlatformLookupError

# The platforms list for testing is set as a constant
# [platforms]
#     [[desktop\d\d|laptop\d\d]]
#         # hosts = platform name (default)
#         # Note: "desktop01" and "desktop02" are both valid and distinct platforms
#     [[sugar]]
#         hosts = localhost
#         batch system = slurm
#     [[hpc]]
#         hosts = hpcl1, hpcl2
#         retrieve job logs = True
#         batch system = pbs
#     [[hpcl1-bg]]
#         hosts = hpcl1
#         retrieve job logs = True
#         batch system = background
#     [[hpcl2-bg]]
#         hosts = hpcl2
#         retrieve job logs = True
#         batch system = background
PLATFORMS = {
    'suite server platform': None,
    'desktop\d\d|laptop\d\d': None,
    'sugar': {
        'login hosts': 'localhost',
        'batch system': 'slurm',
    },
    'hpc': {
        'login hosts': ['hpc1', 'hpc2'],
        'batch system': 'pbs',
    },
    'hpc1-bg': {
        'login hosts': 'hpc1',
        'batch system': 'background',
    },
    'hpc2-bg': {
        'login hosts': 'hpc2',
        'batch system': 'background'
    }
}

PLATFORMS_NO_UNIQUE = {
    'sugar': {
        'login hosts': 'localhost',
        'batch system': 'slurm',
    },
    'pepper': {
        'login hosts': ['hpc1', 'hpc2'],
        'batch system': 'slurm',
    },

}


PLATFORMS_WITH_RE = {
    # Mel - make up some amusing platforms doing wierd stuff with regexes
}


class TestForwardLookup():
    """
    Tests to ensure that the job platform forward lookup works as intended.
    """
    def test_basic(self):
        assert 1 == 1


class TestReverseLookup():
    """
    Tests to ensure that job platform reverse lookup works as intended.
    """
