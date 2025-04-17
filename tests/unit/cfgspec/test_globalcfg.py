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

from typing import TYPE_CHECKING, Callable

import pytest

from cylc.flow.cfgspec.globalcfg import GlobalConfig, SPEC
from cylc.flow.parsec.exceptions import ValidationError
from cylc.flow.parsec.validate import cylc_config_validate


if TYPE_CHECKING:
    from pathlib import Path


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
def mock_global_config(tmp_path: 'Path', monkeypatch: pytest.MonkeyPatch):
    """Create a mock GlobalConfig object, given the global.cylc contents as
    a string."""
    def _mock_global_config(cfg: str) -> GlobalConfig:
        glblcfg = GlobalConfig(SPEC, validator=cylc_config_validate)
        conf_path = tmp_path / GlobalConfig.CONF_BASENAME
        conf_path.write_text(cfg)
        monkeypatch.setenv("CYLC_CONF_PATH", str(conf_path.parent))
        glblcfg.loadcfg(conf_path)
        return glblcfg

    return _mock_global_config


def test_dump_platform_names(capsys, mock_global_config):
    """It dumps lists of platform names, nothing else."""
    glblcfg: GlobalConfig = mock_global_config(TEST_CONF)
    glblcfg.dump_platform_names(glblcfg)
    stdout, _ = capsys.readouterr()
    expected = 'localhost\nfoo\nBAR\n'
    assert stdout == expected


def test_dump_platform_details(capsys, mock_global_config):
    """It dumps lists of platform spec."""
    glblcfg: GlobalConfig = mock_global_config(TEST_CONF)
    glblcfg.dump_platform_details(glblcfg)
    out, _ = capsys.readouterr()
    expected = (
        '[platforms]\n    [[foo]]\n        hosts = of_morgoth\n'
        '[platform groups]\n    [[BAR]]\n        platforms = mario, sonic\n'
    )
    assert expected == out


def test_expand_commas(tmp_path: 'Path', mock_global_config: Callable):
    """It should expand comma separated platform and install target
    definitions."""
    glblcfg: GlobalConfig = mock_global_config('''
    [install]
        [[symlink dirs]]
            [[[foo, bar]]]
                run = /x
            [[[foo]]]
                share = /y
            [[[bar]]]
                share = /z

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
    glblcfg._expand_commas()

    # ensure the definition order is preserved
    assert glblcfg.get(['platforms']).keys() == [
        'localhost',
        'foo',
        'bar',
        'baz',
        'pub',
    ]

    # ensure platform sections are correctly deep-merged
    assert glblcfg.get(['platforms', 'foo', 'meta', 'x']) == '1'
    assert glblcfg.get(['platforms', 'bar', 'meta', 'x']) == '3'
    assert glblcfg.get(['platforms', 'baz', 'meta', 'x']) == '3'
    assert glblcfg.get(['platforms', 'pub', 'meta', 'x']) == '4'

    # ensure install target sections are correctly merged:
    assert glblcfg.get(["install", "symlink dirs", "foo", "run"]) == "/x"
    assert glblcfg.get(["install", "symlink dirs", "foo", "share"]) == "/y"
    assert glblcfg.get(["install", "symlink dirs", "bar", "run"]) == "/x"
    assert glblcfg.get(["install", "symlink dirs", "bar", "share"]) == "/z"


@pytest.mark.parametrize(
    'src_dir, err_expected',
    [
        pytest.param(
            '/theoden/rohan', False,
            id="Abs path ok"
        ),
        pytest.param(
            'theoden/rohan', True,
            id="Rel path bad"
        ),
        pytest.param(
            '~theoden/rohan', False,
            id="Starts with usr - ok"
        ),
        pytest.param(
            '$THEODEN/rohan', False,
            id="Starts with env var - ok"
        ),
        pytest.param(
            'rohan/$THEODEN', True,
            id="Rel path with env var not at start - bad"
        ),
    ]
)
def test_source_dir_validation(
    src_dir: str, err_expected: bool,
    tmp_path: 'Path', mock_global_config: Callable
):
    glblcfg: GlobalConfig = mock_global_config(f'''
    [install]
        source dirs = /denethor/gondor, {src_dir}
    ''')
    if err_expected:
        with pytest.raises(ValidationError) as excinfo:
            glblcfg.load()
        assert "must be an absolute path" in str(excinfo.value)
    else:
        glblcfg.load()


def test_platform_ssh_forward_variables(mock_global_config):

    glblcfg: GlobalConfig = mock_global_config('''
    [platforms]
        [[foo]]
            ssh forward environment variables = "FOO", "BAR"
    ''')

    assert glblcfg.get(
        ['platforms', 'foo', 'ssh forward environment variables']
    ) == ["FOO", "BAR"]


def test_reload(
    mock_global_config, tmp_path: 'Path', monkeypatch: pytest.MonkeyPatch
):
    # Load a config
    glblcfg: GlobalConfig = mock_global_config('''
    [platforms]
        [[foo]]
            [[[meta]]]
                x = 1
    ''')

    # Update the global config file and reload
    conf_path = tmp_path / GlobalConfig.CONF_BASENAME
    conf_path.write_text('''
    [platforms]
        [[foo]]
            [[[meta]]]
                x = 2
    ''')
    glblcfg.load()

    # Mock the global config singleton
    monkeypatch.setattr(GlobalConfig, "get_inst", lambda *a, **k: glblcfg)

    assert glblcfg.get(['platforms', 'foo', 'meta', 'x']) == '2'

    from cylc.flow.platforms import get_platform

    platform = get_platform("foo")

    assert platform['meta']['x'] == "2"
