#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & Contributors.
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

import unittest

from cylc.cfgvalidate import CylcConfigValidator as VDR
from parsec.OrderedDict import OrderedDictWithDefaults
from parsec.validate import *

SAMPLE_SPEC_1 = {
    'section1': {
        'value1': [VDR.V_STRING, ''],
        'value2': [VDR.V_STRING, 'what?']
    },
    'section2': {
        'enabled': [VDR.V_BOOLEAN],
    },
    'section3': {
        'title': [VDR.V_STRING, 'default', '1', '2'],
        'amounts': [VDR.V_INTEGER_LIST, [1, 2, 3], 1, 2, 3],
        'entries': {
            'key': [VDR.V_STRING],
            'value': [VDR.V_INTEGER_LIST]
        }
    },
    '__MANY__': {
        'section3000000': [VDR.V_STRING, ''],
        'ids': [VDR.V_INTEGER_LIST]
    }
}


def get_parsec_validator_invalid_values():
    """
    Data provider or invalid values for parsec validator. All values must not
    be null (covered elsewhere), and not dict's.

    Possible invalid scenarios must include:

    - cfg[key] is a list AND a value is not in list of the possible values
    - OR
    - cfg[key] is not a list AND cfg[key] not in the list of possible values

    :return: a list with sets of tuples for the test parameters
    :rtype: list
    """

    values = []

    # variables reused throughout
    spec = None
    msg = None

    # set 1 (t, f, f, t)
    spec = {
        'value': [VDR.V_INTEGER_LIST, 1, 2, 3, 4]
    }
    cfg = OrderedDictWithDefaults()
    cfg['value'] = "1, 2, 3"
    msg = None
    values.append((spec, cfg, msg))

    # set 2 (t, t, f, t)
    spec = {
        'value': [VDR.V_INTEGER_LIST, 1, 2, 3, 4]
    }
    cfg = OrderedDictWithDefaults()
    cfg['value'] = "1, 2, 5"
    msg = 'Illegal option value: value = [1, 2, 5]'
    values.append((spec, cfg, msg))

    # set 3 (f, f, t, f)
    spec = {
        'value': [VDR.V_INTEGER, 1, 2, 3, 4]
    }
    cfg = OrderedDictWithDefaults()
    cfg['value'] = "2"
    msg = None
    values.append((spec, cfg, msg))

    # set 4 (f, f, t, t)
    spec = {
        'value': [VDR.V_INTEGER, 1, 2, 3, 4]
    }
    cfg = OrderedDictWithDefaults()
    cfg['value'] = "5"
    msg = 'Illegal option value: value = 5'
    values.append((spec, cfg, msg))

    return values


