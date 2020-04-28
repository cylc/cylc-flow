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
import unittest

from cylc.flow.parsec import config
from cylc.flow.parsec.OrderedDict import OrderedDictWithDefaults
from cylc.flow.parsec.exceptions import ParsecError
from cylc.flow.parsec.upgrade import upgrader
from cylc.flow.parsec.validate import (
    cylc_config_validate, IllegalItemError, CylcConfigValidator as VDR)

SAMPLE_SPEC_1 = {
    'section1': {
        'value1': [VDR.V_STRING, ''],
        'value2': [VDR.V_STRING, 'what?']
    },
    'section2': {
        'enabled': [VDR.V_BOOLEAN, False]
    },
    'section3': {
        'title': [VDR.V_STRING],
        'entries': {
            'key': [VDR.V_STRING],
            'value': [VDR.V_INTEGER_LIST]
        }
    }
}


class TestConfig(unittest.TestCase):

    def test_loadcfg(self):
        with tempfile.NamedTemporaryFile() as output_file_name:
            with tempfile.NamedTemporaryFile() as rcfile:
                parsec_config = config.ParsecConfig(
                    spec=SAMPLE_SPEC_1,
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
                self.assertEqual([1, 2, 3, 4], value)

                # calling it multiple times should still work
                parsec_config.loadcfg(rcfile.name, "File test_loadcfg")
                parsec_config.loadcfg(rcfile.name, "File test_loadcfg")

                sparse = parsec_config.sparse
                value = sparse['section3']['entries']['value']
                self.assertEqual([1, 2, 3, 4], value)

    def test_loadcfg_with_upgrade(self):
        def upg(cfg, description):
            u = upgrader(cfg, description)
            u.obsolete('1.0', ['section3', 'entries'])
            u.upgrade()

        with tempfile.NamedTemporaryFile() as output_file_name:
            with tempfile.NamedTemporaryFile() as rcfile:
                parsec_config = config.ParsecConfig(
                    spec=SAMPLE_SPEC_1,
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
                self.assertTrue('entries' not in sparse['section3'])

    def test_validate(self):
        """
        An interesting aspect of the ParsecConfig.validate, is that if you
        have a sparse dict produced by this class, and you call the validate
        on that dict again, you may have TypeErrors.

        That occurs because the values like 'True' are validated against the
        spec and converted from Strings with quotes, to bool types. So the
        next type you run the validation if expects Strings...
        :return:
        """

        spec = {
            'section': {
                'name': [VDR.V_STRING],
                'address': [VDR.V_STRING],
            }
        }

        parsec_config = config.ParsecConfig(
            spec=spec,
            upgrader=None,  # new spec
            output_fname=None,  # not going to call the loadcfg
            tvars=None,
            validator=None  # use default
        )

        sparse = OrderedDictWithDefaults()
        parsec_config.validate(sparse)  # empty dict is OK

        with self.assertRaises(IllegalItemError):
            sparse = OrderedDictWithDefaults()
            sparse['name'] = 'True'
            parsec_config.validate(sparse)  # name is not valid

        sparse = OrderedDictWithDefaults()
        sparse['section'] = OrderedDictWithDefaults()
        sparse['section']['name'] = 'Wind'
        sparse['section']['address'] = 'Corner'
        parsec_config.validate(sparse)

    def test_expand(self):
        spec = {
            'section': {
                'name': [VDR.V_STRING],
                'address': [VDR.V_INTEGER_LIST]
            },
            'allow_many': {
                '__MANY__': [VDR.V_STRING, '']
            }
        }

        with tempfile.NamedTemporaryFile() as output_file_name:
            with tempfile.NamedTemporaryFile() as rcfile:
                parsec_config = config.ParsecConfig(
                    spec=spec,
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
                self.assertEqual('yup', sparse['allow_many']['anything'])
                self.assertTrue('__MANY__' not in sparse['allow_many'])

    def test_get_item(self):
        spec = {
            'section': {
                'name': [VDR.V_STRING],
                'address': [VDR.V_INTEGER_LIST]
            },
            'allow_many': {
                '__MANY__': [VDR.V_STRING, '']
            }
        }

        with tempfile.NamedTemporaryFile() as output_file_name:
            with tempfile.NamedTemporaryFile() as rcfile:
                parsec_config = config.ParsecConfig(
                    spec=spec,
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
                self.assertEqual(parsec_config.dense, cfg)

                cfg = parsec_config.get(keys=None, sparse=True)
                self.assertEqual(parsec_config.sparse, cfg)

                cfg = parsec_config.get(keys=['section'], sparse=True)
                self.assertEqual(parsec_config.sparse['section'], cfg)

                cfg = parsec_config.get(keys=['section', 'name'], sparse=True)
                self.assertEqual('test', cfg)

                with self.assertRaises(config.ItemNotFoundError):
                    parsec_config.get(keys=['section', 'a'], sparse=True)

    def test_item_not_found_error(self):
        error = config.ItemNotFoundError("internal error")
        self.assertEqual('item not found: internal error', str(error))

    def test_not_single_item_error(self):
        error = config.NotSingleItemError("internal error")
        self.assertEqual('not a singular item: internal error', str(error))


if __name__ == '__main__':
    unittest.main()
