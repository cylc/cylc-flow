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

from collections import deque
from contextlib import suppress
from pathlib import Path
from cylc.flow.option_parsers import verbosity_to_opts
import os
from shlex import quote
import re
from subprocess import Popen, PIPE, DEVNULL
import tarfile
from time import sleep, time
from typing import (
    Any, Deque, Dict, TYPE_CHECKING, List,
    NamedTuple, Optional, Tuple
)

from cylc.flow import LOG
from cylc.flow.exceptions import (
    PlatformError, PlatformLookupError, NoHostsError, NoPlatformsError
)
import cylc.flow.flags
from cylc.flow.network.client_factory import CommsMeth
from cylc.flow.pathutil import (
    get_dirs_to_symlink,
    get_remote_workflow_run_dir,
    get_workflow_file_install_log_dir,
    get_workflow_run_dir,
)
from cylc.flow.platforms import (
    HOST_REC_COMMAND,
    PLATFORM_REC_COMMAND,
    NoHostsError,
    PlatformLookupError,
    get_host_from_platform,
    get_install_target_from_platform,
    get_install_target_to_platforms_map,
    get_localhost_install_target,
    log_platform_event,
)
from cylc.flow.remote import construct_rsync_over_ssh_cmd, construct_ssh_cmd
from cylc.flow.subprocctx import SubProcContext
from cylc.flow.util import format_cmd
from cylc.flow.workflow_files import (
    KeyInfo,
    KeyOwner,
    KeyType,
    WorkflowFiles,
    get_contact_file_path,
    get_workflow_srv_dir,
)

from cylc.flow.loggingutil import get_next_log_number, get_sorted_logs_by_time
from cylc.flow.hostuserutil import is_remote_host

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


class RemoteTidyQueueTuple(NamedTuple):
    platform: Dict[str, Any]
    host: str
    proc: 'Popen[str]'


