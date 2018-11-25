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

from cylc.graphing import gtk_rgb_to_hex, CGraph


class fake_gtk_color(object):
    red_float = 1.0
    green_float = 1.0
    blue_float = 1.0


suiterc = {
            'visualization': {
                'default node attributes': [
                    'style=filled',
                    'color=red',
                    'fillcolor=blue',
                    'shape=box'
                ],
                'default edge attributes': [
                    'color=red',
                ],
                'node penwidth': 2,
                'edge penwidth': 2,
                'use node color for edges': True,
                'collapsed families': [],
                'use node color for labels': False,
                'initial cycle point': 1,
                'final cycle point': 10,
                'number of cycle points': 3,
                'node groups': {
                    'root': ['root', 'foo', 'bar', 'baz', 'qux'],
                },
                'node attributes': {
                    'root': [
                        'style=filled',
                        'fillcolor=yellow'
                    ]
                }
            }
        }


class TestGraphParser(unittest.TestCase):
    """Unit tests for the graphing module."""

    def setUp(self):
        self.cgraph = CGraph(
            'foo',
            None,
            suiterc['visualization']
        )
        edges = [('foo.1', 'bar.1', False, False, False),
                 ('foo.1', 'baz.1', False, False, False),
                 ('bar.1', 'qux.1', False, False, False),
                 ('baz.1', 'qux.1', False, False, False),
                 ('foo.2', 'bar.2', False, False, False),
                 ('foo.2', 'baz.2', False, False, False),
                 ('bar.2', 'qux.2', False, False, False),
                 ('baz.2', 'qux.2', False, False, False),
                 ('foo.3', 'bar.3', False, False, False),
                 ('foo.3', 'baz.3', False, False, False),
                 ('bar.3', 'qux.3', False, False, False),
                 ('baz.3', 'qux.3', False, False, False)
                 ]
        self.cgraph.add_edges(edges)

    def test_gtk_rgb_to_hex(self):
        self.assertEqual(gtk_rgb_to_hex(fake_gtk_color()), '#ffffff')

    def test_node_attr_by_taskname(self):
        self.assertEqual(
            self.cgraph.node_attr_by_taskname('foo.1'),
            ['style=filled', 'fillcolor=yellow']
        )

    def test_style_node(self):
        node_str = 'foo.1'
        self.cgraph.style_node(node_str)
        node = self.cgraph.get_node(node_str)
        self.assertEqual(
            node.attr.items(),
            [(u'URL', u'foo.1'),
             (u'fillcolor', u'yellow'),
             (u'label', u'foo\\n1'),
             (u'penwidth', u'2')]
        )

    def test_set_def_style(self):
        fgcolor = 'red'
        bgcolor = 'blue'
        def_node_attr = {}
        def_node_attr['style'] = 'filled'
        self.cgraph.set_def_style(fgcolor, bgcolor, def_node_attr)
        self.assertEqual(
            self.cgraph.graph_attr['bgcolor'], '#ffffff00'
        )
        for attr in ['color', 'fontcolor']:
            self.assertEqual(
                self.cgraph.graph_attr[attr], fgcolor
            )
        self.assertEqual(
            self.cgraph.edge_attr['color'], fgcolor
        )
        self.assertEqual(
            self.cgraph.node_attr['fontcolor'], fgcolor
        )
        def_node_attr['style'] = 'unfilled'
        self.cgraph.set_def_style(fgcolor, bgcolor, def_node_attr)
        self.assertEqual(
            self.cgraph.node_attr['fontcolor'], fgcolor
        )


if __name__ == "__main__":
    unittest.main()
