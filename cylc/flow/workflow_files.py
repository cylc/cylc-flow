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

"""Workflow service files management."""

import aiofiles
from enum import Enum
import logging
import os
from pathlib import Path
from random import shuffle
import re
import shutil
from subprocess import Popen, PIPE, DEVNULL
import time
from typing import List, Optional, Tuple, TYPE_CHECKING, Union
import zmq.auth

from cylc.flow import LOG
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.exceptions import (
    CylcError,
    PlatformLookupError,
    ServiceFileError,
    TaskRemoteMgmtError,
    WorkflowFilesError)
from cylc.flow.pathutil import (
    expand_path,
    get_workflow_run_dir,
    make_localhost_symlinks,
    remove_dir,
    get_next_rundir_number)
from cylc.flow.platforms import (
    get_install_target_to_platforms_map,
    get_localhost_install_target,
    get_platform
)
from cylc.flow.hostuserutil import (
    get_user,
    is_remote_host
)
from cylc.flow.remote import construct_ssh_cmd, DEFAULT_RSYNC_OPTS
from cylc.flow.workflow_db_mgr import WorkflowDatabaseManager
from cylc.flow.loggingutil import CylcLogFormatter
from cylc.flow.unicode_rules import WorkflowNameValidator
from cylc.flow.wallclock import get_current_time_string

if TYPE_CHECKING:
    from optparse import Values
    from logging import Logger


class KeyType(Enum):
    """Used for authentication keys - public or private"""

    PRIVATE = "private"
    PUBLIC = "public"


class KeyOwner(Enum):
    """Used for authentication keys - server or client"""

    SERVER = "server"
    CLIENT = "client"


class KeyInfo():
    """Represents a server or client key file, which can be private or public.

    Attributes:
        file_name:       The file name of this key object.
        key_type:        public or private
        key_owner:       server or client
        key_path:        The absolute path, not including filename,
                         for this key object.
        full_key_path:   The absolute path, including filename,
                         for this key object.


    """

    def __init__(self, key_type, key_owner, full_key_path=None,
                 workflow_srv_dir=None, install_target=None, server_held=True):
        self.key_type = key_type
        self.key_owner = key_owner
        self.full_key_path = full_key_path
        self.workflow_srv_dir = workflow_srv_dir
        self.install_target = install_target
        if self.full_key_path is not None:
            self.key_path, self.file_name = os.path.split(self.full_key_path)
        elif self.workflow_srv_dir is not None:
            # Build key filename
            file_name = key_owner.value

            # Add optional install target name
            if (key_owner is KeyOwner.CLIENT
                and key_type is KeyType.PUBLIC
                    and self.install_target is not None):
                file_name = f"{file_name}_{self.install_target}"

            if key_type == KeyType.PRIVATE:
                file_extension = WorkflowFiles.Service.PRIVATE_FILE_EXTENSION
            elif key_type == KeyType.PUBLIC:
                file_extension = WorkflowFiles.Service.PUBLIC_FILE_EXTENSION

            self.file_name = f"{file_name}{file_extension}"

            # Build key path (without filename) for client public keys
            if (key_owner is KeyOwner.CLIENT
                    and key_type is KeyType.PUBLIC and server_held):
                temp = f"{key_owner.value}_{key_type.value}_keys"
                self.key_path = os.path.join(
                    os.path.expanduser("~"),
                    self.workflow_srv_dir,
                    temp)
            elif (
                (key_owner is KeyOwner.CLIENT
                 and key_type is KeyType.PUBLIC
                 and server_held is False)
                or
                (key_owner is KeyOwner.SERVER
                 and key_type is KeyType.PRIVATE)
                or (key_owner is KeyOwner.CLIENT
                    and key_type is KeyType.PRIVATE)
                or (key_owner is KeyOwner.SERVER
                    and key_type is KeyType.PUBLIC)):
                self.key_path = os.path.expandvars(self.workflow_srv_dir)

        else:
            raise ValueError(
                "Cannot create KeyInfo without workflow path or full path.")

        # Build full key path (including file name)

        self.full_key_path = os.path.join(self.key_path, self.file_name)


class WorkflowFiles:
    """Files and directories located in the workflow directory."""

    FLOW_FILE = 'flow.cylc'
    """The workflow configuration file."""

    SUITE_RC = 'suite.rc'
    """Deprecated workflow configuration file."""

    RUN_N = 'runN'
    """Symbolic link for latest run"""

    LOG_DIR = 'log'
    """Workflow log directory."""

    SHARE_DIR = 'share'
    """Workflow share directory."""

    SHARE_CYCLE_DIR = os.path.join(SHARE_DIR, 'cycle')
    """Workflow share/cycle directory."""

    WORK_DIR = 'work'
    """Workflow work directory."""

    class Service:
        """The directory containing Cylc system files."""

        DIRNAME = '.service'
        """The name of this directory."""

        CONTACT = 'contact'
        """Contains settings for the running workflow.

        For details of the fields see ``ContactFileFields``.
        """

        PUBLIC_FILE_EXTENSION = '.key'
        PRIVATE_FILE_EXTENSION = '.key_secret'
        """Keyword identifiers used to form the certificate names.
        Note: the public & private identifiers are set by CurveZMQ, so cannot
        be renamed, but we hard-code them since they can't be extracted easily.
        """

    class Install:
        """The directory containing install source link."""

        DIRNAME = '_cylc-install'
        """The name of this directory."""

        SOURCE = 'source'
        """Symlink to the workflow definition (For run dir)."""

    RESERVED_DIRNAMES = [
        LOG_DIR, SHARE_DIR, WORK_DIR, RUN_N, Service.DIRNAME, Install.DIRNAME]
    """Reserved directory names that cannot be present in a source dir."""

    RESERVED_NAMES = [
        FLOW_FILE, SUITE_RC, *RESERVED_DIRNAMES]
    """Reserved filenames that cannot be used as run names."""


