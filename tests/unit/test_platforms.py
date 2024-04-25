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
#
# Tests for the platform lookup.

import pytest
from typing import Any, Dict, List, Optional, Type

from cylc.flow.parsec.OrderedDict import OrderedDictWithDefaults
from cylc.flow.platforms import (
    get_platform,
    get_platform_deprecated_settings,
    is_platform_definition_subshell,
    platform_from_name, platform_name_from_job_info,
    get_install_target_from_platform,
    get_install_target_to_platforms_map,
    generic_items_match,
    _validate_single_host
)
from cylc.flow.exceptions import (
    PlatformLookupError,
    GlobalConfigError
)
from cylc.flow.task_state import RunMode


PLATFORMS = {
    'desktop[0-9]{2}|laptop[0-9]{2}': {
        'job runner': 'background'
    },
    'sugar': {
        'hosts': 'localhost',
        'job runner': 'slurm',
    },
    'hpc-no-logs': {
        'hosts': ['hpc1', 'hpc2'],
        'job runner': 'pbs',
        'retrieve job logs': False
    },
    'hpc-logs': {
        'hosts': ['hpc1', 'hpc2'],
        'job runner': 'pbs',
        'retrieve job logs': True
    },
    'hpc1-bg': {
        'hosts': 'hpc1',
        'job runner': 'background',
    },
    'hpc2-bg': {
        'hosts': 'hpc2',
        'job runner': 'background'
    },
    'localhost': {
        'hosts': 'localhost',
        'job runner': 'background'
    }
}

PLATFORMS_NO_UNIQUE = {
    'sugar': {
        'hosts': 'localhost',
        'job runner': 'slurm'
    },
    'pepper': {
        'hosts': ['hpc1', 'hpc2'],
        'job runner': 'slurm'
    },

}

PLATFORMS_WITH_RE = {
    'hpc.*': {'hosts': 'hpc1', 'job runner': 'background'},
    'h.*': {'hosts': 'hpc3'},
    r'vld\d{2,3}, anselm\d{4}': {},
    'nu.*': {
        'job runner': 'slurm',
        'hosts': ['localhost']
    },
    'localhost': {
        'hosts': 'localhost',
        'job runner': 'background'
    }
}

PLATFORMS_TREK = {
    'enterprise': {
        'hosts': ['kirk', 'picard'],
        'install target': 'picard',
        'name': 'enterprise'
    },
    'voyager': {
        'hosts': ['janeway'],
        'install target': 'janeway',
        'name': 'voyager'
    },
    'stargazer': {
        'hosts': ['picard'],
        'install target': 'picard',
        'name': 'stargazer'
    }
}


PLATFORMS_INVALID = {
    'enterprise': {
        'hosts': ['kirk', 'picard'],
        'install target': 'picard',
        'job runner': 'background'  # requires one host
    },
    'voyager': {
        'hosts': ['janeway', 'seven-of-nine'],
        'install target': 'janeway',
        'job runner': 'at'  # requires one host
    }
}


# ----------------------------------------------------------------------------
# Tests of platform_from_name
# ----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "PLATFORMS, platform, expected",
    [
        (PLATFORMS_WITH_RE, "nutmeg", {
            "job runner": "slurm",
            "name": "nutmeg",
            "hosts": ['localhost']
        }),
        (PLATFORMS_WITH_RE, "vld798", ["vld798"]),
        (PLATFORMS_WITH_RE, "vld56", ["vld56"]),
        (
            PLATFORMS_NO_UNIQUE,
            "sugar",
            {
                "hosts": "localhost",
                "job runner": "slurm",
                "name": "sugar"
            },
        ),
        (
            PLATFORMS,
            None,
            {
                "hosts": "localhost",
                "name": "localhost",
                "job runner": "background"
            },
        ),
        (PLATFORMS, "laptop22", {
            "job runner": "background",
            "name": "laptop22",
            "hosts": ["laptop22"]
        }),
        (
            PLATFORMS,
            "hpc1-bg",
            {
                "hosts": "hpc1",
                "job runner": "background",
                "name": "hpc1-bg"
            },
        ),
        (PLATFORMS_WITH_RE, "hpc2", {"hosts": "hpc3", "name": "hpc2"}),
    ],
)
def test_basic(PLATFORMS, platform, expected):
    # n.b. The name field of the platform is set in the Globalconfig object
    # if the name is 'localhost', so we don't test for it here.
    platform = platform_from_name(platform_name=platform, platforms=PLATFORMS)
    if isinstance(expected, dict):
        assert platform == expected
    else:
        assert platform["hosts"] == expected


def test_platform_not_there():
    with pytest.raises(PlatformLookupError):
        platform_from_name('moooo', PLATFORMS)


@pytest.mark.parametrize(
    'platform',
    [
        {i: j} for i, j in PLATFORMS_INVALID.items()
    ]
)
def test_invalid_platforms(platform):
    with pytest.raises(GlobalConfigError):
        _validate_single_host(platform)


