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
#
# Tests for the platform lookup.

import pytest
from cylc.flow.platforms import forward_lookup, reverse_lookup
from cylc.flow.exceptions import PlatformLookupError

PLATFORMS = {
    'desktop[0-9]{2}|laptop[0-9]{2}': {
        'batch system': 'background'
    },
    'sugar': {
        'remote hosts': 'localhost',
        'batch system': 'slurm',
    },
    'hpc': {
        'remote hosts': ['hpc1', 'hpc2'],
        'batch system': 'pbs',
    },
    'hpc1-bg': {
        'remote hosts': 'hpc1',
        'batch system': 'background',
    },
    'hpc2-bg': {
        'remote hosts': 'hpc2',
        'batch system': 'background'
    },
    'localhost': {
        'remote hosts': 'localhost',
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
    'nu.*': {'batch system': 'slurm'},
    'localhost': {
        'remote hosts': 'localhost',
        'batch system': 'background'
    }
}


@pytest.mark.parametrize(
    "PLATFORMS, platform, expected",
    [
        (PLATFORMS_WITH_RE, "nutmeg", {
            "batch system": "slurm",
            "name": "nutmeg"
        }),
        (PLATFORMS_WITH_RE, "vld798", "vld798"),
        (PLATFORMS_WITH_RE, "vld56", "vld56"),
        (
            PLATFORMS_NO_UNIQUE,
            "sugar",
            {
                "login hosts": "localhost",
                "batch system": "slurm",
                "name": "sugar"
            },
        ),
        (
            PLATFORMS,
            None,
            {
                "remote hosts": "localhost",
                "batch system": "background",
                "name": "localhost",
            },
        ),
        (PLATFORMS, "laptop22", {
            "batch system": "background",
            "name": "laptop22"
        }),
        (
            PLATFORMS,
            "hpc1-bg",
            {
                "remote hosts": "hpc1",
                "batch system": "background",
                "name": "hpc1-bg"
            },
        ),
        (PLATFORMS_WITH_RE, "hpc2", {"login hosts": "hpc3", "name": "hpc2"}),
    ],
)
def test_basic(PLATFORMS, platform, expected):
    platform = forward_lookup(platform_name=platform, platforms=PLATFORMS)
    if isinstance(expected, dict):
        assert platform == expected
    else:
        assert platform["remote hosts"] == expected


def test_platform_not_there():
    with pytest.raises(PlatformLookupError):
        forward_lookup('moooo', PLATFORMS)


def test_similar_but_not_exact_match():
    with pytest.raises(PlatformLookupError):
        forward_lookup('vld1', PLATFORMS_WITH_RE)


# Basic tests that we can select sensible platforms
@pytest.mark.parametrize(
    'job, remote, returns',
    [
        # Can we return a sensible platform for desktop 42
        (
            {},
            {'host': 'desktop42'},
            'desktop42'
        ),

        # Basic test where the user hasn't sumbitted anything and the task
        # returns to default, i.e. localhost.
        (
            {'batch system': 'background'},
            {'retrieve job logs retry delays': 'None'},
            'localhost'
        ),
        # Check that when the user asks for batch system = slurm alone
        # they get system = sugar
        (
            {'batch system': 'slurm'},
            {'host': ''},
            'sugar'
        ),
        # Check that when users asks for hpc1 and pbs they get a platform
        # with hpc1 in its list of login hosts
        (
            {'batch system': 'pbs'},
            {'host': 'hpc1'},
            'hpc'
        ),
        # When the user asks for hpc1 without specifying pbs user gets platform
        # hpc bg1
        (
            {'batch system': 'background'},
            {'host': 'hpc1'},
            'hpc1-bg'
        ),
    ]
)
def test_reverse_lookup_basic(job, remote, returns):
    assert reverse_lookup(PLATFORMS, job, remote) == returns


# Cases where the error ought to be raised because no matching platform should
# be found.
@pytest.mark.parametrize(
    'job, remote',
    [
        # Check for error when the user asks for slurm on host desktop01
        (
            {'batch system': 'slurm'},
            {'host': 'desktop01'},
        ),
        # ('hpc1', 'slurm', 'error'),
        (
            {'batch system': 'slurm'},
            {'host': 'hpc1'},
        ),
        # Localhost doesn't support pbs
        (
            {'batch system': 'pbs'},
            {},
        ),
    ]
)
def test_reverse_PlatformLookupError(job, remote):
    with pytest.raises(PlatformLookupError):
        reverse_lookup(PLATFORMS, job, remote)


# An example of a global config with two Spice systems available
@pytest.mark.parametrize(
    'job, remote, returns',
    [
        (
            {'batch system': 'slurm'},
            {'host': 'sugar'},
            'sugar'
        ),
        (
            {'batch system': 'slurm'},
            {},
            'sugar'
        ),
        (
            {'batch system': 'slurm'},
            {'host': 'pepper'},
            'pepper'
        )
    ]
)
def test_reverse_lookup_two_spices(
    job, remote, returns
):
    platforms = {
        'sugar': {
            'remote hosts': ['sugar', 'localhost'],
            'batch system': 'slurm',
        },
        'pepper': {
            'batch system': 'slurm',
            'remote hosts': 'pepper'
        },

    }
    assert reverse_lookup(platforms, job, remote) == returns


# An example of two platforms with the same hosts and batch system settings
# but some other setting different
@pytest.mark.parametrize(
    'job, remote, returns',
    [
        (
            {
                'batch system': 'background',
                'batch submit command template': '',
                'shell': '/bin/fish'
            },
            {
                'host': 'desktop01',
                'owner': '',
                'suite definition directory': '',
                'retrieve job logs': '',
                'retrieve job logs max size': '',
                'retrieve job logs retry delays': 'None'
            },
            'my-platform-with-fish'
        ),
    ]
)
def test_reverse_lookup_similar_platforms(
    job, remote, returns
):
    platforms = {
        'my-platform-with-bash': {
            'remote hosts': 'desktop01',
            'shell': '/bin/bash',
            'batch system': 'background'
        },
        # An extra platform to check that we only pick up the first match
        'my-platform-with-fish-not-this-one': {
            'remote hosts': 'desktop01',
            'shell': '/bin/fish',
            'batch system': 'background'
        },
        'my-platform-with-fish': {
            'remote hosts': 'desktop01',
            'shell': '/bin/fish',
            'batch system': 'background'
        },
    }
    assert reverse_lookup(platforms, job, remote) == returns
