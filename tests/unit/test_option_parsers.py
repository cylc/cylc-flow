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
from typing import List

import sys
import io
from contextlib import redirect_stdout
import cylc.flow.flags
from cylc.flow.option_parsers import (
    CylcOptionParser as COP,
    Options,
    has_rose_cli_opts
)
from types import SimpleNamespace


USAGE_WITH_COMMENT = "usage \n # comment"


@pytest.fixture(scope='module')
def parser():
    return COP(
        USAGE_WITH_COMMENT,
        argdoc=[('SOME_ARG', "Description of SOME_ARG")]
    )


@pytest.mark.parametrize(
    'args,verbosity',
    [
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
def test_verbosity(
    args: List[str],
    verbosity: int,
    parser: COP, monkeypatch: pytest.MonkeyPatch
) -> None:
    """-v, -q, --debug should be additive."""
    # patch the cylc.flow.flags value so that it gets reset after the test
    monkeypatch.setattr('cylc.flow.flags.verbosity', None)
    opts, args = parser.parse_args(['default-arg'] + args)
    assert opts.verbosity == verbosity
    # test side-effect, the verbosity flag should be set
    assert cylc.flow.flags.verbosity == verbosity


def test_help_color(monkeypatch: pytest.MonkeyPatch, parser: COP):
    """Test for colorized comments in 'cylc cmd --help --color=always'."""
    # This colorization is done on the fly when help is printed.
    monkeypatch.setattr("sys.argv", ['cmd', 'foo', '--color=always'])
    parser.parse_args(None)
    assert parser.values.color == "always"
    f = io.StringIO()
    with redirect_stdout(f):
        parser.print_help()
    assert not (f.getvalue()).startswith("Usage: " + USAGE_WITH_COMMENT)


def test_help_nocolor(monkeypatch: pytest.MonkeyPatch, parser: COP):
    """Test for no colorization in 'cylc cmd --help --color=never'."""
    # This colorization is done on the fly when help is printed.
    monkeypatch.setattr(sys, "argv", ['cmd', 'foo', '--color=never'])
    parser.parse_args(None)
    assert parser.values.color == "never"
    f = io.StringIO()
    with redirect_stdout(f):
        parser.print_help()
    assert (f.getvalue()).startswith("Usage: " + USAGE_WITH_COMMENT)


def test_Options_std_opts():
    """Test Python Options API with standard options."""
    parser = COP(USAGE_WITH_COMMENT, auto_add=True)
    MyOptions = Options(parser)
    MyValues = MyOptions(verbosity=1)
    assert MyValues.verbosity == 1


@pytest.mark.parametrize(
    'opts, expect',
    [
        ({'opt_conf_keys': 'A,B,C'}, True),
        ({'defines': ['[env]BAR="HI"']}, True),
        ({'rose_template_vars': ['FOO = 43']}, True),
        (
            {
                'opt_conf_keys': 'A,B,C', 'defines': ['[env]BAR="HI"'],
                'rose_template_vars': ['FOO = 43'], 'hello': 42
            },
            True
        ),
        ({'hello': 42}, False)
    ]
)
def test_has_rose_cli_opts(opts, expect):
    opts = SimpleNamespace(**opts)
    assert has_rose_cli_opts(opts) == expect