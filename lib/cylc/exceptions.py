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
"""Exceptions for "expected" errors."""


class CylcError(Exception):
    """Generic exception for Cylc errors.

    This exception is raised in-place of "expected" errors where a short
    message to the user is more appropriate than traceback.

    CLI commands will catch this exception and exit with str(exception).

    """


class UserInputError(CylcError):
    """Exception covering erroneous user imput to a Cylc interface.

    Ideally this would be handled in the interface (e.g. argument parser).
    If this isn't possible raise UserInputError.

    """


class LogAnalyserError(CylcError):
    """Exception for issues scraping Cylc suite log files."""


class CylcConfigError(CylcError):
    """Generic exception to handle an error in a Cylc configuration file.

    TODO:
        * reference the configuration element causing the problem

    """


class SuiteConfigError(CylcConfigError):
    """Exception for configuration errors in a Cylc suite configuration."""


class GlobalConfigError(CylcConfigError):
    """Exception for configuration errors in a Cylc global configuration."""


class GraphParseError(SuiteConfigError):
    """Exception for errors in Cylc suite graphing."""


class TriggerExpressionError(GraphParseError):
    """Trigger expression syntax issue."""


class TaskProxySequenceBoundsError(CylcError):
    """Error on TaskProxy.__init__ with out of sequence bounds start point."""

    def __init__(self, msg):
        CylcError.__init__(
            self, 'Not loading %s (out of sequence bounds)' % msg)


class ParamExpandError(SuiteConfigError):
    """Exception for errors in Cylc parameter expansion."""


class SuiteEventError(CylcError):
    """Exception for errors in Cylc event handlers."""


class SuiteServiceFileError(CylcError):
    """Exception for errors related to suite service files."""


class TaskRemoteMgmtError(CylcError):
    """Exceptions initialising suite run directory of remote job host."""

    MSG_INIT = '%s: initialisation did not complete:\n'  # %s owner_at_host
    MSG_SELECT = '%s: host selection failed:\n'  # %s host
    MSG_TIDY = '%s: clean up did not complete:\n'  # %s owner_at_host

    def __str__(self):
        msg, (host, owner), cmd_str, ret_code, out, err = self.args
        if owner:
            owner_at_host = owner + '@' + host
        else:
            owner_at_host = host
        ret = (msg + 'COMMAND FAILED (%d): %s\n') % (
            owner_at_host, ret_code, cmd_str)
        for label, item in ('STDOUT', out), ('STDERR', err):
            if item:
                for line in item.splitlines(True):  # keep newline chars
                    ret += 'COMMAND %s: %s' % (label, line)
        return ret


class TaskDefError(SuiteConfigError):
    """Exception raise for errors in TaskDef initialization."""


class ClientError(CylcError):

    def __str__(self):
        ret = 'Request returned error: %s' % self.args[0]
        if len(self.args) > 1 and self.args[1]:
            # append server-side traceback if appended
            ret += '\n' + self.args[1]
        return ret


class ClientTimeout(CylcError):
    pass


class CyclingError(CylcError):
    pass


class CyclerTypeError(CyclingError):
    """An error raised when incompatible cycling types are wrongly mixed."""

    def __init__(self, *args):
        CyclingError.__init__(
            self,
            'Incompatible cycling types: {0} ({1}), {2} ({3})'.format(*args))


class PointParsingError(CyclingError):
    """An error raised when a point has an incorrect value."""

    def __init__(self, *args):
        CyclingError.__init__(
            self, 'Incompatible value for {0}: {1}: {2}'.format(*args))


class IntervalParsingError(CyclingError):
    """An error raised when an interval has an incorrect value."""

    def __init__(self, *args):
        CyclingError.__init__(
            self, 'Incompatible value for {0}: {1}'.format(*args))


class SequenceDegenerateError(CyclingError):
    """An error raised when adjacent points on a sequence are equal."""

    def __init__(self, *args):
        CyclingError.__init__(
            self, (
                '{0}, point format {1}: equal adjacent points:'
                ' {2} => {3}.'
            ).format(*args))


class CylcTimeSyntaxError(CyclingError):
    """An error denoting invalid ISO/Cylc input syntax."""


class CylcMissingContextPointError(CyclingError):
    """An error denoting a missing (but required) context cycle point."""


class CylcMissingFinalCyclePointError(CyclingError):
    """An error denoting a missing (but required) final cycle point."""