class TestValidate(unittest.TestCase):
    """Unit Tests for parsec.validate.ParsecValidator.coerce* methods."""

    def test_list_value_error(self):
        keys = ['a,', 'b', 'c']
        value = 'a sample value'
        error = ListValueError(keys, value, "who cares:")
        output = error.msg
        expected = "who cares:\n    [a,][b]c = a sample value"
        self.assertEqual(expected, output)

    def test_list_value_error_with_exception(self):
        keys = ['a,', 'b', 'c']
        value = 'a sample value'
        exc = Exception('test')
        error = ListValueError(keys, value, "who cares:", exc)
        output = error.msg
        expected = "who cares:\n    [a,][b]c = a sample value: test"
        self.assertEqual(expected, output)

    def test_illegal_value_error(self):
        value_type = 'ClassA'
        keys = ['a,', 'b', 'c']
        value = 'a sample value'
        error = IllegalValueError(value_type, keys, value)
        output = error.msg
        expected = "Illegal ClassA value: [a,][b]c = a sample value"
        self.assertEqual(expected, output)

    def test_illegal_value_error_with_exception(self):
        value_type = 'ClassA'
        keys = ['a,', 'b', 'c']
        value = 'a sample value'
        exc = Exception('test')
        error = IllegalValueError(value_type, keys, value, exc)
        output = error.msg
        expected = "Illegal ClassA value: [a,][b]c = a sample value: test"
        self.assertEqual(expected, output)

    def test_illegal_item_error(self):
        keys = ['a,', 'b', 'c']
        key = 'a sample value'
        error = IllegalItemError(keys, key)
        output = error.msg
        expected = "Illegal item: [a,][b][c]a sample value"
        self.assertEqual(expected, output)

    def test_illegal_item_error_message(self):
        keys = ['a,', 'b', 'c']
        key = 'a sample value'
        message = "invalid"
        error = IllegalItemError(keys, key, message)
        output = error.msg
        expected = "Illegal item (invalid): [a,][b][c]a sample value"
        self.assertEqual(expected, output)

    def test_parsec_validator_invalid_key(self):
        parsec_validator = ParsecValidator()
        cfg = OrderedDictWithDefaults()
        cfg['section1'] = OrderedDictWithDefaults()
        cfg['section1']['value1'] = '1'
        cfg['section1']['value2'] = '2'
        cfg['section22'] = 'abc'
        with self.assertRaises(IllegalItemError):
            parsec_validator.validate(cfg, SAMPLE_SPEC_1)

    def test_parsec_validator_invalid_key_no_spec(self):
        parsec_validator = ParsecValidator()
        cfg = OrderedDictWithDefaults()
        cfg['section1'] = OrderedDictWithDefaults()
        cfg['section1']['value1'] = '1'
        cfg['section1']['value2'] = '2'
        cfg['section22'] = 'abc'
        spec = SAMPLE_SPEC_1.copy()
        del (spec['__MANY__'])
        with self.assertRaises(IllegalItemError):
            parsec_validator.validate(cfg, spec)

    def test_parsec_validator_invalid_key_with_many_spaces(self):
        parsec_validator = ParsecValidator()
        cfg = OrderedDictWithDefaults()
        cfg['section1'] = OrderedDictWithDefaults()
        cfg['section1']['value1'] = '1'
        cfg['section1']['value2'] = '2'
        cfg['section  3000000'] = 'test'
        with self.assertRaises(IllegalItemError) as cm:
            parsec_validator.validate(cfg, SAMPLE_SPEC_1)
        self.assertEqual("Illegal item (consecutive spaces): "
                         "section  3000000", cm.exception.msg)

    def test_parsec_validator_invalid_key_with_many_invalid_values(self):
        for spec, cfg, msg in get_parsec_validator_invalid_values():
            parsec_validator = ParsecValidator()
            if msg is not None:
                with self.assertRaises(IllegalValueError) as cm:
                    parsec_validator.validate(cfg, spec)
                self.assertEqual(msg, cm.exception.msg)
            else:
                # parsec_validator.validate(cfg, spec)
                # let's use the alias `parsec_validate` here
                parsec_validate(cfg, spec)
                # TBD assertIsNotNone when 2.6+
                self.assertTrue(parsec_validator is not None)

    def test_parsec_validator_invalid_key_with_many_1(self):
        parsec_validator = ParsecValidator()
        cfg = OrderedDictWithDefaults()
        cfg['section1'] = OrderedDictWithDefaults()
        cfg['section1']['value1'] = '1'
        cfg['section1']['value2'] = '2'
        cfg['section3000000'] = OrderedDictWithDefaults()
        parsec_validator.validate(cfg, SAMPLE_SPEC_1)
        # TBD assertIsNotNone when 2.6+
        self.assertTrue(parsec_validator is not None)

    def test_parsec_validator_invalid_key_with_many_2(self):
        parsec_validator = ParsecValidator()
        cfg = OrderedDictWithDefaults()
        cfg['section3'] = OrderedDictWithDefaults()
        cfg['section3']['title'] = '1'
        cfg['section3']['entries'] = OrderedDictWithDefaults()
        cfg['section3']['entries']['key'] = 'name'
        cfg['section3']['entries']['value'] = "1, 2, 3, 4"
        parsec_validator.validate(cfg, SAMPLE_SPEC_1)
        # TBD assertIsNotNone when 2.6+
        self.assertTrue(parsec_validator is not None)

    def test_parsec_validator(self):
        parsec_validator = ParsecValidator()
        cfg = OrderedDictWithDefaults()
        cfg['section1'] = OrderedDictWithDefaults()
        cfg['section1']['value1'] = '1'
        cfg['section1']['value2'] = '2'
        cfg['section3'] = OrderedDictWithDefaults()
        cfg['section3']['title'] = None
        parsec_validator.validate(cfg, SAMPLE_SPEC_1)
        # TBD assertIsNotNone when 2.6+
        self.assertTrue(parsec_validator is not None)

    # --- static methods

    def test_coerce_none_fails(self):
        with self.assertRaises(AttributeError):
            ParsecValidator.coerce_boolean(None, [])
        with self.assertRaises(AttributeError):
            ParsecValidator.coerce_float(None, [])
        with self.assertRaises(AttributeError):
            ParsecValidator.coerce_int(None, [])


if __name__ == '__main__':
    unittest.main()
