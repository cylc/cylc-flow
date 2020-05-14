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
from optparse import OptionParser

import pytest

from cylc.flow.scheduler_cli import (
    optparse2namedtuple
)


@pytest.fixture
def simple_parser():
    parser = OptionParser()
    parser.add_option('-a', dest='a', default=False, action='store_true')
    parser.add_option('-b', dest='b')
    parser.add_option('-c', dest='c', type=int, default=42)
    return parser


def test_optparse2namedtuple(simple_parser):
    """It should behave like a dataclass and preserve defaults."""
    option_obj = optparse2namedtuple(simple_parser, 'SimpleOptions')
    assert option_obj.__name__ == 'SimpleOptions'
    assert option_obj._fields == ('a', 'b', 'c')
    assert option_obj._fields_defaults == {'a': False, 'b': None, 'c': 42}

    options = option_obj(True, 'meh', 1)
    assert options.a is True
    assert options.b == 'meh'
    assert options.c == 1

    options = option_obj(c=21)
    assert options.a is False
    assert options.b is None
    assert options.c == 21
