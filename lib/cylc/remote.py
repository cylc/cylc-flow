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
import sys
import shlex
from pipes import quote
from posix import WIFSIGNALED

# CODACY ISSUE:
#   Consider possible security implications associated with Popen module.
# REASON IGNORED:
#   Subprocess is needed, but we use it with security in mind.
from subprocess import Popen, PIPE

import cylc.flags
from cylc.cfgspec.glbl_cfg import glbl_cfg
from cylc.version import CYLC_VERSION


def remote_cylc_cmd(cmd, user=None, host=None, capture=False,
                    ssh_login_shell=None, ssh_cylc=None, stdin=None):
    """Run a given cylc command on another account and/or host.

    Arguments:
        cmd (list): command to run remotely.
        user (string): user ID for the remote login.
        host (string): remote host name. Use 'localhost' if not specified.
        capture (boolean):
            If True, set stdout=PIPE and return the Popen object.
        ssh_login_shell (boolean):
            If True, launch remote command with `bash -l -c 'exec "$0" "$@"'`.
        ssh_cylc (string):
            Location of the remote cylc executable.
        stdin (file):
            If specified, it should be a readable file object.
            If None, it will be set to `open(os.devnull)` and the `-n` option
            will be added to the SSH command line.

    Return:
        If capture=True, return the Popen object if created successfully.
        Otherwise, return the exit code of the remote command.
    """
    if host is None:
        host = "localhost"
    if user is None:
        user_at_host = host
    else:
        user_at_host = '%s@%s' % (user, host)

    # Build the remote command
    command = shlex.split(
        str(glbl_cfg().get_host_item('ssh command', host, user)))
    if stdin is None:
        command.append('-n')
        stdin = open(os.devnull)
    command.append(user_at_host)

    # Pass cylc version through.
    command += ['env', r'CYLC_VERSION=%s' % CYLC_VERSION]

    if ssh_login_shell is None:
        ssh_login_shell = glbl_cfg().get_host_item(
            'use login shell', host, user)
    if ssh_login_shell:
        # A login shell will always source /etc/profile and the user's bash
        # profile file. To avoid having to quote the entire remote command
        # it is passed as arguments to bash.
        command += ['bash', '--login', '-c', quote(r'exec "$0" "$@"')]
    if ssh_cylc is None:
        ssh_cylc = glbl_cfg().get_host_item('cylc executable', host, user)
        if not ssh_cylc.endswith('cylc'):
            raise ValueError(
                r'ERROR: bad cylc executable in global config: %s' % ssh_cylc)
    command.append(ssh_cylc)
    command += cmd
    if cylc.flags.debug:
        sys.stderr.write('%s\n' % command)
    if capture:
        stdout = PIPE
    else:
        stdout = None
    # CODACY ISSUE:
    #   subprocess call - check for execution of untrusted input.
    # REASON IGNORED:
    #   The command is read from the site/user global config file, but we check
    #   above that it ends in 'cylc', and in any case the user could execute
    #   any such command directly via ssh.
    proc = Popen(command, stdout=stdout, stdin=stdin)
    if capture:
        return proc
    else:
        res = proc.wait()
        if WIFSIGNALED(res):
            sys.stderr.write(
                'ERROR: remote command terminated by signal %d\n' % res)
        elif res:
            sys.stderr.write('ERROR: remote command failed %d\n' % res)
        return res


def remrun(dry_run=False, forward_x11=False):
    """Short for RemoteRunner().execute(...)"""
    return RemoteRunner().execute(dry_run, forward_x11)


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
        self.ssh_cylc = None
        self.argv = argv or sys.argv

        cylc.flags.verbose = '-v' in self.argv or '--verbose' in self.argv

        argv = self.argv[1:]
        self.args = []
        # detect and replace host and owner options
        while argv:
            arg = argv.pop(0)
            if arg.startswith('--user='):
                self.owner = arg.replace('--user=', '')
            elif arg.startswith('--host='):
                self.host = arg.replace('--host=', '')
            elif arg.startswith('--ssh-cylc='):
                self.ssh_cylc = arg.replace('--ssh-cylc=', '')
            elif arg == '--login':
                self.ssh_login_shell = True
            elif arg == '--no-login':
                self.ssh_login_shell = False
            else:
                self.args.append(arg)

        if self.owner is None and self.host is None:
            self.is_remote = False
        else:
            from cylc.hostuserutil import is_remote
            self.is_remote = is_remote(self.host, self.owner)

    def execute(self, dry_run=False, forward_x11=False):
        """Execute command on remote host.

        Returns False if remote re-invocation is not needed, True if it is
        needed and executes successfully otherwise aborts.

        """
        if not self.is_remote:
            return False

        # Build the remote command
        command = shlex.split(glbl_cfg().get_host_item(
            'ssh command', self.host, self.owner))
        if forward_x11:
            command.append('-Y')

        user_at_host = ''
        if self.owner:
            user_at_host = self.owner + '@'
        if self.host:
            user_at_host += self.host
        else:
            user_at_host += 'localhost'
        command.append(user_at_host)

        # Pass cylc version through.
        command += ['env', quote(r'CYLC_VERSION=%s' % CYLC_VERSION)]
        if 'CYLC_UTC' in os.environ:
            command.append(quote(r'CYLC_UTC=True'))
            command.append(quote(r'TZ=UTC'))

        # Use bash -l?
        ssh_login_shell = self.ssh_login_shell
        if ssh_login_shell is None:
            ssh_login_shell = glbl_cfg().get_host_item(
                'use login shell', self.host, self.owner)
        if ssh_login_shell:
            # A login shell will always source /etc/profile and the user's bash
            # profile file. To avoid having to quote the entire remote command
            # it is passed as arguments to the bash script.
            command += ['bash', '--login', '-c', quote(r'exec "$0" "$@"')]

        # 'cylc' on the remote host
        if self.ssh_cylc:
            command.append(self.ssh_cylc)
        else:
            command.append(glbl_cfg().get_host_item(
                'cylc executable', self.host, self.owner))

        # /path/to/cylc-foo => foo
        command.append(os.path.basename(self.argv[0])[5:])

        if cylc.flags.verbose or os.getenv('CYLC_VERBOSE') in ["True", "true"]:
            command.append(r'--verbose')
        if cylc.flags.debug or os.getenv('CYLC_DEBUG') in ["True", "true"]:
            command.append(r'--debug')

        for arg in self.args:
            command.append(quote(arg))
            # above: args quoted to avoid interpretation by the shell,
            # e.g. for match patterns such as '.*' on the command line.

        if cylc.flags.debug:
            sys.stderr.write(' '.join(quote(c) for c in command) + '\n')

        if dry_run:
            return command

        try:
            popen = Popen(command)
        except OSError as exc:
            sys.exit(r'ERROR: remote command invocation failed %s' % exc)

        res = popen.wait()
        if WIFSIGNALED(res):
            sys.exit(r'ERROR: remote command terminated by signal %d' % res)
        elif res:
            sys.exit(r'ERROR: remote command failed %d' % res)
        else:
            return True
