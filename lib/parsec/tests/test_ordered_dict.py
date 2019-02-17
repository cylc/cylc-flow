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

from parsec.OrderedDict import OrderedDictWithDefaults


class TestOrderedDict(unittest.TestCase):

    def test_getitem(self):
        d = OrderedDictWithDefaults()
        d['name'] = 'Joseph'
        d.defaults_ = {
            'surname': 'Wyndham'
        }
        self.assertEqual('Joseph', d['name'])
        self.assertEqual('Wyndham', d['surname'])

    def test_setitem(self):
        d = OrderedDictWithDefaults()
        d['name'] = 'Matthews'
        self.assertEqual('Matthews', d['name'])
        d['name'] = 'Zaccharias'
        self.assertEqual('Zaccharias', d['name'])

    def test_keys(self):
        d = OrderedDictWithDefaults()
        d['name'] = 'Andrew'
        d['surname'] = 'Gray'
        d.defaults_ = {
            'address': 'N/A'
        }
        keys = d.keys()
        self.assertTrue(len(keys) == 3)
        self.assertTrue('name' in keys)
        self.assertTrue('surname' in keys)
        self.assertTrue('address' in keys)

    def test_values(self):
        d = OrderedDictWithDefaults()
        d['name'] = 'Paul'
        d['color'] = 'Green'
        values = d.values()
        self.assertTrue(len(values) == 2)
        self.assertTrue('Paul' in values)
        self.assertTrue('Green' in values)

    def test_items(self):
        d = OrderedDictWithDefaults()
        self.assertEqual([], d.items())
        d['key'] = 'Birds'
        d['len'] = '89'
        for _, v in d.items():
            self.assertTrue(v in ['Birds', '89'])

    def test_iterkeys(self):
        d = OrderedDictWithDefaults()
        self.assertEqual([], d.items())
        d['key'] = 'Birds'
        d['len'] = '89'
        d.defaults_ = {
            'surname': 'Wyndham'
        }
        count = 0
        for k in d.iterkeys():
            self.assertTrue(k in ['key', 'len', 'surname'])
            count += 1
        self.assertEqual(3, count)

    def test_itervalues(self):
        d = OrderedDictWithDefaults()
        self.assertEqual([], d.items())
        d['key'] = 'Birds'
        d['len'] = '89'
        d.defaults_ = {
            'surname': 'Wyndham'
        }
        count = 0
        for k in d.itervalues():
            self.assertTrue(k in ['Birds', '89', 'Wyndham'])
            count += 1
        self.assertEqual(3, count)

    def test_iteritems(self):
        d = OrderedDictWithDefaults()
        self.assertEqual([], d.items())
        d['key'] = 'Birds'
        d['len'] = '89'
        d.defaults_ = {
            'surname': 'Wyndham'
        }
        count = 0
        for k, v in d.iteritems():
            self.assertTrue(k in ['key', 'len', 'surname'])
            self.assertTrue(v in ['Birds', '89', 'Wyndham'])
            count += 1
        self.assertEqual(3, count)

    def test_contains(self):
        d = OrderedDictWithDefaults()
        self.assertEqual([], d.items())
        d['key'] = 'Birds'
        d.defaults_ = {
            'value': '10'
        }
        self.assertTrue('key' in d)
        self.assertTrue('value' in d)
        self.assertFalse('test' in d)

    def test_nonzero(self):
        d = OrderedDictWithDefaults()
        self.assertFalse(d)
        d['value'] = 10
        self.assertTrue(d)

    def test_prepend(self):
        d = OrderedDictWithDefaults()
        d['key'] = 'Birds'
        d.prepend('year', 1980)
        d.prepend('key', 2000)

        iterator = d.iterkeys()

        self.assertEqual('key', iterator.next())
        self.assertEqual('year', iterator.next())

        d = OrderedDictWithDefaults()
        d['key'] = 'Birds'
        d.prepend('year', 1980)

        iterator = d.iterkeys()

        self.assertEqual('year', iterator.next())
        self.assertEqual('key', iterator.next())


if __name__ == '__main__':
    unittest.main()
