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


def allowed_characters(*chars):
    """Restrict permitted characters.

    """
    return (
        re.compile(r'^[%s]+$' % ''.join(chars)),
        'can only contain: %s' % ", ".join(regex_chars_to_text(chars))
    )


class UnicodeRuleChecker(object):

    RULES = []

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


class XtriggerNameValidator(UnicodeRuleChecker):
    """The rules for valid xtrigger labels:"""

    RULES = [
        allowed_characters(r'a-zA-Z0-9', '_')
    ]
