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
"""Test the diff.py interface."""
import json
from subprocess import Popen, PIPE
from textwrap import dedent
import unittest

from diffr import Diff, __file__ as SCRIPT


class TestDiff(unittest.TestCase):

    @staticmethod
    def call_cli(this, that, *args):
        cmd = (
            ['python', SCRIPT, json.dumps(this), json.dumps(that)]
            + list(args)
        )
        proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = proc.communicate()
        return [proc.returncode, stdout.decode(), stderr.decode()]

    def test_dict_no_diff(self):
        for this in [
                {'a': 1},
                {'a': {'b': 1}},
                {'a': {'b': 1, 'c': 2}},
                {'a': [1, {'b': 2}]}
        ]:
            with self.subTest(this):
                self.assertTrue(Diff(this, this))

    def test_dict_added(self):
        for this, that in [
                ({}, {'b': 2}),
                ({'a': 1}, {'b': 2}),
                ({'a': 1}, {'a': 1, 'b': 2})
        ]:
            with self.subTest((this, that)):
                diff = Diff(this, that)
                self.assertFalse(diff)
                self.assertEqual(
                    list(diff.added()),
                    [(['b'], 2)]
                )

    def test_dict_removed(self):
        for this, that in [
                ({}, {'b': 2}),
                ({'a': 1}, {'b': 2}),
                ({'a': 1}, {'a': 1, 'b': 2})
        ]:
            with self.subTest((that, this)):
                diff = Diff(that, this)
                self.assertFalse(diff)
                self.assertEqual(
                    list(diff.removed()),
                    [(['b'], 2)]
                )

    def test_dict_modified(self):
        for this, that in [
                ({'a': 1}, {'a': 2}),
                ({'a': 1, 'b': 2}, {'a': 2, 'b': 2}),
        ]:
            with self.subTest((this, that)):
                diff = Diff(this, that)
                self.assertFalse(diff)
                self.assertEqual(
                    list(diff.modified()),
                    [(['a'], 1, 2)]
                )

    def test_dict_str(self):
        diff = Diff(
            {'a': 1, 'b': 2, 'c': 3},
            {'a': 1, 'b': 3, 'd': 4}
        )
        self.assertFalse(diff)
        self.assertEqual(
            str(diff),
            dedent('''
            +++ expected
            --- got
            ============
             {
            ? b: 2 => 3,
            + d: 4,
            - c: 3
             }
            ''').strip() + '\n'
        )

    def test_dict_nested(self):
        diff = Diff(
            {'x': {'y': {'a': 1, 'b': 2, 'c': 3}}},
            {'x': {'y': {'a': 1, 'b': 3, 'd': 4}}}
        )
        self.assertFalse(diff)
        self.assertEqual(
            list(diff.added()),
            [(['x', 'y', 'd'], 4)]
        )
        self.assertEqual(
            list(diff.removed()),
            [(['x', 'y', 'c'], 3)]
        )
        self.assertEqual(
            list(diff.modified()),
            [(['x', 'y', 'b'], 2, 3)]
        )
        self.assertEqual(
            str(diff),
            dedent('''
            +++ expected
            --- got
            ============
             {
              x: {
                  y: {
            ?         b: 2 => 3,
            +         d: 4,
            -         c: 3
                  }
              }
             }
            ''').strip() + '\n'
        )

    def test_dict_types(self):
        diff = Diff(
            {'a': 4.2, 'b': False, 'c': 'a', 'd': 1, 'e': None},
            {'a': 4.1, 'b': True, 'c': 'b', 'd': 2, 'e': 1}
        )
        self.assertFalse(diff)
        self.assertEqual(
            list(diff.modified()),
            [
                (['a'], 4.2, 4.1),
                (['b'], False, True),
                (['c'], 'a', 'b'),
                (['d'], 1, 2),
                (['e'], None, 1)
            ]
        )
        self.assertEqual(
            str(diff),
            dedent('''
            +++ expected
            --- got
            ============
             {
            ? a: 4.2 => 4.1,
            ? b: False => True,
            ? c: a => b,
            ? d: 1 => 2,
            ? e: None => 1
             }
            ''').strip() + '\n'
        )

    def test_dict_names(self):
        diff = Diff({'a': 1}, {'a': 2}, this_name='foo', that_name='bar')
        self.assertEqual(
            str(diff),
            dedent('''
            +++ foo
            --- bar
            ============
             {
            ? a: 1 => 2
             }
            ''').strip() + '\n'
        )

    def test_list_no_diff(self):
        for this in [
                [1],
                [1, 2, 3],
                [1, {'a': 1}, 3]
        ]:
            with self.subTest(this):
                self.assertTrue(Diff(this, this))

    def test_list_equal_length(self):
        diff = Diff([1, 2, 3], [4, 5, 6])
        self.assertFalse(diff)
        self.assertEqual(
            list(diff.modified()),
            [
                ([0], 1, 4),
                ([1], 2, 5),
                ([2], 3, 6),
            ]
        )

        diff = Diff([1, 2, 3], [3, 2, 1])
        self.assertFalse(diff)
        self.assertEqual(
            list(diff.modified()),
            [
                ([0], 1, 3),
                ([2], 3, 1),
            ]
        )

    def test_list_different_length(self):
        that, this = [1, 2, 3, 4, 5, 6], [-1, 2, 3]

        diff = Diff(that, this)
        self.assertFalse(diff)
        self.assertEqual(
            list(diff.modified()),
            [
                ([0], 1, -1),
            ]
        )
        self.assertEqual(
            list(diff.added()),
            []
        )
        self.assertEqual(
            list(diff.removed()),
            [
                ([3], 4),
                ([4], 5),
                ([5], 6)
            ]
        )

        diff = Diff(this, that)
        self.assertFalse(diff)
        self.assertEqual(
            list(diff.modified()),
            [
                ([0], -1, 1),
            ]
        )
        self.assertEqual(
            list(diff.added()),
            [
                ([3], 4),
                ([4], 5),
                ([5], 6)
            ]
        )
        self.assertEqual(
            list(diff.removed()),
            []
        )

    def test_list_nested(self):
        diff = Diff(
            [1, [2, 3], 5, 6],
            [1, [2, 3, 4], 5]
        )
        self.assertFalse(diff)
        self.assertEqual(
            list(diff.removed()),
            [
                ([3], 6)
            ]
        )
        self.assertEqual(
            list(diff.added()),
            [
                ([1, 2], 4)
            ]
        )
        self.assertEqual(
            list(diff.modified()),
            []
        )
        self.assertEqual(
            str(diff),
            dedent('''
            +++ expected
            --- got
            ============
             [
              1: [
            +     2: 4
              ],
            - 3: 6
             ]
            ''').strip() + '\n'
        )

    def test_mixed(self):
        diff = Diff(
            {'x': {'y': [0, 2, {'a': 1, 'b': 2, 'c': 3}]}},
            {'x': {'y': [1, 2, {'a': 1, 'b': 3, 'd': 4}, 5]}}
        )
        self.assertFalse(diff)
        self.assertEqual(
            list(diff.added()),
            [
                (['x', 'y', 2, 'd'], 4),
                (['x', 'y', 3], 5)
            ]
        )
        self.assertEqual(
            list(diff.removed()),
            [
                (['x', 'y', 2, 'c'], 3),
            ]
        )
        self.assertEqual(
            list(diff.modified()),
            [
                (['x', 'y', 0], 0, 1),
                (['x', 'y', 2, 'b'], 2, 3)
            ]
        )
        self.assertEqual(
            str(diff),
            dedent('''
            +++ expected
            --- got
            ============
             {
              x: {
                  y: [
            ?         0: 0 => 1,
                      2: {
            ?             b: 2 => 3,
            +             d: 4,
            -             c: 3
                      },
            +         3: 5
                  ]
              }
             }
            ''').strip() + '\n'
        )

    def test_cli_no_diff(self):
        for this in [
                {'a': 1},
                {'a': {'b': 1}},
                {'a': {'b': 1, 'c': 2}},
                {'a': [1, {'b': 2}]},
                [1, 2, 3],
                [1, {'a': 1}, 2]
        ]:
            ret, out, err = self.call_cli(this, this)
            self.assertEqual(ret, 0)
            self.assertEqual(out, '')
            self.assertEqual(err, '')

    def test_cli_nested(self):
        ret, out, err = self.call_cli(
            {'x': {'y': {'a': 1, 'b': 2, 'c': 3}}},
            {'x': {'y': {'a': 1, 'b': 3, 'd': 4}}}
        )
        self.assertEqual(ret, 1)
        self.assertEqual(out, '')
        self.assertEqual(
            err,
            dedent('''
            +++ expected
            --- got
            ============
             {
              x: {
                  y: {
            ?         b: 2 => 3,
            +         d: 4,
            -         c: 3
                  }
              }
             }
            ''').strip() + '\n'
        )

    def test_cli_contains(self):
        this, that = ({'a': 1, 'b': 2}, {'a': 1})

        ret, out, err = self.call_cli(this, that, '-c2')
        self.assertEqual(ret, 0)
        self.assertEqual(out, '')
        self.assertEqual(err, '')

        ret, out, err = self.call_cli(this, that, '-c1')
        # self.assertEqual(ret, 1)
        self.assertEqual(out, '')
        self.assertEqual(
            err,
            dedent('''
            +++ expected
            --- got
            ============
             {
            - b: 2
             }
            ''').strip() + '\n'
        )

    def test_cli_names(self):
        for args in [[], ['-c1']]:
            ret, out, err = self.call_cli(
                {'a': 1}, {'a': 2}, '-1', 'foo', '-2', 'bar', *args)
            self.assertEqual(ret, 1)
            self.assertEqual(out, '')
            self.assertEqual(
                err,
                dedent('''
                +++ foo
                --- bar
                ============
                 {
                ? a: 1 => 2
                 }
                ''').strip() + '\n'
            )
