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

from typing import Union

from cylc.flow.suite_files import load_contact_file, ContactFileFields
from cylc.flow.network import (
    get_location,
)
import json
from cylc.flow.remote import _remote_cylc_cmd
from cylc.flow.exceptions import ClientError


class SuiteRuntimeClient():
    """Client to the workflow server communication using ssh.

    Determines host from the contact file unless provided.

    Args:
        suite (str):
            Name of the suite to connect to.
        timeout (float):
            Set the default timeout in seconds.
            See: https://github.com/cylc/cylc-flow/issues/4112
        host (str):
            The host where the flow is running if known.

            If host is provided it is not necessary to load
            the contact file.
    """
    def __init__(
            self,
            suite: str,
            timeout: Union[float, str] = None,
            host: str = None,
    ):
        self.suite = suite

        if not host:
            self.host, _, _ = get_location(suite)

    def send_request(self, command, args=None, timeout=None):
        """Send a request, using ssh.

        Determines ssh_cmd, cylc_path and login_shell settings from the contact
        file.

        Converts message to JSON and sends this to stdin. Executes the Cylc
        command, then deserialises the output.

        Use ``__call__`` to call this method.

        Args:
            command (str): The name of the endpoint to call.
            args (dict): Arguments to pass to the endpoint function.
            timeout (float): Override the default timeout (seconds).
            See: https://github.com/cylc/cylc-flow/issues/4112

        Raises:
            ClientError: Coverall, on error from function call
        Returns:
            object: Deserialized output from function called.
        """

        command = ["client", self.suite, command]
        contact = load_contact_file(self.suite)
        ssh_cmd = contact[ContactFileFields.SCHEDULER_SSH_COMMAND]
        login_shell = contact[ContactFileFields.SCHEDULER_USE_LOGIN_SHELL]
        cylc_path = contact[ContactFileFields.SCHEDULER_CYLC_PATH]
        cylc_path = None if cylc_path == 'None' else cylc_path
        if not args:
            args = {}
        message = json.dumps(args)
        proc = _remote_cylc_cmd(
            command,
            host=self.host,
            stdin_str=message,
            ssh_cmd=ssh_cmd,
            remote_cylc_path=cylc_path,
            ssh_login_shell=login_shell,
            capture_process=True)

        out, err = (f.decode() for f in proc.communicate())
        return_code = proc.wait()
        if return_code:
            raise ClientError(err, f"return-code={return_code}")
        return json.loads(out)

    __call__ = send_request
