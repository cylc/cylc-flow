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

"""Functionality to assist working with terminals"""

from contextlib import contextmanager
from functools import wraps
import inspect
import json
import logging
import os
import signal
from subprocess import (  # nosec
    PIPE,
    Popen,
)
import sys
from textwrap import wrap
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    NoReturn,
    Optional,
    Sequence,
    TypeVar,
    Union,
    cast,
    overload,
)

from ansimarkup import parse as cparse
from colorama import init as color_init

from cylc.flow import CYLC_LOG
from cylc.flow.exceptions import CylcError
import cylc.flow.flags
from cylc.flow.loggingutil import CylcLogFormatter
from cylc.flow.parsec.exceptions import ParsecError


if TYPE_CHECKING:
    from optparse import (
        OptionParser,
        Values,
    )

    T = TypeVar('T')
    StrFunc = Callable[[str], str]


# CLI exception message format
EXC_EXIT = cparse('<red><bold>{name}: </bold>{exc}</red>')

# default grey colour (do not use "dim", it is not sufficiently portable)
DIM = 'fg 248'

# turn input into a global() for testing purposes
input = input  # noqa


def is_terminal():
    """Determine if running in (and printing to) a terminal."""
    # Return False if stdout or stderr not going to a terminal.
    return (
        (
            hasattr(sys.stderr, 'isatty') and sys.stderr.isatty()
        ) and (
            hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
        )
    )


def get_width(default=80):
    """Return the terminal width or `default` if it is not determinable."""
    # stty can have different install locs so don't use absolute path
    proc = Popen(['stty', 'size'], stdout=PIPE, stderr=PIPE)  # nosec
    if proc.wait():
        return default
    try:
        return int(proc.communicate()[0].split()[1]) or default
    except (IndexError, ValueError):
        return default


def print_contents(contents, padding=5, char='.', indent=0):
    title_width = max(
        len(title)
        for title, _ in contents
    )
    width = get_width(default=0)
    if width < title_width + 20 - indent - padding:
        width = title_width + 20 - indent - padding
    desc_width = width - title_width - padding - 2 - indent
    indent = ' ' * indent
    for title, desc in contents:
        desc_lines = wrap(desc or '', desc_width) or ['']
        print(
            f'{indent}'
            f'{title} {char * (padding + title_width - len(title))} '
            f'{desc_lines[0]}'
        )
        for line in desc_lines[1:]:
            print(f'{indent}  {" " * title_width}{" " * padding}{line}')


def format_grid(rows, gutter=2):
    """Format gridded text.

    This takes a 2D table of text and formats it to the maximum width of each
    column and adds a bit of space between them.

    Args:
        rows:
            2D list containing the text to format.
        gutter:
            The width of the gutter between columns.

    Examples:
        >>> format_grid([
        ...     ['a', 'b', 'ccccc'],
        ...     ['ddddd', 'e', 'f'],
        ... ])
        ['a      b  ccccc  ',
         'ddddd  e  f      ']

        >>> format_grid([])
        []

    """
    if not rows:
        return rows
    templ = [
        '{col:%d}' % (max(
            len(row[ind])
            for row in rows
        ) + gutter)
        for ind in range(len(rows[0]))
    ]
    lines = []
    for row in rows:
        ret = ''
        for ind, col in enumerate(row):
            ret += templ[ind].format(col=col)
        lines.append(ret)
    return lines


def supports_color() -> bool:
    """Determine if running in a terminal which supports color.

    See equivalent code in Django:
    https://github.com/django/django/blob/master/django/core/management/color.py
    """
    if not is_terminal():
        return False
    if sys.platform in {'Pocket PC', 'win32'}:
        return False
    if 'ANSICON' in os.environ:
        return False
    return True


def should_use_color(opts: 'Optional[Values]') -> bool:
    """Determine whether to use color based on the options supplied."""
    return opts is not None and hasattr(opts, 'color') and (
        opts.color == 'always'
        or (opts.color == 'auto' and supports_color())
    )


