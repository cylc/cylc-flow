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
from typing import Union, Dict

from cylc.flow.exceptions import ClientError, ClientTimeout
from cylc.flow.network.client_factory import CommsMeth
from cylc.flow.network import get_location
from cylc.flow.remote import remote_cylc_cmd
from cylc.flow.workflow_files import load_contact_file, ContactFileFields


class WorkflowRuntimeClient():
    """Client to scheduler communication using ssh.

    Determines host from the contact file unless provided.

    Args:
        workflow (str):
            Name of the workflow to connect to.
        timeout (float):
            Set the default timeout in seconds.
        host (str):
            The host where the flow is running if known.
    """
    def __init__(
            self,
            workflow: str,
            host: str = None,
            timeout: Union[float, str] = None
    ):
        self.workflow = workflow
        self.SLEEP_INTERVAL = 0.1
        if not host:
            self.host, _, _ = get_location(workflow)
        # 5 min default timeout
        self.timeout = timeout if timeout is not None else 300

    async def async_request(self, command, args=None, timeout=None):
        """Send asynchronous request via SSH.
        """
        timeout = timeout if timeout is not None else self.timeout
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
                while True:
                    if proc.poll() is not None:
                        break
                    await asyncio.sleep(self.SLEEP_INTERVAL)
                out, err = (f.decode() for f in proc.communicate())
                return_code = proc.wait()
                if return_code:
                    raise ClientError(err, f"return-code={return_code}")
                return json.loads(out)
        except asyncio.TimeoutError:
            raise ClientTimeout(
                f"Command exceeded the timeout {timeout}. "
                f"This could be due to network problems. "
                "Check the workflow log."
            )

    def serial_request(self, command, args=None, timeout=None):
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
        Raises:
            ClientError: Coverall, on error from function call
        Returns:
            object: Deserialized output from function called.
        """
        loop = asyncio.new_event_loop()
        task = loop.create_task(
            self.async_request(command, args, timeout))
        loop.run_until_complete(task)
        loop.close()
        return task.result()

    def prepare_command(
        self, command: str, args: Dict, timeout: Union[float, str]
    ):
        """Prepare command for submission.
        """
        # Set environment variable to determine the communication for use on
        # the scheduler
        os.environ["CLIENT_COMMS_METH"] = CommsMeth.SSH.value
        cmd = ["client"]
        if timeout:
            cmd += [f'--comms-timeout={timeout}']
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

    __call__ = serial_request
