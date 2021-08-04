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
"""Manage task remotes.

This module provides logic to:
- Set up the directory structure on remote job hosts.
  - Copy workflow service files to remote job hosts for communication clients.
  - Clean up of service files on workflow shutdown.
- Implement basic host select functionality.
"""

from contextlib import suppress
import os
from shlex import quote
import re
from subprocess import Popen, PIPE, DEVNULL
import tarfile
from time import time
from typing import Any, Dict, TYPE_CHECKING

from cylc.flow import LOG, RSYNC_LOG
from cylc.flow.exceptions import TaskRemoteMgmtError
import cylc.flow.flags
from cylc.flow.hostuserutil import is_remote_host
from cylc.flow.network.client_factory import CommsMeth
from cylc.flow.pathutil import (
    get_remote_workflow_run_dir,
    get_dirs_to_symlink,
    get_workflow_run_dir)
from cylc.flow.remote import construct_rsync_over_ssh_cmd, construct_ssh_cmd
from cylc.flow.subprocctx import SubProcContext
from cylc.flow.workflow_files import (
    WorkflowFiles,
    KeyInfo,
    KeyOwner,
    KeyType,
    get_workflow_srv_dir,
    get_contact_file)
from cylc.flow.platforms import (
    get_host_from_platform,
    get_localhost_install_target,
    get_random_platform_for_install_target,
    NoHostsError
)

if TYPE_CHECKING:
    from zmq.auth.thread import ThreadAuthenticator

# Remote installation literals
REMOTE_INIT_DONE = 'REMOTE INIT DONE'
REMOTE_INIT_FAILED = 'REMOTE INIT FAILED'
REMOTE_INIT_IN_PROGRESS = 'REMOTE INIT IN PROGRESS'
REMOTE_FILE_INSTALL_DONE = 'REMOTE FILE INSTALL DONE'
REMOTE_FILE_INSTALL_IN_PROGRESS = 'REMOTE FILE INSTALL IN PROGRESS'
REMOTE_FILE_INSTALL_FAILED = 'REMOTE FILE INSTALL FAILED'
REMOTE_INIT_255 = 'REMOTE INIT 255'
REMOTE_FILE_INSTALL_255 = 'REMOTE FILE INSTALL 255'


