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

from cylc.flow.suite_files import load_contact_file, ContactFileFields
from cylc.flow.network import (
    get_location,
    encode_,
    decode_
)
from cylc.flow.remote import remote_cylc_cmd_using_env_vars
from cylc.flow.exceptions import ClientError


class SuiteRuntimeClient():

    def __init__(
            self,
            suite: str,
            host: str = None,
    ):
        self.suite = suite
        self.header = self.get_header()

        if not host:
            self.host, _, _ = get_location(suite)

    def send_request(self, command, args=None, timeout=None):

        command = ["client", self.suite, command]
        contact = load_contact_file(self.suite)
        ssh_cmd = contact[ContactFileFields.SCHEDULER_SSH_COMMAND]
        login_shell = contact[ContactFileFields.SCHEDULER_USE_LOGIN_SHELL]
        cylc_path = contact[ContactFileFields.SCHEDULER_CYLC_PATH]
        if not args:
            args = {}
        msg = {'command': command, 'args': args}
        message = decode_(msg)
        proc = remote_cylc_cmd_using_env_vars(
            command,
            self.host,
            ssh_cmd,
            login_shell,
            cylc_path,
            capture_process=True,
            stdin=True,
            stdin_str=message)

        out, err = (f.decode() for f in proc.communicate())
        return_code = proc.wait()
        if return_code:
            from pipes import quote
            command_str = " ".join(quote(item) for item in command)
            raise ClientError(command_str, "return-code=%d" % return_code)
        return encode_(out)

    __call__ = send_request
