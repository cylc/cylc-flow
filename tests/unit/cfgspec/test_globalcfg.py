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
"""Tests for the Cylc GlobalConfig object."""

from cylc.flow.cfgspec.globalcfg import GlobalConfig, SPEC
from io import StringIO

import pytest

TEST_CONF = '''
    [platforms]
        [[foo]]
            hosts = of_morgoth
    [platform groups]
        [[BAR]]
            platforms = mario, sonic
    [task events]
        # Checking that config items that aren't platforms or platform groups
        # are not output.
'''


@pytest.fixture
def fake_global_conf(tmp_path):
    glblcfg = GlobalConfig(SPEC)
    (tmp_path / 'global.cylc').write_text(TEST_CONF)
    glblcfg.loadcfg(tmp_path / 'global.cylc')
    return glblcfg


def test_dump_platform_names(capsys, fake_global_conf):
    """It dumps lists of platform names, nothing else."""
    fake_global_conf.dump_platform_names(fake_global_conf)
    stdout, _ = capsys.readouterr()
    expected = 'localhost\nfoo\nBAR\n'
    assert stdout == expected


def test_dump_platform_details(capsys, fake_global_conf):
    """It dumps lists of platform spec."""
    fake_global_conf.dump_platform_details(fake_global_conf)
    out, _ = capsys.readouterr()
    expected = (
        '[platforms]\n    [[foo]]\n        hosts = of_morgoth\n'
        '[platform groups]\n    [[BAR]]\n        platforms = mario, sonic\n'
    )
    assert expected == out


def test_expand_platforms(tmp_path):
    """It should expand comma separated platform definitions."""
    glblcfg = GlobalConfig(SPEC)
    (tmp_path / 'global.cylc').write_text('''
    [platforms]
        [[foo]]
            [[[meta]]]
                x = 1
        [["bar"]]  # double quoted name
            [[[meta]]]
                x = 2
        [[baz, bar, pub]]  # baz before bar to test order is handled correctly
            [[[meta]]]
                x = 3
        [['pub']]  # single quoted name
            [[[meta]]]
                x = 4
    ''')
    glblcfg.loadcfg(tmp_path / 'global.cylc')
    glblcfg._expand_platforms()

    # ensure the definition order is preserved
    assert glblcfg.get(['platforms']).keys() == [
        'localhost',
        'foo',
        'bar',
        'baz',
        'pub',
    ]

    # ensure sections are correctly deep-merged
    assert glblcfg.get(['platforms', 'foo', 'meta', 'x']) == '1'
    assert glblcfg.get(['platforms', 'bar', 'meta', 'x']) == '3'
    assert glblcfg.get(['platforms', 'baz', 'meta', 'x']) == '3'
    assert glblcfg.get(['platforms', 'pub', 'meta', 'x']) == '4'
