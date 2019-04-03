#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
from shlex import quote
from posix import WIFSIGNALED
import shlex
import signal
# CODACY ISSUE:
#   Consider possible security implications associated with Popen module.
# REASON IGNORED:
#   Subprocess is needed, but we use it with security in mind.
from subprocess import Popen, PIPE
import sys
from time import sleep

from cylc import LOG
from cylc.cfgspec.glbl_cfg import glbl_cfg
import cylc.flags
from cylc.hostuserutil import is_remote
from cylc import __version__ as CYLC_VERSION


def get_proc_ancestors():
    """Return list of parent PIDs back to init."""
    pid = os.getpid()
    ancestors = []
    while True:
        p = Popen(["ps", "-p", str(pid), "-oppid="], stdout=PIPE, stderr=PIPE)
        ppid = p.communicate()[0].decode().strip()
        if not ppid:
            return ancestors
        ancestors.append(ppid)
        pid = ppid


def watch_and_kill(proc):
    """Kill proc if my PPID (etc.) changed - e.g. ssh connection dropped."""
    gpa = get_proc_ancestors()
    while True:
        sleep(0.5)
        if proc.poll() is not None:
            break
        if get_proc_ancestors() != gpa:
            sleep(1)
            os.kill(proc.pid, signal.SIGTERM)
            break


def run_cmd(command, stdin=None, capture_process=False, capture_status=False,
            manage=False):
    """Run a given cylc command on another account and/or host.

    Arguments:
        command (list):
            command inclusive of all opts and args required to run via ssh.
        stdin (file):
            If specified, it should be a readable file object.
            If None, `open(os.devnull)` is set if output is to be captured.
        capture_process (boolean):
            If True, set stdout=PIPE and return the Popen object.
        capture_status (boolean):
            If True, and the remote command is unsuccessful, return the
            associated exit code instead of exiting with an error.
        manage (boolean):
            If True, watch ancestor processes and kill command if they change
            (e.g. kill tail-follow commands when parent ssh connection dies).

    Return:
        * If capture_process=True, the Popen object if created successfully.
        * Else True if the remote command is executed successfully, or
          if unsuccessful and capture_status=True the remote command exit code.
        * Otherwise exit with an error message.
    """
    # CODACY ISSUE:
    #   subprocess call - check for execution of untrusted input.
    # REASON IGNORED:
    #   The command is read from the site/user global config file, but we check
    #   above that it ends in 'cylc', and in any case the user could execute
    #   any such command directly via ssh.
    stdout = None
    stderr = None
    if capture_process:
        stdout = PIPE
        stderr = PIPE
        if stdin is None:
            stdin = open(os.devnull)
    if isinstance(stdin, str):
        stdin = stdin.encode()

    try:
        proc = Popen(command, stdin=stdin, stdout=stdout, stderr=stderr)
    except OSError as exc:
        sys.exit(r'ERROR: %s: %s' % (
            exc, ' '.join(quote(item) for item in command)))

    if capture_process:
        return proc
    else:
        if manage:
            watch_and_kill(proc)
        res = proc.wait()
        if WIFSIGNALED(res):
            sys.exit(r'ERROR: command terminated by signal %d: %s' % (
                res, ' '.join(quote(item) for item in command)))
        elif res and capture_status:
            return res
        elif res:
            sys.exit(r'ERROR: command returns %d: %s' % (
                res, ' '.join(quote(item) for item in command)))
        else:
            return True


def construct_ssh_cmd(raw_cmd, user=None, host=None, forward_x11=False,
                      stdin=False, ssh_login_shell=None, ssh_cylc=None,
                      set_UTC=False, allow_flag_opts=False):
    """Append a bare command with further options required to run via ssh.

    Arguments:
        raw_cmd (list): primitive command to run remotely.
        user (string): user ID for the remote login.
        host (string): remote host name. Use 'localhost' if not specified.
        forward_x11 (boolean):
            If True, use 'ssh -Y' to enable X11 forwarding, else just 'ssh'.
        stdin:
            If None, the `-n` option will be added to the SSH command line.
        ssh_login_shell (boolean):
            If True, launch remote command with `bash -l -c 'exec "$0" "$@"'`.
        ssh_cylc (string):
            Location of the remote cylc executable.
        set_UTC (boolean):
            If True, check UTC mode and specify if set to True (non-default).
        allow_flag_opts (boolean):
            If True, check CYLC_DEBUG and CYLC_VERBOSE and if non-default,
            specify debug and/or verbosity as options to the 'raw cmd'.

    Return:
        A list containing a chosen command including all arguments and options
        necessary to directly execute the bare command on a given host via ssh.
    """
    command = shlex.split(glbl_cfg().get_host_item('ssh command', host, user))

    if forward_x11:
        command.append('-Y')
    if stdin is None:
        command.append('-n')

    user_at_host = ''
    if user:
        user_at_host = user + '@'
    if host:
        user_at_host += host
    else:
        user_at_host += 'localhost'
    command.append(user_at_host)

    # Pass CYLC_VERSION and optionally, CYLC_CONF_PATH & CYLC_UTC through.
    command += ['env', quote(r'CYLC_VERSION=%s' % CYLC_VERSION)]
    try:
        command.append(
            quote(r'CYLC_CONF_PATH=%s' % os.environ['CYLC_CONF_PATH']))
    except KeyError:
        pass
    if set_UTC and os.getenv('CYLC_UTC') in ["True", "true"]:
        command.append(quote(r'CYLC_UTC=True'))
        command.append(quote(r'TZ=UTC'))

    # Use bash -l?
    if ssh_login_shell is None:
        ssh_login_shell = glbl_cfg().get_host_item(
            'use login shell', host, user)
    if ssh_login_shell:
        # A login shell will always source /etc/profile and the user's bash
        # profile file. To avoid having to quote the entire remote command
        # it is passed as arguments to the bash script.
        command += ['bash', '--login', '-c', quote(r'exec "$0" "$@"')]

    # 'cylc' on the remote host
    if ssh_cylc:
        command.append(ssh_cylc)
    else:
        ssh_cylc = glbl_cfg().get_host_item('cylc executable', host, user)
        if ssh_cylc.endswith('cylc'):
            command.append(ssh_cylc)
        else:
            # TODO - raise appropriate exception
            raise ValueError(
                r'ERROR: bad cylc executable in global config: %s' % ssh_cylc)

    # Insert core raw command after ssh, but before its own, command options.
    command += raw_cmd

    if allow_flag_opts:
        if (cylc.flags.verbose or os.getenv('CYLC_VERBOSE') in
                ["True", "true"]):
            command.append(r'--verbose')
        if cylc.flags.debug or os.getenv('CYLC_DEBUG') in ["True", "true"]:
            command.append(r'--debug')
    if LOG.handlers:
        LOG.debug("$ %s", ' '.join(quote(c) for c in command))
    elif cylc.flags.debug:
        sys.stderr.write("$ %s\n" % ' '.join(quote(c) for c in command))

    return command


