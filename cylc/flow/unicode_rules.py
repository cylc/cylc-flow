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

"""Module for unicode restrictions"""

import re

from cylc.flow.task_id import (
    _TASK_NAME_CHARACTERS,
    _TASK_NAME_PREFIX,
)
from cylc.flow.run_modes import RunMode
from cylc.flow.task_qualifiers import TASK_QUALIFIERS
from cylc.flow.task_state import TASK_STATUSES_ORDERED

ENGLISH_REGEX_MAP = {
    r'\w': r'alphanumeric (regex word characters - ``\w``)',
    r'a-zA-Z0-9': 'latin letters and numbers',
    r'\d': 'numbers',
    r'\-': '``-``',
    r'\.': '``.``',
    r'\/': '``/``'
}


def regex_chars_to_text(chars):
    r"""Return a string representing a regex component.

    Examples:
        >>> regex_chars_to_text(['a', 'b', 'c'])
        ['``a``', '``b``', '``c``']
        >>> regex_chars_to_text([r'\-', r'\.', r'\/'])
        ['``-``', '``.``', '``/``']
        >>> regex_chars_to_text([r'\w'])
        ['alphanumeric (regex word characters - ``\\w``)']
        >>> regex_chars_to_text(['not_in_map'])
        ['``not_in_map``']

    """
    return [
        ENGLISH_REGEX_MAP.get(char, f'``{char}``')
        for char in chars
    ]


def length(minimum, maximum):
    """Restrict character length.

    Example:
        >>> regex, message = length(0, 5)
        >>> message
        'must be between 0 and 5 characters long'
        >>> bool(regex.match('abcde'))
        True
        >>> bool(regex.match('abcdef'))
        False

    """
    return (
        re.compile(r'^.{%d,%d}$' % (minimum, maximum)),
        f'must be between {minimum} and {maximum} characters long'
    )


def allowed_characters(*chars):
    """Restrict permitted characters.

    Example:
        >>> regex, message = allowed_characters('a', 'b', 'c')
        >>> message
        'can only contain: ``a``, ``b``, ``c``'
        >>> bool(regex.match('abc'))
        True
        >>> bool(regex.match('def'))
        False

    """
    return (
        re.compile(r'^[%s]+$' % ''.join(chars)),
        f'can only contain: {", ".join(regex_chars_to_text(chars))}'
    )


def disallowed_characters(*chars):
    """Restrict permitted characters.

    Example:
        >>> regex, message = disallowed_characters('&', '~')
        >>> message
        'cannot contain: ``&``, ``~``'
        >>> bool(regex.match('abc01'))
        True
        >>> bool(regex.match('abc&01'))
        False

    """
    return (
        re.compile(r'^[^%s]*$' % ''.join(chars)),
        f'cannot contain: {", ".join(regex_chars_to_text(chars))}'
    )


def starts_with(*chars):
    """Restrict first character.

    Example:
        >>> regex, message = starts_with('a', 'b', 'c')
        >>> message
        'must start with: ``a``, ``b``, ``c``'
        >>> bool(regex.match('def'))
        False
        >>> bool(regex.match('adef'))
        True

    """
    return (
        re.compile(r'^[%s]' % ''.join(chars)),
        f'must start with: {", ".join(regex_chars_to_text(chars))}'
    )


def not_starts_with_char(*chars):
    """Restrict first character.

    Example:
        >>> regex, message = not_starts_with_char('a', 'b', 'c')
        >>> message
        'cannot start with: ``a``, ``b``, ``c``'
        >>> bool(regex.match('def'))
        True
        >>> bool(regex.match('adef'))
        False

    """
    return (
        re.compile(r'^[^%s]' % ''.join(chars)),
        f'cannot start with: {", ".join(regex_chars_to_text(chars))}'
    )


def not_starts_with(string):
    """Restrict strings starting with ___.

    Example:
        Regular usage:
        >>> regex, message = not_starts_with('foo')
        >>> message
        'cannot start with: ``foo``'
        >>> bool(regex.match('tfoo'))
        True
        >>> bool(regex.match('foot'))
        False

        Note regex chars are escaped automatically:
        >>> regex, message = not_starts_with('...')
        >>> bool(regex.match('aaa b'))
        True
        >>> bool(regex.match('... b'))
        False

    """
    return (
        re.compile(rf'^(?!{re.escape(string)})'),
        f'cannot start with: ``{string}``'
    )


def _human_format_list(lst):
    """Write a list in plain text.

    Examples:
        >>> _human_format_list(['a'])
        'a'
        >>> _human_format_list(['a', 'b'])
        'a or b'
        >>> _human_format_list(['a', 'b', 'c'])
        'a, b or c'

    """
    if len(lst) > 1:
        return ', '.join(lst[:-1]) + f' or {lst[-1]}'
    return lst[0]


