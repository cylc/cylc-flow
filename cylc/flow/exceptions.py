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
from textwrap import wrap
from typing import (
    Callable,
    Iterable,
    NoReturn,
    Optional,
    Tuple,
    Type,
    Union,
)

from cylc.flow.subprocctx import SubFuncContext
from cylc.flow.util import format_cmd


class CylcError(Exception):
    """Generic exception for Cylc errors.

    This exception is raised in-place of "expected" errors where a short
    message to the user is more appropriate than traceback.

    CLI commands will catch this exception and exit with str(exception).

    """


class PluginError(CylcError):
    """Represents an error arising from a Cylc plugin.

    Args:
        entry_point: The plugin entry point as defined in setup.cfg
            (e.g. 'cylc.main_loop')
        plugin_name: Name of the plugin
        exc: Original exception caught when trying to run the plugin
    """

    def __init__(self, entry_point: str, plugin_name: str, exc: Exception):
        self.entry_point = entry_point
        self.plugin_name = plugin_name
        self.exc = exc

    def __str__(self) -> str:
        return (
            f"Error in plugin {self.entry_point}.{self.plugin_name}\n"
            f"{type(self.exc).__name__}: {self.exc}"
        )


class InputError(CylcError):
    """Exception covering erroneous user input to a Cylc interface.

    Ideally this would be handled in the interface (e.g. argument parser).
    If this isn't possible raise InputError.

    """


class CylcConfigError(CylcError):
    """Generic exception to handle an error in a Cylc configuration file.

    TODO:
        * reference the configuration element causing the problem

    """


class WorkflowConfigError(CylcConfigError):
    """Exception for configuration errors in a Cylc workflow configuration."""


class GlobalConfigError(CylcConfigError):
    """Exception for configuration errors in a Cylc global configuration."""


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


class CommandFailedError(CylcError):
    """Exception for when scheduler commands fail."""
    def __init__(self, value: Union[str, Exception]):
        self.value = value

    def __str__(self) -> str:
        if isinstance(self.value, Exception):
            return f"{type(self.value).__name__}: {self.value}"
        return self.value


class ServiceFileError(CylcError):
    """Exception for errors related to workflow service files."""


class WorkflowFilesError(CylcError):
    """Exception for errors related to workflow files/directories."""
    bullet = "\n    -"


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


class PlatformError(CylcError):
    """Error in the management of a remote platform.

    If the exception represents a command failure, provide either the ctx OR
    manually populate the remaining kwargs. Otherwise leave the kwargs blank.

    Args:
        message:
            Short description.
        platform_name:
            Name of the platform.
        ctx:
            SubFuncContext object if available.
            The other kwargs are derived from this.
        cmd:
            The remote command.
        ret_code:
            The command's return code.
        out:
            The command's stdout.
        err:
            The command's stderr.

    """

    MSG_INIT = "initialisation did not complete"
    MSG_SELECT = "host selection failed"
    MSG_TIDY = "clean up did not complete"

    def __init__(
        self,
        message: str,
        platform_name: str,
        *,
        ctx: Optional[SubFuncContext] = None,
        cmd: Optional[Union[str, Iterable]] = None,
        ret_code: Optional[int] = None,
        out: Optional[str] = None,
        err: Optional[str] = None
    ) -> None:
        self.msg = message
        self.platform_name = platform_name
        if ctx:
            self.cmd = ctx.cmd
            self.ret_code = ctx.ret_code
            self.out = ctx.out
            self.err = ctx.err
        else:
            self.cmd = cmd
            self.ret_code = ret_code
            self.out = out
            self.err = err
        # convert the cmd object to a str if needed
        if self.cmd and not isinstance(self.cmd, str):
            self.cmd = format_cmd(self.cmd)

    def __str__(self):
        # matches cylc.flow.platforms.log_platform_event format
        if self.platform_name:
            ret = f'platform: {self.platform_name} - {self.msg}'
        else:
            ret = f'{self.msg}'
        for label, item in [
            ('COMMAND', self.cmd),
            ('RETURN CODE', self.ret_code),
            ('STDOUT', self.out),
            ('STDERR', self.err)
        ]:
            if item is not None:
                ret += f'\n{label}:'
                for line in str(item).splitlines(True):  # keep newline chars
                    ret += f"\n    {line}"
        return ret


