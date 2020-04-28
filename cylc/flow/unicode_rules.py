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

"""Module for unicode restrictions"""

import re


ENGLISH_REGEX_MAP = {
    r'\w': 'alphanumeric',
    r'\-': '-',
    r'\.': '.',
    r'\/': '/'
}


def regex_chars_to_text(chars):
    r"""Return a string representing a regex component.

    Examples:
        >>> regex_chars_to_text(['a', 'b', 'c'])
        ['a', 'b', 'c']
        >>> regex_chars_to_text([r'\-', r'\.', r'\/'])
        ['-', '.', '/']
        >>> regex_chars_to_text([r'\w'])
        ['alphanumeric']

    """
    return [
        ENGLISH_REGEX_MAP.get(char, char)
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
        'can only contain: a, b, c'
        >>> bool(regex.match('abc'))
        True
        >>> bool(regex.match('def'))
        False

    """
    return (
        re.compile(r'^[%s]+$' % ''.join(chars)),
        f'can only contain: {", ".join(regex_chars_to_text(chars))}'
    )


def not_starts_with(*chars):
    """Restrict first character.

    Example:
        >>> regex, message = not_starts_with('a', 'b', 'c')
        >>> message
        'can not start with: a, b, c'
        >>> bool(regex.match('def'))
        True
        >>> bool(regex.match('adef'))
        False

    """
    return (
        re.compile(r'^[^%s]' % ''.join(chars)),
        f'can not start with: {", ".join(regex_chars_to_text(chars))}'
    )


class UnicodeRuleChecker():

    RULES = []

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
                return (False, message)
        return (True, None)


class SuiteNameValidator(UnicodeRuleChecker):
    """The rules for valid suite names:"""

    RULES = [
        length(1, 254),
        not_starts_with(r'\.', r'\-'),
        allowed_characters(r'\w', r'\/', '_', '+', r'\-', r'\.', '@')
    ]