def test_similar_but_not_exact_match():
    with pytest.raises(PlatformLookupError):
        platform_from_name('vld1', PLATFORMS_WITH_RE)


# ----------------------------------------------------------------------------
# Tests of platform_name_from_job_info
# ----------------------------------------------------------------------------
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

        # Basic test where the user hasn't submitted anything and the task
        # returns to default, i.e. localhost.
        (
            {'batch system': 'background'},
            {'retrieve job logs retry delays': None},
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
        # with hpc1 in its list of hosts
        (
            {'batch system': 'pbs'},
            {'host': 'hpc1'},
            'hpc-logs'
        ),
        # When the user asks for hpc1 without specifying pbs user gets platform
        # hpc bg1
        (
            {'batch system': 'background'},
            {'host': 'hpc1'},
            'hpc1-bg'
        ),
        # Check that None as a value is handled correctly
        (
            {'batch system': None},
            {'host': 'hpc1-bg'},
            'hpc1-bg'
        ),
        (
            # Check that failure to set any items will return localhost
            {'batch system': None},
            {'host': None},
            'localhost'
        ),
        (
            # Check that all generic items are matched
            {'batch system': 'pbs'},
            {'host': 'hpc1', 'retrieve job logs': False},
            'hpc-no-logs'
        ),
    ]
)
def test_platform_name_from_job_info_basic(job, remote, returns):
    assert platform_name_from_job_info(PLATFORMS, job, remote) == returns


def test_platform_name_from_job_info_ordered_dict_comparison():
    """Check that we are only comparing set items in OrderedDictWithDefaults.
    """
    job = {'batch system': 'background', 'Made up key': 'Zaphod'}
    remote = {'host': 'hpc1', 'Made up key': 'Arthur'}
    # Set up a fake OrderedDictWith a fake unset default.
    platform = OrderedDictWithDefaults()
    platform.defaults_ = {k: None for k in PLATFORMS['hpc1-bg'].keys()}
    platform.defaults_['Made up key'] = {}
    platform.update(PLATFORMS['hpc1-bg'])
    platforms = {'hpc1-bg': platform, 'dobbie': PLATFORMS['sugar']}
    assert platform_name_from_job_info(platforms, job, remote) == 'hpc1-bg'


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
        platform_name_from_job_info(PLATFORMS, job, remote)


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
def test_platform_name_from_job_info_two_spices(
    job, remote, returns
):
    platforms = {
        'sugar': {
            'hosts': ['sugar', 'localhost'],
            'job runner': 'slurm',
        },
        'pepper': {
            'job runner': 'slurm',
            'hosts': 'pepper'
        },

    }
    assert platform_name_from_job_info(platforms, job, remote) == returns


# An example of two platforms with the same hosts and job runner settings
# but some other setting different
@pytest.mark.parametrize(
    'job, remote, returns',
    [
        (
            {
                'job runner': 'background',
                'job runner command template': '',
                'shell': '/bin/fish'
            },
            {
                'host': 'desktop01',
                'owner': '',
                'workflow definition directory': '',
                'retrieve job logs': '',
                'retrieve job logs max size': '',
                'retrieve job logs retry delays': 'None'
            },
            'my-platform-with-fish'
        ),
    ]
)
def test_platform_name_from_job_info_similar_platforms(
    job, remote, returns
):
    platforms = {
        'my-platform-with-bash': {
            'hosts': 'desktop01',
            'shell': '/bin/bash',
            'job runner': 'background'
        },
        # An extra platform to check that we only pick up the first match
        'my-platform-with-fish-not-this-one': {
            'hosts': 'desktop01',
            'shell': '/bin/fish',
            'job runner': 'background'
        },
        'my-platform-with-fish': {
            'hosts': 'desktop01',
            'shell': '/bin/fish',
            'job runner': 'background'
        },
    }
    assert platform_name_from_job_info(platforms, job, remote) == returns


# -----------------------------------------------------------------------------
# Tests for getting install target info

@pytest.mark.parametrize(
    'platform, expected',
    [
        ({'name': 'rick', 'install target': 'desktop'}, 'desktop'),
        ({'name': 'morty', 'install target': ''}, 'morty')
    ]
)
def test_get_install_target_from_platform(platform, expected):
    """Test that get_install_target_from_platform works as expected."""
    assert get_install_target_from_platform(platform) == expected


