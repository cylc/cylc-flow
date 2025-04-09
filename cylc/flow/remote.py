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
from typing import Any, Dict, List, Tuple

import cylc.flow.flags
from cylc.flow import __version__ as CYLC_VERSION, LOG
from cylc.flow.log_level import verbosity_to_opts
from cylc.flow.platforms import get_platform, get_host_from_platform
from cylc.flow.util import format_cmd


def get_proc_ancestors():
    """Return list of parent PIDs back to init."""
    pid = os.getpid()
    ancestors = []
    while True:
        p = Popen(  # nosec
            ["ps", "-p", str(pid), "-oppid="],
            stdout=PIPE,
            stderr=PIPE,
            text=True
        )
        # * there is no untrusted output
        ppid = p.communicate()[0].strip()
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
    manage=False,
    text=True,
):
    """Run a given cylc command on another host.

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
        text (boolean):
            If True, use string mode instead of bytes for communicating
            with subprocess.

    Return:
        * If capture_process=True, the Popen[str] object if created
          successfully.
        * Else True if the remote command is executed successfully, or
          if unsuccessful and capture_status=True the remote command exit code.
        * Otherwise exit with an error message.

    Exits with code 1 in the event of certain command errors.

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
        LOG.debug(f'running command:\n$ {format_cmd(command)}')
        proc = Popen(  # nosec
            command,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            text=text
        )
        # * this see CODACY ISSUE comment above
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


DEFAULT_RSYNC_OPTS = [
    '-a',
    '--checksum',
    '--out-format=%o %n%L',
    '--no-t'
]
# %o: the operation (send or del.)
# %n: filename
# %L: "-> symlink_target" if applicable

DEFAULT_INCLUDES = [
    '/ana/***',  # Rose ana analysis modules
    '/app/***',  # Rose applications
    '/bin/***',  # Cylc bin directory (added to PATH)
    '/etc/***',  # Miscellaneous resources
    '/lib/***',  # Cylc lib directory (lib/python added to PYTHONPATH for
                 # workflow config)
]


def construct_rsync_over_ssh_cmd(
    src_path: str, dst_path: str, platform: Dict[str, Any],
    rsync_includes=None, bad_hosts=None
) -> Tuple[List[str], str]:
    """Constructs the rsync command used for remote file installation.

    Includes as standard the directories: app, bin, etc, lib; and the server
    key, used for ZMQ authentication.

    Args:
        src_path: source path
        dst_path: path of target
        platform: contains info relating to platform
        rsync_includes: files and directories to be included in the rsync

    Raises:
        NoHostsError:
            If there are no hosts available for the requested platform.

    Developer Warning:
        The Cylc Subprocess Pool method ``rsync_255_fail`` relies on
        ``rsync_cmd[0] == 'rsync'``. Please check that changes to this function
        do not break ``rsync_255_fail``.
    """
    dst_path = dst_path.replace('$HOME/', '')
    dst_host = get_host_from_platform(platform, bad_hosts=bad_hosts)
    ssh_cmd = platform['ssh command']
    command = platform['rsync command']
    rsync_cmd = shlex.split(command)
    rsync_options = [
        "--delete",
        "--rsh=" + ssh_cmd,
        "--include=/.service/",
        "--include=/.service/server.key"
    ] + DEFAULT_RSYNC_OPTS
    # Note to future devs - be wary of changing the order of the following
    # rsync options, rsync is very particular about order of in/ex-cludes.
    rsync_cmd.extend(rsync_options)
    for exclude in ['log', 'share', 'work']:
        rsync_cmd.append(f"--exclude={exclude}")
    for include in DEFAULT_INCLUDES:
        rsync_cmd.append(f"--include={include}")
    for include in get_includes_to_rsync(rsync_includes):
        rsync_cmd.append(f"--include={include}")
    # The following excludes are required in case these are added to the
    rsync_cmd.append("--exclude=*")  # exclude everything else
    rsync_cmd.append(f"{src_path}/")
    rsync_cmd.append(f"{dst_host}:{dst_path}/")
    return rsync_cmd, dst_host


def construct_ssh_cmd(
    raw_cmd,
    platform,
    host,
    forward_x11=False,
    stdin=False,
    set_UTC=False,
    set_verbosity=False,
    timeout=None,
):
    """Build an SSH command for execution on a remote platform hosts.

    Arguments:
        raw_cmd (list):
            primitive command to run remotely.
        platform (dict):
            The Cylc job "platform" to run the command on. This is used
            to determine the settings used e.g. "ssh command".
        host (string):
            remote host name. Use 'localhost' if not specified.
        forward_x11 (boolean):
            If True, use 'ssh -Y' to enable X11 forwarding, else just 'ssh'.
        stdin:
            If None, the `-n` option will be added to the SSH command line.
        set_UTC (boolean):
            If True, check UTC mode and specify if set to True (non-default).
        set_verbosity (boolean):
            If True apply -q, -v opts to match cylc.flow.flags.verbosity.
        timeout (str):
            String for bash timeout command.

    Returns:
        list - A list containing a chosen command including all arguments and
        options necessary to directly execute the bare command on a given host
        via ssh.

    """
    command = shlex.split(platform['ssh command'])

    if forward_x11:
        command.append('-Y')
    if stdin is None:
        command.append('-n')

    command.append(host)

    # Pass CYLC_VERSION and optionally, CYLC_CONF_PATH & CYLC_UTC through.
    command += ['env', quote(r'CYLC_VERSION=%s' % CYLC_VERSION)]

    for envvar in [
        'CYLC_CONF_PATH',
        'CYLC_COVERAGE',
        'CLIENT_COMMS_METH',
        'CYLC_ENV_NAME',
        *platform['ssh forward environment variables'],
    ]:
        if envvar in os.environ:
            command.append(
                quote(f'{envvar}={os.environ[envvar]}')
            )

    if set_UTC and os.getenv('CYLC_UTC') in ["True", "true"]:
        command.append(quote(r'CYLC_UTC=True'))
        command.append(quote(r'TZ=UTC'))

    # Use bash -l?
    ssh_login_shell = platform['use login shell']
    if ssh_login_shell:
        # A login shell will always source /etc/profile and the user's bash
        # profile file. To avoid having to quote the entire remote command
        # it is passed as arguments to the bash script.
        command += ['bash', '--login', '-c', quote(r'exec "$0" "$@"')]

    if timeout:
        command += ['timeout', timeout]

    # 'cylc' on the remote host
    remote_cylc_path = platform['cylc path']
    if remote_cylc_path:
        cylc_cmd = str(Path(remote_cylc_path) / 'cylc')
    else:
        cylc_cmd = 'cylc'
    command.append(cylc_cmd)

    # Insert core raw command after ssh, but before its own, command options.
    command += raw_cmd

    if set_verbosity:
        command.extend(verbosity_to_opts(cylc.flow.flags.verbosity))

    return command


def construct_cylc_server_ssh_cmd(
    cmd,
    host,
    **kwargs,
):
    """Convenience function to building SSH commands for remote Cylc servers.

    Build an SSH command that connects to the specified host using the
    localhost platform config.

    * To run commands on job platforms use construct_ssh_cmd.
    * Use this interface to connect to:
      * Cylc servers (i.e. `[scheduler][run hosts]available`).
      * The host `cylc play` was run on, use this interface.

    This assumes the host you are connecting to shares the $HOME filesystem
    with the localhost platform.

    For arguments and returns see construct_ssh_cmd.
    """
    return construct_ssh_cmd(
        cmd,
        get_platform(),  # use localhost settings
        host,
        **kwargs,
    )


def remote_cylc_cmd(
    cmd,
    platform,
    bad_hosts=None,
    host=None,
    stdin=None,
    stdin_str=None,
    ssh_login_shell=None,
    ssh_cmd=None,
    remote_cylc_path=None,
    capture_process=False,
    manage=False,
    text=True,
):
    """Execute a Cylc command on a remote platform.

    Uses the provided platform configuration to construct the command.

    For arguments and returns see construct_ssh_cmd and run_cmd.

    Raises:
        NoHostsError: If the platform is not contactable.

    Exits with code 1 in the event of certain command errors.

    """
    if not host:
        # no host selected => perform host selection from platform config
        host = get_host_from_platform(platform, bad_hosts=bad_hosts)

    return run_cmd(
        construct_ssh_cmd(
            cmd,
            platform,
            host=host,
            stdin=True if stdin_str else stdin,
        ),
        stdin=stdin,
        stdin_str=stdin_str,
        capture_process=capture_process,
        capture_status=True,
        manage=manage,
        text=text
    )


def cylc_server_cmd(cmd, host=None, **kwargs):
    """Convenience function for running commands on remote Cylc servers.

    Executes a Cylc command on the specified host using localhost platform
    config.

    * To run commands on job platforms use remote_cylc_cmd.
    * Use this interface to run commands on:
      * Cylc servers (i.e. `[scheduler][run hosts]available`).
      * The host `cylc play` was run on.

    Runs a command via SSH using the configuration for the localhost platform.
    This assumes the host you are connecting to shares the $HOME filesystem
    with the localhost platform.

    For arguments and returns see construct_ssh_cmd and run_cmd.

    Raises:
        NoHostsError: If the platform is not contactable.

    Exits with code 1 in the event of certain command errors.

    """
    return remote_cylc_cmd(
        cmd,
        get_platform(),  # use localhost settings
        host=host,
        **kwargs,
    )