class TaskRemoteMgr:
    """Manage task remote initialisation, tidy, selection."""

    def __init__(self, workflow, proc_pool, bad_hosts, db_mgr):
        self.workflow = workflow
        self.proc_pool = proc_pool
        # self.remote_command_map = {command: host|PlatformError|None}
        self.remote_command_map = {}
        # self.remote_init_map = {(install target): status, ...}
        self.remote_init_map = {}
        self.uuid_str = None
        # This flag is turned on when a host init/select command completes
        self.ready = False
        self.rsync_includes = None
        self.bad_hosts = bad_hosts
        self.is_reload = False
        self.is_restart = False
        self.db_mgr = db_mgr

    def _subshell_eval(
        self, eval_str: str, command_pattern: re.Pattern
    ) -> Optional[str]:
        """Evaluate a platform or host from a possible subshell string.

        Arguments:
            eval_str:
                An explicit host/platform name, a command, or an environment
                variable holding a host/patform name.
            command_pattern:
                A compiled regex pattern designed to match subshell strings.

        Return:
            - None if evaluation of command is still taking place.
            - 'localhost' if string is empty/not defined.
            - Otherwise, return the evaluated host/platform name on success.

        Raise PlatformError on error.

        """
        if not eval_str:
            return 'localhost'

        # Host selection command: $(command) or `command`
        match = command_pattern.match(eval_str)
        if match:
            cmd_str = match.groups()[1]
            if cmd_str in self.remote_command_map:
                # Command recently launched
                value = self.remote_command_map[cmd_str]
                if isinstance(value, PlatformError):
                    raise value  # command failed
                if value is None:
                    return None  # command not yet ready
                eval_str = value  # command succeeded
            else:
                # Command not launched (or already reset)
                self.proc_pool.put_command(
                    SubProcContext(
                        'remote-host-select',
                        ['bash', '-c', cmd_str],
                        env=dict(os.environ)
                    ),
                    callback=self._subshell_eval_callback,
                    callback_args=[cmd_str]
                )
                self.remote_command_map[cmd_str] = None
                return None

        # Environment variable substitution
        return os.path.expandvars(eval_str)

    # BACK COMPAT: references to "host"
        # remove at:
        #     Cylc8.x
    def eval_host(self, host_str: str) -> Optional[str]:
        """Evaluate a host from a possible subshell string.

        Args:
            host_str: An explicit host name, a command in back-tick or
                $(command) format, or an environment variable holding
                a hostname.

        Returns 'localhost' if evaluated name is equivalent
        (e.g. localhost4.localdomain4).
        """
        host = self._subshell_eval(host_str, HOST_REC_COMMAND)
        return host if is_remote_host(host) else 'localhost'

    def eval_platform(self, platform_str: str) -> Optional[str]:
        """Evaluate a platform from a possible subshell string.

        Args:
            platform_str: An explicit platform name, a command in $(command)
                format, or an environment variable holding a platform name.
        """
        return self._subshell_eval(platform_str, PLATFORM_REC_COMMAND)

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
        remote_init_items = self._remote_init_items(comms_meth)

        # Create a TAR archive with the service files,
        # so they can be sent later via SSH's STDIN to the task remote.
        tmphandle = self.proc_pool.get_temporary_file()
        with tarfile.open(fileobj=tmphandle, mode='w') as tarhandle:
            for path, arcname in remote_init_items:
                tarhandle.add(path, arcname=arcname)
        tmphandle.seek(0)
        # Build the remote-init command to be run over ssh
        cmd = [
            'remote-init',
            *verbosity_to_opts(cylc.flow.flags.verbosity),
            str(install_target),
            get_remote_workflow_run_dir(self.workflow)
        ]
        dirs_to_symlink = get_dirs_to_symlink(install_target, self.workflow)
        for key, value in dirs_to_symlink.items():
            if value is not None:
                cmd.append(f"{key}={quote(value)} ")
        # Create the ssh command
        try:
            host = get_host_from_platform(
                platform, bad_hosts=self.bad_hosts
            )
        except NoHostsError as exc:
            LOG.error(
                PlatformError(
                    f'{PlatformError.MSG_INIT}\n{exc}',
                    platform['name'],
                )
            )
            self.remote_init_map[
                platform['install target']] = REMOTE_INIT_FAILED
            # reset the bad hosts to allow remote-init to retry
            self.bad_hosts -= set(platform['hosts'])
            self.ready = True
        else:
            log_platform_event('remote init', platform, host)
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

    def construct_remote_tidy_ssh_cmd(
        self, platform: Dict[str, Any]
    ) -> Tuple[List[str], str]:
        """Return a remote-tidy SSH command.

        Rasies:
            NoHostsError: If the platform is not contactable.
        """
        cmd = ['remote-tidy']
        cmd.extend(verbosity_to_opts(cylc.flow.flags.verbosity))
        cmd.append(get_install_target_from_platform(platform))
        cmd.append(get_remote_workflow_run_dir(self.workflow))
        host = get_host_from_platform(
            platform, bad_hosts=self.bad_hosts
        )
        cmd = construct_ssh_cmd(cmd, platform, host, timeout='10s')
        return cmd, host

    @staticmethod
    def _get_remote_tidy_targets(
        platform_names: Optional[List[str]],
        install_targets: Set[str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Finds valid platforms for install targets, warns about in invalid
        install targets.

        logs:
            A list of install targets where no platform can be found.

        returns:
            A mapping of install targets to valid platforms only where
            platforms are available.
        """
        if platform_names is None and install_targets:
            install_targets_map = {t: [] for t in install_targets}
        else:
            install_targets_map = get_install_target_to_platforms_map(
                platform_names, quiet=True)

        # If we couldn't find a platform for a target, we cannot tidy it -
        # raise an Error:
        unreachable_targets = install_targets.difference(install_targets_map)
        if unreachable_targets:
            msg = 'No platforms available to remote tidy install targets:'
            for unreachable_target in unreachable_targets:
                msg += f'\n * {unreachable_target}'
            LOG.error(msg)

        return install_targets_map

    def remote_tidy(self) -> None:
        """Remove workflow contact files and keys from initialised remotes.

        Call "cylc remote-tidy".
        This method is called on workflow shutdown, so we want nothing to hang.
        Timeout any incomplete commands after 10 seconds.
        """
        # Get a list of all platforms used from workflow database:
        platforms_used = (
            self.db_mgr.get_pri_dao().select_task_job_platforms())
        # For each install target compile a list of platforms:
        install_targets = {
            target for target, msg
            in self.remote_init_map.items()
            if msg == REMOTE_FILE_INSTALL_DONE
        }
        install_targets_map = self._get_remote_tidy_targets(
            platforms_used, install_targets)

        # Issue all SSH commands in parallel
        queue: Deque[RemoteTidyQueueTuple] = deque()
        for install_target, platforms in install_targets_map.items():
            if install_target == get_localhost_install_target():
                continue
            for platform in platforms:
                try:
                    cmd, host = self.construct_remote_tidy_ssh_cmd(platform)
                except NoHostsError as exc:
                    LOG.warning(
                        PlatformError(
                            f'{PlatformError.MSG_TIDY}\n{exc}',
                            platform['name'],
                        )
                    )
                else:
                    log_platform_event('remote tidy', platform, host)
                    queue.append(
                        RemoteTidyQueueTuple(
                            platform,
                            host,
                            Popen(  # nosec
                                cmd, stdout=PIPE, stderr=PIPE, stdin=DEVNULL,
                                text=True
                            )  # * command constructed by internal interface
                        )
                    )
                    break
            else:
                LOG.error(
                    NoPlatformsError(
                        install_target, 'install target', 'remote tidy'))
        # Wait for commands to complete for a max of 10 seconds
        timeout = time() + 10.0
        while queue and time() < timeout:
            item = queue.popleft()
            if item.proc.poll() is None:  # proc still running
                queue.append(item)
                continue
            out, err = item.proc.communicate()
            # 255 error has to be handled here because remote tidy doesn't
            # use SubProcPool.
            if item.proc.returncode == 255:
                timeout = time() + 10.0
                self.bad_hosts.add(item.host)
                try:
                    retry_cmd, retry_host = self.construct_remote_tidy_ssh_cmd(
                        item.platform
                    )
                except (NoHostsError, PlatformLookupError) as exc:
                    LOG.warning(
                        PlatformError(
                            f'{PlatformError.MSG_TIDY}\n{exc}',
                            item.platform['name']
                        )
                    )
                else:
                    queue.append(
                        item._replace(
                            host=retry_host,
                            proc=Popen(  # nosec
                                retry_cmd, stdout=PIPE, stderr=PIPE,
                                stdin=DEVNULL, text=True
                            )  # * command constructed by internal interface
                        )
                    )
            elif item.proc.returncode:
                LOG.warning(
                    PlatformError(
                        PlatformError.MSG_TIDY,
                        item.platform['name'],
                        cmd=item.proc.args,
                        ret_code=item.proc.returncode,
                        out=out,
                        err=err
                    )
                )
            sleep(0.1)
        # Terminate any remaining commands
        for item in queue:
            with suppress(OSError):
                item.proc.terminate()
            out, err = item.proc.communicate()
            if item.proc.wait():
                LOG.warning(
                    PlatformError(
                        PlatformError.MSG_TIDY,
                        item.platform['name'],
                        cmd=item.proc.args,
                        ret_code=item.proc.returncode,
                        out=out,
                        err=err,
                    )
                )

    def _subshell_eval_callback(self, proc_ctx, cmd_str):
        """Callback when subshell eval command exits"""
        self.ready = True
        if proc_ctx.ret_code == 0 and proc_ctx.out:
            self.remote_command_map[cmd_str] = proc_ctx.out.splitlines()[0]
        else:
            # Bad status
            LOG.error(proc_ctx)
            self.remote_command_map[cmd_str] = PlatformError(
                PlatformError.MSG_SELECT,
                None,
                ctx=proc_ctx,
            )

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
        LOG.error(
            PlatformError(
                PlatformError.MSG_INIT,
                platform['name'],
                cmd=proc_ctx.cmd,
                ret_code=proc_ctx.ret_code,
                out=proc_ctx.out,
                err=proc_ctx.err,
            )
        )

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
        except NoHostsError as exc:
            LOG.error(
                PlatformError(
                    f'{PlatformError.MSG_INIT}\n{exc}',
                    platform['name'],
                )
            )
            self.remote_init_map[
                platform['install target']] = REMOTE_FILE_INSTALL_FAILED
            self.bad_hosts -= set(platform['hosts'])
            self.ready = True
        else:
            log_platform_event('remote file install', platform, host)
            self.proc_pool.put_command(
                ctx,
                bad_hosts=self.bad_hosts,
                callback=self._file_install_callback,
                callback_args=[platform, install_target],
                callback_255=self._file_install_callback_255,
            )

    def _file_install_callback_255(self, ctx, platform, install_target):
        """Callback when file installation exits.

        Sets remote_init_map to REMOTE_FILE_INSTALL_255.
         """
        self.remote_init_map[install_target] = REMOTE_FILE_INSTALL_255
        self.ready = True

    def _file_install_callback(self, ctx, platform, install_target):
        """Callback when file installation exits.

        Sets remote_init_map to REMOTE_FILE_INSTALL_DONE on success and to
        REMOTE_FILE_INSTALL_FAILED on error.
         """
        install_log_dir = get_workflow_file_install_log_dir(
            self.workflow)
        file_name = self.get_log_file_name(
            install_target, install_log_dir
        )
        install_log_path = get_workflow_file_install_log_dir(
            self.workflow, file_name)

        if ctx.out:
            Path(install_log_path).parent.mkdir(parents=True, exist_ok=True)
            with open(install_log_path, 'a') as install_log:
                install_log.write(
                    f'$ {format_cmd(ctx.cmd, maxlen=80)}'
                    '\n\n### STDOUT:'
                    f'\n{ctx.out}'
                )
                if ctx.err:
                    install_log.write(
                        '\n\n### STDERR:'
                        f'\n{ctx.err}'
                    )
        if ctx.ret_code == 0:
            # Both file installation and remote init success
            log_platform_event('remote file install complete', platform)
            self.remote_init_map[install_target] = REMOTE_FILE_INSTALL_DONE
            self.ready = True
            return
        else:
            self.remote_init_map[install_target] = REMOTE_FILE_INSTALL_FAILED
            LOG.error(
                PlatformError(
                    PlatformError.MSG_INIT,
                    platform['name'],
                    ctx=ctx,
                )
            )
            self.ready = True

    def get_log_file_name(
        self,
        install_target,
        install_log_dir
    ):
        log_files = get_sorted_logs_by_time(install_log_dir, '*.log')
        log_num = get_next_log_number(log_files[-1]) if log_files else 1
        load_type = "start"
        if self.is_reload:
            load_type = "reload"
            self.is_reload = False  # reset marker
        elif self.is_restart:
            load_type = "restart"
            self.is_restart = False  # reset marker
        file_name = f"{log_num:02d}-{load_type}-{install_target}.log"
        return file_name

    def _remote_init_items(
        self, comms_meth: CommsMeth
    ) -> List[Tuple[str, str]]:
        """Return list of items to install based on communication method.

        (At the moment this is only the contact file.)

        Return (list):
            Each item is (source_path, dest_path) where:
            - source_path is the path to the source file to install.
            - dest_path is relative path under workflow run directory
              at target remote.
        """
        if comms_meth not in {CommsMeth.SSH, CommsMeth.ZMQ}:
            return []
        return [
            (
                get_contact_file_path(self.workflow),
                os.path.join(
                    WorkflowFiles.Service.DIRNAME,
                    WorkflowFiles.Service.CONTACT
                )
            )
        ]
