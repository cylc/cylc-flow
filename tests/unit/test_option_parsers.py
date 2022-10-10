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
from pytest import param
from typing import List

import sys
import io
from contextlib import redirect_stdout
from cylc.flow.exceptions import WorkflowConfigError
import cylc.flow.flags
from cylc.flow.option_parsers import (
    CylcOptionParser as COP,
    Options,
    can_revalidate,
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
    'rundir, revalidate, expect',
    (
        (True, True, ''),
        (True, False, ''),
        (False, True, False),
        (False, False, ''),
    )
)
def test_can_revalidate(monkeypatch, tmp_path, rundir, revalidate, expect):
    """It raises an error if revalidation isn't allowed and the user
    has asked for revalidation.
    """
    is_ = tmp_path / 'is'
    not_ = tmp_path / 'not'
    monkeypatch.setattr(
        'cylc.flow.pathutil.get_cylc_run_dir', lambda: is_)

    flow_file = is_ if rundir else not_
    flow_file = flow_file / 'foo/bar/baz/flow.cylc'
    if expect is False:
        with pytest.raises(WorkflowConfigError):
            can_revalidate(
                flow_file,
                SimpleNamespace(**{'revalidate': revalidate})
            )
    else:
        assert (
            can_revalidate(
                flow_file,
                SimpleNamespace(**{'revalidate': revalidate})
            )
            is True
        )
