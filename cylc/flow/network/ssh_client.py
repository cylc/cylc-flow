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

import json
from sys import stdin

from cylc.flow.network.scan import contact_info
from cylc.flow.suite_files import load_contact_file, ContactFileFields
from cylc.flow.network import (
    get_location
)
from cylc.flow.remote import construct_ssh_cmd, remote_cylc_cmd_using_env_vars
from cylc.flow.exceptions import ClientError
from cylc.flow import LOG

class SuiteRuntimeClient():

    def __init__(
            self,
            suite: str,
            host: str = None,
    ):
        self.suite = suite
        if not host:
            self.host, _, _ = get_location(suite)

    def send_request(self, function, args=None, timeout=None):
        command = ["client", self.suite, function]
        contact = load_contact_file(self.suite)
        ssh_cmd = contact[ContactFileFields.SCHEDULER_SSH_COMMAND]
        login_shell = contact[ContactFileFields.SCHEDULER_USE_LOGIN_SHELL]
        cylc_path = contact[ContactFileFields.SCHEDULER_CYLC_PATH]

        if args:
            tfile = json.dumps(args)
        else:
            # With stdin=None, `remote_cylc_cmd` will:
            # * Set stdin to open(os.devnull)
            # * Add `-n` to the SSH command
            tfile = None
        proc = remote_cylc_cmd_using_env_vars(
            command,
            self.host,
            ssh_cmd,
            login_shell,
            cylc_path,
            capture_process=True,
            stdin=True,
            stdin_str=tfile)
        out, err = (f.decode() for f in proc.communicate())
        return_code = proc.wait()
        if return_code:
            from pipes import quote
            command_str = " ".join(quote(item) for item in command)
            raise ClientError(command_str, "return-code=%d" % return_code)
        return json.loads(out)

    __call__ = send_request
