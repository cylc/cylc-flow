#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2015 NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Run command on a remote host."""

import os
from posix import WIFSIGNALED
from pipes import quote
import shlex
import subprocess
import sys
from textwrap import TextWrapper

from cylc.cfgspec.globalcfg import GLOBAL_CFG
from cylc.suite_host import is_remote_host
from cylc.owner import is_remote_user
import cylc.flags


class remrun(object):
    """Run current command on a remote host.

    If owner or host differ from username and localhost, strip the
    remote options from the commandline and reinvoke the command on the
    remote host by passwordless ssh, then exit; else do nothing.

    To ensure that users are aware of remote re-invocation info is always
    printed, but to stderr so as not to interfere with results.

    """

    def __init__(self):
        self.owner = None
        self.host = None
        self.ssh_login_shell = None

        cylc.flags.verbose = '-v' in sys.argv or '--verbose' in sys.argv

        argv = sys.argv[1:]
        self.args = []
        # detect and replace host and owner options
        while argv:
            arg = argv.pop(0)
            if arg.startswith("--user="):
                self.owner = arg.replace("--user=", "")
            elif arg.startswith("--host="):
                self.host = arg.replace("--host=", "")
            elif arg == "--login":
                self.ssh_login_shell = True
            elif arg == "--no-login":
                self.ssh_login_shell = False
            else:
                self.args.append(arg)

        self.is_remote = (
            is_remote_user(self.owner) or is_remote_host(self.host))

    def execute(self, force_required=False, env=None, path=None):
        """Execute command on remote host.

        Returns False if remote re-invocation is not needed, True if it is
        needed and executes successfully otherwise aborts.

        """
        if not self.is_remote:
            return False

        if (force_required and
                '-f' not in sys.argv[1:] and '--force' not in sys.argv[1:]):
            sys.exit(
                "ERROR: force (-f) required for non-interactive " +
                "command invocation.")

        name = os.path.basename(sys.argv[0])[5:]  # /path/to/cylc-foo => foo

        user_at_host = ''
        if self.owner:
            user_at_host = self.owner + '@'
        if self.host:
            user_at_host += self.host
        else:
            user_at_host += 'localhost'

        # Build the remote command

        # ssh command and options (X forwarding)
        ssh_tmpl = str(GLOBAL_CFG.get_host_item(
            "remote shell template", self.host, self.owner))
        ssh_tmpl = ssh_tmpl.replace("%s", "-Y %s")
        command = shlex.split(ssh_tmpl % user_at_host)

        # Use bash -l?
        ssh_login_shell = self.ssh_login_shell
        if ssh_login_shell is None:
            ssh_login_shell = GLOBAL_CFG.get_host_item(
                "use login shell", self.host, self.owner)
        if ssh_login_shell:
            # A login shell will always source /etc/profile and the user's bash
            # profile file. To avoid having to quote the entire remote command
            # it is passed as arguments to the bash script.
            command += ["bash", "--login", "-c", "'exec $0 \"$@\"'"]

        # "cylc" on the remote host
        if path:
            command.append(os.sep.join(path + ["cylc"]))
        else:
            command.append(GLOBAL_CFG.get_host_item(
                "cylc executable", self.host, self.owner))

        command.append(name)

        if env is None:
            env = {}
        for var, val in env.iteritems():
            command.append("--env=%s=%s" % (var, val))
        for arg in self.args:
            command.append("'" + arg + "'")
            # above: args quoted to avoid interpretation by the shell,
            # e.g. for match patterns such as '.*' on the command line.

        if cylc.flags.verbose:
            # Wordwrap the command, quoting arguments so they can be run
            # properly from the command line
            command_str = ' '.join([quote(arg) for arg in command])
            print '\n'.join(
                TextWrapper(subsequent_indent='\t').wrap(command_str))

        try:
            popen = subprocess.Popen(command)
        except OSError as exc:
            sys.exit("ERROR: remote command invocation failed %s" % str(exc))

        res = popen.wait()
        if WIFSIGNALED(res):
            sys.exit("ERROR: remote command terminated by signal %d" % res)
        elif res:
            sys.exit("ERROR: remote command failed %d" % res)
        else:
            return True
