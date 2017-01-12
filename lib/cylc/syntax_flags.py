#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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

"""Global syntax flags used in cylc"""

import sys

VERSION_PREV = "pre-cylc-6"  # < cylc-6
VERSION_NEW = "post-cylc-6"  # cylc 6 +

DEPRECATED_SYNTAX_WARNING = {
    VERSION_PREV: "WARNING: pre cylc 6 syntax is deprecated: {0}\n"
}


class SyntaxVersion(object):

    """Store the syntax version used in the suite.rc."""
    VERSION_REASON = None
    VERSION = None
    WARNING_MESSAGES = set()


class SyntaxVersionError(ValueError):

    """Raise an error if conflicting syntax versions are used."""

    ERROR_CONFLICTING_SYNTAX_VERSIONS = (
        "Conflicting syntax: %s syntax (%s) vs %s syntax (%s)")

    def __str__(self):
        return (self.ERROR_CONFLICTING_SYNTAX_VERSIONS % (
                SyntaxVersion.VERSION, SyntaxVersion.VERSION_REASON,
                self.args[0], self.args[1]))


def set_syntax_version(version, message):
    """Attempt to define the syntax version.

    If it's already defined differently, raise SyntaxVersionError.
    """
    if SyntaxVersion.VERSION is None:
        SyntaxVersion.VERSION = version
        SyntaxVersion.VERSION_REASON = message
    elif SyntaxVersion.VERSION != version:
        raise SyntaxVersionError(version, message)
    if SyntaxVersion.VERSION in DEPRECATED_SYNTAX_WARNING:
        warning = (
            DEPRECATED_SYNTAX_WARNING[SyntaxVersion.VERSION].format(message))
        if warning not in SyntaxVersion.WARNING_MESSAGES:
            sys.stderr.write(warning)
            SyntaxVersion.WARNING_MESSAGES.add(warning)
