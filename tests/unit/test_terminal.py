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

from optparse import OptionParser, Values

import pytest

from cylc.flow.exceptions import CylcError
from cylc.flow.parsec.exceptions import ParsecError
from cylc.flow.terminal import (
    cli_function,
    prompt,
    should_use_color,
)


# this puts Exception in globals() where we can easily find it later
Exception = Exception     # noqa: A001
SystemExit = SystemExit   # noqa: A001


def get_option_parser():
    """An option parser with no options."""
    return OptionParser()


@cli_function(get_option_parser)
def cli(parser, opts, exc_class):
    """Dummy command line interface which raises an exception.

    Args:
        exc_class: The class of the exception to raise.

    """
    if exc_class:
        raise globals()[exc_class]('message')


@pytest.mark.parametrize(
    'verbosity,exception_in,exception_out,return_code,stderr',
    [
        # CylcError - "known" error
        pytest.param(  # nicely formatted
            0,
            CylcError,
            SystemExit,
            1,
            'CylcError: message\n',
            id='CylcError'
        ),
        pytest.param(  # full traceback in debug mode
            2,
            CylcError,
            CylcError,
            None,
            None,
            id='CylcError-debug'
        ),

        # ParsecError - "known" error
        pytest.param(  # nicely formatted
            0,
            ParsecError,
            SystemExit,
            1,
            'ParsecError: message\n',
            id='ParsecError'
        ),
        pytest.param(  # full traceback in debug mode
            2,
            ParsecError,
            ParsecError,
            None,
            None,
            id='ParsecError-debug'
        ),

        # Exception - "unknown" error
        pytest.param(  # full traceback
            0,
            Exception,
            Exception,
            None,
            None,
            id='Exception'
        ),
        pytest.param(  # full traceback in debug mode
            2,
            Exception,
            Exception,
            None,
            None,
            id='Exception-debug'
        ),

        # SystemExit - "unknown" error
        pytest.param(  # full traceback
            0,
            SystemExit,
            SystemExit,
            1,
            'ERROR: message\n',
            id='SystemExit'
        ),
        pytest.param(  # full traceback in debug mode
            2,
            SystemExit,
            SystemExit,
            1,
            'ERROR: message\n',
            id='SystemExit-debug'
        ),
    ]
)
def test_cli(
    verbosity,
    exception_in,
    exception_out,
    return_code,
    stderr,
    monkeypatch,
    capsys
):
    """Test that the CLI formats exceptions appropriately.

    The idea here is that "known" errors (those which subclass CylcError or
    ParsecError) should be formatted nicely (as opposed to dumping the
    full traceback to stderr) in interactive mode. This behaviour can be
    overridden using --debug mode. In non-interactive mode we always print the
    full traceback for logging purposes.

    Other exceptions represent "unknown" errors which we would expect to occur.
    We should print the full traceback in these situations.
    """
    monkeypatch.setattr('cylc.flow.flags.verbosity', verbosity)
    monkeypatch.setattr('cylc.flow.terminal.supports_color', lambda: False)

    with pytest.raises(exception_out) as exc_ctx:
        cli(exception_in.__name__)

    if return_code is not None:
        assert exc_ctx.value.args[0] == return_code

    if stderr is not None:
        assert capsys.readouterr()[1] == stderr


@pytest.fixture
def stdinput(monkeypatch):
    def _input(*lines):
        lines = list(lines)

        def __input(_message):
            nonlocal lines
            try:
                return lines.pop(0)
            except IndexError:
                raise Exception('stdinput ran out of lines') from None

        monkeypatch.setattr(
            'cylc.flow.terminal.input',
            __input,
        )

    return _input


def test_prompt(stdinput):
    """Test the prompt function with some simulated input."""
    # test a multiple choice prompt
    stdinput('y')
    assert prompt('yes or no', ['y', 'n']) == 'y'
    stdinput('n')
    assert prompt('yes or no', ['y', 'n']) == 'n'

    # test a prompt with mapped return values
    stdinput('42')
    assert prompt('what is the answer', {'41': False, '42': True}) is True
    stdinput('41')
    assert prompt('what is the answer', {'41': False, '42': True}) is False

    # test incorrect input (should re-prompt until it gets a valid response)
    stdinput('40', '41', '42')
    assert prompt('what is the answer', ['42']) == '42'

    # test a prompt with a default
    stdinput('')
    assert prompt('whatever', ['x'], default='x') == 'x'

    # test a prompt with an input pre-process method thinggy
    stdinput('YES')
    assert prompt('yes yes yes no', ['yes', 'no'], process=str.lower) == 'yes'


@pytest.mark.parametrize('opts, supported, expected', [
    ({}, True, False),
    ({'color': 'never'}, True, False),
    ({'color': 'auto'}, True, True),
    ({'color': 'auto'}, False, False),
    ({'color': 'always'}, False, True),
])
def test_should_use_color(
    opts: dict, expected: bool, supported: bool,
    monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr('cylc.flow.terminal.supports_color', lambda: supported)
    options = Values(opts)
    assert should_use_color(options) == expected