class TaskDefError(WorkflowConfigError):
    """Exception raise for errors in TaskDef initialization."""


class XtriggerConfigError(WorkflowConfigError):
    """An error in an xtrigger.

    For example:

    * If the function module was not found.
    * If the function was not found in the xtrigger module.
    * If the function is not callable.
    * If any string template in the function context
      arguments are not present in the expected template values.

    """

    def __init__(self, label: str, trigger: str, message: str):
        self.label: str = label
        self.trigger: str = trigger
        self.message: str = message

    def __str__(self):
        return f'[{self.label}] {self.message}'


class ClientError(CylcError):

    def __init__(
        self,
        message: str,
        traceback: Optional[str] = None,
        workflow: Optional[str] = None
    ):
        self.message = message
        self.traceback = traceback
        # Workflow not included in string representation but useful bit of
        # info to attach to the exception object
        self.workflow = workflow

    def __str__(self) -> str:
        ret = self.message
        if self.traceback:
            # append server-side traceback
            ret += '\n' + self.traceback
        return ret


class WorkflowStopped(ClientError):
    """Special case of ClientError for a stopped workflow."""

    def __init__(self, workflow):
        self.workflow = workflow

    def __str__(self):
        return f'{self.workflow} is not running'


class ClientTimeout(CylcError):

    def __init__(self, message: str, workflow: Optional[str] = None):
        self.message = message
        self.workflow = workflow

    def __str__(self) -> str:
        return self.message


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


class SequenceParsingError(CyclingError):
    """Error on parsing an invalid sequence."""


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
            if host != 'ranking':
                ret += f'\n    {host}:'
                for key, value in data.items():
                    ret += f'\n        {key}: {value}'
        hint = self.get_hint()
        if hint:
            ret += f'\n\n{hint}'
        return ret

    def get_hint(self):
        """Return a hint to explain this error for certain cases."""
        if all(
            # all procs came back with special SSH error code 255
            datum.get('returncode') == 255
            for key, datum in self.data.items()
            if key != 'ranking'
        ):
            # likely SSH issues
            return (
                'Cylc could not establish SSH connection to the run hosts.'
                '\nEnsure you can SSH to these hosts without having to'
                ' answer any prompts.'
            )

        if (
            # a ranking expression was used
            self.data.get('ranking')
            # and all procs came back with special 'cylc psutil' error code 2
            # (which is used for errors relating to the extraction of metrics)
            and all(
                datum.get('returncode') == 2
                for key, datum in self.data.items()
                if key != 'ranking'
            )
        ):
            # likely an issue with the ranking expression
            ranking = "\n".join(
                wrap(
                    self.data.get("ranking"),
                    initial_indent='    ',
                    subsequent_indent='    ',
                )
            )
            return (
                'This is likely an error in the ranking expression:'
                f'\n{ranking}'
                '\n\nConfigured by:'
                '\n    global.cylc[scheduler][run hosts]ranking'
            )

        return None


class NoHostsError(CylcError):
    """None of the hosts of a given platform were reachable."""
    def __init__(self, platform):
        self.platform_name = platform['name']
        super().__init__()

    def __str__(self):
        return f'Unable to find valid host for {self.platform_name}'


class NoPlatformsError(CylcError):
    """None of the platforms of a given group were reachable."""
    def __init__(self, platform_group):
        self.platform_group = platform_group
        super().__init__()

    def __str__(self):
        return f'Unable to find a platform from group {self.platform_group}.'


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
