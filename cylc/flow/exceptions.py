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
"""Exceptions for "expected" errors."""

import errno
from typing import Callable, Iterable, NoReturn, Tuple, Type


class CylcError(Exception):
    """Generic exception for Cylc errors.

    This exception is raised in-place of "expected" errors where a short
    message to the user is more appropriate than traceback.

    CLI commands will catch this exception and exit with str(exception).

    """


class PluginError(CylcError):
    """Represents an error arising from a Cylc plugin."""

    def __init__(self, entry_point, plugin_name, exc):
        self.entry_point = entry_point
        self.plugin_name = plugin_name
        self.exc = exc

    def __str__(self):
        return (
            f'Error in plugin {self.entry_point}.{self.plugin_name}'
            f'\n{self.exc}'
        )


class UserInputError(CylcError):
    """Exception covering erroneous user input to a Cylc interface.

    Ideally this would be handled in the interface (e.g. argument parser).
    If this isn't possible raise UserInputError.

    """


class CylcConfigError(CylcError):
    """Generic exception to handle an error in a Cylc configuration file.

    TODO:
        * reference the configuration element causing the problem

    """


class WorkflowConfigError(CylcConfigError):
    """Exception for configuration errors in a Cylc workflow configuration."""


class GraphParseError(WorkflowConfigError):
    """Exception for errors in Cylc workflow graphing."""


class TriggerExpressionError(GraphParseError):
    """Trigger expression syntax issue."""


class TaskProxySequenceBoundsError(CylcError):
    """Error on TaskProxy.__init__ with out of sequence bounds start point."""

    def __init__(self, msg):
        CylcError.__init__(
            self, 'Not loading %s (out of sequence bounds)' % msg)


class ParamExpandError(WorkflowConfigError):
    """Exception for errors in Cylc parameter expansion."""


class WorkflowEventError(CylcError):
    """Exception for errors in Cylc event handlers."""


class ServiceFileError(CylcError):
    """Exception for errors related to workflow service files."""


class WorkflowFilesError(CylcError):
    """Exception for errors related to workflow files/directories."""


def handle_rmtree_err(
    function: Callable,
    path: str,
    excinfo: Tuple[Type[Exception], Exception, object]
) -> NoReturn:
    """Error handler for shutil.rmtree."""
    exc = excinfo[1]
    if isinstance(exc, OSError) and exc.errno == errno.ENOTEMPTY:
        # "Directory not empty", likely due to filesystem lag
        raise FileRemovalError(exc)
    raise exc


class FileRemovalError(CylcError):
    """Exception for errors during deletion of files/directories, which are
    probably the filesystem's fault, not Cylc's."""

    def __init__(self, exc: Exception) -> None:
        CylcError.__init__(
            self,
            f"{exc}. This is probably a temporary issue with the filesystem, "
            "not a problem with Cylc."
        )


class TaskRemoteMgmtError(CylcError):
    """Exceptions initialising workflow run directory of remote job host."""

    MSG_INIT = "initialisation did not complete"
    MSG_SELECT = "host selection failed"
    MSG_TIDY = "clean up did not complete"

    def __init__(
        self, message: str, platform_name: str, cmd: Iterable,
        ret_code: int, out: str, err: str
    ) -> None:
        self.msg = message
        self.platform_n = platform_name
        self.ret_code = ret_code
        self.out = out
        self.err = err
        self.cmd = cmd
        if isinstance(cmd, list):
            self.cmd = " ".join(cmd)

    def __str__(self):
        ret = (f"{self.platform_n}: {self.msg}:\n"
               f"COMMAND FAILED ({self.ret_code}): {self.cmd}\n")
        for label, item in ('STDOUT', self.out), ('STDERR', self.err):
            if item:
                for line in item.splitlines(True):  # keep newline chars
                    ret += f"COMMAND {label}: {line}"
        return ret


class TaskDefError(WorkflowConfigError):
    """Exception raise for errors in TaskDef initialization."""


class ClientError(CylcError):

    def __str__(self):
        ret = self.args[0]
        if len(self.args) > 1 and self.args[1]:
            # append server-side traceback if appended
            ret += '\n' + self.args[1]
        return ret


class WorkflowStopped(ClientError):
    """Special case of ClientError for a stopped workflow."""

    def __init__(self, workflow):
        self.workflow = workflow

    def __str__(self):
        return f'{self.workflow} is not running'


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


class PlatformLookupError(CylcConfigError):
    """Unable to determine the correct job platform from the information
    given"""


class HostSelectException(CylcError):
    """No hosts could be selected from the provided configuration."""

    def __init__(self, data):
        self.data = data
        CylcError.__init__(self)

    def __str__(self):
        ret = 'Could not select host from:'
        for host, data in sorted(self.data.items()):
            ret += f'\n    {host}:'
            for key, value in data.items():
                ret += f'\n        {key}: {value}'
        return ret


class NoHostsError(CylcError):
    """None of the hosts of a given platform were reachable."""
    def __init__(self, platform):
        self.platform_n = platform['name']
        super().__init__(f'Unable to find valid host for {self.platform_n}')


class CylcVersionError(CylcError):
    """Contact file is for a Cylc Version not supported by this script."""
    def __init__(self, version=None):
        self.version = version

    def __str__(self):
        if self.version is not None:
            return (
                f'Installed Cylc {self.version} workflow is not '
                'compatible with Cylc 8.'
            )
        else:
            return "Installed workflow is not compatible with Cylc 8."
