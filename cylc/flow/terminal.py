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
import json
import os
import re
import sys
import inspect
import logging
from textwrap import wrap

from functools import wraps
from subprocess import PIPE, Popen  # nosec

from ansimarkup import parse as cparse
from colorama import init as color_init

import cylc.flow.flags

from cylc.flow.exceptions import CylcError
from cylc.flow.loggingutil import CylcLogFormatter
from cylc.flow.parsec.exceptions import ParsecError
from cylc.flow.pathutil import get_workflow_run_dir
from cylc.flow.workflow_files import WorkflowFiles


# CLI exception message format
EXC_EXIT = cparse('<red><bold>{name}: </bold>{exc}</red>')


def is_terminal():
    """Determine if running in a terminal."""
    return hasattr(sys.stderr, 'isatty') and sys.stderr.isatty()


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


def centered(string, width=None):
    """Print centered text.

    Examples:
        >>> centered('foo', 9)
        '   foo'

    """
    if not width:
        width = get_width()
    return '\n'.join(
        ' ' * int((width - len(line)) / 2)
        + line
        for line in string.splitlines()
    )


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


def supports_color():
    """Determine if running in a terminal which supports color.

    See equivalent code in Django:
    https://github.com/django/django/blob/master/django/core/management/color.py
    """
    if not is_terminal():
        return False
    if sys.platform in ['Pocket PC', 'win32']:
        return False
    if 'ANSICON' in os.environ:
        return False
    return True


def ansi_log(name='cylc', stream='stderr'):
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
    # raise ValueError(f'Invalid JSON: {orig}')
    raise ValueError(orig)


def parse_reg(arg: str):
    """Replace runN with true reg name.

    Args:
        arg (str): flow as entered by user on cli e.g. myflow/runN
    """
    arg = arg.rstrip('/')
    if not arg.startswith(get_workflow_run_dir('')):
        workflow_dir = get_workflow_run_dir(arg)
    else:
        workflow_dir = arg
    run_number = re.search(  # type: ignore
        r'(?:run)(\d*$)',
        os.readlink(workflow_dir)).group(1)
    return arg.replace(WorkflowFiles.RUN_N, f'run{run_number}')


def cli_function(parser_function=None, **parser_kwargs):
    """Decorator for CLI entry points.

    Catches "known" errors and suppresses [full] traceback.

    """
    def inner(wrapped_function):
        @wraps(wrapped_function)
        def wrapper(*api_args):
            """The function that we actually call.

            Args:
                api_args (tuple|list):
                    CLI arguments as specified via Python rather than
                    sys.argv directly.
                    If specified these will be passed to the option parser.

            """
            use_color = False
            wrapped_args, wrapped_kwargs = tuple(), {}
            # should we use colour?
            if parser_function:
                parser = parser_function()
                opts, args = parser_function().parse_args(
                    list(api_args),
                    **parser_kwargs
                )
                # Ensure runN args are replaced with actual run number.
                endings = (WorkflowFiles.RUN_N, f'{WorkflowFiles.RUN_N}/')
                args = [
                    parse_reg(cli_arg) if cli_arg.endswith(endings)
                    else cli_arg for cli_arg in args
                ]
                use_color = (
                    hasattr(opts, 'color')
                    and (
                        opts.color == 'always'
                        or (opts.color == 'auto' and supports_color())
                    )
                )
                wrapped_args = (parser, opts, *args)
            if 'color' in inspect.signature(wrapped_function).parameters:
                wrapped_kwargs['color'] = use_color

            # configure Cylc to use colour
            color_init(autoreset=True, strip=not use_color)
            if use_color:
                ansi_log()

            try:
                # run the command
                wrapped_function(*wrapped_args, **wrapped_kwargs)
            except (CylcError, ParsecError) as exc:
                if cylc.flow.flags.verbosity < 2:
                    # catch "known" CylcErrors which should have sensible short
                    # summations of the issue, full traceback not necessary
                    print(
                        EXC_EXIT.format(
                            name=exc.__class__.__name__,
                            exc=exc
                        ),
                        file=sys.stderr
                    )
                    sys.exit(1)
                else:
                    # if command is running non-interactively just raise the
                    # full traceback
                    raise
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
        return wrapper
    return inner