class ContactFileFields:
    """Field names present in ``WorkflowFiles.Service.CONTACT``.

    These describe properties of a running workflow.

    .. note::

       The presence of this file indicates the workflow is running as it is
       removed on shutdown. however, if a workflow is not properly shut down
       this file may be left behind.

    """

    API = 'CYLC_API'
    """The Workflow API version string."""

    HOST = 'CYLC_WORKFLOW_HOST'
    """The name of the host the scheduler process is running on."""

    NAME = 'CYLC_WORKFLOW_NAME'
    """The name of the workflow."""

    OWNER = 'CYLC_WORKFLOW_OWNER'
    """The user account under which the scheduler process is running."""

    PROCESS = 'CYLC_WORKFLOW_PROCESS'
    """The process ID of the running workflow on ``CYLC_WORKFLOW_HOST``."""

    PORT = 'CYLC_WORKFLOW_PORT'
    """The port Cylc uses to communicate with this workflow."""

    PUBLISH_PORT = 'CYLC_WORKFLOW_PUBLISH_PORT'
    """The port Cylc uses to publish data."""

    WORKFLOW_RUN_DIR_ON_WORKFLOW_HOST = (
        'CYLC_WORKFLOW_RUN_DIR_ON_WORKFLOW_HOST'
    )
    """The path to the workflow run directory as seen from ``HOST``."""

    UUID = 'CYLC_WORKFLOW_UUID'
    """Unique ID for this run of the workflow."""

    VERSION = 'CYLC_VERSION'
    """The Cylc version under which the workflow is running."""

    SCHEDULER_SSH_COMMAND = 'SCHEDULER_SSH_COMMAND'

    SCHEDULER_CYLC_PATH = 'SCHEDULER_CYLC_PATH'
    """The path containing the Cylc executable on a remote host."""

    SCHEDULER_USE_LOGIN_SHELL = 'SCHEDULER_USE_LOGIN_SHELL'
    """Remote command setting for Scheduler."""


REG_DELIM = "/"

NO_TITLE = "No title provided"
REC_TITLE = re.compile(r"^\s*title\s*=\s*(.*)\s*$")

PS_OPTS = '-wopid,args'

MAX_SCAN_DEPTH = 4  # How many subdir levels down to look for valid run dirs

CONTACT_FILE_EXISTS_MSG = r"""workflow contact file exists: %(fname)s

Workflow "%(workflow)s" is already running, listening at "%(host)s:%(port)s".

To start a new run, stop the old one first with one or more of these:
* cylc stop %(workflow)s              # wait for active tasks/event handlers
* cylc stop --kill %(workflow)s       # kill active tasks and wait

* cylc stop --now %(workflow)s        # don't wait for active tasks
* cylc stop --now --now %(workflow)s  # don't wait
* ssh -n "%(host)s" kill %(pid)s   # final brute force!
"""


def detect_old_contact_file(reg, check_host_port=None):
    """Detect old workflow contact file.

    If an old contact file does not exist, do nothing. If one does exist
    but the workflow process is definitely not alive, remove it. If one exists
    and the workflow process is still alive, raise ServiceFileError.

    If check_host_port is specified and does not match the (host, port)
    value in the old contact file, raise AssertionError.

    Args:
        reg (str): workflow name
        check_host_port (tuple): (host, port) to check against

    Raise:
        AssertionError:
            If old contact file exists but does not have matching
            (host, port) with value of check_host_port.
        ServiceFileError:
            If old contact file exists and the workflow process still alive.
    """
    # An old workflow of the same name may be running if a contact file exists
    # and can be loaded.
    try:
        data = load_contact_file(reg)
        old_host = data[ContactFileFields.HOST]
        old_port = data[ContactFileFields.PORT]
        old_proc_str = data[ContactFileFields.PROCESS]
    except (IOError, ValueError, ServiceFileError):
        # Contact file does not exist or corrupted, should be OK to proceed
        return
    if check_host_port and check_host_port != (old_host, int(old_port)):
        raise AssertionError("%s != (%s, %s)" % (
            check_host_port, old_host, old_port))
    # Run the "ps" command to see if the process is still running or not.
    # If the old workflow process is still running, it should show up with the
    # same command line as before.
    # Terminate command after 10 seconds to prevent hanging, etc.
    old_pid_str = old_proc_str.split(None, 1)[0].strip()
    cmd = ["timeout", "10", "ps", PS_OPTS, str(old_pid_str)]
    if is_remote_host(old_host):
        import shlex
        ssh_str = get_platform()["ssh command"]
        cmd = shlex.split(ssh_str) + ["-n", old_host] + cmd
    from time import sleep, time
    proc = Popen(cmd, stdin=DEVNULL, stdout=PIPE, stderr=PIPE)
    # Terminate command after 10 seconds to prevent hanging SSH, etc.
    timeout = time() + 10.0
    while proc.poll() is None:
        if time() > timeout:
            proc.terminate()
        sleep(0.1)
    fname = get_contact_file(reg)
    ret_code = proc.wait()
    out, err = (f.decode() for f in proc.communicate())
    if ret_code:
        LOG.debug("$ %s  # return %d\n%s", ' '.join(cmd), ret_code, err)
    for line in reversed(out.splitlines()):
        if line.strip() == old_proc_str:
            # Workflow definitely still running
            break
        elif line.split(None, 1)[0].strip() == "PID":
            # Only "ps" header - "ps" has run, but no matching results.
            # Workflow not running. Attempt to remove workflow contact file.
            try:
                os.unlink(fname)
                return
            except OSError:
                break

    raise ServiceFileError(
        CONTACT_FILE_EXISTS_MSG % {
            "host": old_host,
            "port": old_port,
            "pid": old_pid_str,
            "fname": fname,
            "workflow": reg,
        }
    )


