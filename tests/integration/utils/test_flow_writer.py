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
"""Tests to ensure the tests are working - very meta.

https://github.com/cylc/cylc-flow/pull/2740#discussion_r206086008

And yes, these are unit-tests inside a functional test framework thinggy.

"""

from textwrap import dedent

from .flow_writer import (
    _write_header,
    _write_setting,
    _write_section,
    flow_config_str
)


def test_write_header():
    """It should write out cylc configuration headings."""
    assert _write_header('foo', 1) == '[foo]'
    assert _write_header('foo', 2) == '    [[foo]]'


def test_write_setting_singleline():
    """It should write out cylc configuration settings."""
    assert _write_setting('key', 'value', 1) == [
        'key = value'
    ]
    assert _write_setting('key', 'value', 2) == [
        '    key = value'
    ]


def test_write_setting_script():
    """It should preserve indentation for script items."""
    assert _write_setting('script', 'a\nb\nc', 2) == [
        '    script = """',
        'a',
        'b',
        'c',
        '    """'
    ]


def test_write_setting_multiline():
    """It should write out cylc configuration settings over multiple lines."""
    assert _write_setting('key', 'foo\nbar', 1) == [
        'key = """',
        '    foo',
        '    bar',
        '"""'
    ]
    assert _write_setting('key', 'foo\nbar', 2) == [
        '    key = """',
        '        foo',
        '        bar',
        '    """'
    ]


def test_write_section():
    """It should write out entire cylc configuraitons."""
    assert _write_section(
        'foo',
        {
            'bar': {
                'pub': 'beer'
            },
            'baz': 42
        },
        1
    ) == [
        '[foo]',
        '    baz = 42',
        '    [[bar]]',
        '        pub = beer'
    ]


def test_flow_config_str():
    """It should write out entire cylc configuration files."""
    assert flow_config_str(
        {
            '#!JiNjA2': None,
            'foo': {
                'bar': {
                    'pub': 'beer'
                },
                'baz': 42
            },
            'qux': 'asdf'
        }
    ) == dedent('''
        #!jinja2
        qux = asdf
        [foo]
            baz = 42
            [[bar]]
                pub = beer
    ''').strip() + '\n'