def _re_format_list(lst):
    """Write a list in regex format.

    Examples:
        >>> _re_format_list('a')
        '(a)'
        >>> _re_format_list(['a', 'b'])
        '(a|b)'
        >>> _re_format_list(['a', 'b', 'c'])
        '(a|b|c)'

    """
    return f"({'|'.join(map(re.escape, lst))})"


def not_equals(*strings):
    r"""Restrict entire string.

    Example:
        Regular usage:
        >>> regex, message = not_equals('foo')
        >>> message
        'cannot be: ``foo``'
        >>> bool(regex.match('foot'))  # "foot" shouldn't match
        True
        >>> bool(regex.match('a\nb'))  # newlines should be tolerated
        True
        >>> bool(regex.match('foo'))   # "foo" should match
        False

        Regular use (multi):
        >>> regex, message = not_equals('foo', 'bar', 'baz')
        >>> regex.pattern
        '^(?!^(foo|bar|baz)$).*$'
        >>> message
        'cannot be: ``foo``, ``bar`` or ``baz``'

        Note regex chars are escaped automatically:
        >>> regex, message = not_equals('...')
        >>> bool(regex.match('...'))
        False
        >>> bool(regex.match('aaa'))
        True

    """
    return (
        re.compile(rf'^(?!^{_re_format_list(strings)}$).*$', re.M),
        'cannot be: ' + _human_format_list([f'``{s}``' for s in strings])
    )


def disallow_char_if_not_at_end_of_first_word(char):
    """Prevent use of a (non-alphanumeric) character unless it occurs directly
    after first word (in which case there is no limit on subsequent
    occurances).

    Example:
        >>> regex, message = disallow_char_if_not_at_end_of_first_word(':')
        >>> message
        'cannot contain ``:`` unless it occurs at the end of the first word'
        >>> bool(regex.match('Foo: bar'))
        True
        >>> bool(regex.match('INFO: Foo: bar'))
        True
        >>> bool(regex.match('Foo bar: baz'))
        False
        >>> bool(regex.match('Foo bar'))
        True

    """
    return (
        re.compile(fr'^(\w+{char}.*|[^{char}]+)$', flags=re.S),
        f'cannot contain ``{char}`` unless it occurs at the end of the '
        'first word'
    )


class UnicodeRuleChecker():

    RULES: list = []

    @classmethod
    def __init_subclass__(cls):
        cls.__doc__ = cls.__doc__ + '\n' if cls.__doc__ else ''
        cls.__doc__ += '\n' + '\n'.join([
            f'* {message}'
            for regex, message in cls.RULES
        ])

    @classmethod
    def validate(cls, string):
        """Run this collection of rules against the given string.

        Args:
            string (str):
                String to validate.

        Returns:
            tuple - (outcome, message)
            outcome (bool) - True if all patterns match.
            message (str) - User-friendly error message.

        """
        for rule, message in cls.RULES:
            if not rule.match(string):
                return (
                    False,
                    # convert RST style literals to Markdown for error messages
                    # (RST used in docs)
                    message.replace('``', '`'),
                )
        return (True, None)


class WorkflowNameValidator(UnicodeRuleChecker):
    """The rules for valid workflow names:"""

    RULES = [
        length(1, 254),
        not_starts_with_char(r'\.', r'\-', r'\d'),
        allowed_characters(r'\w', r'\/', '_', '+', r'\-', r'\.', '@'),
    ]


class XtriggerNameValidator(UnicodeRuleChecker):
    """The rules for valid xtrigger labels:"""

    RULES = [
        allowed_characters(r'a-zA-Z0-9', '_'),
        not_starts_with('_cylc'),
    ]


class TaskMessageValidator(UnicodeRuleChecker):
    """The rules for valid task messages:"""

    RULES = [
        # <severity>:<message> e.g. "WARN: something went wrong
        disallow_char_if_not_at_end_of_first_word(':'),
        # blacklist built-in qualifiers
        # (technically we need only blacklist task messages, however, to avoid
        # confusion it's best to blacklist qualifiers too)
        not_equals(*TASK_QUALIFIERS),
        not_starts_with('_cylc'),
    ]


class TaskOutputValidator(UnicodeRuleChecker):
    """The rules for valid task outputs/message triggers:"""

    RULES = [
        # restrict outputs to sensible characters
        allowed_characters(r'\w', r'\d', r'\-'),
        # blacklist the _cylc prefix
        not_starts_with('_cylc'),
        # blacklist keywords
        not_equals('required', 'optional', 'all', 'and', 'or'),
        # blacklist Run Modes:
        not_equals(RunMode.SKIP.value),
        # blacklist built-in task qualifiers and statuses (e.g. "waiting")
        not_equals(*sorted({*TASK_QUALIFIERS, *TASK_STATUSES_ORDERED})),
    ]


class TaskNameValidator(UnicodeRuleChecker):
    """The rules for valid task and family names:"""

    RULES = [
        starts_with(_TASK_NAME_PREFIX),
        allowed_characters(*_TASK_NAME_CHARACTERS),
        not_starts_with('_cylc'),
        not_equals('root'),
    ]
