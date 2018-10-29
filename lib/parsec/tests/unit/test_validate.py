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
"""Unit Tests for parsec.validate.ParsecValidator.coerce* methods."""

import unittest

from parsec.validate import IllegalValueError, ParsecValidator


class TestParsecValidator(unittest.TestCase):
    """Unit Tests for parsec.validate.ParsecValidator.coerce* methods."""

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
                ('  ', None)]:
            self.assertEqual(
                validator.coerce_boolean(value, ['whatever']), result)
        # The bad
        for value in [
                'None', ' Who cares? ', '3.14', '[]', '[True]', 'True, False']:
            self.assertRaises(
                IllegalValueError,
                validator.coerce_boolean, value, ['whatever'])

    def test_coerce_float(self):
        """Test coerce_float."""
        validator = ParsecValidator()
        # The good
        for value, result in [
                ('', None),
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
                ('6.62607004e-34', 6.62607004e-34)]:
            self.assertAlmostEqual(
                validator.coerce_float(value, ['whatever']), result)
        # The bad
        for value in [
                'None', ' Who cares? ', 'True', '[]', '[3.14]', '3.14, 2.72']:
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
                 [6.02e23, -1.6021765e-19, 6.62607004e-34])]:
            items = validator.coerce_float_list(value, ['whatever'])
            for item, result in zip(items, results):
                self.assertAlmostEqual(item, result)
        # The bad
        for value in [
                'None', 'e, i, e, i, o', '[]', '[3.14]', 'pi, 2.72']:
            self.assertRaises(
                IllegalValueError,
                validator.coerce_float_list, value, ['whatever'])

    def test_coerce_int(self):
        """Test coerce_int."""
        validator = ParsecValidator()
        # The good
        for value, result in [
                ('', None),
                ('0', 0),
                ('3', 3),
                ('-3', -3),
                ('-0', -0),
                ('653456', 653456),
                ('-8362583645365', -8362583645365)]:
            self.assertAlmostEqual(
                validator.coerce_int(value, ['whatever']), result)
        # The bad
        for value in [
                'None', ' Who cares? ', 'True', '4.8', '[]', '[3]', '60*60']:
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
                 [128] * 10 + [-78, -77, -76, -75, -74, -73, -72, 2048])]:
            self.assertEqual(
                validator.coerce_int_list(value, ['whatever']), results)
        # The bad
        for value in [
                'None', 'e, i, e, i, o', '[]', '1..3, x', 'one..ten']:
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
                ('None', 'None')]:
            self.assertAlmostEqual(
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
                 ['New Zealand', 'United Kingdom'])]:
            self.assertEqual(
                validator.coerce_str_list(value, ['whatever']), results)


if __name__ == '__main__':
    unittest.main()
