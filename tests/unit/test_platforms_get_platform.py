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
# Tests for the platform lookup module's get_platform method.

import pytest
import random
from cylc.flow.platforms import (
    get_localhost_install_target,
    get_platform
)
from cylc.flow.exceptions import PlatformLookupError


def test_get_platform_no_args():
    # If no task conf is given, we get localhost args.
    assert get_platform()['hosts'] == ['localhost']


def test_get_platform_from_platform_name_str(mock_glbl_cfg):
    # Check that an arbitrary string name returns a sensible platform
    mock_glbl_cfg(
        'cylc.flow.platforms.glbl_cfg',
        '''
        [platforms]
            [[saffron]]
                hosts = saff01
                job runner = slurm
        '''
    )
    platform = get_platform('saffron')
    assert platform['hosts'] == ['saff01']
    assert platform['job runner'] == 'slurm'


def test_get_platform_cylc7_8_syntax_mix_fails(mock_glbl_cfg):
    """If a task with a mix of Cylc7 and 8 syntax is passed to get_platform
    this should return an error.
    """
    task_conf = {
        'platform': 'localhost',
        'remote': {
            'host': 'localhost'
        }
    }
    with pytest.raises(
        PlatformLookupError,
        match=r'A mixture of Cylc 7 \(host\) and Cylc 8 \(platform\).*'
    ):
        get_platform(task_conf)


def test_get_platform_from_config_with_platform_name(mock_glbl_cfg):
    # A platform name is present, and no clashing cylc7 configs are:
    mock_glbl_cfg(
        'cylc.flow.platforms.glbl_cfg',
        '''
        [platforms]
            [[mace]]
                hosts = mace001, mace002
                job runner = slurm
        '''
    )
    task_conf = {'platform': 'mace'}
    platform = get_platform(task_conf)
    assert platform['hosts'] == ['mace001', 'mace002']
    assert platform['job runner'] == 'slurm'


@pytest.mark.parametrize(
    'task_conf, expected_platform_name',
    [
        (
            {
                'remote': {'host': 'cumin'},
                'job': {'batch system': 'slurm'}
            },
            'ras_el_hanout'
        ),
        (
            {'remote': {'host': 'cumin'}},
            'spice_bg'
        ),
        (
            {'job': {'batch system': 'batchyMcBatchFace'}},
            'local_job_runner'
        ),
        (
            {'script': 'true'},
            'localhost'
        ),
        (
            {
                'remote': {'host': 'localhost'},
                'job': {
                    'batch system': None,
                    'batch submit command template': None,
                    'execution polling intervals': None
                }
            },
            'localhost'
        ),
        (
            {
                'remote': {'host': 'cylcdevbox'},
                'job': {
                    'batch system': None,
                    'batch submit command template': None,
                    'execution polling intervals': None
                }
            },
            'cylcdevbox'
        )
    ]
)
def test_get_platform_using_platform_from_job_info(
    mock_glbl_cfg, task_conf, expected_platform_name
):
    """Calculate platform from Cylc 7 config: n.b. If this fails we don't
    warn because this might lead to many thousands of warnings

    This should not contain a comprehensive set of use-cases - these should
    be coverend by the unit tests for `platform_from_host_items`
    """
    mock_glbl_cfg(
        'cylc.flow.platforms.glbl_cfg',
        '''
        [platforms]
            [[ras_el_hanout]]
                hosts = rose, chilli, cumin, paprika
                job runner = slurm
            [[spice_bg]]
                hosts = rose, chilli, cumin, paprika
            [[local_job_runner]]
                hosts = localhost
                job runner = batchyMcBatchFace
            [[cylcdevbox]]
                hosts = cylcdevbox
        '''
    )
    assert get_platform(task_conf)['name'] == expected_platform_name


def test_get_platform_warn_mode(caplog):
    task_conf = {
        'remote': {'host': 'cylcdevbox'},
        'job': {
            'batch system': 'pbs',
            'batch submit command template': 'some template'
        }
    }
    output = get_platform(task_conf, warn_only=True)
    for forbidden_item in (
        'batch submit command template = some template',
        'host = cylcdevbox',
        'batch system = pbs'
    ):
        assert forbidden_item in output


def test_get_platform_groups_basic(mock_glbl_cfg):
    # get platform from group works.
    mock_glbl_cfg(
        'cylc.flow.platforms.glbl_cfg',
        '''
        [platforms]
            [[aleph]]
                hosts = aleph
            [[bet]]
                hosts = bet

        [platform groups]
            [[hebrew_letters]]
                platforms = aleph, bet
        '''
    )
    output = get_platform('hebrew_letters')
    assert output['group'] == 'hebrew_letters'
    random.seed(42)
    assert get_platform('hebrew_letters')['name'] == 'aleph'
    random.seed(44)
    assert get_platform('hebrew_letters')['name'] == 'bet'


def test_get_platform_warn_mode_fail_if_backticks():
    # Platform = `cmd in backticks` not allowed.
    task_conf = {
        'platform': '`echo ${chamber}`'
    }
    with pytest.raises(PlatformLookupError) as err:
        get_platform(task_conf, warn_only=True)
    assert err.match(
        r'platform = `echo \$\{chamber\}`: '
        r'backticks are not supported; please use \$\(\)'
    )


def test_get_localhost_install_target():
    assert get_localhost_install_target() == 'localhost'


def test_localhost_different_install_target(mock_glbl_cfg):
    mock_glbl_cfg(
        'cylc.flow.platforms.glbl_cfg',
        '''
        [platforms]
            [[localhost]]
                install target = file_system_1
        '''
    )

    assert get_localhost_install_target() == 'file_system_1'
