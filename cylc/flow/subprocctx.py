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
"""Extend parsec.validate for Cylc configuration.

Coerce more value type from string (to time point, duration, xtriggers, etc.).
"""

from inspect import Parameter
import json
from shlex import quote
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from cylc.flow.wallclock import get_current_time_string

if TYPE_CHECKING:
    from inspect import Signature


def add_kwarg_to_sig(
    sig: 'Signature', arg_name: str, default: Any
) -> 'Signature':
    """Return a new signature with a kwarg added."""
    # Note: added kwarg has to be before **kwargs ("variadic") in the signature
    positional_or_keyword: List[Parameter] = []
    variadic: List[Parameter] = []
    for param in sig.parameters.values():
        if param.kind == Parameter.VAR_KEYWORD:
            variadic.append(param)
        else:
            positional_or_keyword.append(param)
    return sig.replace(parameters=[
        *positional_or_keyword,
        Parameter(
            arg_name,
            kind=Parameter.KEYWORD_ONLY,
            default=default,
        ),
        *variadic,
    ])


class SubProcContext:  # noqa: SIM119 (not really relevant to this case)
    """Represent the context of an external command to run as a subprocess.

    Attributes:
        .cmd (list/str):
            The command to run expressed as a list (or as a str if shell=True
            is set in cmd_kwargs).
        .cmd_key (str):
            A key to identify the type of command. E.g. "jobs-submit".
        .cmd_kwargs (dict):
            Extra information about the command. This may contain:
                env (dict):
                    Specify extra environment variables for command.
                err (str):
                    Default STDERR content.
                out (str):
                    Default STDOUT content.
                ret_code (int):
                    Default return code.
                shell (boolean):
                    Launch command with "/bin/sh"?
                stdin_files (list):
                    Files with content to send to command's STDIN.
                    Can be file paths or opened file handles.
                stdin_str (str):
                    Content to send to command's STDIN.
        .err (str):
            Content of the command's STDERR.
        .host (str):
            The host Cylc intended to use for this command.
        .out (str)
            Content of the command's STDOUT.
        .ret_code (int):
            Return code of the command.
        .timestamp (str):
            Time string of latest update.
        .proc_pool_timeout (float):
            command execution timeout.
    """

    # Format string for single line output
    JOB_LOG_FMT_1 = '[%(cmd_key)s %(attr)s] %(mesg)s'
    # Format string for multi-line output
    JOB_LOG_FMT_M = '[%(cmd_key)s %(attr)s]\n%(mesg)s'

    def __init__(self, cmd_key, cmd, host='localhost', **cmd_kwargs):
        self.timestamp = get_current_time_string()
        self.cmd_key = cmd_key
        self.cmd = cmd
        self.cmd_kwargs = cmd_kwargs

        self.err = cmd_kwargs.get('err')
        self.ret_code = cmd_kwargs.get('ret_code')
        self.out = cmd_kwargs.get('out')
        self.host = host

    def __str__(self):
        ret = ''
        for attr in 'cmd', 'ret_code', 'out', 'err':
            value = getattr(self, attr, None)
            if value is not None and str(value).strip():
                mesg = ''
                if attr == 'cmd' and self.cmd_kwargs.get('stdin_files'):
                    mesg += 'cat'
                    for file_path in self.cmd_kwargs.get('stdin_files'):
                        mesg += ' ' + quote(str(file_path))
                    mesg += ' | '
                if attr == 'cmd' and isinstance(value, list):
                    mesg += ' '.join(quote(item) for item in value)
                else:
                    mesg = str(value).strip()
                if attr == 'cmd' and self.cmd_kwargs.get('stdin_str'):
                    mesg += ' <<<%s' % quote(self.cmd_kwargs.get('stdin_str'))
                if len(mesg.splitlines()) > 1:
                    fmt = self.JOB_LOG_FMT_M
                else:
                    fmt = self.JOB_LOG_FMT_1
                if not mesg.endswith('\n'):
                    mesg += '\n'
                ret += fmt % {
                    'cmd_key': self.cmd_key,
                    'attr': attr,
                    'mesg': mesg}
        return ret.rstrip()


class SubFuncContext(SubProcContext):
    """Represent the context of a Python function to run as a subprocess.

    Attributes:
        # See also parent class attributes.
        .label:
            function label under [xtriggers] in flow.cylc
        .func_name:
            function name
        .func_args:
            function positional args
        .func_kwargs:
            function keyword args
        .intvl:
            function call interval in secs (how often to check the
            external trigger)
        .ret_val
            function return: (satisfied?, result to pass to trigger tasks)
    """

    DEFAULT_INTVL = 10.0

    def __init__(
        self,
        label: str,
        func_name: str,
        func_args: List[Any],
        func_kwargs: Dict[str, Any],
        intvl: Union[float, str] = DEFAULT_INTVL,
        mod_name: Optional[str] = None
    ):
        """Initialize a function context."""
        self.label = label
        self.mod_name = mod_name or func_name
        self.func_name = func_name
        self.func_kwargs = func_kwargs
        self.func_args = func_args
        try:
            self.intvl = float(intvl)
        except (TypeError, ValueError):
            self.intvl = self.DEFAULT_INTVL
        self.ret_val: Tuple[
            bool, Optional[dict]
        ] = (False, None)  # (satisfied, broadcast)
        super(SubFuncContext, self).__init__(
            'xtrigger-func', cmd=[], shell=False
        )

    def update_command(self, workflow_run_dir):
        """Update the function wrap command after changes."""
        self.cmd = ['cylc', 'function-run',
                    self.mod_name,
                    self.func_name,
                    json.dumps(self.func_args),
                    json.dumps(self.func_kwargs),
                    workflow_run_dir]

    def get_signature(self):
        """Return the function call signature (as a string)."""
        skeys = sorted(self.func_kwargs.keys())
        args = self.func_args + [
            "%s=%s" % (i, self.func_kwargs[i]) for i in skeys]
        return "%s(%s)" % (self.func_name, ", ".join([str(a) for a in args]))

    def dump(self) -> str:
        """Output for logging."""
        return SubProcContext.__str__(self)

    def __str__(self) -> str:
        """
        >>> str(SubFuncContext('label', 'my_func', [1, 2], {'a': 3}))
        'my_func(1, 2, a=3):10.0'
        """
        return f"{self.get_signature()}:{self.intvl}"

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self}>"
