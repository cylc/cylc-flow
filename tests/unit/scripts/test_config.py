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

import os
from pathlib import Path
from typing import Any, Optional, List

import pytest

from cylc.flow.scripts.config import get_config_file_hierarchy
from cylc.flow.cfgspec.globalcfg import GlobalConfig


Fixture = Any
HOME: str = str(Path('~').expanduser())


@pytest.fixture
def conf_env(monkeypatch):
    """Clear any env vars that affect which conf files get loaded.

    Return a convenience function for setting environment variables.
    """
    # wipe any cached config
    monkeypatch.setattr(
        GlobalConfig,
        '_DEFAULT',
        None,
    )

    for envvar in ('CYLC_SITE_CONF_PATH', 'CYLC_CONF_PATH'):
        if envvar in os.environ:
            monkeypatch.delenv(envvar)

    def _set_env(key, value):
        if value:
            monkeypatch.setenv(key, value)

    return _set_env


@pytest.fixture
def dummy_version_hierarchy(monkeypatch):
    """Set the config version hierarchy."""
    monkeypatch.setattr(
        'cylc.flow.cfgspec.globalcfg.GlobalConfig.VERSION_HIERARCHY',
        ['', '1', '1.0']
    )


@pytest.fixture
def capload(monkeypatch):
    """Capture configuration load events.

    This prevents actual file loading.

    If the file name contains the string "invalid" it will not appear in the
    results as if it diddn't exist on the filesystem.
    """
    files = []

    def _capload(glblcfg, fname, _):
        nonlocal files
        if 'invalid' not in fname:
            # if the file is called invalid skip it
            # this is to replicate the behaviour of skipping files that
            # don't exist
            files.append(fname.replace(HOME, '~'))

    monkeypatch.setattr(
        GlobalConfig,
        '_load',
        _capload
    )
    return files


def test_get_config_file_hierarchy_global(
    monkeypatch: Fixture,
    conf_env: Fixture,
    capload: Fixture,
    dummy_version_hierarchy: Fixture
):
    """Test get_config_file_hierarchy() for the global hierarchy only."""
    assert [
        path.replace(HOME, '~')
        for path in get_config_file_hierarchy()
    ] == [
        '/etc/cylc/flow/global.cylc',
        '/etc/cylc/flow/1/global.cylc',
        '/etc/cylc/flow/1.0/global.cylc',
        '~/.cylc/flow/global.cylc',
        '~/.cylc/flow/1/global.cylc',
        '~/.cylc/flow/1.0/global.cylc'
    ]


@pytest.mark.parametrize(
    'conf_path,site_conf_path,files',
    [
        pytest.param(
            None,
            None,
            [
                '/etc/cylc/flow/global.cylc',
                '/etc/cylc/flow/1/global.cylc',
                '/etc/cylc/flow/1.0/global.cylc',
                '~/.cylc/flow/global.cylc',
                '~/.cylc/flow/1/global.cylc',
                '~/.cylc/flow/1.0/global.cylc',
            ],
            id='(default)'
        ),

        pytest.param(
            None,
            '<path>',
            [
                '<path>/flow/global.cylc',
                '<path>/flow/1/global.cylc',
                '<path>/flow/1.0/global.cylc',
                '~/.cylc/flow/global.cylc',
                '~/.cylc/flow/1/global.cylc',
                '~/.cylc/flow/1.0/global.cylc',
            ],
            id='CYLC_SITE_CONF_PATH=valid'
        ),

        pytest.param(
            None,
            'invalid',
            [
                '~/.cylc/flow/global.cylc',
                '~/.cylc/flow/1/global.cylc',
                '~/.cylc/flow/1.0/global.cylc',
            ],
            id='CYLC_SITE_CONF_PATH=invalid'
        ),

        pytest.param(
            '<path>',
            None,
            ['<path>/global.cylc'],
            id='CYLC_CONF_PATH=valid'
        ),

        pytest.param(
            'invalid',
            None,
            [],
            id='CYLC_CONF_PATH=invalid'
        ),

        pytest.param(
            '<path1>',
            '<path2>',
            ['<path1>/global.cylc'],  # should ignore CYLC_SITE_CONF_PATH
            id='CYLC_CONF_PATH=valid, CYLC_SITE_CONF_PATH=valid'
        ),

        pytest.param(
            'invalid',
            '<path>',
            [],
            id='CYLC_CONF_PATH=invalid, CYLC_SITE_CONF_PATH=valid'
        ),
    ]
)
def test_cylc_site_conf_path_env_var(
    monkeypatch: Fixture,
    conf_env: Fixture,
    capload: Fixture,
    dummy_version_hierarchy: Fixture,
    conf_path: Optional[str],
    site_conf_path: Optional[str],
    files: List[str],
):
    """Test that the right files are loaded according to env vars."""
    # set the relevant environment variables
    conf_env('CYLC_CONF_PATH', conf_path)
    conf_env('CYLC_SITE_CONF_PATH', site_conf_path)

    # load the global config
    GlobalConfig.get_inst()

    assert capload == files