@pytest.mark.parametrize('quiet', [True, False])
@pytest.mark.parametrize(
    'platform_names, expected_map, expected_err',
    [
        (
            ['enterprise', 'stargazer'],
            {
                'picard': [
                    PLATFORMS_TREK['enterprise'],
                    PLATFORMS_TREK['stargazer']
                ]
            },
            None
        ),
        (
            ['enterprise', 'voyager', 'enterprise'],
            {
                'picard': [
                    PLATFORMS_TREK['enterprise']
                ],
                'janeway': [
                    PLATFORMS_TREK['voyager']
                ]
            },
            None
        ),
        (
            ['enterprise', 'discovery'],
            None,
            PlatformLookupError
        )
    ]
)
def test_get_install_target_to_platforms_map(
        platform_names: List[str],
        expected_map: Dict[str, Any],
        expected_err: Type[Exception],
        quiet: bool,
        monkeypatch: pytest.MonkeyPatch
):
    """Test that get_install_target_to_platforms_map works as expected."""
    monkeypatch.setattr('cylc.flow.platforms.platform_from_name',
                        lambda x: platform_from_name(x, PLATFORMS_TREK))

    if expected_err and not quiet:
        with pytest.raises(expected_err):
            get_install_target_to_platforms_map(platform_names)
    elif expected_err and quiet:
        # No error should be raised in quiet mode.
        assert get_install_target_to_platforms_map(platform_names, quiet=quiet)
    else:
        result = get_install_target_to_platforms_map(platform_names)
        # Sort the maps:
        for _map in (result, expected_map):
            for install_target in _map:
                _map[install_target] = sorted(_map[install_target],
                                              key=lambda k: k['name'])
        result.pop('localhost')
        assert result == expected_map

@pytest.mark.parametrize(
    'platform, job, remote, expect',
    [
        (
            # Default, no old settings.
            {'ship': 'Enterprise'}, {}, {}, True
        ),
        (
            {'captain': 'Kirk'},
            {'captain': 'Picard'},
            {},
            False
        ),
        (
            {'captain': 'Sisko'},
            {},
            {'captain': 'Janeway'},
            False
        ),
        (
            {'captain': 'Picard', 'ship': 'Enterprise'},
            {'captain': 'Picard'},
            {'ship': 'Enterprise'},
            True
        ),
        (
            {'captain': 'Picard', 'ship': 'Enterprise'},
            {'captain': 'Picard'},
            {'ship': 'Defiant'},
            False
        ),
        (
            {'captain': 'Picard', 'ship': 'Enterprise'},
            {'captain': 'Picard'},
            {},
            True
        )
    ]
)
def test_generic_items_match(platform, job, remote, expect):
    assert generic_items_match(platform, job, remote) == expect


@pytest.mark.parametrize(
    'task_conf, expected',
    [
        pytest.param(
            {
                'remote': {
                    'host': 'cylcdevbox',
                    'retrieve job logs': True
                },
                'job': {
                    'batch system': 'pbs',
                    'batch submit command template': 'meow'
                }
            },
            [
                '[runtime][task][job]batch submit command template = meow',
                '[runtime][task][remote]retrieve job logs = True',
                '[runtime][task][remote]host = cylcdevbox',
                '[runtime][task][job]batch system = pbs'
            ],
            id="All are deprecated settings"
        ),
        pytest.param(
            {
                'remote': {'host': 'localhost'},
                'job': {
                    'batch system': 'pbs',
                    'batch submit command template': None
                }
            },
            ['[runtime][task][job]batch system = pbs'],
            id="Exclusions are excluded"
        ),
        pytest.param(
            {
                'environment filter': {
                    'include': ['frodo', 'sam']
                }
            },
            [],
            id="No deprecated settings"
        )
    ]
)
def test_get_platform_deprecated_settings(
    task_conf: Dict[str, Any], expected: List[str]
):
    output = get_platform_deprecated_settings(task_conf, task_name='task')
    assert set(output) == set(expected)


@pytest.mark.parametrize(
    'plat_val, expected, err_msg',
    [('normal', False, None),
     ('$(yes)', True, None),
     ('`echo ${chamber}`', None, "backticks are not supported")]
)
def test_is_platform_definition_subshell(
        plat_val: str, expected: Optional[bool], err_msg: Optional[str]):
    if err_msg:
        with pytest.raises(PlatformLookupError) as exc:
            is_platform_definition_subshell(plat_val)
        assert err_msg in str(exc.value)
    else:
        assert is_platform_definition_subshell(plat_val) is expected


def test_get_platform_from_OrderedDictWithDefaults(mock_glbl_cfg):
    """Get platform works with OrderedDictWithDefaults.

    Most tests use dictionaries to check platforms functionality.
    This one was added to catch an issue where the behaviour of
    dict.get != OrderedDictWithDefaults.get.
    See - https://github.com/cylc/cylc-flow/issues/4979
    """
    mock_glbl_cfg(
        'cylc.flow.platforms.glbl_cfg',
        '''
        [platforms]
            [[skarloey]]
                hosts = foo, bar
                job runner = slurm
        '''
    )
    task_conf = OrderedDictWithDefaults()
    task_conf.defaults_ = OrderedDictWithDefaults([
        ('job', OrderedDictWithDefaults([
            ('batch system', 'slurm')
        ])),
        ('remote', OrderedDictWithDefaults([
            ('host', 'foo')
        ])),
    ])
    result = get_platform(task_conf)['name']
    assert result == 'skarloey'
