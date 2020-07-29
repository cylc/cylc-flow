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
"""Manage task remotes.

This module provides logic to:
- Set up the directory structure on remote job hosts.
  - Copy suite service files to remote job hosts for communication clients.
  - Clean up of service files on suite shutdown.
- Implement basic host select functionality.
"""

import os
from shlex import quote
import re
from subprocess import Popen, PIPE, DEVNULL
import tarfile
from time import time

from cylc.flow import LOG
from cylc.flow.exceptions import TaskRemoteMgmtError
import cylc.flow.flags
from cylc.flow.hostuserutil import (
    is_remote_host, is_remote_platform
)
from cylc.flow.pathutil import get_remote_suite_run_dir
from cylc.flow.subprocctx import SubProcContext
from cylc.flow.suite_files import (
    SuiteFiles,
    KeyInfo,
    KeyOwner,
    KeyType,
    get_suite_srv_dir,
    get_contact_file)
from cylc.flow.task_remote_cmd import (
    FILE_BASE_UUID, REMOTE_INIT_DONE, REMOTE_INIT_NOT_REQUIRED)
from cylc.flow.platforms import platform_from_name, get_host_from_platform
from cylc.flow.remote import construct_platform_ssh_cmd


REC_COMMAND = re.compile(r'(`|\$\()\s*(.*)\s*([`)])$')
REMOTE_INIT_FAILED = 'REMOTE INIT FAILED'


