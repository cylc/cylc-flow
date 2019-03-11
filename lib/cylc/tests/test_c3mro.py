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

import unittest

from cylc.c3mro import *


class TestC3mro(unittest.TestCase):

    def test_tree_is_empty_by_default(self):
        c3 = C3()
        self.assertFalse(c3.tree)

    def test_tree_parameter(self):
        c3 = C3({'a': 1})
        self.assertTrue(c3.tree)

    def test_simple_inheritance(self):
        parents = {}
        parents['object'] = []
        parents['string'] = ['object']
        c3 = C3(parents)
        string_hierarchy = c3.mro('string')
        self.assertEqual(['string', 'object'], string_hierarchy)

    def test_simple_inheritance_extra_nodes(self):
        parents = {}
        parents['object'] = []
        parents['string'] = ['object']
        # nodes not related to string
        parents['root'] = []
        parents['diamond'] = ['root']
        c3 = C3(parents)
        self.assertEqual(['string', 'object'], c3.mro('string'))
        self.assertEqual(['diamond', 'root'], c3.mro('diamond'))

    def test_empty_tree_key_error(self):
        parents = {}
        c3 = C3(parents)
        with self.assertRaises(KeyError):
            c3.mro('test')

    def test_multiple_inheritance_error_py23(self):
        parents = {}
        parents['object'] = []
        parents['x'] = ['object']
        parents['y'] = ['object']
        parents['a'] = ['x', 'y']
        parents['b'] = ['y', 'x']
        parents['z'] = ['a', 'b']
        c3 = C3(parents)
        # see class docstring, this is the case #2
        with self.assertRaises(Exception) as cm:
            c3.mro('z')
        self.assertTrue("ERROR: z: bad runtime namespace inheritance hierarchy"
                        in str(cm.exception))

    def test_mro_of_none(self):
        with self.assertRaises(Exception) as cm:
            C3.merge([[], ['x', 'y', 'o'], ['y', 'x', 'o'], []], None)
        self.assertTrue("ERROR: bad runtime namespace inheritance hierarchy"
                        in str(cm.exception))


if __name__ == '__main__':
    unittest.main()
