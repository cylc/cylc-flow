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

import tempfile
import unittest

from cylc.templatevars import load_template_vars


class TestTemplatevars(unittest.TestCase):

    def test_load_template_vars_no_params(self):
        self.assertFalse(load_template_vars())

    def test_load_template_vars_from_string(self):
        pairs = [
            "name=John",
            "type=Human",
            "age=12"
        ]
        expected = {
            "name": "John",
            "type": "Human",
            "age": "12"
        }
        self.assertEqual(expected, load_template_vars(template_vars=pairs))

    def test_load_template_vars_from_file(self):
        with tempfile.NamedTemporaryFile() as tf:
            tf.write("""
            name=John
            type=Human
            # a comment
            # type=Test
            age=12
            """.encode())
            tf.flush()
            expected = {
                "name": "John",
                "type": "Human",
                "age": "12"
            }
            self.assertEqual(
                expected, load_template_vars(template_vars=None,
                                             template_vars_file=tf.name))

    def test_load_template_vars_from_string_and_file(self):
        """Text pair variables take precedence over file."""
        pairs = [
            "name=John",
            "age=12"
        ]
        with tempfile.NamedTemporaryFile() as tf:
            tf.write("""
            name=Mariah
            type=Human
            # a comment
            # type=Test
            age=70
            """.encode())
            tf.flush()
            expected = {
                "name": "John",
                "type": "Human",
                "age": "12"
            }
            self.assertEqual(
                expected, load_template_vars(template_vars=pairs,
                                             template_vars_file=tf.name))


if __name__ == '__main__':
    unittest.main()
