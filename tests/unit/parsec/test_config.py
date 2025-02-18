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

import pytest
import tempfile

from typing import TYPE_CHECKING

from cylc.flow.parsec.config import (
    ConfigNode as Conf,
    ParsecConfig
)
from cylc.flow.parsec.exceptions import (
    IllegalItemError,
    InvalidConfigError,
    ItemNotFoundError,
)
from cylc.flow.parsec.OrderedDict import OrderedDictWithDefaults
from cylc.flow.parsec.upgrade import upgrader
from cylc.flow.parsec.validate import (
    cylc_config_validate,
    CylcConfigValidator as VDR
)


if TYPE_CHECKING:
    from pathlib import Path


def test_loadcfg(sample_spec):
    with (
        tempfile.NamedTemporaryFile() as output_file_name,
        tempfile.NamedTemporaryFile() as rcfile
    ):
        parsec_config = ParsecConfig(
            spec=sample_spec,
            upgrader=None,  # new spec
            output_fname=output_file_name.name,
            tvars=None,
            validator=None  # use default
        )
        rcfile.write("""
            [section1]
                value1 = 'test'
                value2 = 'test'
            [section2]
                enabled = True
            [section3]
                title = 'Ohm'
                [[entries]]
                    key = 'product'
                    value = 1, 2, 3, 4
        """.encode())
        rcfile.seek(0)
        parsec_config.loadcfg(rcfile.name, "File test_loadcfg")

        sparse = parsec_config.sparse
        value = sparse['section3']['entries']['value']
        assert [1, 2, 3, 4] == value

        # calling it multiple times should still work
        parsec_config.loadcfg(rcfile.name, "File test_loadcfg")
        parsec_config.loadcfg(rcfile.name, "File test_loadcfg")

        sparse = parsec_config.sparse
        value = sparse['section3']['entries']['value']
        assert [1, 2, 3, 4] == value


def test_loadcfg_override(sample_spec):
    """Test that loading a second config file overrides common settings but
    leaves in settings only present in the first"""
    with tempfile.NamedTemporaryFile() as output_file_name:
        parsec_config = ParsecConfig(
            spec=sample_spec,
            upgrader=None,
            output_fname=output_file_name.name,
            tvars=None,
            validator=None
        )
        with tempfile.NamedTemporaryFile() as conf_file1:
            conf_file1.write("""
                [section1]
                    value1 = 'frodo'
                    value2 = 'sam'
            """.encode())
            conf_file1.seek(0)
            parsec_config.loadcfg(conf_file1.name, "File test_loadcfg")
        sparse = parsec_config.sparse
        assert sparse['section1']['value1'] == 'frodo'
        assert sparse['section1']['value2'] == 'sam'

        with tempfile.NamedTemporaryFile() as conf_file2:
            conf_file2.write("""
                [section1]
                    value2 = 'pippin'
            """.encode())
            conf_file2.seek(0)
            parsec_config.loadcfg(conf_file2.name, "File test_loadcfg")
        sparse = parsec_config.sparse
        assert sparse['section1']['value1'] == 'frodo'
        assert sparse['section1']['value2'] == 'pippin'


def test_loadcfg_with_upgrade(sample_spec):
    def upg(cfg, description):
        u = upgrader(cfg, description)
        u.obsolete('1.0', ['section3', 'entries'])
        u.upgrade()

    with (
        tempfile.NamedTemporaryFile() as output_file_name,
        tempfile.NamedTemporaryFile() as rcfile
    ):
        parsec_config = ParsecConfig(
            spec=sample_spec,
            upgrader=upg,
            output_fname=output_file_name.name,
            tvars=None,
            validator=None  # use default
        )
        rcfile.write("""
        [section1]
        value1 = 'test'
        value2 = 'test'
        [section2]
        enabled = True
        [section3]
        title = 'Ohm'
        [[entries]]
        key = 'product'
        value = 1, 2, 3, 4
        """.encode())
        rcfile.seek(0)
        parsec_config.loadcfg(rcfile.name, "1.1")

        sparse = parsec_config.sparse
        # removed by the obsolete upgrade
        assert 'entries' not in sparse['section3']


