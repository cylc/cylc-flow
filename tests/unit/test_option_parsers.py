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

import pytest

import sys
import cylc.flow.flags
from cylc.flow.option_parsers import CylcOptionParser as COP


USAGE_WITH_COMMENT = "usage \n # comment"


@pytest.fixture(scope='module')
def parser():
    return COP('usage')


@pytest.fixture(scope='module')
def parser_nocolor():
    argv = sys.argv
    sys.argv = ['cmd', 'arg', '--help', '--color=never']
    cop = COP(USAGE_WITH_COMMENT)
    sys.argv = argv
    return cop


@pytest.fixture(scope='module')
def parser_color():
    return COP(USAGE_WITH_COMMENT)


@pytest.mark.parametrize(
    'args,verbosity', [
        ([], 0),
        (['-v'], 1),
        (['-v', '-v', '-v'], 3),
        (['-q'], -1),
        (['-q', '-q', '-q'], -3),
        (['-q', '-v', '-q'], -1),
        (['--debug'], 2),
        (['--debug', '-q'], 1),
        (['--debug', '-v'], 3),
    ]
)
def test_verbosity(args, verbosity, parser, monkeypatch):
    """-v, -q, --debug should be additive."""
    # patch the cylc.flow.flags value so that it gets reset after the test
    monkeypatch.setattr('cylc.flow.flags.verbosity', None)
    opts, args = parser.parse_args(['default-arg'] + args)
    assert opts.verbosity == verbosity
    # test side-effect, the verbosity flag should be set
    assert cylc.flow.flags.verbosity == verbosity


def test_help_color(parser_color):
    """Test for colorized comments in 'cylc cmd --help'."""
    assert not parser_color.usage.startswith(USAGE_WITH_COMMENT)


def test_help_nocolor(parser_nocolor):
    """Test for no colorization in 'cylc cmd --help --color=never'."""
    assert parser_nocolor.usage.startswith(USAGE_WITH_COMMENT)