def dump_contact_file(reg, data):
    """Create contact file. Data should be a key=value dict."""
    # Note:
    # 1st fsync for writing the content of the contact file to disk.
    # 2nd fsync for writing the file metadata of the contact file to disk.
    # The double fsync logic ensures that if the contact file is written to
    # a shared file system e.g. via NFS, it will be immediately visible
    # from by a process on other hosts after the current process returns.
    with open(get_contact_file(reg), "wb") as handle:
        for key, value in sorted(data.items()):
            handle.write(("%s=%s\n" % (key, value)).encode())
        os.fsync(handle.fileno())
    dir_fileno = os.open(get_workflow_srv_dir(reg), os.O_DIRECTORY)
    os.fsync(dir_fileno)
    os.close(dir_fileno)


def get_contact_file(reg):
    """Return name of contact file."""
    return os.path.join(
        get_workflow_srv_dir(reg), WorkflowFiles.Service.CONTACT)


def get_flow_file(reg: str) -> str:
    """Return the path of a workflow's flow.cylc file.

    Creates a flow.cylc symlink to suite.rc if only suite.rc exists.
    """
    run_dir = get_workflow_run_dir(reg)
    check_flow_file(run_dir, symlink_suiterc=True)
    return os.path.join(run_dir, WorkflowFiles.FLOW_FILE)


def get_workflow_source_dir(
    run_dir: Union[Path, str]
) -> Union[Tuple[str, Path], Tuple[None, None]]:
    """Get the source directory path of the workflow in directory provided.

    Args:
        run_dir: directory to check for an installed flow inside.

    Returns (source_dir, symlink) where the latter is the symlink to the source
    dir that exists in the run dir.
    """
    source_path = Path(
        run_dir,
        WorkflowFiles.Install.DIRNAME,
        WorkflowFiles.Install.SOURCE)
    try:
        source = os.readlink(source_path)
        return source, source_path
    except OSError:
        alt_source_path = Path(
            Path(run_dir).parent,
            WorkflowFiles.Install.DIRNAME,
            WorkflowFiles.Install.SOURCE)
        try:
            source = os.readlink(alt_source_path)
            return source, alt_source_path
        except OSError:
            return None, None


def get_workflow_srv_dir(reg, workflow_owner=None):
    """Return service directory of a workflow."""
    if not workflow_owner:
        workflow_owner = get_user()
    run_d = os.getenv("CYLC_WORKFLOW_RUN_DIR")
    if (
        not run_d
        or os.getenv("CYLC_WORKFLOW_NAME") != reg
        or os.getenv("CYLC_WORKFLOW_OWNER") != workflow_owner
    ):
        run_d = get_workflow_run_dir(reg)
    return os.path.join(run_d, WorkflowFiles.Service.DIRNAME)


def load_contact_file(reg):
    """Load contact file. Return data as key=value dict."""
    file_base = WorkflowFiles.Service.CONTACT
    path = get_workflow_srv_dir(reg)
    file_content = _load_local_item(file_base, path)
    if file_content:
        data = {}
        for line in file_content.splitlines():
            key, value = [item.strip() for item in line.split("=", 1)]
            # BACK COMPAT: contact pre "suite" to "workflow" conversion.
            # from:
            #     Cylc 8
            # remove at:
            #     Cylc 9
            data[key.replace('SUITE', 'WORKFLOW')] = value
        return data
    else:
        raise ServiceFileError("Couldn't load contact file")


async def load_contact_file_async(reg, run_dir=None):
    if not run_dir:
        path = Path(
            get_workflow_srv_dir(reg),
            WorkflowFiles.Service.CONTACT
        )
    else:
        path = Path(
            run_dir,
            WorkflowFiles.Service.DIRNAME,
            WorkflowFiles.Service.CONTACT
        )
    try:
        async with aiofiles.open(path, mode='r') as cont:
            data = {}
            async for line in cont:
                key, value = [item.strip() for item in line.split("=", 1)]
                # BACK COMPAT: contact pre "suite" to "workflow" conversion.
                # from:
                #     Cylc 8
                # remove at:
                #     Cylc 9
                data[key.replace('SUITE', 'WORKFLOW')] = value
            return data
    except IOError:
        raise ServiceFileError("Couldn't load contact file")


def parse_reg(arg: str):
    """Replace runN with true reg name.

    Args:
        reg (str): flow as entered by user on cli e.g. myflow/runN
    """
    if not arg.startswith(get_workflow_run_dir('')):
        workflow_dir = get_workflow_run_dir(arg)
    else:
        workflow_dir = arg

    run_number = re.search(
        r'(?:run)(\d*$)',
        os.readlink(workflow_dir)).group(1)

    return arg.replace(WorkflowFiles.RUN_N, f'run{run_number}')


def parse_workflow_arg(options, arg):
    """From CLI arg "WORKFLOW", return workflow name and flow.cylc path.

    * If arg is an installed workflow, workflow name is the installed name.
    * If arg is a directory, workflow name is the base name of the
      directory.
    * If arg is a file, workflow name is the base name of its container
      directory.
    """
    if arg == '.':
        arg = os.getcwd()
    if os.path.isfile(arg):
        name = os.path.dirname(arg)
        path = os.path.abspath(arg)
    else:
        name = arg
        path = get_flow_file(arg)
        if not path:
            arg = os.path.abspath(arg)
            if os.path.isdir(arg):
                path = os.path.join(arg, WorkflowFiles.FLOW_FILE)
                name = os.path.basename(arg)
                check_flow_file(arg, logger=None)
            else:
                path = arg
                name = os.path.basename(os.path.dirname(arg))
    return name, path


