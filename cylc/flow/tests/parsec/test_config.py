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

import tempfile

import pytest

from cylc.flow.parsec import config
from cylc.flow.parsec.config import ConfigNode as Conf
from cylc.flow.parsec.OrderedDict import OrderedDictWithDefaults
from cylc.flow.parsec.upgrade import upgrader
from cylc.flow.parsec.validate import (
    cylc_config_validate,
    IllegalItemError,
    CylcConfigValidator as VDR
)

from . import (
    config as parse_config,
    sample_spec,
)


def test_loadcfg(sample_spec):
    with tempfile.NamedTemporaryFile() as output_file_name:
        with tempfile.NamedTemporaryFile() as rcfile:
            parsec_config = config.ParsecConfig(
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


def test_loadcfg_with_upgrade(sample_spec):
    def upg(cfg, description):
        u = upgrader(cfg, description)
        u.obsolete('1.0', ['section3', 'entries'])
        u.upgrade()

    with tempfile.NamedTemporaryFile() as output_file_name:
        with tempfile.NamedTemporaryFile() as rcfile:
            parsec_config = config.ParsecConfig(
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

    parsec_config = config.ParsecConfig(
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
def sample_spec_2():
    with Conf('myconf') as spec:
        with Conf('section'):
            Conf('name', VDR.V_STRING)
            Conf('address', VDR.V_INTEGER_LIST)
        with Conf('allow_many'):
            Conf('<user defined>', VDR.V_STRING, '')
    return spec


def test_expand(sample_spec_2):
    with tempfile.NamedTemporaryFile() as output_file_name:
        with tempfile.NamedTemporaryFile() as rcfile:
            parsec_config = config.ParsecConfig(
                spec=sample_spec_2,
                upgrader=None,
                output_fname=output_file_name.name,
                tvars=None,
                validator=cylc_config_validate
            )
            rcfile.write("""
                    [section]
                    name = test
                    [allow_many]
                    anything = yup
                    """.encode())
            rcfile.seek(0)
            parsec_config.loadcfg(rcfile.name, "1.0")

            parsec_config.expand()

            sparse = parsec_config.sparse
            assert 'yup' == sparse['allow_many']['anything']
            assert '__MANY__' not in sparse['allow_many']


def test_get_item(sample_spec_2):
    with tempfile.NamedTemporaryFile() as output_file_name:
        with tempfile.NamedTemporaryFile() as rcfile:
            parsec_config = config.ParsecConfig(
                spec=sample_spec_2,
                upgrader=None,
                output_fname=output_file_name.name,
                tvars=None,
                validator=cylc_config_validate
            )
            rcfile.write("""
                            [section]
                            name = test
                            [allow_many]
                            anything = yup
                            """.encode())
            rcfile.seek(0)
            parsec_config.loadcfg(rcfile.name, "1.0")

            cfg = parsec_config.get(keys=None, sparse=None)
            assert parsec_config.dense == cfg

            cfg = parsec_config.get(keys=None, sparse=True)
            assert parsec_config.sparse == cfg

            cfg = parsec_config.get(keys=['section'], sparse=True)
            assert parsec_config.sparse['section'] == cfg

            cfg = parsec_config.get(keys=['section', 'name'], sparse=True)
            assert 'test' == cfg

            with pytest.raises(config.ItemNotFoundError):
                parsec_config.get(keys=['section', 'a'], sparse=True)


def test_item_not_found_error():
    error = config.ItemNotFoundError("internal error")
    assert 'item not found: internal error' == str(error)


def test_not_single_item_error():
    error = config.NotSingleItemError("internal error")
    assert 'not a singular item: internal error' == str(error)


def test_mdump_none(parse_config, sample_spec, capsys):
    cfg = parse_config(sample_spec, '''
        [section1]
            value1 = abc
            value2 = def
    ''')
    cfg.mdump(pnative=True)
    std = capsys.readouterr()
    assert std.out == ''
    assert std.err == ''


def test_mdump_some(parse_config, sample_spec, capsys):
    cfg = parse_config(sample_spec, '''
        [section1]
            value1 = abc
            value2 = def
    ''')
    cfg.mdump(
        [
            ['section1', 'value1'],
            ['section1', 'value2'],
        ],
        pnative=True
    )
    std = capsys.readouterr()
    assert std.out == 'abc\ndef\n'
    assert std.err == ''


def test_mdump_oneline(parse_config, sample_spec, capsys):
    cfg = parse_config(sample_spec, '''
        [section1]
            value1 = abc
            value2 = def
    ''')
    cfg.mdump(
        [
            ['section1', 'value1'],
            ['section1', 'value2'],
        ],
        pnative=True,
        oneline=True
    )
    std = capsys.readouterr()
    assert std.out == 'abc def\n'
    assert std.err == ''


def test_get_none(parse_config):
    cfg = parse_config(sample_spec, '')  # blank config
    assert cfg.get(sparse=True) == {}
