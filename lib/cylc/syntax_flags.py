#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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


VERSION_PREV = "pre-cylc-6"  # < cylc-6
VERSION_NEW = "post-cylc-6"  # cylc 6 +


class SyntaxVersion(object):

    """Store the syntax version used in the suite.rc."""
    VERSION_REASON = None
    VERSION = None


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
