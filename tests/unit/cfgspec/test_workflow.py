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

import logging
import pytest
from typing import Any, Dict, Optional

from cylc.flow import CYLC_LOG
from cylc.flow.cfgspec.workflow import warn_about_depr_platform, upg
from cylc.flow.exceptions import PlatformLookupError


@pytest.mark.parametrize(
    'runtime_cfg, fail_expected, expected_warning',
    [
        pytest.param(
            {
                'foo': {'script': 'true'}
            },
            False, None,
            id="No platform setting"
        ),
        pytest.param(
            {
                'foo': {'platform': 'fine'}
            },
            False, None,
            id="Valid platform"
        ),
        pytest.param(
            {
                'foo': {'platform': 'fine'},
                'bar': {'platform': '`not good`'}
            },
            True, None,
            id="Invalid subshell notation"
        ),
        pytest.param(
            {
                'foo': {'platform': 'fine'},
                'bar': {
                    'platform': '$(fine)',
                    'job': {'batch system': 'pbs'}
                }
            },
            True, None,
            id="Platform/host conflict"
        ),
        pytest.param(
            {
                'foo': {'platform': 'fine'},
                'bar': {
                    'job': {'batch system': 'pbs'}
                }
            },
            False, "please replace with [runtime][bar]platform",
            id="Deprecated settings"
        )
    ]
)
def test_warn_about_depr_platform(
        runtime_cfg: Dict[str, Any], fail_expected: bool,
        expected_warning: Optional[str],
        caplog: pytest.LogCaptureFixture):
    """Test warn_about_depr_platform()"""
    caplog.set_level(logging.WARNING, CYLC_LOG)
    cfg = {'runtime': runtime_cfg}
    if fail_expected:
        with pytest.raises(PlatformLookupError):
            warn_about_depr_platform(cfg)
    else:
        warn_about_depr_platform(cfg)
        if expected_warning:
            assert expected_warning in caplog.text
        else:
            assert caplog.record_tuples == []


def test_max_active_cycle_point_converter(caplog):
    cfg = {'scheduling': {'max active cycle points': 5}}
    upg(cfg, 'standalone run of upgrader.')
    assert cfg['scheduling']['runahead limit'] == 'P4'
