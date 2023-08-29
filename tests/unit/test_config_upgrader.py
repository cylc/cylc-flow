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
# Tests that configs can be upgraded from earlier versions of Cylc.

import pytest
from cylc.flow.cfgspec.workflow import upg, upgrade_param_env_templates
from cylc.flow.parsec.OrderedDict import OrderedDictWithDefaults as ord_dict


@pytest.mark.parametrize(
    'cfg, expected',
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
    upgrade_param_env_templates(config, 'flow.cylc')
    assert config == _cfg(expected)


@pytest.mark.parametrize(
    'macp, rlim',
    [(16, 'P15'),
     ('', '')]
)
def test_upgrade_max_active_cycle_points(macp, rlim):
    """Test that `max active cycle points` is correctly upgraded to
    `runahead limit`."""
    cfg = {
        'scheduling': {'max active cycle points': macp}
    }
    expected = {
        'scheduling': {'runahead limit': rlim}
    }
    upg(cfg, 'flow.cylc')
    assert cfg == expected