def test_validate():
    """
    An interesting aspect of the ParsecConfig.validate, is that if you
    have a sparse dict produced by this class, and you call the validate
    on that dict again, you may have TypeErrors.

    That occurs because the values like 'True' are validated against the
    spec and converted from Strings with quotes, to bool types. So the
    next type you run the validation if expects Strings...
    :return:
    """

    with Conf('myconf') as spec:
        with Conf('section'):
            Conf('name', VDR.V_STRING)
            Conf('address', VDR.V_STRING)

    parsec_config = ParsecConfig(
        spec=spec,
        upgrader=None,  # new spec
        output_fname=None,  # not going to call the loadcfg
        tvars=None,
        validator=None  # use default
    )

    sparse = OrderedDictWithDefaults()
    parsec_config.validate(sparse)  # empty dict is OK

    with pytest.raises(IllegalItemError):
        sparse = OrderedDictWithDefaults()
        sparse['name'] = 'True'
        parsec_config.validate(sparse)  # name is not valid

    sparse = OrderedDictWithDefaults()
    sparse['section'] = OrderedDictWithDefaults()
    sparse['section']['name'] = 'Wind'
    sparse['section']['address'] = 'Corner'
    parsec_config.validate(sparse)


@pytest.fixture
def parsec_config_2(tmp_path: 'Path'):
    with Conf('myconf') as spec:
        with Conf('section'):
            Conf('name', VDR.V_STRING)
            Conf('address', VDR.V_INTEGER_LIST)
        with Conf('allow_many'):
            Conf('<user defined>', VDR.V_STRING, '')
        with Conf('so_many'):
            with Conf('<thing>'):
                Conf('color', VDR.V_STRING)
                Conf('horsepower', VDR.V_INTEGER)
    parsec_config = ParsecConfig(spec, validator=cylc_config_validate)
    conf_file = tmp_path / 'myconf'
    conf_file.write_text("""
    [section]
    name = test
    [allow_many]
    anything = yup
    [so_many]
    [[legs]]
    horsepower = 123
    """)
    parsec_config.loadcfg(conf_file, "1.0")
    return parsec_config


def test_expand(parsec_config_2: ParsecConfig):
    parsec_config_2.expand()
    sparse = parsec_config_2.sparse
    assert sparse['allow_many']['anything'] == 'yup'
    assert '__MANY__' not in sparse['allow_many']


def test_get(parsec_config_2: ParsecConfig):
    cfg = parsec_config_2.get(keys=None, sparse=False)
    assert cfg == parsec_config_2.dense

    cfg = parsec_config_2.get(keys=None, sparse=True)
    assert cfg == parsec_config_2.sparse

    cfg = parsec_config_2.get(keys=['section'], sparse=True)
    assert cfg == parsec_config_2.sparse['section']


@pytest.mark.parametrize('keys, expected', [
    (['section', 'name'], 'test'),
    (['section', 'a'], InvalidConfigError),
    (['alloy_many', 'anything'], InvalidConfigError),
    (['allow_many', 'anything'], 'yup'),
    (['allow_many', 'a'], ItemNotFoundError),
    (['so_many', 'legs', 'horsepower'], 123),
    (['so_many', 'legs', 'color'], ItemNotFoundError),
    (['so_many', 'legs', 'a'], InvalidConfigError),
    (['so_many', 'teeth', 'horsepower'], ItemNotFoundError),
])
def test_get__sparse(parsec_config_2: ParsecConfig, keys, expected):
    if isinstance(expected, type) and issubclass(expected, Exception):
        with pytest.raises(expected):
            parsec_config_2.get(keys, sparse=True)
    else:
        assert parsec_config_2.get(keys, sparse=True) == expected


def test_mdump_none(config, sample_spec, capsys):
    cfg = config(sample_spec, '''
        [section1]
            value1 = abc
            value2 = def
    ''')
    cfg.mdump()
    std = capsys.readouterr()
    assert std.out == ''
    assert std.err == ''


def test_mdump_some(config, sample_spec, capsys):
    cfg = config(sample_spec, '''
        [section1]
            value1 = abc
            value2 = def
    ''')
    cfg.mdump(
        [
            ['section1', 'value1'],
            ['section1', 'value2'],
        ]
    )
    std = capsys.readouterr()
    assert std.out == 'abc\ndef\n'
    assert std.err == ''


def test_mdump_oneline(config, sample_spec, capsys):
    cfg = config(sample_spec, '''
        [section1]
            value1 = abc
            value2 = def
    ''')
    cfg.mdump(
        [
            ['section1', 'value1'],
            ['section1', 'value2'],
        ],
        oneline=True
    )
    std = capsys.readouterr()
    assert std.out == 'abc def\n'
    assert std.err == ''


def test_get_none(config, sample_spec):
    cfg = config(sample_spec, '')  # blank config
    assert cfg.get(sparse=True) == {}


def test__get_namespace_parents():
    """It returns a list of parents and nothing else"""
    with Conf('myconfig.cylc') as myconf:
        with Conf('a'):
            with Conf('b'):
                with Conf('<c>'):
                    with Conf('d'):
                        Conf('<e>')
        with Conf('x'):
            Conf('y')

    cfg = ParsecConfig(myconf)
    assert cfg.manyparents == [
        ['a', 'b'],
        ['a', 'b', '__MANY__', 'd'],
    ]
