#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA
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
"""Run command on a remote, (i.e. a remote [user@]host)."""

import os
from posix import WIFSIGNALED
from pipes import quote
import shlex
from subprocess import Popen, PIPE
import sys
from textwrap import TextWrapper

from cylc.cfgspec.glbl_cfg import glbl_cfg
import cylc.flags
from cylc.cfgspec.globalcfg import GLOBAL_CFG
from cylc.version import CYLC_VERSION


def remote_cylc_cmd(cmd, user=None, host=None, capture=False,
                    ssh_login_shell=None):
    """Run a given cylc command on a remote account.

    """
    # TODO - TEST FAILED COMMAND OSERROR
    if host is None:
        host = "localhost"
    if user is None:
        user_at_host = host
    else:
        user_at_host = "%s@%s" % (user, host)

    # Pass cylc version through.
    command = ["env", "CYLC_VERSION=%s" % CYLC_VERSION]

    ssh = str(GLOBAL_CFG.get_host_item("ssh command", host, user))
    command += shlex.split(ssh) + ["-n", user_at_host]

    # Use bash loging shell?
    if ssh_login_shell is None:
        ssh_login_shell = GLOBAL_CFG.get_host_item(
            "use login shell", host, user)
    if ssh_login_shell:
        # A login shell will always source /etc/profile and the user's bash
        # profile file. To avoid having to quote the entire remote command
        # it is passed as arguments to bash.
        command += ["bash", "--login", "-c", "'exec $0 \"$@\"'"]

    cmd = "%s %s" % (
        GLOBAL_CFG.get_host_item("cylc executable", host, user), cmd)

    command += [cmd]
    if cylc.flags.debug:
        msg = ' '.join(quote(c) for c in command)
        print >> sys.stderr, msg
    out = None
    if capture:
        proc = Popen(command, stdout=PIPE, stdin=open(os.devnull))
        out = proc.communicate()[0]
    else:
        proc = Popen(command, stdin=open(os.devnull))
    res = proc.wait()
    if WIFSIGNALED(res):
        print >> sys.stderr, (
            "ERROR: remote command terminated by signal %d" % res)
    elif res:
        print >> sys.stderr, "ERROR: remote command failed %d" % res
    return out


def remrun(env=None, path=None, dry_run=False, forward_x11=False):
    """Short for RemoteRunner().execute(...)"""
    return RemoteRunner().execute(env, path, dry_run, forward_x11)


class RemoteRunner(object):
    """Run current command on a remote host.

    If owner or host differ from username and localhost, strip the
    remote options from the commandline and reinvoke the command on the
    remote host by non-interactive ssh, then exit; else do nothing.

    To ensure that users are aware of remote re-invocation info is always
    printed, but to stderr so as not to interfere with results.

    """

    def __init__(self, argv=None):
        self.owner = None
        self.host = None
        self.ssh_login_shell = None
        self.argv = argv or sys.argv

        cylc.flags.verbose = '-v' in self.argv or '--verbose' in self.argv

        argv = self.argv[1:]
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

        if self.owner is None and self.host is None:
            self.is_remote = False
        else:
            from cylc.hostuserutil import is_remote
            self.is_remote = is_remote(self.host, self.owner)

    def execute(self, env=None, path=None, dry_run=False, forward_x11=False):
        """Execute command on remote host.

        Returns False if remote re-invocation is not needed, True if it is
        needed and executes successfully otherwise aborts.

        """
        if not self.is_remote:
            return False

        from cylc.version import CYLC_VERSION

        name = os.path.basename(self.argv[0])[5:]  # /path/to/cylc-foo => foo

        # Build the remote command
        command = shlex.split(glbl_cfg().get_host_item(
            "ssh command", self.host, self.owner))
        if forward_x11:
            command.append("-Y")

        user_at_host = ""
        if self.owner:
            user_at_host = self.owner + "@"
        if self.host:
            user_at_host += self.host
        else:
            user_at_host += "localhost"
        command.append(user_at_host)

        # Use bash -l?
        ssh_login_shell = self.ssh_login_shell
        if ssh_login_shell is None:
            ssh_login_shell = glbl_cfg().get_host_item(
                "use login shell", self.host, self.owner)

        # Pass cylc version through.
        command += ["env", "CYLC_VERSION=%s" % CYLC_VERSION]

        if ssh_login_shell:
            # A login shell will always source /etc/profile and the user's bash
            # profile file. To avoid having to quote the entire remote command
            # it is passed as arguments to the bash script.
            command += ["bash", "--login", "-c", "'exec $0 \"$@\"'"]

        # "cylc" on the remote host
        if path:
            command.append(os.sep.join(path + ["cylc"]))
        else:
            command.append(glbl_cfg().get_host_item(
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

        if cylc.flags.debug:
            print >> sys.stderr, ' '.join(quote(c) for c in command)

        if dry_run:
            return command

        try:
            popen = Popen(command)
        except OSError as exc:
            sys.exit("ERROR: remote command invocation failed %s" % str(exc))

        res = popen.wait()
        if WIFSIGNALED(res):
            sys.exit("ERROR: remote command terminated by signal %d" % res)
        elif res:
            sys.exit("ERROR: remote command failed %d" % res)
        else:
            return True
