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
from subprocess import Popen, PIPE
import tarfile
from time import time

from cylc import LOG
from cylc.cfgspec.glbl_cfg import glbl_cfg
from cylc.exceptions import TaskRemoteMgmtError
import cylc.flags
from cylc.hostuserutil import is_remote, is_remote_host, is_remote_user
from cylc.subprocctx import SubProcContext
from cylc.task_remote_cmd import (
    FILE_BASE_UUID, REMOTE_INIT_DONE, REMOTE_INIT_NOT_REQUIRED)


REC_COMMAND = re.compile(r'(`|\$\()\s*(.*)\s*([`)])$')
REMOTE_INIT_FAILED = 'REMOTE INIT FAILED'


class TaskRemoteMgr(object):
    """Manage task job remote initialisation, tidy, selection."""

    def __init__(self, suite, proc_pool, suite_srv_files_mgr):
        self.suite = suite
        self.proc_pool = proc_pool
        self.suite_srv_files_mgr = suite_srv_files_mgr
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
                timeout = glbl_cfg().get(['task host select command timeout'])
                if timeout:
                    cmd = ['timeout', str(int(timeout)), 'bash', '-c', cmd_str]
                else:
                    cmd = ['bash', '-c', cmd_str]
                self.proc_pool.put_command(
                    SubProcContext(
                        'remote-host-select', cmd, env=dict(os.environ)),
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

    def remote_init(self, host, owner):
        """Initialise a remote [owner@]host if necessary.

        Create UUID file on suite host ".service/uuid" for remotes to identify
        shared file system with suite host.

        Call "cylc remote-init" to install suite items to remote:
            ".service/contact": For TCP task communication
            ".service/passphrase": For TCP task communication
            "python/": if source exists

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
        if self.single_task_mode or not is_remote(host, owner):
            return REMOTE_INIT_NOT_REQUIRED
        try:
            status = self.remote_init_map[(host, owner)]
        except KeyError:
            pass  # Not yet initialised
        else:
            if status == REMOTE_INIT_FAILED:
                del self.remote_init_map[(host, owner)]  # reset to allow retry
            return status

        # Determine what items to install
        comm_meth = glbl_cfg().get_host_item(
            'task communication method', host, owner)
        owner_at_host = 'localhost'
        if host:
            owner_at_host = host
        if owner:
            owner_at_host = owner + '@' + owner_at_host
        LOG.debug('comm_meth[%s]=%s' % (owner_at_host, comm_meth))
        items = self._remote_init_items(comm_meth)
        # No item to install
        if not items:
            self.remote_init_map[(host, owner)] = REMOTE_INIT_NOT_REQUIRED
            return self.remote_init_map[(host, owner)]

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
            self.suite_srv_files_mgr.get_suite_srv_dir(self.suite),
            FILE_BASE_UUID)
        if not os.path.exists(uuid_fname):
            open(uuid_fname, 'wb').write(str(self.uuid_str).encode())
        # Build the command
        cmd = ['cylc', 'remote-init']
        if is_remote_host(host):
            cmd.append('--host=%s' % host)
        if is_remote_user(owner):
            cmd.append('--user=%s' % owner)
        if cylc.flags.debug:
            cmd.append('--debug')
        if comm_meth in ['ssh']:
            cmd.append('--indirect-comm=%s' % comm_meth)
        cmd.append(str(self.uuid_str))
        cmd.append(glbl_cfg().get_derived_host_item(
            self.suite, 'suite run directory', host, owner))
        self.proc_pool.put_command(
            SubProcContext('remote-init', cmd, stdin_files=[tmphandle]),
            self._remote_init_callback,
            [host, owner, tmphandle])
        # None status: Waiting for command to finish
        self.remote_init_map[(host, owner)] = None
        return self.remote_init_map[(host, owner)]

    def remote_tidy(self):
        """Remove suite contact files from initialised remotes.

        Call "cylc remote-tidy".
        This method is called on suite shutdown, so we want nothing to hang.
        Timeout any incomplete commands after 10 seconds.

        Also remove UUID file on suite host ".service/uuid".
        """
        # Remove UUID file
        uuid_fname = os.path.join(
            self.suite_srv_files_mgr.get_suite_srv_dir(self.suite),
            FILE_BASE_UUID)
        try:
            os.unlink(uuid_fname)
        except OSError:
            pass
        # Issue all SSH commands in parallel
        procs = {}
        for (host, owner), init_with_contact in self.remote_init_map.items():
            if init_with_contact != REMOTE_INIT_DONE:
                continue
            cmd = ['timeout', '10', 'cylc', 'remote-tidy']
            if is_remote_host(host):
                cmd.append('--host=%s' % host)
            if is_remote_user(owner):
                cmd.append('--user=%s' % owner)
            if cylc.flags.debug:
                cmd.append('--debug')
            cmd.append(os.path.join(glbl_cfg().get_derived_host_item(
                self.suite, 'suite run directory', host, owner)))
            procs[(host, owner)] = (
                cmd,
                Popen(cmd, stdout=PIPE, stderr=PIPE, stdin=open(os.devnull)))
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

    def _remote_init_callback(self, proc_ctx, host, owner, tmphandle):
        """Callback when "cylc remote-init" exits"""
        self.ready = True
        try:
            tmphandle.close()
        except OSError:  # E.g. ignore bad unlink, etc
            pass
        if proc_ctx.ret_code == 0:
            for status in (REMOTE_INIT_DONE, REMOTE_INIT_NOT_REQUIRED):
                if status in proc_ctx.out:
                    # Good status
                    LOG.debug(proc_ctx)
                    self.remote_init_map[(host, owner)] = status
                    return
        # Bad status
        LOG.error(TaskRemoteMgmtError(
            TaskRemoteMgmtError.MSG_INIT,
            (host, owner), ' '.join(quote(item) for item in proc_ctx.cmd),
            proc_ctx.ret_code, proc_ctx.out, proc_ctx.err))
        LOG.error(proc_ctx)
        self.remote_init_map[(host, owner)] = REMOTE_INIT_FAILED

    def _remote_init_items(self, comm_meth):
        """Return list of items to install based on communication method.

        Return (list):
            Each item is (path, name) where:
            - path is the path to the source file to install.
            - name is relative path under suite run directory at target remote.
        """
        items = []
        if comm_meth in ['ssh', 'zmq']:
            # Contact file
            items.append((
                self.suite_srv_files_mgr.get_contact_file(self.suite),
                os.path.join(
                    self.suite_srv_files_mgr.DIR_BASE_SRV,
                    self.suite_srv_files_mgr.FILE_BASE_CONTACT)))
        if comm_meth in ['zmq']:
            # Passphrase file
            items.append((
                self.suite_srv_files_mgr.get_auth_item(
                    self.suite_srv_files_mgr.FILE_BASE_PASSPHRASE,
                    self.suite),
                os.path.join(
                    self.suite_srv_files_mgr.DIR_BASE_SRV,
                    self.suite_srv_files_mgr.FILE_BASE_PASSPHRASE)))
        return items