def register(
    flow_name: str, source: Optional[str] = None
) -> str:
    """Set up workflow.
    This completes some of the set up completed by cylc install.
    Called only if running a workflow that has not been installed.

    Validates workflow name.
    Validates run directory structure.
    Creates symlinks for localhost symlink dirs.
    Symlinks flow.cylc -> suite.rc.
    Creates the .service directory.

    Args:
        flow_name: workflow name.
        source: directory location of flow.cylc file, default $PWD.

    Return:
        The installed workflow name (which may be computed here).

    Raise:
        WorkflowFilesError:
           - No flow.cylc or suite.rc file found in source location.
           - Illegal name (can look like a relative path, but not absolute).
           - Nested workflow run directories.
    """
    validate_flow_name(flow_name)
    if source is not None:
        if os.path.basename(source) == WorkflowFiles.FLOW_FILE:
            source = os.path.dirname(source)
    else:
        source = os.getcwd()
    # flow.cylc must exist so we can detect accidentally reversed args.
    source = os.path.abspath(source)
    check_flow_file(source, symlink_suiterc=True, logger=None)
    symlinks_created = make_localhost_symlinks(
        get_workflow_run_dir(flow_name), flow_name)
    if bool(symlinks_created):
        for src, dst in symlinks_created.items():
            LOG.info(f"Symlink created from {src} to {dst}")
    # Create service dir if necessary.
    srv_d = get_workflow_srv_dir(flow_name)
    os.makedirs(srv_d, exist_ok=True)
    return flow_name


def is_installed(path):
    """Check to see if the path sent contains installed flow.

    Checks for valid _cylc-install directory in current folder and checks
    source link exists.
    """
    cylc_install_folder = Path(path, WorkflowFiles.Install.DIRNAME)
    source = Path(cylc_install_folder, WorkflowFiles.Install.SOURCE)
    if cylc_install_folder.exists and source.is_symlink():
        return True
    return False


def _clean_check(reg, run_dir):
    """Check whether a workflow can be cleaned.

    Args:
        reg (str): Workflow name.
        run_dir (str): Path to the workflow run dir on the filesystem.
    """
    validate_flow_name(reg)
    reg = os.path.normpath(reg)
    if reg.startswith('.'):
        raise WorkflowFilesError(
            "Workflow name cannot be a path that points to the cylc-run "
            "directory or above")
    if not run_dir.is_dir() and not run_dir.is_symlink():
        msg = f"No directory to clean at {run_dir}"
        raise FileNotFoundError(msg)
    try:
        detect_old_contact_file(reg)
    except ServiceFileError as exc:
        raise ServiceFileError(
            f"Cannot remove running workflow.\n\n{exc}")


def init_clean(reg: str, opts: 'Values') -> None:
    """Initiate the process of removing a stopped workflow from the local
    scheduler filesystem and remote hosts.

    Args:
        reg (str): Workflow name.
        opts (optparse.Values): CLI options object for cylc clean.
    """
    local_run_dir = Path(get_workflow_run_dir(reg))
    try:
        _clean_check(reg, local_run_dir)
    except FileNotFoundError as exc:
        LOG.info(str(exc))
        return

    platform_names = None
    try:
        platform_names = get_platforms_from_db(local_run_dir)
    except FileNotFoundError:
        LOG.info("No workflow database - will only clean locally")
    except ServiceFileError as exc:
        raise ServiceFileError(f"Cannot clean - {exc}")

    if platform_names and platform_names != {'localhost'}:
        remote_clean(reg, platform_names, opts.remote_timeout)
    LOG.info("Cleaning on local filesystem")
    clean(reg)


def clean(reg):
    """Remove a stopped workflow from the local filesystem only.

    Deletes the workflow run directory and any symlink dirs. Note: if the
    run dir has already been manually deleted, it will not be possible to
    clean the symlink dirs.

    Args:
        reg (str): Workflow name.
    """
    run_dir = Path(get_workflow_run_dir(reg))
    try:
        _clean_check(reg, run_dir)
    except FileNotFoundError as exc:
        LOG.info(str(exc))
        return

    # Note: 'share/cycle' must come first, and '' must come last
    for possible_symlink in (
            WorkflowFiles.SHARE_CYCLE_DIR, WorkflowFiles.SHARE_DIR,
            WorkflowFiles.LOG_DIR, WorkflowFiles.WORK_DIR, ''):
        name = Path(possible_symlink)
        path = Path(run_dir, possible_symlink)
        if path.is_symlink():
            # Ensure symlink is pointing to expected directory. If not,
            # something is wrong and we should abort
            target = path.resolve()
            if target.exists() and not target.is_dir():
                raise WorkflowFilesError(
                    f'Invalid Cylc symlink directory {path} -> {target}\n'
                    f'Target is not a directory')
            expected_end = str(Path('cylc-run', reg, name))
            if not str(target).endswith(expected_end):
                raise WorkflowFilesError(
                    f'Invalid Cylc symlink directory {path} -> {target}\n'
                    f'Expected target to end with "{expected_end}"')
            # Remove <symlink_dir>/cylc-run/<reg>
            target_cylc_run_dir = str(target).rsplit(str(reg), 1)[0]
            target_reg_dir = Path(target_cylc_run_dir, reg)
            if target_reg_dir.is_dir():
                remove_dir(target_reg_dir)
            # Remove empty parents
            _remove_empty_reg_parents(reg, target_reg_dir)

    remove_dir(run_dir)
    _remove_empty_reg_parents(reg, run_dir)


