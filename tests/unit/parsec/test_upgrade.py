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

import unittest

import pytest

from cylc.flow.parsec.upgrade import upgrader, converter
from cylc.flow.parsec.exceptions import UpgradeError
from cylc.flow.parsec.OrderedDict import OrderedDict


def test_simple():
    """A quick test of overall functionality."""
    cfg = {
        'item one': 1,
        'item two': 'move me up',
        'section A': {
            'abc': 5,
            'cde': 'foo',
            'gah': 'bar'
        },
        'hostnames': {
            'host 1': {
                'work dir': '/a/b/c',
                'running dir': '/a/b/c/d'
            },
            'host 2': {
                'work dir': '/x/b/c',
                'running dir': '/x/b/c/d'
            },
        }
    }
    x2 = converter(lambda x: 2 * x, 'value x 2')

    upg = upgrader(cfg, 'test file')
    # successive upgrades are incremental - at least until I think of a
    # good way to remember what items have already been translated...
    upg.deprecate('1.3', ['item one'], ['item ONE'], x2)
    upg.deprecate('1.3', ['section A'], ['Heading A'])
    # NOTE change to new item keys here!
    upg.deprecate('1.3', ['Heading A', 'cde'], ['Heading A', 'CDE'])
    upg.deprecate(
        '1.4', ['Heading A', 'abc'], ['Heading A', 'abc'], cvtr=x2,
        silent=True)
    upg.deprecate(
        '1.4.1', ['item two'], ['Heading A', 'item two'], silent=True)
    upg.deprecate('1.5', ['hostnames'], ['hosts'])
    upg.deprecate(
        '1.5',
        ['hosts', '__MANY__', 'running dir'], ['hosts', '__MANY__', 'run dir'])
    # obsolete() but with a custom message - `[Heading A]gah` will be deleted:
    upg.deprecate(
        '1.3', ['Heading A', 'gah'], None,
        cvtr=converter(lambda x: x, 'Yaba daba do'))

    upg.upgrade()

    assert cfg == {
        'item ONE': 2,
        'Heading A': {
            'CDE': 'foo',
            'abc': 10,
            'item two': 'move me up'
        },
        'hosts': {
            'host 1': {
                'work dir': '/a/b/c',
                'run dir': '/a/b/c/d'
            },
            'host 2': {
                'work dir': '/x/b/c',
                'run dir': '/x/b/c/d'
            }
        }
    }


def test_conflicting_items():
    cfg = {
        'item one': 1,
        'item two': 2,
    }

    def get_upgrader():
        nonlocal cfg
        upg = upgrader(cfg, 'test file')
        upg.deprecate('1.3', ['item one'], ['item two'])
        return upg

    # specifying both the old and new variants of a config should result in an
    # error
    upg = get_upgrader()
    with pytest.raises(UpgradeError):
        upg.upgrade()

    # unless the new config is unset
    cfg['item two'] = None
    upg = get_upgrader()
    upg.upgrade()


