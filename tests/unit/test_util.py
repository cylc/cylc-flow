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

from optparse import OptionParser

from cylc.flow.util import (
    deserialise,
    format_parsed_opts,
    get_parsed_opts,
)

import pytest


def test_deserialise():
    actual = deserialise('["2", "3"]')
    expected = {'2', '3'}
    assert actual == expected


@pytest.fixture
def option_parser():
    parser = OptionParser()
    parser.add_option('--foo', dest='my_foo', action='store')
    parser.add_option('--bar', '-b', action='store_true')
    parser.add_option('--baz', action='store_false', default=True)
    parser.add_option('--pub', '-p', action='append')
    return parser


@pytest.mark.parametrize(
    'cli_in, cli_out', [
        (['-b'], ['--bar']),
        (['--bar', '--baz'], ['--bar', '--baz']),
        (['--foo', 'foofoofoo'], ['--foo', 'foofoofoo']),
        (['-p', 'a', '-p', 'b', '-p', 'c'], ['--pub', 'a', '--pub', 'b', '--pub', 'c'])
    ]
)
def test_get_parsed_opts(option_parser, cli_in, cli_out):
    parsed_opts, _ = option_parser.parse_args(cli_in)
    assert get_parsed_opts(option_parser, parsed_opts) == cli_out


@pytest.mark.parametrize(
    'cli_in, cli_out', [
        (['-b'], 'cylc whatever --bar arg1 arg2'),
        (['--bar', '--baz'], 'cylc whatever --bar --baz arg1 arg2'),
        (['--foo', 'foofoofoo'], 'cylc whatever --foo foofoofoo arg1 arg2'),
        (['-p', 'a', '-p', 'b'], 'cylc whatever --pub a --pub b arg1 arg2')
    ]
)
def test_format_parsed_opts(option_parser, cli_in, cli_out):
    parsed_opts, _ = option_parser.parse_args(cli_in)
    assert format_parsed_opts(
        option_parser,
        ['cylc', 'whatever'],
        parsed_opts,
        ['arg1', 'arg2'],
        width=99,
    ) == cli_out