def remote_clean(reg, platform_names, timeout):
    """Run subprocesses to clean workflows on remote install targets
    (skip localhost), given a set of platform names to look up.

    Args:
        reg (str): Workflow name.
        platform_names (list): List of platform names to look up in the global
            config, in order to determine the install targets to clean on.
        timeout (str): Number of seconds to wait before cancelling.
    """
    try:
        install_targets_map = (
            get_install_target_to_platforms_map(platform_names))
    except PlatformLookupError as exc:
        raise PlatformLookupError(
            "Cannot clean on remote platforms as the workflow database is "
            f"out of date/inconsistent with the global config - {exc}")

    pool = []
    for target, platforms in install_targets_map.items():
        if target == get_localhost_install_target():
            continue
        shuffle(platforms)
        LOG.info(
            f"Cleaning on install target: {platforms[0]['install target']}")
        # Issue ssh command:
        pool.append(
            (_remote_clean_cmd(reg, platforms[0], timeout), target, platforms)
        )
    failed_targets = []
    # Handle subproc pool results almost concurrently:
    while pool:
        for proc, target, platforms in pool:
            ret_code = proc.poll()
            if ret_code is None:  # proc still running
                continue
            pool.remove((proc, target, platforms))
            out, err = (f.decode() for f in proc.communicate())
            if out:
                LOG.debug(out)
            if ret_code:
                # Try again using the next platform for this install target:
                this_platform = platforms.pop(0)
                excn = TaskRemoteMgmtError(
                    TaskRemoteMgmtError.MSG_TIDY, this_platform['name'],
                    " ".join(proc.args), ret_code, out, err)
                LOG.debug(excn)
                if platforms:
                    pool.append(
                        (_remote_clean_cmd(reg, platforms[0], timeout),
                         target, platforms)
                    )
                else:  # Exhausted list of platforms
                    failed_targets.append(target)
            elif err:
                LOG.debug(err)
        time.sleep(0.2)
    if failed_targets:
        raise CylcError(
            f"Could not clean on install targets: {', '.join(failed_targets)}")


def _remote_clean_cmd(reg, platform, timeout):
    """Remove a stopped workflow on a remote host.

    Call "cylc clean --local-only" over ssh and return the subprocess.

    Args:
        reg (str): Workflow name.
        platform (dict): Config for the platform on which to remove the
            workflow.
        timeout (str): Number of seconds to wait before cancelling the command.
    """
    LOG.debug(
        f'Cleaning on install target: {platform["install target"]} '
        f'(using platform: {platform["name"]})'
    )
    cmd = construct_ssh_cmd(
        ['clean', '--local-only', reg],
        platform,
        timeout=timeout,
        set_verbosity=True
    )
    LOG.debug(" ".join(cmd))
    return Popen(cmd, stdin=DEVNULL, stdout=PIPE, stderr=PIPE)


def _remove_empty_reg_parents(reg, path):
    """If reg is nested e.g. a/b/c, work our way up the tree, removing empty
    parents only.

    Args:
        reg (str): workflow name, e.g. a/b/c
        path (str): path to this directory, e.g. /foo/bar/a/b/c

    Example:
        _remove_empty_reg_parents('a/b/c', '/foo/bar/a/b/c') would remove
        /foo/bar/a/b (assuming it's empty), then /foo/bar/a (assuming it's
        empty).
    """
    reg = Path(reg)
    reg_depth = len(reg.parts) - 1
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('Path must be absolute')
    for i in range(reg_depth):
        parent = path.parents[i]
        if not parent.is_dir():
            continue
        try:
            parent.rmdir()
            LOG.debug(f'Removing directory: {parent}')
        except OSError:
            break


def remove_keys_on_server(keys):
    """Removes server-held authentication keys"""
    # WARNING, DESTRUCTIVE. Removes old keys if they already exist.
    for k in keys.values():
        if os.path.exists(k.full_key_path):
            os.remove(k.full_key_path)
    # Remove client public key folder
    client_public_key_dir = keys["client_public_key"].key_path
    if os.path.exists(client_public_key_dir):
        shutil.rmtree(client_public_key_dir)


def create_server_keys(keys, workflow_srv_dir):
    """Create or renew authentication keys for workflow 'reg' in the .service
     directory.
     Generate a pair of ZMQ authentication keys"""

    # ZMQ keys generated in .service directory.
    # .service/client_public_keys will store client public keys generated on
    # platform and sent back.
    # ZMQ keys need to be created with stricter file permissions, changing
    # umask default denials.
    os.makedirs(keys["client_public_key"].key_path, exist_ok=True)
    old_umask = os.umask(0o177)  # u=rw only set as default for file creation
    _server_public_full_key_path, _server_private_full_key_path = (
        zmq.auth.create_certificates(
            workflow_srv_dir,
            KeyOwner.SERVER.value))

    # cylc scan requires host to behave as a client, so copy public server
    # key into client public key folder
    server_pub_in_client_folder = keys["client_public_key"].full_key_path
    client_host_private_key = keys["client_private_key"].full_key_path
    shutil.copyfile(_server_private_full_key_path, client_host_private_key)
    shutil.copyfile(_server_public_full_key_path, server_pub_in_client_folder)
    # Return file permissions to default settings.
    os.umask(old_umask)


def get_workflow_title(reg):
    """Return the the workflow title without a full file parse

    Limitations:
    * 1st line of title only.
    * Assume title is not in an include-file.
    """
    title = NO_TITLE
    for line in open(get_flow_file(reg), 'r'):
        if line.lstrip().startswith("[meta]"):
            # continue : title comes inside [meta] section
            continue
        elif line.lstrip().startswith("["):
            # abort: title comes before first [section]
            break
        match = REC_TITLE.match(line)
        if match:
            title = match.groups()[0].strip('"\'')
    return title


def _load_local_item(item, path):
    """Load and return content of a file (item) in path."""
    try:
        with open(os.path.join(path, item)) as file_:
            return file_.read()
    except IOError:
        return None


def get_platforms_from_db(run_dir):
    """Load the set of names of platforms (that jobs ran on) from the
    workflow database.

    Args:
        run_dir (str): The workflow run directory.
    """
    workflow_db_mgr = WorkflowDatabaseManager(
        os.path.join(run_dir, WorkflowFiles.Service.DIRNAME))
    workflow_db_mgr.check_workflow_db_compatibility()
    try:
        pri_dao = workflow_db_mgr.get_pri_dao()
        platform_names = pri_dao.select_task_job_platforms()
        return platform_names
    finally:
        pri_dao.close()


