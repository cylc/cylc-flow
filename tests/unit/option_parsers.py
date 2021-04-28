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

import optparse

import pytest

from cylc.flow.option_parsers import Options


@pytest.fixture
def simple_parser():
    """Simple option parser."""
    parser = optparse.OptionParser()
    parser.add_option('-a', action='store')
    parser.add_option('-b', action='store_true')
    parser.add_option('-c', default='C')
    return parser


def test_options(simple_parser):
    """It is a substitute for an optparse options object."""
    options = Options(parser=simple_parser)
    opts = options(a=1, b=True)

    # we can access options as attributes
    assert opts.a == 1
    assert opts.b is True

    # defaults are automatically substituted
    assert opts.c == 'C'

    # get-like syntax should work
    assert opts.get('d', 42) == 42

    # invalid keys result in KeyErrors
    with pytest.raises(KeyError):
        opts.d
    with pytest.raises(KeyError):
        opts(d=1)

    # just for fun we can still use dict syntax
    assert opts['a'] == 1
