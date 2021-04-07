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

from cylc.flow.exceptions import CylcError
from cylc.flow.parsec.exceptions import ParsecError
from cylc.flow.terminal import cli_function


# this puts Exception in globals() where we can easily find it later
Exception = Exception
SystemExit = SystemExit


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
    'debug,is_terminal,exception_in,exception_out,return_code,stderr',
    [
        # CylcError - "known" error
        pytest.param(  # full traceback in non-interactive mode
            False,
            False,
            CylcError,
            CylcError,
            None,
            None,
            id='CylcError-non-interactive'
        ),
        pytest.param(  # nicely formatted in interactive mode
            False,
            True,
            CylcError,
            SystemExit,
            1,
            'CylcError: message\n',
            id='CylcError-interactive'
        ),
        pytest.param(  # full traceback in debug mode
            True,
            True,
            CylcError,
            CylcError,
            None,
            None,
            id='CylcError-debug'
        ),

        # ParsecError - "known" error
        pytest.param(  # full traceback in non-interactive mode
            False,
            False,
            ParsecError,
            ParsecError,
            None,
            None,
            id='ParsecError-non-interactive'
        ),
        pytest.param(  # nicely formatted in interactive mode
            False,
            True,
            ParsecError,
            SystemExit,
            1,
            'ParsecError: message\n',
            id='ParsecError-interactive'
        ),
        pytest.param(  # full traceback in debug mode
            True,
            True,
            ParsecError,
            ParsecError,
            None,
            None,
            id='ParsecError-debug'
        ),

        # Exception - "unknown" error
        pytest.param(  # full traceback in non-interactive mode
            False,
            False,
            Exception,
            Exception,
            None,
            None,
            id='Exception-non-interactive'
        ),
        pytest.param(  # full traceback in interactive mode
            False,
            True,
            Exception,
            Exception,
            None,
            None,
            id='Exception-interactive'
        ),
        pytest.param(  # full traceback in debug mode
            True,
            True,
            Exception,
            Exception,
            None,
            None,
            id='Exception-debug'
        ),

        # SystemExit - "unknown" error
        pytest.param(  # full traceback in non-interactive mode
            False,
            False,
            SystemExit,
            SystemExit,
            1,
            'ERROR: message\n',
            id='SystemExit-non-interactive'
        ),
        pytest.param(  # full traceback in interactive mode
            False,
            True,
            SystemExit,
            SystemExit,
            1,
            'ERROR: message\n',
            id='SystemExit-interactive'
        ),
        pytest.param(  # full traceback in debug mode
            True,
            True,
            SystemExit,
            SystemExit,
            1,
            'ERROR: message\n',
            id='SystemExit-debug'
        ),
    ]
)
def test_cli(
    debug,
    is_terminal,
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
    overridden using --debug mode. In non-interactive mode we allways print the
    full traceback for logging purposes.

    Other exceptions represent "unknown" errors which we would expect to occur.
    We should print the full traceback in these situations.
    """
    monkeypatch.setattr('cylc.flow.flags.debug', debug)
    monkeypatch.setattr('cylc.flow.terminal.is_terminal', lambda: is_terminal)
    monkeypatch.setattr('cylc.flow.terminal.supports_color', lambda: False)

    with pytest.raises(exception_out) as exc_ctx:
        cli(exception_in.__name__)

    if return_code is not None:
        assert exc_ctx.value.args[0] == return_code

    if stderr is not None:
        assert capsys.readouterr()[1] == stderr