class TestUpgrade(unittest.TestCase):

    def setUp(self):
        self.cfg = OrderedDict()
        self.cfg['section'] = OrderedDict()
        self.cfg['section']['a'] = '1'
        self.cfg['section']['b'] = '2'
        self.u = upgrader(self.cfg, "1.0 to 2.0")

    def test_converter(self):
        def callback(i):
            return 1 + i

        c = converter(callback=callback, descr="My callback")
        self.assertEqual("My callback", c.describe())
        self.assertEqual(2, c.convert(1))

    def test_constructor(self):
        self.assertEqual(self.cfg, self.u.cfg)
        self.assertEqual("1.0 to 2.0", self.u.descr)

    def test_deprecate(self):
        # b is being deprecated; use c instead
        self.u.deprecate('entry', ['section', 'b'],
                         ['section', 'c'])
        self.assertTrue('entry' in self.u.upgrades)

        def callback(i):
            return 10 * i

        c = converter(callback=callback, descr="My callback")
        self.u.deprecate(vn='entry',
                         oldkeys=[1, 2, 3],
                         newkeys=[10, 20, 30],
                         cvtr=c)

        # assert the key exists before deprecation
        self.assertTrue('b' in self.cfg['section'])
        self.assertFalse('c' in self.cfg['section'])
        self.u.upgrade()
        # assert the key exists before deprecation
        self.assertFalse('b' in self.cfg['section'])
        self.assertTrue('c' in self.cfg['section'])

    def test_obsolete(self):
        # b is obsolete, so the value is omitted
        self.u.obsolete(vn='entry', oldkeys=['section', 'b'], silent=True)
        self.assertTrue('entry' in self.u.upgrades)
        self.assertEqual(True, self.u.upgrades['entry'][0]['silent'])

        self.assertTrue('b' in self.cfg['section'])
        self.u.upgrade()
        self.assertFalse('b' in self.cfg['section'])

        self.u.obsolete(
            vn='entry',
            oldkeys=['section', 'b'],
            silent=False)
        self.assertEqual(True, self.u.upgrades['entry'][0]['silent'])
        self.assertEqual(False, self.u.upgrades['entry'][1]['silent'])

        self.u.obsolete(vn='whocalled?', oldkeys=['section', 'b'], silent=True)

    def test_get_item(self):
        for keys, results in [
            (['section', 'a'], '1'),
            (['section', 'b'], '2'),
            (['section'], {'a': '1', 'b': '2'})
        ]:
            item = self.u.get_item(keys)
            self.assertEqual(results, item)

    def test_put_item(self):
        for keys, value in [
            (['section', 'a'], '100'),
            (['section', 'b'], '200'),
            (['special', 'c'], '3'),
        ]:
            self.u.put_item(keys, value)
            self.assertEqual(self.u.get_item(keys), value)

    def test_expand_not_many(self):
        upg = {
            'new': None,
            'cvt': None,
            'silent': True,
            'is_section': False,
            'old': [
            ]
        }
        self.assertEqual([upg], self.u.expand(upg))

    def test_expand_too_many(self):
        upg = {
            'new': None,
            'cvt': None,
            'silent': True,
            'is_section': True,
            'old': [
                'section', '__MANY__', '__MANY__'
            ]
        }
        with self.assertRaises(UpgradeError) as cm:
            self.u.expand(upg)
        self.assertTrue('Multiple simultaneous __MANY__ not supported' in
                        str(cm.exception))

    def test_expand_deprecate_many_mismatch(self):
        upg = {
            'new': [
                'section', '__MANY__'
            ],
            'cvt': None,
            'silent': True,
            'is_section': False,
            'old': [
                'section', '__MANY__', 'b'
            ]
        }
        with self.assertRaises(UpgradeError) as cm:
            self.u.expand(upg)
        self.assertEqual('__MANY__ mismatch', str(cm.exception))

    def test_expand_deprecate(self):

        def callback(i):
            return i

        c = converter(callback=callback, descr="My callback")
        upg = {
            'new': [
                'section', '__MANY__', 'e'
            ],
            'cvt': c,
            'silent': True,
            'is_section': False,
            'old': [
                'section', '__MANY__', 'c'
            ]
        }
        self.u.upgrade()
        expanded = self.u.expand(upg)
        self.assertEqual(2, len(expanded))
        self.assertEqual(['section', 'a', 'e'], expanded[0]['new'])

    def test_expand_obsolete(self):
        upg = {
            'new': None,
            'cvt': None,
            'silent': True,
            'is_section': False,
            'old': [
                'section', '__MANY__', 'a'
            ]
        }
        self.cfg['__MANY__'] = OrderedDict()
        self.cfg['__MANY__']['name'] = 'Arthur'
        self.u.obsolete('entry', ['section', '__MANY__'])
        self.u.upgrade()
        expanded = self.u.expand(upg)
        self.assertEqual(1, len(expanded))
        self.assertTrue(expanded[0]['new'] is None)


def test_template_in_converter_description(caplog, capsys):
    """Before and after values are available to the conversion descriptor"""
    cfg = {'old': 42}
    u = upgrader(cfg, 'Whateva')
    u.deprecate(
        '2.0.0', ['old'], ['new'],
        cvtr=converter(lambda x: x + 20, '{old} -> {new}'),
        silent=False,
    )
    u.upgrade()
    assert cfg == {'new': 62}
    assert '42 -> 62' in caplog.records[1].message
