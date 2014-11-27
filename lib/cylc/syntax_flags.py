#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

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


def set_syntax_version(version, message, exc_class=None,
                       exc_args=None, exc_kwargs=None):
    """Attempt to define the syntax version.

    If it's already defined differently, raise an exception.
    The exception is exc_class if it is not None, raised
    using *exc_args and **exc_kwargs (or using message as the
    first argument if exc_args and exc_kwargs aren't set).
    Otherwise, raise SyntaxVersionError.

    """
    if exc_args is None:
        exc_args = (message,)
    if exc_kwargs is None:
        exc_kwargs = {}
    if exc_class is None:
        exc_class = SyntaxVersionError
        exc_args = (version, message)
    if SyntaxVersion.VERSION is None:
        SyntaxVersion.VERSION = version
        SyntaxVersion.VERSION_REASON = message
    elif SyntaxVersion.VERSION != version:
        raise exc_class(*exc_args, **exc_kwargs)
