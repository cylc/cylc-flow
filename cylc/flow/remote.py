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
"""Run command on a remote, (i.e. a remote [user@]host)."""

import os
from shlex import quote
from pathlib import Path
from posix import WIFSIGNALED
import shlex
import signal
# CODACY ISSUE:
#   Consider possible security implications associated with Popen module.
# REASON IGNORED:
#   Subprocess is needed, but we use it with security in mind.
from subprocess import Popen, PIPE, DEVNULL
import sys
from time import sleep

import cylc.flow.flags
from cylc.flow import __version__ as CYLC_VERSION
from cylc.flow.platforms import get_platform, get_host_from_platform


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


def run_cmd(
        command,
        stdin=None,
        stdin_str=None,
        capture_process=False,
        capture_status=False,
        manage=False
):
    """Run a given cylc command on another account and/or host.

    Arguments:
        command (list):
            command inclusive of all opts and args required to run via ssh.
        stdin (file):
            If specified, it should be a readable file object.
            If None, DEVNULL is set if output is to be captured.
        stdin_str (str):
            A string to be passed to stdin.
            Implies `stdin=PIPE`.
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
            stdin = DEVNULL
    if stdin_str:
        read, write = os.pipe()
        os.write(write, stdin_str.encode())
        os.close(write)
        stdin = read

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


def get_includes_to_rsync(rsync_includes=None):
    """Returns list of configured dirs/files for remote file installation."""

    configured_includes = []

    if rsync_includes is not None:
        for include in rsync_includes:
            if include.endswith("/"):  # item is a directory
                configured_includes.append("/" + include + "***")
            else:  # item is a file
                configured_includes.append("/" + include)

    return configured_includes


def construct_rsync_over_ssh_cmd(
        src_path, dst_path, platform, rsync_includes=None):
    """Constructs the rsync command used for remote file installation.

    Includes as standard the directories: app, bin, etc, lib; and the server
    key, used for ZMQ authentication.

    Args:
        src_path(string): source path
        dst_path(string): path of target
        platform(dict)): contains info relating to platform
        rsync_includes(list): files and directories to be included in the rsync

    """
    dst_host = get_host_from_platform(platform)
    rsync_cmd = ["rsync"]
    ssh_cmd = platform['ssh command']
    rsync_options = [
        "-v",
        "--perms",
        "--recursive",
        "--links",
        "--checksum",
        "--delete",
        "--rsh=" + ssh_cmd,
        "--include=/.service/",
        "--include=/.service/server.key"
    ]
    rsync_cmd.extend(rsync_options)
    # Note to future devs - be wary of changing the order of the following
    # rsync options, rsync is very particular about order of in/ex-cludes.

    for exclude in ['log', 'share', 'work']:
        rsync_cmd.append(f"--exclude={exclude}")
    default_includes = [
        '/app/***',
        '/bin/***',
        '/etc/***',
        '/lib/***']
    for include in default_includes:
        rsync_cmd.append(f"--include={include}")
    for include in get_includes_to_rsync(rsync_includes):
        rsync_cmd.append(f"--include={include}")
    # The following excludes are required in case these are added to the
    rsync_cmd.append("--exclude=*")  # exclude everything else
    rsync_cmd.append(f"{src_path}/")
    rsync_cmd.append(f"{dst_host}:{dst_path}/")
    return rsync_cmd


def construct_ssh_cmd(raw_cmd, platform, **kwargs):
    """Build an SSH command for execution on a remote platform.

    Constructs the SSH command according to the platform configuration.

    See _construct_ssh_cmd for argument documentation.
    """
    return _construct_ssh_cmd(
        raw_cmd,
        host=get_host_from_platform(platform),
        ssh_cmd=platform['ssh command'],
        remote_cylc_path=platform['cylc path'],
        ssh_login_shell=platform['use login shell'],
        **kwargs
    )


def _construct_ssh_cmd(
        raw_cmd,
        host=None,
        forward_x11=False,
        stdin=False,
        ssh_cmd=None,
        ssh_login_shell=None,
        remote_cylc_path=None,
        set_UTC=False,
        allow_flag_opts=False,
        timeout=None
):
    """Build an SSH command for execution on a remote platform hosts.

    Arguments:
        raw_cmd (list):
            primitive command to run remotely.
        host (string):
            remote host name. Use 'localhost' if not specified.
        forward_x11 (boolean):
            If True, use 'ssh -Y' to enable X11 forwarding, else just 'ssh'.
        stdin:
            If None, the `-n` option will be added to the SSH command line.
        ssh_cmd (string):
            ssh command to use: If unset defaults to localhost ssh cmd.
        ssh_login_shell (boolean):
            If True, launch remote command with `bash -l -c 'exec "$0" "$@"'`.
        remote_cylc_path (string):
            Path containing the `cylc` executable.
            This is required if the remote executable is not in $PATH.
        set_UTC (boolean):
            If True, check UTC mode and specify if set to True (non-default).
        allow_flag_opts (boolean):
            If True, check CYLC_DEBUG and CYLC_VERBOSE and if non-default,
            specify debug and/or verbosity as options to the 'raw cmd'.
        timeout (str):
            String for bash timeout command.

    Return:
        list - A list containing a chosen command including all arguments and
        options necessary to directly execute the bare command on a given host
        via ssh.
    """
    # If ssh cmd isn't given use the default from localhost settings.
    if ssh_cmd is None:
        command = shlex.split(get_platform()['ssh command'])
    else:
        command = shlex.split(ssh_cmd)

    if forward_x11:
        command.append('-Y')
    if stdin is None:
        command.append('-n')

    user_at_host = ''
    if host:
        user_at_host += host
    else:
        user_at_host += 'localhost'
    command.append(user_at_host)

    # Pass CYLC_VERSION and optionally, CYLC_CONF_PATH & CYLC_UTC through.
    command += ['env', quote(r'CYLC_VERSION=%s' % CYLC_VERSION)]

    for envvar in [
        'CYLC_CONF_PATH',
        'CYLC_COVERAGE',
        'CLIENT_COMMS_METH'
    ]:
        if envvar in os.environ:
            command.append(
                quote(f'{envvar}={os.environ[envvar]}')
            )

    if set_UTC and os.getenv('CYLC_UTC') in ["True", "true"]:
        command.append(quote(r'CYLC_UTC=True'))
        command.append(quote(r'TZ=UTC'))

    # Use bash -l?
    if ssh_login_shell is None:
        ssh_login_shell = get_platform()['use login shell']
    if ssh_login_shell:
        # A login shell will always source /etc/profile and the user's bash
        # profile file. To avoid having to quote the entire remote command
        # it is passed as arguments to the bash script.
        command += ['bash', '--login', '-c', quote(r'exec "$0" "$@"')]

    if timeout:
        command += ['timeout', timeout]

    # 'cylc' on the remote host
    if not remote_cylc_path:
        remote_cylc_path = get_platform()['cylc path']

    if remote_cylc_path:
        cylc_cmd = str(Path(remote_cylc_path) / 'cylc')
    else:
        cylc_cmd = 'cylc'

    command.append(cylc_cmd)

    # Insert core raw command after ssh, but before its own, command options.
    command += raw_cmd

    if allow_flag_opts:
        if (cylc.flow.flags.verbose or os.getenv('CYLC_VERBOSE') in
                ["True", "true"]):
            command.append(r'--verbose')
        if (cylc.flow.flags.debug or os.getenv('CYLC_DEBUG') in
                ["True", "true"]):
            command.append(r'--debug')

    return command


def remote_cylc_cmd(cmd, platform, **kwargs):
    """Execute a Cylc command on a remote platform.

    Uses the platform configuration to construct the command.

    See _construct_ssh_cmd for argument documentation.
    """
    return _remote_cylc_cmd(
        cmd,
        host=get_host_from_platform(platform),
        ssh_cmd=platform['ssh command'],
        remote_cylc_path=platform['cylc path'],
        ssh_login_shell=platform['use login shell'],
        **kwargs
    )


def _remote_cylc_cmd(
        cmd,
        host=None,
        stdin=None,
        stdin_str=None,
        ssh_login_shell=None,
        ssh_cmd=None,
        remote_cylc_path=None,
        capture_process=False,
        manage=False
):
    """Execute a Cylc command on a remote platform.

    See run_cmd and _construct_ssh_cmd for argument documentation.

    Returns:
        subprocess.Popen or int - If capture_process=True, return the Popen
        object if created successfully. Otherwise, return the exit code of the
        remote command.

    """
    return run_cmd(
        _construct_ssh_cmd(
            cmd,
            host=host,
            stdin=True if stdin_str else stdin,
            ssh_login_shell=ssh_login_shell,
            ssh_cmd=ssh_cmd,
            remote_cylc_path=remote_cylc_path
        ),
        stdin=stdin,
        stdin_str=stdin_str,
        capture_process=capture_process,
        capture_status=True,
        manage=manage
    )
