#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
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

"""Some global flags used in cylc"""

# Set pflag = True to stimulate task dependency negotiation whenever a
# task changes state in such a way that others could be affected. The
# flag should only be turned off again after use in scheduler.py, to
# ensure that dependency negotation occurs when required.
pflag = False

# Set iflag = True to simulate an update of the suite state summary
# structure accessed by gcylc and commands.
iflag = False

# verbose mode
verbose = False

# debug mode
debug = False

# TODO - run mode should be a flag

# utc mode
utc = False


class SyntaxVersion(object):

    """Store the syntax version used in the suite.rc."""
    is_prev = False
    is_new = False


class SyntaxVersionError(ValueError):

    """Raise an error if conflicting syntax versions are used."""

    ERROR_CONFLICTING_SYNTAX_VERSIONS = "Not allowed under %s syntax: %s"
    VERSION_STRINGS = {False: "previous", True: "new"}

    def __str__(self):
        return (self.ERROR_CONFLICTING_SYNTAX_VERSIONS % (
                self.VERSION_STRINGS[self.args[0]], self.args[1]))


def set_is_prev_syntax(is_prev, exc_message_or_class, *exc_args,
                       **exc_kwargs):
    """Attempt to define the syntax version.
    
    If it's already defined differently, raise an exception.
    If exc_message_or_class is a string, raise SyntaxVersionError
    using that string. If exc_message_or_class is an Exception-based
    class, raise it using *exc_args and **exc_kwargs in the
    constructor.

    """
    if isinstance(exc_message_or_class, basestring):
        exc_class = SyntaxVersionError
        exc_args = (SyntaxVersion.is_new, exc_message_or_class)
        exc_kwargs = {}
    else:
        exc_class = exc_message_or_class
    if is_prev:
        if SyntaxVersion.is_new:
            raise exc_class(*exc_args, **exc_kwargs)
        SyntaxVersion.is_prev = True
    else:
        if SyntaxVersion.is_prev:
            raise exc_class(*exc_args, **exc_kwargs)
        SyntaxVersion.is_new = True