def validate_flow_name(flow_name: str) -> None:
    """Check workflow name is valid and not an absolute path.

    Raise WorkflowFilesError if not valid.
    """
    is_valid, message = WorkflowNameValidator.validate(flow_name)
    if not is_valid:
        raise WorkflowFilesError(
            f"invalid workflow name '{flow_name}' - {message}")
    if os.path.isabs(flow_name):
        raise WorkflowFilesError(
            f"workflow name cannot be an absolute path: {flow_name}")


def check_nested_run_dirs(run_dir: Union[Path, str], flow_name: str) -> None:
    """Disallow nested run dirs e.g. trying to install foo/bar where foo is
    already a valid workflow directory.

    Args:
        run_dir: Absolute workflow run directory path.
        flow_name: Workflow name.

    Raise:
        WorkflowFilesError:
            - reg dir is nested inside a run dir
            - reg dir contains a nested run dir (if not deeper than max scan
                depth)
    """
    exc_msg = (
        'Nested run directories not allowed - cannot install workflow name '
        '"{0}" as "{1}" is already a valid run directory.')

    def _check_child_dirs(path: Union[Path, str], depth_count: int = 1):
        for result in os.scandir(path):
            if result.is_dir() and not result.is_symlink():
                if is_valid_run_dir(result.path):
                    raise WorkflowFilesError(
                        exc_msg.format(flow_name, result.path)
                    )
                if depth_count < MAX_SCAN_DEPTH:
                    _check_child_dirs(result.path, depth_count + 1)

    reg_path: Union[Path, str] = os.path.normpath(run_dir)
    parent_dir = os.path.dirname(reg_path)
    while parent_dir not in ['', '/']:
        if is_valid_run_dir(parent_dir):
            raise WorkflowFilesError(
                exc_msg.format(parent_dir, get_cylc_run_abs_path(parent_dir))
            )
        parent_dir = os.path.dirname(parent_dir)

    reg_path = get_cylc_run_abs_path(reg_path)
    if os.path.isdir(reg_path):
        _check_child_dirs(reg_path)


def is_valid_run_dir(path):
    """Return True if path is a valid, existing run directory, else False.

    Args:
        path (str): if this is a relative path, it is taken to be relative to
            the cylc-run directory.
    """
    path = get_cylc_run_abs_path(path)
    if os.path.isdir(os.path.join(path, WorkflowFiles.Service.DIRNAME)):
        return True
    return False


def get_cylc_run_abs_path(path: Union[Path, str]) -> Union[Path, str]:
    """Return the absolute path under the cylc-run directory for the specified
    relative path.

    If the specified path is already absolute, just return it.
    The path need not exist.
    """
    if os.path.isabs(path):
        return path
    return get_workflow_run_dir(path)


def _get_logger(rund, log_name):
    """Get log and create and open if necessary."""
    logger = logging.getLogger(log_name)
    if not logger.getEffectiveLevel == logging.INFO:
        logger.setLevel(logging.INFO)
    if not logger.hasHandlers():
        _open_install_log(rund, logger)
    return logger


def _open_install_log(rund, logger):
    """Open Cylc log handlers for install/reinstall."""
    time_str = get_current_time_string(
        override_use_utc=True, use_basic_format=True,
        display_sub_seconds=False
    )
    rund = Path(rund).expanduser()
    log_type = logger.name[logger.name.startswith('cylc-') and len('cylc-'):]
    log_path = Path(
        rund,
        WorkflowFiles.LOG_DIR,
        'install',
        f"{time_str}-{log_type}.log")
    log_parent_dir = log_path.parent
    log_parent_dir.mkdir(exist_ok=True, parents=True)
    handler = logging.FileHandler(log_path)
    handler.setFormatter(CylcLogFormatter())
    logger.addHandler(handler)


def _close_install_log(logger):
    """Close Cylc log handlers for install/reinstall.
        Args:
            logger (constant)"""
    for handler in logger.handlers:
        try:
            handler.close()
        except IOError:
            pass


def get_rsync_rund_cmd(src, dst, reinstall=False, dry_run=False):
    """Create and return the rsync command used for cylc install/re-install.

    Args:
        src (str):
            file path location of source directory
        dst (str):
            file path location of destination directory
        reinstall (bool):
            indicate reinstall (--delete option added)
        dry-run (bool):
            indicate dry-run, rsync will not take place but report output if a
            real run were to be executed

    Return:
        list: command to use for rsync.

    """
    rsync_cmd = ["rsync"] + DEFAULT_RSYNC_OPTS
    if dry_run:
        rsync_cmd.append("--dry-run")
    if reinstall:
        rsync_cmd.append('--delete')
    for exclude in [
        '.git',
        '.svn',
        '.cylcignore',
        'rose-suite.conf',
        'opt/rose-suite-cylc-install.conf',
        WorkflowFiles.LOG_DIR,
        WorkflowFiles.Install.DIRNAME,
        WorkflowFiles.Service.DIRNAME
    ]:
        if (Path(src).joinpath(exclude).exists() or
                Path(dst).joinpath(exclude).exists()):
            rsync_cmd.append(f"--exclude={exclude}")
    if Path(src).joinpath('.cylcignore').exists():
        rsync_cmd.append("--exclude-from=.cylcignore")
    rsync_cmd.append(f"{src}/")
    rsync_cmd.append(f"{dst}/")

    return rsync_cmd


