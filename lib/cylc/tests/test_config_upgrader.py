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

# Tests for the config upgrader - this is specifically for the function
# testing that configs can be upgraded from Cylc 7 to 8.

import pytest
from parsec.OrderedDict import OrderedDictWithDefaults as ord_dict
from cylc.cfgspec.suite import _upgrade_param_env_templates


@pytest.mark.parametrize(
    'cfg,expected',
    [
        (   # No clashes - order is important:
            {
                'parameter environment templates': ord_dict([
                    ('FOO', 'jupiter'),
                    ('MOO', 'pluto')
                ]),
                'environment': ord_dict([
                    ('BAR', 'neptune'),
                    ('BAZ', 'ares')
                ])
            },
            {
                'environment': ord_dict([
                    ('FOO', 'jupiter'),
                    ('MOO', 'pluto'),
                    ('BAR', 'neptune'),
                    ('BAZ', 'ares')
                ])
            }
        ),
        (   # Clashes - environment wins:
            {
                'parameter environment templates': ord_dict([
                    ('FOO', 'jupiter'),
                    ('BAR', 'neptune')
                ]),
                'environment': ord_dict([
                    ('FOO', 'zeus'),
                    ('BAR', 'poseidon')
                ])
            },
            {
                'environment': ord_dict([
                    ('FOO', 'zeus'),
                    ('BAR', 'poseidon')
                ])
            }
        ),
        (   # No environment section:
            {
                'parameter environment templates': ord_dict([
                    ('FOO', 'jupiter'),
                    ('BAR', 'neptune')
                ])
            },
            {
                'environment': ord_dict([
                    ('FOO', 'jupiter'),
                    ('BAR', 'neptune')
                ])
            }
        )
    ]
)
def test_upgrade_param_env_templates(cfg, expected):
    """Test that the deprecated [runtime][X][parameter environment templates]
    contents are prepended to [runtime][X][environment], in the correct
    order"""

    def _cfg(dic):
        """Return OrderedDictWithDefaults config populated with values from
        dic (dictionary)"""
        result = ord_dict({
            'runtime': ord_dict({
                '<foo>': ord_dict({
                    'script': 'echo whatever'
                })
            })
        })
        if 'parameter environment templates' in dic:
            result['runtime']['<foo>']['parameter environment templates'] = (
                dic['parameter environment templates']
            )
        if 'environment' in dic:
            result['runtime']['<foo>']['environment'] = dic['environment']
        return result

    config = _cfg(cfg)
    _upgrade_param_env_templates(config, 'suite.rc')
    assert config == _cfg(expected)