class TaskRemoteMgr:
    """Manage task job remote initialisation, tidy, selection."""

    def __init__(self, workflow, proc_pool, bad_hosts):
        self.workflow = workflow
        self.proc_pool = proc_pool
        # self.remote_command_map = {command: host|TaskRemoteMgmtError|None}
        self.remote_command_map = {}
        # self.remote_init_map = {(install target): status, ...}
        self.remote_init_map = {}
        self.uuid_str = None
        # This flag is turned on when a host init/select command completes
        self.ready = False
        self.rsync_includes = None
        self.bad_hosts = bad_hosts

    def subshell_eval(self, command, command_pattern, host_check=True):
        """Evaluate a task platform from a subshell string.

        At Cylc 7, from a host string.

        Arguments:
            command (str):
                An explicit host name, a command in back-tick or $(command)
                format, or an environment variable holding a hostname.
            command_pattern (re.Pattern):
                A compiled regex pattern designed to match subshell strings.
            host_check (bool):
                A flag to enable remote testing. If True, and if the command
                is running locally, then it will return 'localhost'.

        Return (str):
            - None if evaluation of command is still taking place.
            - If command is not defined or the evaluated name is equivalent
              to 'localhost', _and_ host_check is set to True then
              'localhost'
            - Otherwise, return the evaluated host name on success.

        Raise TaskRemoteMgmtError on error.

        """
        # BACK COMPAT: references to "host"
        # remove at:
        #     Cylc9
        if not command:
            return 'localhost'

        # Host selection command: $(command) or `command`
        match = command_pattern.match(command)
        if match:
            cmd_str = match.groups()[1]
            if cmd_str in self.remote_command_map:
                # Command recently launched
                value = self.remote_command_map[cmd_str]
                if isinstance(value, TaskRemoteMgmtError):
                    raise value  # command failed
                elif value is None:
                    return  # command not yet ready
                else:
                    command = value  # command succeeded
            else:
                # Command not launched (or already reset)
                self.proc_pool.put_command(
                    SubProcContext(
                        'remote-host-select',
                        ['bash', '-c', cmd_str],
                        env=dict(os.environ)),
                    callback=self._subshell_eval_callback,
                    callback_args=[cmd_str]
                )
                self.remote_command_map[cmd_str] = None
                return self.remote_command_map[cmd_str]

        # Environment variable substitution
        command = os.path.expandvars(command)
        # Remote?
        # TODO - Remove at Cylc 9 as this only makes sense with host logic
        if host_check is True:
            if is_remote_host(command):
                return command
            else:
                return 'localhost'
        else:
            return command

    def subshell_eval_reset(self):
        """Reset remote eval subshell results.

        This is normally called after the results are consumed.
        """
        for key, value in list(self.remote_command_map.copy().items()):
            if value is not None:
                del self.remote_command_map[key]

    def remote_init(
            self, platform: Dict[str, Any], curve_auth: 'ThreadAuthenticator',
            client_pub_key_dir: str) -> None:
        """Initialise a remote host if necessary.

        Call "cylc remote-init" to install workflow items to remote:
            ".service/contact": For TCP task communication
            "python/": if source exists

        Args:
            platform: A dict containing settings relating to platform used in
                this remote installation.
            curve_auth: The ZMQ authenticator.
            client_pub_key_dir: Client public key directory, used by the
                ZMQ authenticator.

        """
        install_target = platform['install target']
        if install_target == get_localhost_install_target():
            self.remote_init_map[install_target] = REMOTE_FILE_INSTALL_DONE
            return

        # Set status of install target to in progress while waiting for remote
        # initialisation to finish
        self.remote_init_map[install_target] = REMOTE_INIT_IN_PROGRESS

        # Determine what items to install
        comms_meth: CommsMeth = CommsMeth(platform['communication method'])
        items = self._remote_init_items(comms_meth)

        # Create a TAR archive with the service files,
        # so they can be sent later via SSH's STDIN to the task remote.
        tmphandle = self.proc_pool.get_temporary_file()
        tarhandle = tarfile.open(fileobj=tmphandle, mode='w')
        for path, arcname in items:
            tarhandle.add(path, arcname=arcname)
        tarhandle.close()
        tmphandle.seek(0)
        # Build the remote-init command to be run over ssh
        cmd = ['remote-init']
        if cylc.flow.flags.verbosity > 1:
            cmd.append('--debug')
        cmd.append(str(install_target))
        cmd.append(get_remote_workflow_run_dir(self.workflow))
        dirs_to_symlink = get_dirs_to_symlink(install_target, self.workflow)
        for key, value in dirs_to_symlink.items():
            if value is not None:
                cmd.append(f"{key}={quote(value)} ")
        # Create the ssh command
        try:
            host = get_host_from_platform(
                platform, bad_hosts=self.bad_hosts
            )
        except NoHostsError:
            LOG.error(TaskRemoteMgmtError(
                TaskRemoteMgmtError.MSG_INIT,
                install_target, ' '.join(
                    quote(item) for item in cmd),
                42, '', ''))
            self.remote_init_map[
                platform['install target']] = REMOTE_INIT_FAILED
            self.bad_hosts -= set(platform['hosts'])
            self.ready = True
        else:
            cmd = construct_ssh_cmd(cmd, platform, host)
            self.proc_pool.put_command(
                SubProcContext(
                    'remote-init',
                    cmd,
                    stdin_files=[tmphandle],
                    host=host
                ),
                bad_hosts=self.bad_hosts,
                callback=self._remote_init_callback,
                callback_args=[
                    platform, tmphandle, curve_auth, client_pub_key_dir
                ],
                callback_255=self._remote_init_callback_255,
                callback_255_args=[platform]
            )

    def remote_tidy(self):
        """Remove workflow contact files and keys from initialised remotes.

        Call "cylc remote-tidy".
        This method is called on workflow shutdown, so we want nothing to hang.
        Timeout any incomplete commands after 10 seconds.
        """
        from cylc.flow.platforms import PlatformLookupError
        # Issue all SSH commands in parallel

        def construct_remote_tidy_ssh_cmd(install_target, platform):
            cmd = ['remote-tidy']
            if cylc.flow.flags.verbosity > 1:
                cmd.append('--debug')
            cmd.append(install_target)
            cmd.append(get_remote_workflow_run_dir(self.workflow))
            host = get_host_from_platform(
                platform, bad_hosts=self.bad_hosts
            )
            cmd = construct_ssh_cmd(
                cmd, platform, host, timeout='10s'
            )
            return cmd, host

        procs = {}
        for install_target, message in self.remote_init_map.items():
            if message != REMOTE_FILE_INSTALL_DONE:
                continue
            if install_target == get_localhost_install_target():
                continue
            platform = get_random_platform_for_install_target(install_target)
            platform_n = platform['name']
            try:
                cmd, host = construct_remote_tidy_ssh_cmd(
                    install_target, platform)
            except (NoHostsError, PlatformLookupError):
                LOG.warning(TaskRemoteMgmtError(
                    TaskRemoteMgmtError.MSG_TIDY,
                    platform_n, 1, '', '', 'remote tidy'
                ))
            else:
                LOG.debug(
                    "Removing authentication keys and contact file "
                    f"from remote: \"{install_target}\"")
                procs[platform_n] = (
                    cmd,
                    host,
                    Popen(cmd, stdout=PIPE, stderr=PIPE, stdin=DEVNULL)
                )
        # Wait for commands to complete for a max of 10 seconds
        timeout = time() + 10.0
        while procs and time() < timeout:
            for platform_n, (cmd, host, proc) in procs.copy().items():
                if proc.poll() is None:
                    continue
                del procs[platform_n]
                out, err = (f.decode() for f in proc.communicate())
                # 255 error has to be handled here becuase remote tidy doesn't
                # use SubProcPool.
                if proc.returncode == 255:
                    timeout = time() + 10.0
                    self.bad_hosts.add(host)
                    LOG.warning(
                        f'Tried to tidy remote platform: \'{platform_n}\' '
                        f'using host \'{host}\' but failed; '
                        'trying a different host'
                    )
                    try:
                        retry_cmd, host = construct_remote_tidy_ssh_cmd(
                            install_target, platform
                        )
                    except (NoHostsError, PlatformLookupError):
                        LOG.warning(TaskRemoteMgmtError(
                            TaskRemoteMgmtError.MSG_TIDY, platform_n, '',
                            '', '', ''
                        ))
                    else:
                        procs[platform_n] = (
                            retry_cmd,
                            host,
                            Popen(
                                retry_cmd, stdout=PIPE, stderr=PIPE,
                                stdin=DEVNULL
                            )
                        )
                if proc.wait() and proc.returncode != 255:
                    LOG.warning(TaskRemoteMgmtError(
                        TaskRemoteMgmtError.MSG_TIDY,
                        platform_n, ' '.join(quote(item) for item in cmd),
                        proc.returncode, out, err))
        # Terminate any remaining commands
        for platform_n, (cmd, proc) in procs.items():
            with suppress(OSError):
                proc.terminate()
            out, err = (f.decode() for f in proc.communicate())
            if proc.wait():
                LOG.warning(TaskRemoteMgmtError(
                    TaskRemoteMgmtError.MSG_TIDY,
                    platform_n, ' '.join(quote(item) for item in cmd),
                    proc.returncode, out, err))

    def _subshell_eval_callback(self, proc_ctx, cmd_str):
        """Callback when subshell eval command exits"""
        self.ready = True
        if proc_ctx.ret_code == 0 and proc_ctx.out:
            self.remote_command_map[cmd_str] = proc_ctx.out.splitlines()[0]
        else:
            # Bad status
            LOG.error(proc_ctx)
            self.remote_command_map[cmd_str] = TaskRemoteMgmtError(
                TaskRemoteMgmtError.MSG_SELECT, (cmd_str, None), cmd_str,
                proc_ctx.ret_code, proc_ctx.out, proc_ctx.err)

    def _remote_init_callback_255(self, proc_ctx, platform):
        """Callback when "cylc remote-init" exits with 255 error.
        """
        install_target = platform['install target']
        self.remote_init_map[install_target] = REMOTE_INIT_255
        self.bad_hosts.add(proc_ctx.host)
        self.ready = True
        return

    def _remote_init_callback(
            self, proc_ctx, platform, tmphandle,
            curve_auth, client_pub_key_dir):
        """Callback when "cylc remote-init" exits.

        Write public key for install target into client public key
        directory.
        Set remote_init__map status to REMOTE_INIT_DONE on success which
        in turn will trigger file installation to start.
        Set remote_init_map status to REMOTE_INIT_FAILED on error.

        """
        with suppress(OSError):  # E.g. ignore bad unlink, etc
            tmphandle.close()
        install_target = platform['install target']
        if proc_ctx.ret_code == 0 and "KEYSTART" in proc_ctx.out:
            regex_result = re.search(
                'KEYSTART((.|\n|\r)*)KEYEND', proc_ctx.out)
            key = regex_result.group(1)
            workflow_srv_dir = get_workflow_srv_dir(self.workflow)
            public_key = KeyInfo(
                KeyType.PUBLIC,
                KeyOwner.CLIENT,
                workflow_srv_dir=workflow_srv_dir,
                install_target=install_target
            )
            old_umask = os.umask(0o177)
            with open(
                    public_key.full_key_path,
                    'w', encoding='utf8') as text_file:
                text_file.write(key)
            os.umask(old_umask)
            # configure_curve must be called every time certificates are
            # added or removed, in order to update the Authenticator's
            # state.
            curve_auth.configure_curve(
                domain='*', location=(client_pub_key_dir))
            self.remote_init_map[install_target] = REMOTE_INIT_DONE
            self.ready = True
            return
        # Bad status
        LOG.error(TaskRemoteMgmtError(
            TaskRemoteMgmtError.MSG_INIT,
            install_target, ' '.join(
                quote(item) for item in proc_ctx.cmd),
            proc_ctx.ret_code, proc_ctx.out, proc_ctx.err))

        self.remote_init_map[platform['install target']] = REMOTE_INIT_FAILED
        self.ready = True

    def file_install(self, platform):
        """Install required files on the remote install target.

        Included by default in the file installation:
            Files:
                .service/server.key  (required for ZMQ authentication)
            Directories:
                app/
                bin/
                etc/
                lib/
        """
        install_target = platform['install target']
        self.remote_init_map[install_target] = REMOTE_FILE_INSTALL_IN_PROGRESS
        src_path = get_workflow_run_dir(self.workflow)
        dst_path = get_remote_workflow_run_dir(self.workflow)
        install_target = platform['install target']
        try:
            cmd, host = construct_rsync_over_ssh_cmd(
                src_path,
                dst_path,
                platform,
                self.rsync_includes,
                bad_hosts=self.bad_hosts
            )
            ctx = SubProcContext(
                'file-install',
                cmd,
                host
            )
        except NoHostsError:
            LOG.error(TaskRemoteMgmtError(
                TaskRemoteMgmtError.MSG_INIT,
                install_target, '', '', '', ''))
            self.remote_init_map[
                platform['install target']] = REMOTE_FILE_INSTALL_FAILED
            self.bad_hosts -= set(platform['hosts'])
            self.ready = True
        else:
            LOG.debug(f"Begin file installation on {install_target}")
            self.proc_pool.put_command(
                ctx,
                bad_hosts=self.bad_hosts,
                callback=self._file_install_callback,
                callback_args=[install_target, platform],
                callback_255=self._file_install_callback_255,
            )

    def _file_install_callback_255(self, ctx, install_target):
        """Callback when file installation exits.

        Sets remote_init_map to REMOTE_FILE_INSTALL_DONE on success and to
        REMOTE_FILE_INSTALL_FAILED on error.
         """
        self.remote_init_map[install_target] = REMOTE_FILE_INSTALL_255
        self.ready = True

    def _file_install_callback(self, ctx, install_target):
        """Callback when file installation exits.

        Sets remote_init_map to REMOTE_FILE_INSTALL_DONE on success and to
        REMOTE_FILE_INSTALL_FAILED on error.
         """
        if ctx.out:
            RSYNC_LOG.info(
                'File installation information for '
                f'{install_target}:\n{ctx.out}')
        if ctx.ret_code == 0:
            # Both file installation and remote init success
            LOG.debug(ctx)
            LOG.debug(f"File installation complete for {install_target}")
            self.remote_init_map[install_target] = REMOTE_FILE_INSTALL_DONE
            self.ready = True
            return
        else:
            self.remote_init_map[install_target] = REMOTE_FILE_INSTALL_FAILED
            LOG.error(TaskRemoteMgmtError(
                TaskRemoteMgmtError.MSG_INIT,
                install_target, ' '.join(
                    quote(item) for item in ctx.cmd),
                ctx.ret_code, ctx.out, ctx.err))
            LOG.error(ctx)
            self.ready = True

    def _remote_init_items(self, comms_meth: CommsMeth):
        """Return list of items to install based on communication method.

        Return (list):
            Each item is (source_path, dest_path) where:
            - source_path is the path to the source file to install.
            - dest_path is relative path under workflow run directory
              at target remote.
        """
        items = []

        if comms_meth in [CommsMeth.SSH, CommsMeth.ZMQ]:
            # Contact file
            items.append((
                get_contact_file(self.workflow),
                os.path.join(
                    WorkflowFiles.Service.DIRNAME,
                    WorkflowFiles.Service.CONTACT)))

        return items
