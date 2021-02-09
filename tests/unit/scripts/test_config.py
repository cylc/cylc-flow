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

from typing import Any

from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.scripts.config import get_config_file_hierarchy

Fixture = Any


def test_get_config_file_hierarchy_global(monkeypatch: Fixture):
    """Test get_config_file_hierarchy() for the global hierarchy only."""
    for cls_attr, val in {'SITE_CONF_PATH': '/etc/cylc/flow',
                          'USER_CONF_PATH': '~/.cylc/flow',
                          'VERSION_HIERARCHY': ['', '1', '1.0']}.items():
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