class TaskRemoteMgr(object):
    """Manage task job remote initialisation, tidy, selection."""

    def __init__(self, suite, proc_pool):
        self.suite = suite
        self.proc_pool = proc_pool
        # self.remote_host_str_map = {host_str: host|TaskRemoteMgmtError|None}
        self.remote_host_str_map = {}
        # self.remote_init_map = {(host, owner): status, ...}
        self.remote_init_map = {}
        self.single_task_mode = False
        self.uuid_str = None
        self.ready = False

    def remote_host_select(self, host_str):
        """Evaluate a task host string.

        Arguments:
            host_str (str):
                An explicit host name, a command in back-tick or $(command)
                format, or an environment variable holding a hostname.

        Return (str):
            None if evaluate of host_str is still taking place.
            'localhost' if host_str is not defined or if the evaluated host
            name is equivalent to 'localhost'.
            Otherwise, return the evaluated host name on success.

        Raise TaskRemoteMgmtError on error.

        """
        if not host_str:
            return 'localhost'

        # Host selection command: $(command) or `command`
        match = REC_COMMAND.match(host_str)
        if match:
            cmd_str = match.groups()[1]
            if cmd_str in self.remote_host_str_map:
                # Command recently launched
                value = self.remote_host_str_map[cmd_str]
                if isinstance(value, TaskRemoteMgmtError):
                    raise value  # command failed
                elif value is None:
                    return  # command not yet ready
                else:
                    host_str = value  # command succeeded
            else:
                # Command not launched (or already reset)
                self.proc_pool.put_command(
                    SubProcContext(
                        'remote-host-select',
                        ['bash', '-c', cmd_str],
                        env=dict(os.environ)),
                    self._remote_host_select_callback, [cmd_str])
                self.remote_host_str_map[cmd_str] = None
                return self.remote_host_str_map[cmd_str]

        # Environment variable substitution
        host_str = os.path.expandvars(host_str)
        # Remote?
        if is_remote_host(host_str):
            return host_str
        else:
            return 'localhost'

    def remote_host_select_reset(self):
        """Reset remote host select results.

        This is normally called after the results are consumed.
        """
        for key, value in list(self.remote_host_str_map.copy().items()):
            if value is not None:
                del self.remote_host_str_map[key]

    def remote_init(self, platform_name, curve_auth, client_pub_key_dir):
        """Initialise a remote [owner@]host if necessary.

        Create UUID file on a platform ".service/uuid" for remotes to identify
        shared file system with suite host.

        Call "cylc remote-init" to install suite items to remote:
            ".service/contact": For TCP task communication
            "python/": if source exists

        Args:
            platform_name (str):
                The name of the platform to be initialized.

        Return:
            REMOTE_INIT_NOT_REQUIRED:
                If remote init is not required, e.g. not remote
            REMOTE_INIT_DONE:
                If remote init done.
            REMOTE_INIT_FAILED:
                If init of the remote failed.
                Note: this will reset to None to allow retry.
            None:
                If waiting for remote init command to complete

        """
        # get the platform from the platform_name
        platform = platform_from_name(platform_name)

        # If task is running locally we can skip the rest of this function
        if self.single_task_mode or not is_remote_platform(platform):
            return REMOTE_INIT_NOT_REQUIRED

        # See if a previous failed attempt to initialize this platform has
        # occured.
        try:
            status = self.remote_init_map[platform['name']]
        except KeyError:
            pass  # Not yet initialised
        else:
            if status == REMOTE_INIT_FAILED:
                del self.remote_init_map[platform['name']]
            return status

        # Determine what items to install
        comm_meth = platform['communication method']

        # Get a host and the owner from platform
        host = get_host_from_platform(platform)
        owner = platform['owner']

        # Get a list of files and folders to install;
        # if nothing needs install say so to remote_init_map and return.
        items = self._remote_init_items(comm_meth)

        # Create a TAR archive with the service files,
        # so they can be sent later via SSH's STDIN to the task remote.
        tmphandle = self.proc_pool.get_temporary_file()
        tarhandle = tarfile.open(fileobj=tmphandle, mode='w')
        for path, arcname in items:
            tarhandle.add(path, arcname=arcname)
        tarhandle.close()
        tmphandle.seek(0)
        # UUID file - for remote to identify shared file system with suite host
        uuid_fname = os.path.join(
            get_suite_srv_dir(self.suite),
            FILE_BASE_UUID
        )
        if not os.path.exists(uuid_fname):
            open(uuid_fname, 'wb').write(str(self.uuid_str).encode())

        # Build the remote-init command to be run over ssh
        cmd = ['remote-init']
        if cylc.flow.flags.debug:
            cmd.append('--debug')
        if comm_meth in ['ssh']:
            cmd.append('--indirect-comm=%s' % comm_meth)
        cmd.append(str(self.uuid_str))
        cmd.append(get_remote_suite_run_dir(platform, self.suite))
        # Create the ssh command
        cmd = construct_platform_ssh_cmd(cmd, platform)

        self.proc_pool.put_command(
            SubProcContext(
                'remote-init',
                cmd,
                stdin_files=[tmphandle]),
            self._remote_init_callback,
            [platform, tmphandle,
             curve_auth, client_pub_key_dir])
        # None status: Waiting for command to finish
        self.remote_init_map[platform['name']] = None
        return self.remote_init_map[platform['name']]

    def remote_tidy(self):
        """Remove suite contact files from initialised remotes.

        Call "cylc remote-tidy".
        This method is called on suite shutdown, so we want nothing to hang.
        Timeout any incomplete commands after 10 seconds.

        Also remove UUID file on suite host ".service/uuid".
        """
        # Remove UUID file
        uuid_fname = os.path.join(
            get_suite_srv_dir(self.suite), FILE_BASE_UUID
        )
        try:
            os.unlink(uuid_fname)
        except OSError:
            pass
        # Issue all SSH commands in parallel
        procs = {}
        for platform, init_with_contact in self.remote_init_map.items():
            platform = platform_from_name(platform)
            host = get_host_from_platform(platform)
            owner = platform['owner']
            if init_with_contact != REMOTE_INIT_DONE:
                continue
            cmd = ['remote-tidy']
            if cylc.flow.flags.debug:
                cmd.append('--debug')
            cmd.append(get_remote_suite_run_dir(platform, self.suite))
            if is_remote_platform(platform):
                cmd = construct_platform_ssh_cmd(cmd, platform, timeout='10s')
            else:
                cmd = ['cylc'] + cmd
            procs[(host, owner)] = (
                cmd,
                Popen(cmd, stdout=PIPE, stderr=PIPE, stdin=DEVNULL))
        # Wait for commands to complete for a max of 10 seconds
        timeout = time() + 10.0
        while procs and time() < timeout:
            for (host, owner), (cmd, proc) in procs.copy().items():
                if proc.poll() is None:
                    continue
                del procs[(host, owner)]
                out, err = (f.decode() for f in proc.communicate())
                if proc.wait():
                    LOG.warning(TaskRemoteMgmtError(
                        TaskRemoteMgmtError.MSG_TIDY,
                        (host, owner), ' '.join(quote(item) for item in cmd),
                        proc.returncode, out, err))
        # Terminate any remaining commands
        for (host, owner), (cmd, proc) in procs.items():
            try:
                proc.terminate()
            except OSError:
                pass
            out, err = proc.communicate()
            if proc.wait():
                LOG.warning(TaskRemoteMgmtError(
                    TaskRemoteMgmtError.MSG_TIDY,
                    (host, owner), ' '.join(quote(item) for item in cmd),
                    proc.returncode, out, err))

    def _remote_host_select_callback(self, proc_ctx, cmd_str):
        """Callback when host select command exits"""
        self.ready = True
        if proc_ctx.ret_code == 0 and proc_ctx.out:
            # Good status
            LOG.debug(proc_ctx)
            self.remote_host_str_map[cmd_str] = proc_ctx.out.splitlines()[0]
        else:
            # Bad status
            LOG.error(proc_ctx)
            self.remote_host_str_map[cmd_str] = TaskRemoteMgmtError(
                TaskRemoteMgmtError.MSG_SELECT, (cmd_str, None), cmd_str,
                proc_ctx.ret_code, proc_ctx.out, proc_ctx.err)

    def _remote_init_callback(
        self, proc_ctx, platform, tmphandle,
        curve_auth, client_pub_key_dir
    ):
        """Callback when "cylc remote-init" exits"""
        self.ready = True
        try:
            tmphandle.close()
        except OSError:  # E.g. ignore bad unlink, etc
            pass
        if proc_ctx.ret_code == 0:
            if "KEYSTART" in proc_ctx.out:
                regex_result = re.search(
                    'KEYSTART((.|\n|\r)*)KEYEND', proc_ctx.out)
                key = regex_result.group(1)
                suite_srv_dir = get_suite_srv_dir(self.suite)
                public_key = KeyInfo(
                    KeyType.PUBLIC,
                    KeyOwner.CLIENT,
                    suite_srv_dir=suite_srv_dir,
                    platform=platform['name']
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
            for status in (REMOTE_INIT_DONE, REMOTE_INIT_NOT_REQUIRED):
                if status in proc_ctx.out:
                    # Good status
                    LOG.debug(proc_ctx)
                    self.remote_init_map[platform['name']] = status
                    return
        # Bad status
        LOG.error(TaskRemoteMgmtError(
            TaskRemoteMgmtError.MSG_INIT,
            platform['name'], ' '.join(quote(item) for item in proc_ctx.cmd),
            proc_ctx.ret_code, proc_ctx.out, proc_ctx.err))
        LOG.error(proc_ctx)
        self.remote_init_map[platform['name']] = REMOTE_INIT_FAILED

    def _remote_init_items(self, comm_meth):
        """Return list of items to install based on communication method.

        Return (list):
            Each item is (source_path, dest_path) where:
            - source_path is the path to the source file to install.
            - dest_path is relative path under suite run directory
              at target remote.
        """
        items = []

        if comm_meth in ['ssh', 'zmq']:
            # Contact file
            items.append((
                get_contact_file(self.suite),
                os.path.join(
                    SuiteFiles.Service.DIRNAME,
                    SuiteFiles.Service.CONTACT)))

        if comm_meth in ['zmq']:
            suite_srv_dir = get_suite_srv_dir(self.suite)
            server_pub_keyinfo = KeyInfo(
                KeyType.PUBLIC,
                KeyOwner.SERVER,
                suite_srv_dir=suite_srv_dir)
            dest_path_srvr_public_key = os.path.join(
                SuiteFiles.Service.DIRNAME, server_pub_keyinfo.file_name)
            items.append(
                (server_pub_keyinfo.full_key_path,
                 dest_path_srvr_public_key))
        return items
