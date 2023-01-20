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
# Tests for the platform lookup module's get_platform method.

from typing import Callable, Dict, Optional
import pytest
from cylc.flow.platforms import (
    get_localhost_install_target,
    get_platform
)
from cylc.flow.exceptions import PlatformLookupError


def test_get_platform_no_args():
    # If no task conf is given, we get localhost args.
    assert get_platform()['hosts'] == ['localhost']


@pytest.mark.parametrize(
    'platform_re',
    [
        None,
        'localhost',
        'localhost, otherplatform',
        'otherplatform, localhost',
        'localhost, xylophone\\d{1,5}'
    ]
)
def test_get_localhost_platform(mock_glbl_cfg, clean_platform_cache, platform_re):
    # Check that an arbitrary string name returns a sensible platform
    mock_glbl_cfg(
        'cylc.flow.platforms.glbl_cfg',
        f'''
        [platforms]
            [[localhost]]
                hosts = localhost
                ssh command = ssh -oConnectTimeout=42
            [[{platform_re}]]
                hosts = localhost
                ssh command = ssh -oConnectTimeout=24
        '''
    )
    platform = get_platform('localhost')
    if platform_re:
        assert platform['ssh command'] == 'ssh -oConnectTimeout=24'
    else:
        assert platform['ssh command'] == 'ssh -oConnectTimeout=42'


@pytest.mark.parametrize(
    'platform_re',
    [
        'saffron',
        'sumac|saffron',
        'sumac, saffron',
        'sumac|asafoetida, saffron',
    ]
)
def test_get_platform_from_platform_name_str(
    mock_glbl_cfg,
    clean_platform_cache,
    platform_re,
):
    # Check that an arbitrary string name returns a sensible platform
    mock_glbl_cfg(
        'cylc.flow.platforms.glbl_cfg',
        f'''
        [platforms]
            [[{platform_re}]]
                hosts = saff01
                job runner = slurm
        '''
    )
    platform = get_platform('saffron')
    assert platform['hosts'] == ['saff01']
    assert platform['job runner'] == 'slurm'


@pytest.mark.parametrize(
    'task_conf, err_expected',
    [
        (
            {
                'platform': 'localhost',
                'remote': {
                    'host': 'localhost'
                }
            },
            True
        ),
        (
            {
                'platform': 'gondor',
                'remote': {
                    'retrieve job logs': False
                }
            },
            True
        ),
        (
            {
                'platform': 'gondor',
                'remote': {
                    'host': None
                }
            },
            False
        ),
    ]
)
def test_get_platform_cylc7_8_syntax_mix_fails(
    task_conf: dict,
    err_expected: bool,
    mock_glbl_cfg: Callable,
    clean_platform_cache,
):
    """If a task with a mix of Cylc7 and 8 syntax is passed to get_platform
    this should return an error.
    """
    mock_glbl_cfg(
        'cylc.flow.platforms.glbl_cfg',
        '''
        [platforms]
            [[gondor]]
                hosts = denethor
        '''
    )
    if err_expected:
        with pytest.raises(
            PlatformLookupError,
            match=(
                r"Task .* has the following deprecated '\[runtime\]' "
                r"setting\(s\) which cannot be used with 'platform.*"
            )
        ):
            get_platform(task_conf)
    else:
        get_platform(task_conf)


def test_get_platform_from_config_with_platform_name(
    mock_glbl_cfg,
    clean_platform_cache,
):
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
def test_get_platform_using_platform_name_from_job_info(
    mock_glbl_cfg,
    clean_platform_cache,
    task_conf,
    expected_platform_name,
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


def test_get_platform_groups_basic(mock_glbl_cfg, clean_platform_cache):
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
                [[[selection]]]
                    method = definition order
        '''
    )
    output = get_platform('hebrew_letters')
    assert output['name'] == 'aleph'


@pytest.mark.parametrize(
    'task_conf, expected_err_msg',
    [
        ({'platform': '$(host)'}, None),
        ({'platform': '`echo ${chamber}`'}, "backticks are not supported")
    ]
)
def test_get_platform_subshell(
        task_conf: Dict[str, str], expected_err_msg: Optional[str]):
    """Test get_platform() for subshell platform definition."""
    if expected_err_msg:
        with pytest.raises(PlatformLookupError) as err:
            get_platform(task_conf)
        assert expected_err_msg in str(err.value)
    else:
        assert get_platform(task_conf) is None


def test_get_localhost_install_target():
    assert get_localhost_install_target() == 'localhost'


def test_localhost_different_install_target(mock_glbl_cfg, clean_platform_cache):
    mock_glbl_cfg(
        'cylc.flow.platforms.glbl_cfg',
        '''
        [platforms]
            [[localhost]]
                install target = file_system_1
        '''
    )

    assert get_localhost_install_target() == 'file_system_1'
