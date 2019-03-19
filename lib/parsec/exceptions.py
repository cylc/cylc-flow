#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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

from copy import copy
import os

from parsec.util import itemstr


class ParsecError(Exception):
    """Generic exception for Parsec errors."""

    def __str__(self):
        return ' '.join(self.args)


class ItemNotFoundError(ParsecError, KeyError):
    """Error raised for missing configuration items."""

    def __init__(self, msg):
        ParsecError.__init__(self, 'item not found: %s' % msg)


class NotSingleItemError(ParsecError, TypeError):
    """Error raised if an iterable is given where an item is expected."""

    def __init__(self, msg):
        ParsecError.__init__(self, 'not a singular item: %s' % msg)


class FileParseError(ParsecError):
    """Error raised when attempting to read in the config file(s)."""

    def __init__(self, reason, index=None, line=None, lines=None,
                 error_name=""):
        msg = ''
        if error_name:
            msg = error_name + ":\n"
        msg += reason
        if index:
            msg += " (line " + str(index + 1) + ")"
        if line:
            msg += ":\n   " + line.strip()
        if lines:
            msg += "\nContext lines:\n" + "\n".join(lines)
            msg += "\t<-- " + error_name
        if index:
            # TODO - make 'view' function independent of cylc:
            msg += "\n(line numbers match 'cylc view -p')"
        ParsecError.__init__(self, msg)


class IncludeFileNotFoundError(ParsecError):
    """Error raised for missing include files."""

    def __init__(self, flist):
        """Missing include file error.

        E.g. for [DIR/top.rc, DIR/inc/sub.rc, DIR/inc/gone.rc]
        "Include-file not found: inc/gone.rc via inc/sub.rc from DIR/top.rc"
        """
        rflist = copy(flist)
        top_file = rflist[0]
        top_dir = os.path.dirname(top_file) + '/'
        rflist.reverse()
        msg = rflist[0].replace(top_dir, '')
        for f in rflist[1:-1]:
            msg += ' via %s' % f.replace(top_dir, '')
        msg += ' from %s' % top_file
        ParsecError.__init__(self, msg)


class UpgradeError(ParsecError):
    """Error raised upon fault in an upgrade operation."""


class ValidationError(ParsecError):
    """Generic exception for invalid configurations."""


class IllegalValueError(ValidationError):
    """Bad setting value."""

    def __init__(self, vtype, keys, value, exc=None):
        msg = '(type=%s) %s' % (
            vtype, itemstr(keys[:-1], keys[-1], value=value))
        if exc:
            msg += " - (%s)" % exc
        ValidationError.__init__(self, msg)


class ListValueError(IllegalValueError):
    """Bad setting value, for a comma separated list."""

    def __init__(self, keys, value, msg='', exc=None):
        msg = '%s\n    %s' % (
            msg, itemstr(keys[:-1], keys[-1], value=value))
        if exc:
            msg += ": %s" % exc
        ValidationError.__init__(self, msg)


class IllegalItemError(ValidationError):
    """Bad setting section or option name."""

    def __init__(self, keys, key, msg=None):
        if msg is not None:
            msg = '%s - (%s)' % (itemstr(keys, key), msg)
        else:
            msg = '%s' % itemstr(keys, key)
        ValidationError.__init__(self, msg)


class EmPyError(Exception):
    """Wrapper class for EmPy exceptions."""

    def __init__(self, exc, lineno):
        Exception.__init__(self, exc)
        self.lineno = lineno
