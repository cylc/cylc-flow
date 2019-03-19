"""Functionality to assist working with terminals"""
import os
import sys

from parsec.exceptions import ParsecError

from cylc.cfgspec.glbl_cfg import glbl_cfg
from cylc.exceptions import CylcError
import cylc.flags


def is_terminal():
    """Determine if running in a terminal."""
    return hasattr(sys.stderr, 'isatty') and sys.stderr.isatty()


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


def prompt(question, force=False, gui=False, no_force=False, no_abort=False,
           keep_above=True):
    """Interactive Yes/No prompt for cylc CLI scripts.

    For convenience, on No we just exit rather than return.
    If force is True don't prompt, just return immediately.

    """
    if (force or glbl_cfg().get(['disable interactive command prompts'])) and (
            not no_force):
        return True
    if gui:
        raise NotImplementedError
    else:
        cli_response = input('%s (y/n)? ' % question)
        response_no = (cli_response not in ['y', 'Y'])
    if response_no:
        if no_abort:
            return False
        else:
            sys.exit(0)
    else:
        return True


def cli_function(function):
    """Decorator for CLI entry points.

    Catches "known" errors and suppresses [full] traceback.

    """
    def wrapper(*args, **kwargs):
        try:
            function(*args, **kwargs)
        except (CylcError, ParsecError) as exc:
            if is_terminal() or not cylc.flags.debug:
                # catch "known" CylcErrors which should have sensible short
                # summations of the issue, full traceback not necessary
                sys.exit(f'{exc.__class__.__name__}: {exc}')
            else:
                # if command is running non-interactively just raise the full
                # traceback
                raise
    return wrapper
