#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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
"""Manage a remote job host."""

import os
from pipes import quote
from subprocess import Popen, PIPE
import shlex
from time import sleep, time
from uuid import uuid4

from cylc.cfgspec.globalcfg import GLOBAL_CFG
from cylc.owner import USER
from cylc.suite_logging import ERR, LOG
from cylc.suite_srv_files_mgr import SuiteSrvFilesManager


class RemoteJobHostInitError(Exception):
    """Cannot initialise suite run directory of remote job host."""

    MSG_INIT = "%s: initialisation did not complete:\n"  # %s user_at_host
    MSG_TIDY = "%s: clean up did not complete:\n"  # %s user_at_host

    def __str__(self):
        msg, user_at_host, cmd_str, ret_code, out, err = self.args
        ret = (msg + "COMMAND FAILED (%d): %s\n") % (
            user_at_host, ret_code, cmd_str)
        for label, item in ("STDOUT", out), ("STDERR", err):
            if item:
                for line in item.splitlines(True):  # keep newline chars
                    ret += "COMMAND %s: %s" % (label, line)
        return ret


class RemoteJobHostManager(object):
    """Manage a remote job host."""

    _INSTANCE = None

    @classmethod
    def get_inst(cls):
        """Return a singleton instance of this class."""
        if cls._INSTANCE is None:
            cls._INSTANCE = cls()
        return cls._INSTANCE

    def __init__(self):
        self.initialised_hosts = {}  # user_at_host: should_unlink
        self.single_task_mode = False
        self.suite_srv_files_mgr = SuiteSrvFilesManager()

    def init_suite_run_dir(self, reg, user_at_host):
        """Initialise suite run dir on a user@host.

        Create SUITE_RUN_DIR/log/job/ if necessary.
        Install suite contact environment file.
        Install suite python modules.

        Raise RemoteJobHostInitError if initialisation cannot complete.

        """
        if '@' in user_at_host:
            owner, host = user_at_host.split('@', 1)
        else:
            owner, host = None, user_at_host
        if ((owner, host) in [(None, 'localhost'), (USER, 'localhost')] or
                host in self.initialised_hosts or
                self.single_task_mode):
            return

        r_suite_run_dir = GLOBAL_CFG.get_derived_host_item(
            reg, 'suite run directory', host, owner)
        r_log_job_dir = GLOBAL_CFG.get_derived_host_item(
            reg, 'suite job log directory', host, owner)
        r_suite_srv_dir = os.path.join(
            r_suite_run_dir, self.suite_srv_files_mgr.DIR_BASE_SRV)

        # Create a UUID file in the service directory.
        # If remote host has the file in its service directory, we can assume
        # that the remote host has a shared file system with the suite host.
        ssh_tmpl = GLOBAL_CFG.get_host_item(
            'remote shell template', host, owner)
        uuid_str = str(uuid4())
        uuid_fname = os.path.join(
            self.suite_srv_files_mgr.get_suite_srv_dir(reg), uuid_str)
        try:
            open(uuid_fname, 'wb').close()
            proc = Popen(
                shlex.split(ssh_tmpl) + [
                    '-n', user_at_host,
                    'test', '-e', os.path.join(r_suite_srv_dir, uuid_str)],
                stdout=PIPE, stderr=PIPE)
            if proc.wait() == 0:
                # Initialised, but no need to tidy up
                self.initialised_hosts[user_at_host] = False
                return
        finally:
            try:
                os.unlink(uuid_fname)
            except OSError:
                pass

        cmds = []
        # Command to create suite directory structure on remote host.
        cmds.append(shlex.split(ssh_tmpl) + [
            '-n', user_at_host,
            'mkdir', '-p',
            r_suite_run_dir, r_log_job_dir, r_suite_srv_dir])
        # Command to copy contact and authentication files to remote host.
        # Note: no need to do this if task communication method is "poll".
        should_unlink = GLOBAL_CFG.get_host_item(
            'task communication method', host, owner) != "poll"
        if should_unlink:
            scp_tmpl = GLOBAL_CFG.get_host_item(
                'remote copy template', host, owner)
            cmds.append(shlex.split(scp_tmpl) + [
                '-p',
                self.suite_srv_files_mgr.get_contact_file(reg),
                self.suite_srv_files_mgr.get_auth_item(
                    self.suite_srv_files_mgr.FILE_BASE_PASSPHRASE, reg),
                self.suite_srv_files_mgr.get_auth_item(
                    self.suite_srv_files_mgr.FILE_BASE_SSL_CERT, reg),
                user_at_host + ':' + r_suite_srv_dir + '/'])
        # Command to copy python library to remote host.
        suite_run_py = os.path.join(
            GLOBAL_CFG.get_derived_host_item(reg, 'suite run directory'),
            'python')
        if os.path.isdir(suite_run_py):
            cmds.append(shlex.split(scp_tmpl) + [
                '-pr',
                suite_run_py, user_at_host + ':' + r_suite_run_dir + '/'])
        # Run commands in sequence.
        for cmd in cmds:
            proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
            out, err = proc.communicate()
            if proc.wait():
                raise RemoteJobHostInitError(
                    RemoteJobHostInitError.MSG_INIT,
                    user_at_host, ' '.join([quote(item) for item in cmd]),
                    proc.returncode, out, err)
        self.initialised_hosts[user_at_host] = should_unlink
        LOG.info('Initialised %s:%s' % (user_at_host, r_suite_run_dir))

    def unlink_suite_contact_files(self, reg):
        """Remove suite contact files from initialised hosts.

        This is called on shutdown, so we don't want anything to hang.
        Terminate any incomplete SSH commands after 10 seconds.
        """
        # Issue all SSH commands in parallel
        procs = {}
        for user_at_host, should_unlink in self.initialised_hosts.items():
            if not should_unlink:
                continue
            if '@' in user_at_host:
                owner, host = user_at_host.split('@', 1)
            else:
                owner, host = None, user_at_host
            ssh_tmpl = GLOBAL_CFG.get_host_item(
                'remote shell template', host, owner)
            r_suite_contact_file = os.path.join(
                GLOBAL_CFG.get_derived_host_item(
                    reg, 'suite run directory', host, owner),
                SuiteSrvFilesManager.DIR_BASE_SRV,
                SuiteSrvFilesManager.FILE_BASE_CONTACT)
            cmd = shlex.split(ssh_tmpl) + [
                '-n', user_at_host, 'rm', '-f', r_suite_contact_file]
            procs[user_at_host] = (cmd, Popen(cmd, stdout=PIPE, stderr=PIPE))
        # Wait for commands to complete for a max of 10 seconds
        timeout = time() + 10.0
        while procs and time() < timeout:
            for user_at_host, (cmd, proc) in procs.items():
                if not proc.poll():
                    continue
                del procs[user_at_host]
                out, err = proc.communicate()
                if proc.wait():
                    ERR.warning(RemoteJobHostInitError(
                        RemoteJobHostInitError.MSG_TIDY,
                        user_at_host, ' '.join([quote(item) for item in cmd]),
                        proc.returncode, out, err))
        # Terminate any remaining commands
        for user_at_host, (cmd, proc) in procs.items():
            try:
                proc.terminate()
            except OSError:
                pass
            out, err = proc.communicate()
            proc.wait()
            ERR.warning(RemoteJobHostInitError(
                RemoteJobHostInitError.MSG_TIDY,
                user_at_host, ' '.join([quote(item) for item in cmd]),
                proc.returncode, out, err))
