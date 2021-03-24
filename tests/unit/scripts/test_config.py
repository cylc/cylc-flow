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

import logging
import os
from pathlib import Path
from typing import Any, Optional, List

import pytest

from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.scripts.config import get_config_file_hierarchy

from cylc.flow import (
    CYLC_LOG,
    __version__ as VERSION,
)
from cylc.flow.cfgspec.globalcfg import GlobalConfig


Fixture = Any
HOME: str = str(Path('~').expanduser())
MAJVER: str = VERSION[0]


@pytest.fixture
def clear_env(monkeypatch):
    """Clear any env vars that effect which conf files get loaded."""
    for envvar in ('CYLC_SITE_CONF_PATH', 'CYLC_CONF_PATH'):
        if envvar in os.environ:
            monkeypatch.delenv(envvar)


def test_get_config_file_hierarchy_global(
    monkeypatch: Fixture,
    clear_env: Fixture
):
    """Test get_config_file_hierarchy() for the global hierarchy only."""
    for cls_attr, val in [
        ('USER_CONF_PATH', '~/.cylc/flow'),
        ('VERSION_HIERARCHY', ['', '1', '1.0'])
    ]:
        monkeypatch.setattr(
            f'cylc.flow.cfgspec.globalcfg.GlobalConfig.{cls_attr}', val)
    # Prevent the cached global config from being used, as this can be
    # affected by previous tests
    monkeypatch.setattr('cylc.flow.scripts.config.glbl_cfg',
                        lambda cached=False: glbl_cfg(cached))

    assert get_config_file_hierarchy() == [
        '/etc/cylc/flow/global.cylc',
        '/etc/cylc/flow/1/global.cylc',
        '/etc/cylc/flow/1.0/global.cylc',
        '~/.cylc/flow/global.cylc',
        '~/.cylc/flow/1/global.cylc',
        '~/.cylc/flow/1.0/global.cylc'
    ]


@pytest.fixture(scope='module')
def conf_dirs(mod_tmp_path):
    """Directory with some dirs for testing global config loading."""
    dirs = {
        '<tmp1>': mod_tmp_path / 'a',
        '<tmp1>/flow': Path(mod_tmp_path / 'a', 'flow'),
        '<tmp2>': mod_tmp_path / 'b',
        '<site>': mod_tmp_path / 'flow'
    }
    for dir_ in dirs.values():
        dir_.mkdir(exist_ok=True)
        (dir_ / 'global.cylc').touch()
        flow_dir = dir_ / 'flow'
        flow_dir.mkdir()
        (flow_dir / 'global.cylc').touch()
    return dirs


@pytest.mark.parametrize(
    'conf_path,site_conf_path,files',
    [
        pytest.param(
            None,
            None,
            [
                '<site>',
                '~/.cylc/flow/global.cylc',
                f'~/.cylc/flow/{MAJVER}/global.cylc',
                f'~/.cylc/flow/{VERSION}/global.cylc',
            ],
            id='(default)'
        ),

        pytest.param(
            None,
            '<tmp1>',
            [
                '<tmp1>/flow',
                '~/.cylc/flow/global.cylc',
                f'~/.cylc/flow/{MAJVER}/global.cylc',
                f'~/.cylc/flow/{VERSION}/global.cylc',
            ],
            id='CYLC_SITE_CONF_PATH=valid'
        ),

        pytest.param(
            None,
            'elephant',
            [
                '~/.cylc/flow/global.cylc',
                f'~/.cylc/flow/{MAJVER}/global.cylc',
                f'~/.cylc/flow/{VERSION}/global.cylc',
            ],
            id='CYLC_SITE_CONF_PATH=invalid'
        ),

        pytest.param(
            '<tmp1>',
            None,
            ['<tmp1>'],
            id='CYLC_CONF_PATH=valid'
        ),

        pytest.param(
            'elephant',
            None,
            [],
            id='CYLC_CONF_PATH=invalid'
        ),

        pytest.param(
            '<tmp1>',
            '<tmp2>',
            ['<tmp1>'],  # should ignore CYLC_SITE_CONF_PATH
            id='CYLC_CONF_PATH=valid, CYLC_SITE_CONF_PATH=valid'
        ),

        pytest.param(
            'elephant',
            '<tmp1>',
            [],
            id='CYLC_CONF_PATH=invalid, CYLC_SITE_CONF_PATH=valid'
        ),
    ]
)
def test_cylc_site_conf_path_env_var(
    monkeypatch: Fixture,
    caplog: Fixture,
    clear_env: Fixture,
    conf_dirs: Fixture,
    conf_path: Optional[str],
    site_conf_path: Optional[str],
    files: List[str],
):
    """Test that the right files are loaded according to env vars."""
    # patch the default site config path
    monkeypatch.setattr(
        GlobalConfig,
        'DEFAULT_SITE_CONF_PATH',
        str(conf_dirs['<site>'].parent)
    )

    # del/set the relevant environment variables
    for var, env_var in (
        (conf_path, 'CYLC_CONF_PATH'),
        (site_conf_path, 'CYLC_SITE_CONF_PATH')
    ):
        if var is None:
            pass
        elif var in conf_dirs:
            monkeypatch.setenv(env_var, conf_dirs[var])
        elif var:
            monkeypatch.setenv(env_var, var)

    # reset the global config
    monkeypatch.setattr(
        GlobalConfig,
        '_DEFAULT',
        None,
    )

    # capture logging
    caplog.clear()
    caplog.set_level(logging.DEBUG, logger=CYLC_LOG)

    # load the global config
    GlobalConfig.get_inst()

    # make sure the right files are loaded
    assert [
        msg
        .replace('Reading file ', '')
        .replace(HOME, '~')
        for *_, msg in caplog.record_tuples
        if msg.startswith('Reading file ')
    ] == [
        str(conf_dirs[file_] / 'global.cylc')
        if file_ in conf_dirs
        else file_
        for file_ in files
    ]