def ansi_log(name=CYLC_LOG, stream='stderr'):
    """Configure log formatter for terminal usage.

    Re-configures the formatter of any logging handlers pointing at the
    specified stream.

    Args:
        name (str): Logger name.
        stream (str): Either stdout or stderr.

    """
    stream_name = f'<{stream}>'
    for handler in logging.getLogger(name).handlers:
        if (
            getattr(handler, 'formatter', None)
            and isinstance(handler.formatter, CylcLogFormatter)
            and isinstance(handler, logging.StreamHandler)
            and handler.stream.name == stream_name
        ):
            handler.formatter.configure(color=True, max_width=get_width())


def parse_dirty_json(stdout):
    """Parse JSON from a string from dirty output.

    This is designed to handle cases where users have trash like this in their
    shell profile files::

        echo "[Hello $USER]"

    Examples:
        Prevents stdout trash from corrupting following json:
        >>> parse_dirty_json('''
        ...     some mess here
        ...     ["some json here"]
        ... ''')
        ['some json here']

        Ignores stdout trash which looks like json:
        >>> parse_dirty_json('''
        ...     ["something which isn't meant to be json here"]
        ...     {"something": "which is intended to be json here"}
        ... ''')
        {'something': 'which is intended to be json here'}

        Any stdout trash must be followed by a newline though:
        >>> parse_dirty_json('''
        ...     this approach can't handle everything [
        ...         "nicely"
        ...     ]
        ... ''')
        Traceback (most recent call last):
        ValueError: this approach can't handle everything [
                "nicely"
            ]

        Other:
        >>> parse_dirty_json('')
        Traceback (most recent call last):
        ValueError


    """
    stdout = stdout.strip()
    orig = stdout
    while stdout:
        try:
            return json.loads(stdout)
        except ValueError:
            try:
                stdout = stdout.split('\n', 1)[1]
            except IndexError:
                break
    raise ValueError(orig)


def cli_function(
    parser_function: 'Optional[Callable[..., OptionParser]]' = None,
    **parser_kwargs: Any
):
    """Decorator for CLI entry points.

    Catches "known" errors and suppresses [full] traceback.

    """
    def inner(wrapped_function: Callable):
        @wraps(wrapped_function)
        def wrapper(*api_args: str) -> None:
            """The function that we actually call.

            Args:
                api_args (tuple|list):
                    CLI arguments as specified via Python rather than
                    sys.argv directly.
                    If specified these will be passed to the option parser.

            """
            try:
                use_color = False
                wrapped_args, wrapped_kwargs = [], {}
                if parser_function:
                    parser = parser_function()
                    opts, args = parser.parse_args(
                        list(api_args),
                        **parser_kwargs
                    )
                    use_color = should_use_color(opts)
                    wrapped_args = [parser, opts, *args]
                if 'color' in inspect.signature(wrapped_function).parameters:
                    wrapped_kwargs['color'] = use_color

                # configure Cylc to use colour
                # TODO: re-enable autoreset
                # (https://github.com/cylc/cylc-flow/issues/6076)
                color_init(autoreset=False, strip=not use_color)
                if use_color:
                    ansi_log()

                try:
                    # run the command
                    wrapped_function(*wrapped_args, **wrapped_kwargs)
                except (CylcError, ParsecError) as exc:
                    if cylc.flow.flags.verbosity > 1:
                        # raise the full traceback
                        raise
                    # else catch "known" CylcErrors which should have sensible
                    # short summations of the issue, full traceback not
                    # necessary
                    print(
                        EXC_EXIT.format(
                            name=exc.__class__.__name__,
                            exc=exc
                        ),
                        file=sys.stderr
                    )
                    sys.exit(1)

                except SystemExit as exc:
                    if exc.args and isinstance(exc.args[0], str):
                        # catch and reformat sys.exit(<str>)
                        # NOTE: sys.exit(a) is equivalent to:
                        #       print(a, file=sys.stderr); sys.exit(1)
                        print(
                            EXC_EXIT.format(
                                name='ERROR',
                                exc=exc.args[0]
                            ),
                            file=sys.stderr
                        )
                        sys.exit(1)
                    raise
            except UnicodeEncodeError as exc:
                # this error can be raised from any code which attempts to
                # write a UTF-8 character to a terminal which does not or is
                # not configured to support UTF-8
                try:
                    # double check that this error is due to a non-UTF-8
                    # compatible terminal and not an internal issue...
                    print('😭')
                except UnicodeEncodeError:
                    # ... yep
                    print(
                        EXC_EXIT.format(
                            name='UnicodeEncodeError',
                            exc=(
                                '- A UTF-8 compatible terminal is'
                                ' required for this command.'
                                '\nTry adding ".UTF-8" onto the LANG'
                                ' environment variable e.g:'
                                '\n$ LANG=C.UTF-8'
                                f' cylc {" ".join(sys.argv[1:])}'
                            ),
                        ),
                        file=sys.stderr,
                    )
                    sys.exit(1)
                raise exc from None
        wrapper.parser_function = parser_function  # type: ignore
        return wrapper
    return inner


