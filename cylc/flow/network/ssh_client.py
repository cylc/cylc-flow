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

from async_timeout import timeout as ascyncto
import asyncio
import json
import os
from typing import Any, List, Optional, Tuple, Union, Dict

from cylc.flow.exceptions import ClientError, ClientTimeout
from cylc.flow.network.client import WorkflowRuntimeClientBase
from cylc.flow.network.client_factory import CommsMeth
from cylc.flow.remote import remote_cylc_cmd
from cylc.flow.workflow_files import load_contact_file, ContactFileFields


class WorkflowRuntimeClient(WorkflowRuntimeClientBase):
    """Client to scheduler communication using ssh."""

    DEFAULT_TIMEOUT = 300  # seconds
    SLEEP_INTERVAL = 0.1

    async def async_request(
        self, command: str,
        args: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        req_meta: Optional[Dict[str, Any]] = None
    ):
        """Send asynchronous request via SSH.

        Determines ssh_cmd, cylc_path and login_shell settings from the contact
        file.

        Converts message to JSON and sends this to stdin. Executes the Cylc
        command, then deserialises the output.

        Args:
            command (str): The name of the endpoint to call.
            args (dict): Arguments to pass to the endpoint function.
            timeout (float): Override the default timeout (seconds).
        Raises:
            ClientError: Coverall, on error from function call
        Returns:
            object: Deserialized output from function called.
        """
        if timeout is None:
            timeout = self.timeout
        try:
            async with ascyncto(timeout):
                cmd, ssh_cmd, login_sh, cylc_path, msg = self.prepare_command(
                    command, args, timeout
                )
                platform = {
                    'ssh command': ssh_cmd,
                    'cylc path': cylc_path,
                    'use login shell': login_sh,
                }
                proc = remote_cylc_cmd(
                    cmd,
                    platform,
                    host=self.host,
                    stdin_str=msg,
                    capture_process=True
                )
                while proc.poll() is None:
                    await asyncio.sleep(self.SLEEP_INTERVAL)
                out, err = proc.communicate()
                if proc.returncode:
                    raise ClientError(err, f"return-code={proc.returncode}")
                return json.loads(out)
        except asyncio.TimeoutError:
            self.timeout_handler()
            raise ClientTimeout(
                f"Command exceeded the timeout {timeout}s. "
                "This could be due to network problems. "
                "Check the workflow log."
            )

    def prepare_command(
        self, command: str, args: Optional[dict], timeout: Union[float, str]
    ) -> Tuple[List[str], str, str, Optional[str], str]:
        """Prepare command for submission."""
        # Set environment variable to determine the communication for use on
        # the scheduler
        os.environ["CLIENT_COMMS_METH"] = CommsMeth.SSH.value
        cmd = ["client"]
        if timeout:
            cmd.append(f'--comms-timeout={timeout}')
        cmd += [self.workflow, command]
        contact = load_contact_file(self.workflow)
        ssh_cmd = contact[ContactFileFields.SCHEDULER_SSH_COMMAND]
        login_shell = contact[ContactFileFields.SCHEDULER_USE_LOGIN_SHELL]
        cylc_path = contact[ContactFileFields.SCHEDULER_CYLC_PATH]
        cylc_path = None if cylc_path == 'None' else cylc_path
        if not args:
            args = {}
        message = json.dumps(args)
        return cmd, ssh_cmd, login_shell, cylc_path, message