def reinstall_workflow(named_run, rundir, source, dry_run=False):
    """ Reinstall workflow.

    Args:
        named_run (str):
            name of the run e.g. my-flow/run1
        rundir (path):
            run directory
        source (path):
            source directory
        dry_run (bool):
            if True, will not execute the file transfer but report what would
            be changed.
    """
    validate_source_dir(source, named_run)
    check_nested_run_dirs(rundir, named_run)
    reinstall_log = _get_logger(rundir, 'cylc-reinstall')
    reinstall_log.info(f"Reinstalling \"{named_run}\", from "
                       f"\"{source}\" to \"{rundir}\"")
    rsync_cmd = get_rsync_rund_cmd(
        source, rundir, reinstall=True, dry_run=dry_run)
    proc = Popen(rsync_cmd, stdout=PIPE, stderr=PIPE, text=True)
    stdout, stderr = proc.communicate()
    reinstall_log.info(
        f"Copying files from {source} to {rundir}"
        f'\n{stdout}'
    )
    if not proc.returncode == 0:
        reinstall_log.warning(
            f"An error occurred when copying files from {source} to {rundir}")
        reinstall_log.warning(f" Error: {stderr}")
    check_flow_file(rundir, symlink_suiterc=True, logger=reinstall_log)
    reinstall_log.info(f'REINSTALLED {named_run} from {source}')
    print(f'REINSTALLED {named_run} from {source}')
    _close_install_log(reinstall_log)
    return


def install_workflow(
    flow_name: Optional[str] = None,
    source: Optional[Union[Path, str]] = None,
    run_name: Optional[str] = None,
    no_run_name: bool = False,
    no_symlinks: bool = False
) -> Tuple[Path, Path, str]:
    """Install a workflow, or renew its installation.

    Install workflow into new run directory.
    Create symlink to workflow source location, creating any symlinks for run,
    work, log, share, share/cycle directories.

    Args:
        flow_name: workflow name, default basename($PWD).
        source: directory location of flow.cylc file, default $PWD.
        run_name: name of the run, overrides run1, run2, run 3 etc...
            If specified, cylc install will not create runN symlink.
        rundir: for overriding the default cylc-run directory.
        no_run_name: Flag as True to install workflow into
            ~/cylc-run/<flow_name>
        no_symlinks: Flag as True to skip making localhost symlink dirs

    Return:
        source: The source directory.
        rundir: The directory the workflow has been installed into.
        flow_name: The installed workflow name (which may be computed here).

    Raise:
        WorkflowFilesError:
            No flow.cylc file found in source location.
            Illegal name (can look like a relative path, but not absolute).
            Another workflow already has this name (unless --redirect).
            Trying to install a workflow that is nested inside of another.
    """
    if not source:
        source = Path.cwd()
    elif Path(source).name == WorkflowFiles.FLOW_FILE:
        source = Path(source).parent
    source = Path(expand_path(source))
    if not flow_name:
        flow_name = source.name
    validate_flow_name(flow_name)
    if run_name in WorkflowFiles.RESERVED_NAMES:
        raise WorkflowFilesError(f'Run name cannot be "{run_name}".')
    validate_source_dir(source, flow_name)
    run_path_base = Path(get_workflow_run_dir(flow_name))
    relink, run_num, rundir = get_run_dir_info(
        run_path_base, run_name, no_run_name)
    if Path(rundir).exists():
        raise WorkflowFilesError(
            f"\"{rundir}\" exists."
            " Try using cylc reinstall. Alternatively, install with another"
            " name, using the --run-name option.")
    check_nested_run_dirs(rundir, flow_name)
    symlinks_created = {}
    named_run = flow_name
    if run_name:
        named_run = os.path.join(named_run, run_name)
    elif run_num:
        named_run = os.path.join(named_run, f'run{run_num}')
    if not no_symlinks:
        symlinks_created = make_localhost_symlinks(rundir, named_run)
    install_log = _get_logger(rundir, 'cylc-install')
    if not no_symlinks and bool(symlinks_created) is True:
        for src, dst in symlinks_created.items():
            install_log.info(f"Symlink created from {src} to {dst}")
    try:
        rundir.mkdir(exist_ok=True)
    except FileExistsError:
        raise WorkflowFilesError("Run directory already exists")
    if relink:
        link_runN(rundir)
    create_workflow_srv_dir(rundir)
    rsync_cmd = get_rsync_rund_cmd(source, rundir)
    proc = Popen(rsync_cmd, stdout=PIPE, stderr=PIPE, text=True)
    stdout, stderr = proc.communicate()
    install_log.info(
        f"Copying files from {source} to {rundir}"
        f"\n{stdout}"
    )
    if proc.returncode != 0:
        install_log.warning(
            f"An error occurred when copying files from {source} to {rundir}")
        install_log.warning(f" Error: {stderr}")
    cylc_install = Path(rundir.parent, WorkflowFiles.Install.DIRNAME)
    check_flow_file(rundir, symlink_suiterc=True, logger=install_log)
    if no_run_name:
        cylc_install = Path(rundir, WorkflowFiles.Install.DIRNAME)
    source_link = cylc_install.joinpath(WorkflowFiles.Install.SOURCE)
    # check source link matches the source symlink from workflow dir.
    cylc_install.mkdir(parents=True, exist_ok=True)
    if not source_link.exists():
        install_log.info(f"Creating symlink from {source_link}")
        source_link.symlink_to(source)
    elif source_link.exists() and (
        source_link.resolve() == source.resolve()
    ):
        install_log.info(
            f"Symlink from \"{source_link}\" to \"{source}\" in place.")
    else:
        raise WorkflowFilesError(
            "Source directory between runs are not consistent.")
    install_log.info(f'INSTALLED {named_run} from {source}')
    print(f'INSTALLED {named_run} from {source}')
    _close_install_log(install_log)
    return source, rundir, flow_name