def remote_cylc_cmd(
        cmd, user=None, host=None, stdin=None, ssh_login_shell=None,
        ssh_cylc=None, capture_process=False, manage=False):
    """Run a given cylc command on another account and/or host.

    Arguments:
    Args are directly inputted to one of two functions; see those docstrings:
            * See 'construct_ssh_cmd()' docstring:
                * cmd (--> raw_cmd);
                * user;
                * host;
                * stdin;
                * ssh_login_shell;
                * ssh_cylc.
            * See 'run_cmd()' docstring:
                * stdin [see also above]
                * capture (--> capture_process);
                * manage.

    Return:
        If capture_process=True, return the Popen object if created
        successfully. Otherwise, return the exit code of the remote command.
    """
    return run_cmd(
        construct_ssh_cmd(
            cmd, user=user, host=host, stdin=stdin,
            ssh_login_shell=ssh_login_shell, ssh_cylc=ssh_cylc),
        stdin=stdin, capture_process=capture_process,
        capture_status=True, manage=manage)


def remrun(dry_run=False, forward_x11=False, abort_if=None,
           set_rel_local=False):
    """Short for RemoteRunner().execute(...)"""
    return RemoteRunner().execute(
        dry_run, forward_x11, abort_if, set_rel_local)


class RemoteRunner(object):
    """Run current command on a remote host.

    If user/owner or host differ from username and localhost, strip the
    remote options from the commandline and reinvoke the command on the
    remote host by non-interactive ssh, then exit; else do nothing.

    To ensure that users are aware of remote re-invocation info is always
    printed, but to stderr so as not to interfere with results.
    """
    OPT_ARG_OPTS = ('--user', '--host', '--ssh-cylc')

    def __init__(self, argv=None):
        self.user = None  # i.e. owner; name it user for consistency with CLI
        self.host = None
        self.ssh_login_shell = None
        self.ssh_cylc = None
        self.argv = argv or sys.argv

        cylc.flags.verbose = '-v' in self.argv or '--verbose' in self.argv

        # Detect and replace host and user options
        argv = self.argv[1:]

        self.args = []
        while argv:
            arg = argv.pop(0)
            if arg.startswith(tuple([opt + '=' for opt in self.OPT_ARG_OPTS])):
                # e.g. if arg is '--host=HOST' here set self.host to HOST
                opt_with_dashes, opt_arg = arg.split('=', 1)
                setattr(self, opt_with_dashes.strip('--'), opt_arg)
            elif arg in self.OPT_ARG_OPTS:  # if opt arg provided after a space
                # e.g. if arg is '--host' set self.host to next element in argv
                setattr(self, arg.strip('--'), argv.pop(0))
            elif arg == '--login':
                self.ssh_login_shell = True
            elif arg == '--no-login':
                self.ssh_login_shell = False
            else:
                self.args.append(arg)

        if self.user is None and self.host is None:
            self.is_remote = False
        else:
            self.is_remote = is_remote(self.host, self.user)

    def execute(self, dry_run=False, forward_x11=False, abort_if=None,
                set_rel_local=False):
        """Execute command on remote host.

        Returns False if remote re-invocation is not needed, True if it is
        needed and executes successfully otherwise aborts.
        """
        if not self.is_remote:
            return False

        if abort_if is not None and abort_if in sys.argv:
            sys.exit(
                "ERROR: option '%s' not available for remote run" % abort_if)

        cmd = [os.path.basename(self.argv[0])[5:]]  # /path/to/cylc-foo => foo
        for arg in self.args:
            cmd.append(quote(arg))
            # above: args quoted to avoid interpretation by the shell,
            # e.g. for match patterns such as '.*' on the command line.

        if set_rel_local:
            # State as relative localhost to prevent recursive host selection.
            cmd.append("--host=localhost")
        command = construct_ssh_cmd(
            cmd, user=self.user, host=self.host, forward_x11=forward_x11,
            ssh_login_shell=self.ssh_login_shell, ssh_cylc=self.ssh_cylc,
            set_UTC=True, allow_flag_opts=False)

        if dry_run:
            return command
        else:
            return run_cmd(command)