@overload
def prompt(
    message: str,
    options: Sequence[str],
    default: Optional[str] = None,
    process: Optional['StrFunc'] = None,
) -> str:
    ...


@overload
def prompt(
    message: str,
    options: Dict[str, 'T'],
    default: Optional[str] = None,
    process: Optional['StrFunc'] = None,
) -> 'T':
    ...


def prompt(
    message: str,
    options: Union[Sequence[str], Dict[str, 'T']],
    default: Optional[str] = None,
    process: Optional['StrFunc'] = None,
) -> Union[str, 'T']:
    """Dead simple CLI textual prompting.

    Args:
        message:
            The message to put before the user, don't end this with
            punctuation.
        options:
            The choices the user can pick:
            * If this is a list the option selected will be returned.
            * If this is a dict the keys are options, the corresponding value
              will be returned.
        default:
            A value to be chosen if the user presses <return> without first
            typing anything.
        process:
            A function to run the user's input through before comparision.
            E.G. string.lower.

    Returns:
        The selected option (if options is a list) else the corresponding
        value (if options is a dict).

    """
    default_ = ''
    if default:
        default_ = f'[{default}] '
    message += f': {default_}{",".join(options)}? '
    usr = cast('str', None)
    while usr not in options:
        usr = input(f'{message}')
        if default is not None and not usr:
            usr = default
        if process:
            usr = process(usr)
    if isinstance(options, dict):
        return options[usr]
    return usr


def flatten_cli_lists(lsts: List[str]) -> List[str]:
    """Return a sorted flat list for multi-use CLI command options.

    Examples:
        # --out='a,b,c'
        >>> flatten_cli_lists(['a,b,c'])
        ['a', 'b', 'c']

        # --out='a' --out='a,b'
        >>> flatten_cli_lists(['a', 'b,c'])
        ['a', 'b', 'c']

        # --out='a' --out='a,b'
        >>> flatten_cli_lists(['a', 'a,b'])
        ['a', 'b']

        # --out='  a '
        >>> flatten_cli_lists(['  a  '])
        ['a']

        # --out='a, b, c , d'
        >>> flatten_cli_lists(['a, b, c , d'])
        ['a', 'b', 'c', 'd']

    """
    return sorted({
        item.strip()
        for lst in (lsts or [])
        for item in lst.strip().split(',')
    })


@contextmanager
def handle_sigint(handler: Callable | None = None):
    """Context manager to handle if Ctrl+C happens while in input().

    If no handler is specified, it will print "Aborted" and exit 1.

    Sets the SIGINT handler inside the context and restores the previous
    handler after.
    """
    prev_handler = signal.signal(signal.SIGINT, handler or abort)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, prev_handler)


def abort(*args) -> NoReturn:
    print("\nAborted")
    sys.exit(1)


def interrupt(*args) -> NoReturn:
    print()  # go to next line after `^C`
    raise KeyboardInterrupt()