def get_run_dir_info(
    run_path_base: Path, run_name: Optional[str], no_run_name: bool
) -> Tuple[bool, Optional[int], Path]:
    """Get (numbered, named or unnamed) run directory info for current install.

    Args:
        run_path_base: The workflow directory absolute path.
        run_name: Name of the run.
        no_run_name: Flag as True to indicate no run name - workflow installed
            into ~/cylc-run/<run_path_base>.

    Returns:
        relink: True if runN symlink needs updating.
        run_num: Run number of the current install, if using numbered runs.
        rundir: Run directory absolute path.
    """
    relink = False
    run_num = None
    if no_run_name:
        rundir = run_path_base
    elif run_name:
        rundir = run_path_base.joinpath(run_name)
        if (run_path_base.exists() and
                detect_flow_exists(run_path_base, True)):
            raise WorkflowFilesError(
                f"This path: \"{run_path_base}\" contains installed numbered"
                " runs. Try again, using cylc install without --run-name.")
    else:
        run_num = get_next_rundir_number(run_path_base)
        rundir = Path(run_path_base, f'run{run_num}')
        if run_path_base.exists() and detect_flow_exists(run_path_base, False):
            raise WorkflowFilesError(
                f"This path: \"{run_path_base}\" contains an installed"
                " workflow. Try again, using --run-name.")
        unlink_runN(run_path_base)
        relink = True
    return relink, run_num, rundir


def detect_flow_exists(run_path_base, numbered):
    """Returns True if installed flow already exists.

    Args:
        run_path_base (Path):
            Workflow run directory i.e ~/cylc-run/<flow_name>
        numbered (bool):
            If true, will detect if numbered runs exist
            If false, will detect if non-numbered runs exist, i.e. runs
            installed by --run-name)

    Returns:
        True if installed flows exist.

    """
    for entry in Path(run_path_base).iterdir():
        isNumbered = bool(re.search(r'^run\d+$', entry.name))
        if (
            entry.is_dir()
            and entry.name not in [
                WorkflowFiles.Install.DIRNAME, WorkflowFiles.RUN_N
            ]
            and Path(entry, WorkflowFiles.FLOW_FILE).exists()
            and isNumbered == numbered
        ):
            return True


def check_flow_file(
    path: Union[Path, str],
    symlink_suiterc: bool = False,
    logger: Optional['Logger'] = LOG
) -> Path:
    """Raises WorkflowFilesError if no flow file in path sent.

    Args:
        path: Path to check for a flow.cylc and/or suite.rc file.
        symlink_suiterc: If True and suite.rc exists, create flow.cylc as a
            symlink to suite.rc. If a flow.cylc symlink already exists but
            points elsewhere, it will be replaced.
        logger: A custom logger to use to log warnings.

    Returns the path of the flow file if present.
    """
    flow_file_path = Path(expand_path(path), WorkflowFiles.FLOW_FILE)
    suite_rc_path = Path(expand_path(path), WorkflowFiles.SUITE_RC)
    depr_msg = (
        f'The filename "{WorkflowFiles.SUITE_RC}" is deprecated '
        f'in favour of "{WorkflowFiles.FLOW_FILE}"')
    if flow_file_path.is_file():
        if not flow_file_path.is_symlink():
            return flow_file_path
        if flow_file_path.resolve() == suite_rc_path.resolve():
            # A symlink that points to *existing* suite.rc
            if logger:
                logger.warning(depr_msg)
            return flow_file_path
    if suite_rc_path.is_file():
        if not symlink_suiterc:
            if logger:
                logger.warning(depr_msg)
            return suite_rc_path
        if flow_file_path.is_symlink():
            # Symlink broken or points elsewhere - replace
            flow_file_path.unlink()
        flow_file_path.symlink_to(WorkflowFiles.SUITE_RC)
        if logger:
            logger.warning(f'{depr_msg}. Symlink created.')
        return flow_file_path
    raise WorkflowFilesError(
        f"no {WorkflowFiles.FLOW_FILE} or {WorkflowFiles.SUITE_RC} in {path}")


def create_workflow_srv_dir(rundir=None, source=None):
    """Create workflow service directory"""

    workflow_srv_d = rundir.joinpath(WorkflowFiles.Service.DIRNAME)
    workflow_srv_d.mkdir(exist_ok=True, parents=True)


def validate_source_dir(source, flow_name):
    """Ensure the source directory is valid.

    Args:
        source (path): Path to source directory
    Raises:
        WorkflowFilesError:
            If log, share, work or _cylc-install directories exist in the
            source directory.
            Cylc installing from within the cylc-run dir
    """
    # Ensure source dir does not contain log, share, work, _cylc-install
    for dir_ in WorkflowFiles.RESERVED_DIRNAMES:
        if Path(source, dir_).exists():
            raise WorkflowFilesError(
                f'{flow_name} installation failed. - {dir_} exists in source '
                'directory.')
    cylc_run_dir = Path(get_workflow_run_dir(''))
    if (os.path.abspath(os.path.realpath(cylc_run_dir))
            in os.path.abspath(os.path.realpath(source))):
        raise WorkflowFilesError(
            f'{flow_name} installation failed. Source directory should not be '
            f'in {cylc_run_dir}')
    check_flow_file(source, logger=None)


def unlink_runN(path: Union[Path, str]) -> bool:
    """Remove symlink runN if it exists.

    Args:
        path: Absolute path to workflow dir containing runN.
    """
    try:
        Path(expand_path(path, WorkflowFiles.RUN_N)).unlink()
    except OSError:
        return False
    return True


def link_runN(latest_run: Union[Path, str]):
    """Create symlink runN, pointing at the latest run"""
    latest_run = Path(latest_run)
    run_n = Path(latest_run.parent, WorkflowFiles.RUN_N)
    try:
        run_n.symlink_to(latest_run.name)
    except OSError:
        pass


def search_install_source_dirs(flow_name: str) -> Path:
    """Return the path of a workflow source dir if it is present in the
    'global.cylc[install]source dirs' search path."""
    search_path: List[str] = glbl_cfg().get(['install', 'source dirs'])
    if not search_path:
        raise WorkflowFilesError(
            "Cannot find workflow as 'global.cylc[install]source dirs' "
            "does not contain any paths")
    for path in search_path:
        try:
            flow_file = check_flow_file(Path(path, flow_name), logger=None)
            return flow_file.parent
        except WorkflowFilesError:
            continue
    raise WorkflowFilesError(
        f"Could not find workflow '{flow_name}' in: {', '.join(search_path)}")
