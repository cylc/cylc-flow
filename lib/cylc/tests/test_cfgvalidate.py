#!/usr/bin/env python3

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
"""Unit Tests for cylc.cfgvalidate.CylcConfigValidator.coerce* methods."""

import unittest

from cylc.cfgvalidate import (
    CylcConfigValidator, DurationFloat, IllegalValueError)


class TestCylcConfigValidator(unittest.TestCase):
    """Unit Tests for cylc.cfgvalidate.CylcConfigValidator.coerce* methods."""

    def test_coerce_cycle_point(self):
        """Test coerce_cycle_point."""
        validator = CylcConfigValidator()
        # The good
        for value, result in [
                ('', None),
                ('3', '3'),
                ('2018', '2018'),
                ('20181225T12Z', '20181225T12Z'),
                ('2018-12-25T12:00+11:00', '2018-12-25T12:00+11:00')]:
            self.assertEqual(
                validator.coerce_cycle_point(value, ['whatever']), result)
        # The bad
        for value in [
                'None', ' Who cares? ', 'True', '1, 2', '20781340E10']:
            self.assertRaises(
                IllegalValueError,
                validator.coerce_cycle_point, value, ['whatever'])

    def test_coerce_cycle_point_format(self):
        """Test coerce_cycle_point_format."""
        validator = CylcConfigValidator()
        # The good
        for value, result in [
                ('', None),
                ('%Y%m%dT%H%M%z', '%Y%m%dT%H%M%z'),
                ('CCYYMMDDThhmmZ', 'CCYYMMDDThhmmZ'),
                ('XCCYYMMDDThhmmZ', 'XCCYYMMDDThhmmZ')]:
            self.assertEqual(
                validator.coerce_cycle_point_format(value, ['whatever']),
                result)
        # The bad
        for value in ['%i%j', 'Y/M/D']:
            self.assertRaises(
                IllegalValueError,
                validator.coerce_cycle_point_format, value, ['whatever'])

    def test_coerce_cycle_point_time_zone(self):
        """Test coerce_cycle_point_time_zone."""
        validator = CylcConfigValidator()
        # The good
        for value, result in [
                ('', None),
                ('Z', 'Z'),
                ('+0000', '+0000'),
                ('+0100', '+0100'),
                ('+1300', '+1300'),
                ('-0630', '-0630')]:
            self.assertEqual(
                validator.coerce_cycle_point_time_zone(value, ['whatever']),
                result)
        # The bad
        for value in ['None', 'Big Bang Time', 'Standard Galaxy Time']:
            self.assertRaises(
                IllegalValueError,
                validator.coerce_cycle_point_time_zone, value, ['whatever'])

    def test_coerce_interval(self):
        """Test coerce_interval."""
        validator = CylcConfigValidator()
        # The good
        for value, result in [
                ('', None),
                ('P3D', DurationFloat(259200)),
                ('PT10M10S', DurationFloat(610))]:
            self.assertEqual(
                validator.coerce_interval(value, ['whatever']), result)
        # The bad
        for value in ['None', '5 days', '20', '-12']:
            self.assertRaises(
                IllegalValueError,
                validator.coerce_interval, value, ['whatever'])

    def test_coerce_interval_list(self):
        """Test coerce_interval_list."""
        validator = CylcConfigValidator()
        # The good
        for value, results in [
                ('', []),
                ('P3D', [DurationFloat(259200)]),
                ('P3D, PT10M10S', [DurationFloat(259200), DurationFloat(610)]),
                ('25*PT30M,10*PT1H',
                 [DurationFloat(1800)] * 25 + [DurationFloat(3600)] * 10)]:
            items = validator.coerce_interval_list(value, ['whatever'])
            for item, result in zip(items, results):
                self.assertAlmostEqual(item, result)
        # The bad
        for value in ['None', '5 days', '20', 'PT10S, -12']:
            self.assertRaises(
                IllegalValueError,
                validator.coerce_interval_list, value, ['whatever'])

    def test_coerce_parameter_list(self):
        """Test coerce_parameter_list."""
        validator = CylcConfigValidator()
        # The good
        for value, result in [
                ('', []),
                ('planet', ['planet']),
                ('planet, star, galaxy', ['planet', 'star', 'galaxy']),
                ('1..5, 21..25', [1, 2, 3, 4, 5, 21, 22, 23, 24, 25]),
                ('-15, -10, -5, -1..1', [-15, -10, -5, -1, 0, 1])]:
            self.assertEqual(
                validator.coerce_parameter_list(value, ['whatever']), result)
        # The bad
        for value in ['foo/bar', 'p1, 1..10', '2..3, 4, p']:
            self.assertRaises(
                IllegalValueError,
                validator.coerce_parameter_list, value, ['whatever'])

    def test_coerce_xtrigger(self):
        """Test coerce_xtrigger."""
        validator = CylcConfigValidator()
        # The good
        for value, result in [
                ('foo(x="bar")', 'foo(x=bar)'),
                ('foo(x, y, z="zebra")', 'foo(x, y, z=zebra)')]:
            self.assertEqual(
                validator.coerce_xtrigger(value, ['whatever']).get_signature(),
                result)
        # The bad
        for value in [
                '', 'foo(', 'foo)', 'foo,bar']:
            self.assertRaises(
                IllegalValueError,
                validator.coerce_xtrigger, value, ['whatever'])


if __name__ == '__main__':
    unittest.main()
