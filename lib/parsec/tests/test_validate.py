#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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

    def test_coerce_boolean(self):
        """Test coerce_boolean."""
        validator = ParsecValidator()
        # The good
        for value, result in [
            ('True', True),
            (' True ', True),
            ('"True"', True),
            ("'True'", True),
            ('true', True),
            (' true ', True),
            ('"true"', True),
            ("'true'", True),
            ('False', False),
            (' False ', False),
            ('"False"', False),
            ("'False'", False),
            ('false', False),
            (' false ', False),
            ('"false"', False),
            ("'false'", False),
            ('', None),
            ('  ', None)
        ]:
            self.assertEqual(
                validator.coerce_boolean(value, ['whatever']), result)
        # The bad
        for value in [
            'None', ' Who cares? ', '3.14', '[]', '[True]', 'True, False'
        ]:
            self.assertRaises(
                IllegalValueError,
                validator.coerce_boolean, value, ['whatever'])

    def test_coerce_float(self):
        """Test coerce_float."""
        validator = ParsecValidator()
        # The good
        for value, result in [
            ('3', 3.0),
            ('9.80', 9.80),
            ('3.141592654', 3.141592654),
            ('"3.141592654"', 3.141592654),
            ("'3.141592654'", 3.141592654),
            ('-3', -3.0),
            ('-3.1', -3.1),
            ('0', 0.0),
            ('-0', -0.0),
            ('0.0', 0.0),
            ('1e20', 1.0e20),
            ('6.02e23', 6.02e23),
            ('-1.6021765e-19', -1.6021765e-19),
            ('6.62607004e-34', 6.62607004e-34)
        ]:
            self.assertAlmostEqual(
                validator.coerce_float(value, ['whatever']), result)
        self.assertEqual(
            validator.coerce_int('', ['whatever']), None)  # not a number
        # The bad
        for value in [
            'None', ' Who cares? ', 'True', '[]', '[3.14]', '3.14, 2.72'
        ]:
            self.assertRaises(
                IllegalValueError,
                validator.coerce_float, value, ['whatever'])

    def test_coerce_float_list(self):
        """Test coerce_float_list."""
        validator = ParsecValidator()
        # The good
        for value, results in [
            ('', []),
            ('3', [3.0]),
            ('2*3.141592654', [3.141592654, 3.141592654]),
            ('12*8, 8*12.0', [8.0] * 12 + [12.0] * 8),
            ('-3, -2, -1, -0.0, 1.0', [-3.0, -2.0, -1.0, -0.0, 1.0]),
            ('6.02e23, -1.6021765e-19, 6.62607004e-34',
             [6.02e23, -1.6021765e-19, 6.62607004e-34])
        ]:
            items = validator.coerce_float_list(value, ['whatever'])
            for item, result in zip(items, results):
                self.assertAlmostEqual(item, result)
        # The bad
        for value in [
            'None', 'e, i, e, i, o', '[]', '[3.14]', 'pi, 2.72', '2*True'
        ]:
            self.assertRaises(
                IllegalValueError,
                validator.coerce_float_list, value, ['whatever'])

    def test_coerce_int(self):
        """Test coerce_int."""
        validator = ParsecValidator()
        # The good
        for value, result in [
            ('0', 0),
            ('3', 3),
            ('-3', -3),
            ('-0', -0),
            ('653456', 653456),
            ('-8362583645365', -8362583645365)
        ]:
            self.assertAlmostEqual(
                validator.coerce_int(value, ['whatever']), result)
        self.assertEqual(
            validator.coerce_int('', ['whatever']), None)  # not a number
        # The bad
        for value in [
            'None', ' Who cares? ', 'True', '4.8', '[]', '[3]', '60*60'
        ]:
            self.assertRaises(
                IllegalValueError,
                validator.coerce_int, value, ['whatever'])

    def test_coerce_int_list(self):
        """Test coerce_int_list."""
        validator = ParsecValidator()
        # The good
        for value, results in [
            ('', []),
            ('3', [3]),
            ('1..10, 11..20..2',
             [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19]),
            ('18 .. 24', [18, 19, 20, 21, 22, 23, 24]),
            ('18 .. 24 .. 3', [18, 21, 24]),
            ('-10..10..3', [-10, -7, -4, -1, 2, 5, 8]),
            ('10*3, 4*-6', [3] * 10 + [-6] * 4),
            ('10*128, -78..-72, 2048',
             [128] * 10 + [-78, -77, -76, -75, -74, -73, -72, 2048])
        ]:
            self.assertEqual(
                validator.coerce_int_list(value, ['whatever']), results)
        # The bad
        for value in [
            'None', 'e, i, e, i, o', '[]', '1..3, x', 'one..ten'
        ]:
            self.assertRaises(
                IllegalValueError,
                validator.coerce_int_list, value, ['whatever'])

    def test_coerce_str(self):
        """Test coerce_str."""
        validator = ParsecValidator()
        # The good
        for value, result in [
            ('', ''),
            ('Hello World!', 'Hello World!'),
            ('"Hello World!"', 'Hello World!'),
            ('"Hello Cylc\'s World!"', 'Hello Cylc\'s World!'),
            ("'Hello World!'", 'Hello World!'),
            ('0', '0'),
            ('My list is:\nfoo, bar, baz\n', 'My list is:\nfoo, bar, baz'),
            ('    Hello:\n    foo\n    bar\n    baz\n',
             'Hello:\nfoo\nbar\nbaz'),
            ('    Hello:\n        foo\n    Greet\n        baz\n',
             'Hello:\n    foo\nGreet\n    baz'),
            ('False', 'False'),
            ('None', 'None'),
            (['a', 'b'], 'a\nb')
        ]:
            self.assertEqual(
                validator.coerce_str(value, ['whatever']), result)

    def test_coerce_str_list(self):
        """Test coerce_str_list."""
        validator = ParsecValidator()
        # The good
        for value, results in [
            ('', []),
            ('Hello', ['Hello']),
            ('"Hello"', ['Hello']),
            ('1', ['1']),
            ('Mercury, Venus, Earth, Mars',
             ['Mercury', 'Venus', 'Earth', 'Mars']),
            ('Mercury, Venus, Earth, Mars,\n"Jupiter",\n"Saturn"\n',
             ['Mercury', 'Venus', 'Earth', 'Mars', 'Jupiter', 'Saturn']),
            ('New Zealand, United Kingdom',
             ['New Zealand', 'United Kingdom'])
        ]:
            self.assertEqual(
                validator.coerce_str_list(value, ['whatever']), results)

    def test_strip_and_unquote(self):
        with self.assertRaises(IllegalValueError):
            ParsecValidator.strip_and_unquote(['a'], '"""')

    def test_strip_and_unquote_list(self):
        for value, results in [
            ('"a"\n"b"', ['a', 'b']),
            ('"a", "b"', ['a', 'b']),
            ('"a", "b"', ['a', 'b']),
            ('"c" # d', ['c']),
            ('"a", "b", "c" # d', ['a', 'b', 'c']),
            ('"a"\n"b"\n"c" # d', ['a', 'b', 'c']),
            ("'a', 'b'", ['a', 'b']),
            ("'c' #d", ['c']),
            ("'a', 'b', 'c' # d", ['a', 'b', 'c']),
            ("'a'\n'b'\n'c' # d", ['a', 'b', 'c']),
            ('a, b, c,', ['a', 'b', 'c']),
            ('a, b, c # d', ['a', 'b', 'c']),
            ('a, b, c\n"d"', ['a', 'b', 'd']),
            ('a, b, c\n"d" # e', ['a', 'b', '"d"'])
        ]:
            self.assertEqual(results, ParsecValidator.strip_and_unquote_list(
                ['a'], value))

    def test_strip_and_unquote_list_multiparam(self):
        with self.assertRaises(ListValueError):
            ParsecValidator.strip_and_unquote_list(
                ['a'], 'a, b, c<a,b>'
            )


if __name__ == '__main__':
    unittest.main()
