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

from collections import deque
from contextlib import suppress
from enum import Enum
from functools import partial
import glob
import logging
import os
from pathlib import Path
from random import shuffle
import re
from subprocess import Popen, PIPE, DEVNULL, TimeoutExpired
import shlex
import shutil
import sqlite3
from time import sleep
from typing import (
    Any, Container, Deque, Dict, Iterable, List, NamedTuple, Optional, Set,
    Tuple, TYPE_CHECKING, Union
)

import aiofiles
import zmq.auth

import cylc.flow.flags
from cylc.flow import LOG
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.exceptions import (
    CylcError,
    CylcVersionError,
    PlatformError,
    PlatformLookupError,
    ServiceFileError,
    InputError,
    WorkflowFilesError,
    handle_rmtree_err,
)
from cylc.flow.loggingutil import (
    CylcLogFormatter,
    close_log,
    get_next_log_number,
    get_sorted_logs_by_time
)
from cylc.flow.pathutil import (
    expand_path,
    get_cylc_run_dir,
    get_workflow_run_dir,
    make_localhost_symlinks,
    parse_rm_dirs,
    remove_dir_and_target,
    get_next_rundir_number,
    remove_dir_or_file,
    remove_empty_parents
)
from cylc.flow.platforms import (
    get_host_from_platform,
    get_install_target_to_platforms_map,
    get_localhost_install_target,
)
from cylc.flow.hostuserutil import (
    get_user,
    is_remote_host
)
from cylc.flow.remote import (
    DEFAULT_RSYNC_OPTS,
    construct_cylc_server_ssh_cmd,
    construct_ssh_cmd,
)
from cylc.flow.terminal import parse_dirty_json
from cylc.flow.unicode_rules import WorkflowNameValidator
from cylc.flow.util import cli_format
from cylc.flow.workflow_db_mgr import WorkflowDatabaseManager

if TYPE_CHECKING:
    from optparse import Values


class KeyType(Enum):
    """Used for authentication keys - public or private"""

    PRIVATE = "private"
    PUBLIC = "public"


class KeyOwner(Enum):
    """Used for authentication keys - server or client"""

    SERVER = "server"
    CLIENT = "client"


class KeyInfo():  # noqa: SIM119 (not really relevant here)
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
        elif self.workflow_srv_dir is not None:  # noqa: SIM106
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
    """Names of files and directories located in the workflow directory."""

    FLOW_FILE = 'flow.cylc'
    """The workflow configuration file."""

    FLOW_FILE_PROCESSED = 'flow-processed.cylc'
    """The workflow configuration file after processing."""

    SUITE_RC = 'suite.rc'
    """Deprecated workflow configuration file."""

    RUN_N = 'runN'
    """Symbolic link for latest run"""

    class LogDir:
        """The directory containing workflow log files"""

        DIRNAME = 'log'
        """Workflow log directory."""

        INSTALL = 'install'
        """Install log dir"""

        VERSION = 'version'
        """Version control log dir"""

    SHARE_DIR = 'share'
    """Workflow share directory."""

    SHARE_CYCLE_DIR = os.path.join(SHARE_DIR, 'cycle')
    """Workflow share/cycle directory."""

    WORK_DIR = 'work'
    """Workflow work directory."""

    RUN_DIR = 'run'
    """Workflow run directory."""

    class Service:
        """The directory containing Cylc system files."""

        DIRNAME = '.service'
        """The name of this directory."""

        CONTACT = 'contact'
        """Contains settings for the running workflow.

        For details of the fields see ``ContactFileFields``.
        """

        DB = 'db'
        """The workflow database.

        Contains information about the execution and status of a workflow.
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

    RESERVED_DIRNAMES = frozenset([
        LogDir.DIRNAME, SHARE_DIR, WORK_DIR, RUN_N,
        Service.DIRNAME, Install.DIRNAME
    ])
    """Reserved directory names that cannot be present in a source dir."""

    RESERVED_NAMES = frozenset([FLOW_FILE, SUITE_RC, *RESERVED_DIRNAMES])
    """Reserved filenames that cannot be used as run names."""

    SYMLINK_DIRS = frozenset([
        SHARE_CYCLE_DIR, SHARE_DIR, LogDir.DIRNAME, WORK_DIR, ''
    ])
    """The paths of the symlink dirs that may be set in
    global.cylc[install][symlink dirs], relative to the run dir
    ('' represents the run dir)."""


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

    NAME = 'CYLC_WORKFLOW_ID'
    """The name of the workflow."""

    OWNER = 'CYLC_WORKFLOW_OWNER'
    """The user account under which the scheduler process is running."""

    PID = 'CYLC_WORKFLOW_PID'
    """The process ID of the running workflow on ``CYLC_WORKFLOW_HOST``."""

    COMMAND = 'CYLC_WORKFLOW_COMMAND'
    """The command that was used to run the workflow on
    ``CYLC_WORKFLOW_HOST```.

    Note that this command may be affected by:

    * Workflow host selection (this adds the ``--host`` argument).
    * Auto restart (this reconstructs the command and changes the ``--host``
      argument.
    """

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


class RemoteCleanQueueTuple(NamedTuple):
    proc: 'Popen[str]'
    install_target: str
    platforms: List[Dict[str, Any]]


REG_DELIM = "/"

NO_TITLE = "No title provided"
REC_TITLE = re.compile(r"^\s*title\s*=\s*(.*)\s*$")

CONTACT_FILE_EXISTS_MSG = r"""workflow contact file exists: %(fname)s

Workflow "%(workflow)s" is already running, listening at "%(host)s:%(port)s".

To start a new run, stop the old one first with one or more of these:
* cylc stop %(workflow)s              # wait for active tasks/event handlers
* cylc stop --kill %(workflow)s       # kill active tasks and wait

* cylc stop --now %(workflow)s        # don't wait for active tasks
* cylc stop --now --now %(workflow)s  # don't wait
* ssh -n "%(host)s" kill %(pid)s   # final brute force!
"""

SUITERC_DEPR_MSG = "Backward compatibility mode ON"

NO_FLOW_FILE_MSG = (
    f"No {WorkflowFiles.FLOW_FILE} or {WorkflowFiles.SUITE_RC} "
    "in {}"
)

NESTED_DIRS_MSG = (
    "Nested {dir_type} directories not allowed - cannot install workflow"
    " in '{dest}' as '{existing}' is already a valid {dir_type} directory."
)


def _is_process_running(
    host: str,
    pid: Union[int, str],
    command: str
) -> bool:
    """Check if a workflow process is still running.

    * Returns True if the process is still running.
    * Returns False if it is not.
    * Raises CylcError if we cannot tell (e.g. due to network issues).

    Args:
        host:
            The host where you expect it to be running.
        pid:
            The process ID you expect it to be running under.
        command:
            The command you expect to be running as it would appear in `ps`
            output` (e.g. `cylc play <flow> --host=localhost`).

    Raises:
        CylcError:
            If it is not possible to tell whether the process is running
            or not.

    Returns:
        True if the workflow is running else False.

    Examples:
        >>> import psutil; proc = psutil.Process()

        # check a process that is running (i.e. this one)
        >>> _is_process_running(
        ...     'localhost',
        ...     proc.pid,
        ...     cli_format(proc.cmdline()),
        ... )
        True

        # check a process that is running but with a command line  that
        # doesn't match
        >>> _is_process_running('localhost', proc.pid, 'something-else')
        False

    """
    # See if the process is still running or not.
    metric = f'[["Process", {pid}]]'
    if is_remote_host(host):
        cmd = ['psutil']
        cmd = construct_cylc_server_ssh_cmd(cmd, host)
    else:
        cmd = ['cylc', 'psutil']
    proc = Popen(  # nosec
        cmd,
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
        text=True
    )  # * hardcoded command
    try:
        # Terminate command after 10 seconds to prevent hanging, etc.
        out, err = proc.communicate(timeout=10, input=metric)
    except TimeoutExpired:
        raise CylcError(
            f'Cannot determine whether workflow is running on {host}.'
        )

    if proc.returncode == 2:
        # the psutil call failed to gather metrics on the process
        # because the process does not exist
        return False

    error = False
    if proc.returncode:
        # the psutil call failed in some other way e.g. network issues
        LOG.debug(
            f'$ {cli_format(cmd)}  # returned {proc.returncode}\n{err}'
        )
        error = True
    else:
        try:
            process = parse_dirty_json(out)[0]
        except ValueError:
            # the JSON cannot be parsed, log it
            LOG.warning(f'Could not parse JSON:\n{out}')
            error = True

    if error:
        raise CylcError(
            f'Cannot determine whether workflow is running on {host}.'
            f'\n{command}'
        )

    return cli_format(process['cmdline']) == command


def detect_old_contact_file(
    reg: str, contact_data=None
) -> None:
    """Check if the workflow process is still running.

    As a side-effect this should detect and rectify the situation
    where an old contact file is still present from a previous run. This can be
    caused by the uncontrolled teardown of a running Scheduler (e.g. a power
    off).

    * If an old contact file does not exist, do nothing.
    * If one does exist but the workflow process is definitely not alive,
      remove it.
    * If one exists and the workflow process is still alive, raise
      ServiceFileError.

    Args:
        reg: workflow name
        contact_date:

    Raises:
        CylcError:
            If it is not possible to tell for sure if the workflow is running
            or not.
        ServiceFileError(CylcError):
            If old contact file exists and the workflow process still alive.

    """
    # An old workflow of the same name may be running if a contact file exists
    # and can be loaded.
    if not contact_data:
        try:
            contact_data = load_contact_file(reg)
        except (IOError, ValueError, ServiceFileError):
            # Contact file does not exist or corrupted, workflow should be dead
            return

    try:
        old_version: str = contact_data[ContactFileFields.VERSION]
        old_host: str = contact_data[ContactFileFields.HOST]
        old_port: str = contact_data[ContactFileFields.PORT]
        old_pid: str = contact_data[ContactFileFields.PID]
        old_cmd: str = contact_data[ContactFileFields.COMMAND]
    except KeyError as exc:
        # scenario - playing a workflow which is already running with Cylc 7:
        if old_version and int(old_version.split('.')[0]) < 8:
            raise CylcVersionError(version=old_version, status="Running")
        # this shouldn't happen
        # but if it does re-raise the error as something more informative
        raise Exception(f'Found contact file with incomplete data:\n{exc}.')

    # check if the workflow process is running ...
    # NOTE: can raise CylcError
    process_is_running = _is_process_running(old_host, old_pid, old_cmd)

    fname = get_contact_file_path(reg)
    if process_is_running:
        # ... the process is running, raise an exception
        raise ServiceFileError(
            CONTACT_FILE_EXISTS_MSG % {
                "host": old_host,
                "port": old_port,
                "pid": old_pid,
                "fname": fname,
                "workflow": reg,
            }
        )
    else:
        # ... the process isn't running so the contact file is out of date
        # remove it
        try:
            os.unlink(fname)
        except FileNotFoundError:
            # contact file has been removed by another process
            # (likely by another cylc client, no problem, safe to ignore)
            pass
        except OSError as exc:
            # unexpected error removing the contact file
            # (note the FileNotFoundError incorporated errno.ENOENT)
            LOG.error(
                f'Failed to remove contact file for {reg}:\n{exc}'
            )
        else:
            LOG.info(
                f'Removed contact file for {reg}'
                ' (workflow no longer running).'
            )


def dump_contact_file(reg, data):
    """Create contact file. Data should be a key=value dict."""
    # Note:
    # 1st fsync for writing the content of the contact file to disk.
    # 2nd fsync for writing the file metadata of the contact file to disk.
    # The double fsync logic ensures that if the contact file is written to
    # a shared file system e.g. via NFS, it will be immediately visible
    # from by a process on other hosts after the current process returns.
    with open(get_contact_file_path(reg), "wb") as handle:
        for key, value in sorted(data.items()):
            handle.write(("%s=%s\n" % (key, value)).encode())
        os.fsync(handle.fileno())
    dir_fileno = os.open(get_workflow_srv_dir(reg), os.O_DIRECTORY)
    os.fsync(dir_fileno)
    os.close(dir_fileno)


def get_contact_file_path(reg: str) -> str:
    """Return name of contact file."""
    return os.path.join(
        get_workflow_srv_dir(reg), WorkflowFiles.Service.CONTACT)


def get_flow_file(reg: str) -> Path:
    """Return the path of a workflow's flow.cylc file."""
    run_dir = get_workflow_run_dir(reg)
    path = check_flow_file(run_dir)
    return path


def get_workflow_source_dir(
    run_dir: Union[Path, str]
) -> Union[Tuple[str, Path], Tuple[None, None]]:
    """Get the source directory path for a given workflow run directory.

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


def get_workflow_srv_dir(reg):
    """Return service directory of a workflow."""
    run_d = os.getenv("CYLC_WORKFLOW_RUN_DIR")
    if (
        not run_d
        or os.getenv("CYLC_WORKFLOW_ID") != reg
        or os.getenv("CYLC_WORKFLOW_OWNER") != get_user()
    ):
        run_d = get_workflow_run_dir(reg)
    return os.path.join(run_d, WorkflowFiles.Service.DIRNAME)


def load_contact_file(reg: str) -> Dict[str, str]:
    """Load contact file. Return data as key=value dict."""
    try:
        with open(get_contact_file_path(reg)) as f:
            file_content = f.read()
    except IOError:
        raise ServiceFileError("Couldn't load contact file")
    data: Dict[str, str] = {}
    for line in file_content.splitlines():
        key, value = [item.strip() for item in line.split("=", 1)]
        # BACK COMPAT: contact pre "suite" to "workflow" conversion.
        # from:
        #     Cylc 8
        # remove at:
        #     Cylc 8.x
        data[key.replace('SUITE', 'WORKFLOW')] = value
    return data


async def load_contact_file_async(reg, run_dir=None):
    if not run_dir:
        path = Path(get_contact_file_path(reg))
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
                #     Cylc 8.x
                data[key.replace('SUITE', 'WORKFLOW')] = value
            return data
    except IOError:
        raise ServiceFileError("Couldn't load contact file")


def register(
    workflow_name: str, source: Optional[str] = None
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
        workflow_name: workflow name.
        source: directory location of flow.cylc file, default $PWD.

    Return:
        The installed workflow name (which may be computed here).

    Raise:
        WorkflowFilesError:
           - No flow.cylc or suite.rc file found in source location.
           - Illegal name (can look like a relative path, but not absolute).
           - Nested workflow run directories.
    """
    validate_workflow_name(workflow_name)
    if source is not None:
        if os.path.basename(source) == WorkflowFiles.FLOW_FILE:
            source = os.path.dirname(source)
    else:
        source = os.getcwd()
    # flow.cylc must exist so we can detect accidentally reversed args.
    source = os.path.abspath(source)
    check_flow_file(source)
    if not is_installed(get_workflow_run_dir(workflow_name)):
        symlinks_created = make_localhost_symlinks(
            get_workflow_run_dir(workflow_name), workflow_name)
        if symlinks_created:
            for target, symlink in symlinks_created.items():
                LOG.info(f"Symlink created: {symlink} -> {target}")
    # Create service dir if necessary.
    srv_d = get_workflow_srv_dir(workflow_name)
    os.makedirs(srv_d, exist_ok=True)
    return workflow_name


def is_installed(rund: Union[Path, str]) -> bool:
    """Check to see if the path sent contains installed flow.

    Checks for valid _cylc-install directory in the two possible locations in
    relation to the run directory.

    Args:
        rund: run directory path to check

    Returns:
        bool: True if rund belongs to an installed workflow
    """
    rund = Path(rund)
    cylc_install_dir = Path(rund, WorkflowFiles.Install.DIRNAME)
    alt_cylc_install_dir = Path(rund.parent, WorkflowFiles.Install.DIRNAME)
    return cylc_install_dir.is_dir() or alt_cylc_install_dir.is_dir()


async def get_contained_workflows(partial_id) -> List[str]:
    """Return the sorted names of any workflows in a directory.

    Args:
        path: Absolute path to the dir.
        scan_depth: How many levels deep to look inside the dir.
    """
    from cylc.flow.network.scan import scan
    run_dir = Path(get_workflow_run_dir(partial_id))
    # Note: increased scan depth for safety
    scan_depth = glbl_cfg().get(['install', 'max depth']) + 1
    return sorted(
        [i['name'] async for i in scan(scan_dir=run_dir, max_depth=scan_depth)]
    )


def _clean_check(opts: 'Values', reg: str, run_dir: Path) -> None:
    """Check whether a workflow can be cleaned.

    Args:
        reg: Workflow name.
        run_dir: Path to the workflow run dir on the filesystem.
    """
    validate_workflow_name(reg)
    reg = os.path.normpath(reg)
    # Thing to clean must be a dir or broken symlink:
    if not run_dir.is_dir() and not run_dir.is_symlink():
        raise FileNotFoundError(f"No directory to clean at {run_dir}")
    db_path = (
        run_dir / WorkflowFiles.Service.DIRNAME / WorkflowFiles.Service.DB
    )
    if opts.local_only and not db_path.is_file():
        # Will reach here if this is cylc clean re-invoked on remote host
        # (workflow DB only exists on scheduler host); don't need to worry
        # about contact file.
        return
    try:
        detect_old_contact_file(reg)
    except ServiceFileError as exc:
        raise ServiceFileError(
            f"Cannot clean running workflow {reg}.\n\n{exc}"
        )


def init_clean(id_: str, opts: 'Values') -> None:
    """Initiate the process of removing a stopped workflow from the local
    scheduler filesystem and remote hosts.

    Args:
        id_: Workflow ID.
        opts: CLI options object for cylc clean.

    """
    local_run_dir = Path(get_workflow_run_dir(id_))
    with suppress(InputError):
        local_run_dir, id_ = infer_latest_run(
            local_run_dir, implicit_runN=False, warn_runN=False
        )
    try:
        _clean_check(opts, id_, local_run_dir)
    except FileNotFoundError as exc:
        LOG.info(exc)
        return

    # Parse --rm option to make sure it's valid
    rm_dirs = parse_rm_dirs(opts.rm_dirs) if opts.rm_dirs else None

    if not opts.local_only:
        platform_names = None
        db_file = Path(get_workflow_srv_dir(id_), 'db')
        if not db_file.is_file():
            # no DB -> do nothing
            if opts.remote_only:
                raise ServiceFileError(
                    f"No workflow database for {id_} - cannot perform "
                    "remote clean"
                )
            LOG.info(
                f"No workflow database for {id_} - will only clean locally"
            )
        else:
            # DB present -> load platforms
            try:
                platform_names = get_platforms_from_db(local_run_dir)
            except ServiceFileError as exc:
                raise ServiceFileError(f"Cannot clean {id_} - {exc}")
            except sqlite3.OperationalError as exc:
                # something went wrong with the query
                # e.g. the table/field we need isn't there
                LOG.warning(
                    'This database is either corrupted or not compatible with'
                    ' this version of "cylc clean".'
                    '\nTry using the version of Cylc the workflow was last ran'
                    ' with to remove it.'
                    '\nOtherwise please delete the database file.'
                )
                raise ServiceFileError(f"Cannot clean {id_} - {exc}")

        if platform_names and platform_names != {'localhost'}:
            remote_clean(
                id_, platform_names, opts.rm_dirs, opts.remote_timeout
            )

    if not opts.remote_only:
        # Must be after remote clean
        clean(id_, local_run_dir, rm_dirs)


def clean(id_: str, run_dir: Path, rm_dirs: Optional[Set[str]] = None) -> None:
    """Remove a stopped workflow from the local filesystem only.

    Deletes the workflow run directory and any symlink dirs, or just the
    specified sub dirs if rm_dirs is specified.

    Note: if the run dir has already been manually deleted, it will not be
    possible to clean any symlink dirs.

    Args:
        id_: Workflow ID.
        run_dir: Absolute path of the workflow's run dir.
        rm_dirs: Set of sub dirs to remove instead of the whole run dir.

    """
    symlink_dirs = get_symlink_dirs(id_, run_dir)
    if rm_dirs is not None:
        # Targeted clean
        for pattern in rm_dirs:
            _clean_using_glob(run_dir, pattern, symlink_dirs)
    else:
        # Wholesale clean
        LOG.debug(f"Cleaning {run_dir}")
        for symlink in symlink_dirs:
            # Remove <symlink_dir>/cylc-run/<id>/<symlink>
            remove_dir_and_target(run_dir / symlink)
        if '' not in symlink_dirs:
            # if run dir isn't a symlink dir and hasn't been deleted yet
            remove_dir_and_target(run_dir)

    # Tidy up if necessary
    # Remove `runN` symlink if it's now broken
    runN = run_dir.parent / WorkflowFiles.RUN_N
    if (
        runN.is_symlink() and
        not run_dir.exists() and
        os.readlink(str(runN)) == run_dir.name
    ):
        runN.unlink()
    # Remove _cylc-install if it's the only thing left
    cylc_install_dir = run_dir.parent / WorkflowFiles.Install.DIRNAME
    for entry in run_dir.parent.iterdir():
        if entry == cylc_install_dir:
            continue
        break
    else:  # no break
        if cylc_install_dir.is_dir():
            remove_dir_or_file(cylc_install_dir)
    # Remove any empty parents of run dir up to ~/cylc-run/
    remove_empty_parents(run_dir, id_)
    for symlink, target in symlink_dirs.items():
        # Remove empty parents of symlink target up to <symlink_dir>/cylc-run/
        remove_empty_parents(target, Path(id_, symlink))


def get_symlink_dirs(reg: str, run_dir: Union[Path, str]) -> Dict[str, Path]:
    """Return the standard symlink dirs and their targets if they exist in
    the workflow run dir.

    Note: does not check the global config, only the existing run dir filetree.

    Raises WorkflowFilesError if a symlink points to an unexpected place.
    """
    ret: Dict[str, Path] = {}
    for _dir in sorted(WorkflowFiles.SYMLINK_DIRS, reverse=True):
        # ordered by deepest to shallowest
        path = Path(run_dir, _dir)
        if path.is_symlink():
            target = path.resolve()
            if target.exists() and not target.is_dir():
                raise WorkflowFilesError(
                    f'Invalid symlink at {path}.\n'
                    f'Link target is not a directory: {target}')
            expected_end = str(Path('cylc-run', reg, _dir))
            if not str(target).endswith(expected_end):
                raise WorkflowFilesError(
                    f'Invalid symlink at {path}\n'
                    f'The target should end with "{expected_end}"'
                )
            ret[_dir] = target
    return ret


def glob_in_run_dir(
    run_dir: Union[Path, str], pattern: str, symlink_dirs: Container[Path]
) -> List[Path]:
    """Execute a (recursive) glob search in the given run directory.

    Returns list of any absolute paths that match the pattern. However:
    * Does not follow symlinks (apart from the spcedified symlink dirs).
    * Also does not return matching subpaths of matching directories (because
        that would be redundant).

    Args:
        run_dir: Absolute path of the workflow run dir.
        pattern: The glob pattern.
        symlink_dirs: Absolute paths to the workflow's symlink dirs.
    """
    # Note: use os.path.join, not pathlib, to preserve trailing slash if
    # present in pattern
    pattern = os.path.join(glob.escape(str(run_dir)), pattern)
    # Note: don't use pathlib.Path.glob() because when you give it an exact
    # filename instead of pattern, it doesn't return broken symlinks
    matches = sorted(Path(i) for i in glob.iglob(pattern, recursive=True))
    # sort guarantees parents come before their children
    if len(matches) == 1 and not os.path.lexists(matches[0]):
        # https://bugs.python.org/issue35201
        return []
    results: List[Path] = []
    subpath_excludes: Set[Path] = set()
    for path in matches:
        for rel_ancestor in reversed(path.relative_to(run_dir).parents):
            ancestor = run_dir / rel_ancestor
            if ancestor in subpath_excludes:
                break
            if ancestor.is_symlink() and ancestor not in symlink_dirs:
                # Do not follow non-standard symlinks
                subpath_excludes.add(ancestor)
                break
            if not symlink_dirs and (ancestor in results):
                # We can be sure all subpaths of this ancestor are redundant
                subpath_excludes.add(ancestor)
                break
            if ancestor == path.parent:  # noqa: SIM102
                # Final iteration over ancestors
                if ancestor in matches and path not in symlink_dirs:
                    # Redundant (but don't exclude subpaths in case any of the
                    # subpaths are std symlink dirs)
                    break
        else:  # No break
            results.append(path)
    return results


def _clean_using_glob(
    run_dir: Path, pattern: str, symlink_dirs: Iterable[str]
) -> None:
    """Delete the files/dirs in the run dir that match the pattern.

    Does not follow symlinks (apart from the standard symlink dirs).

    Args:
        run_dir: Absolute path of workflow run dir.
        pattern: The glob pattern.
        symlink_dirs: Paths of the workflow's symlink dirs relative to
            the run dir.
    """
    abs_symlink_dirs = tuple(sorted(
        (run_dir / d for d in symlink_dirs),
        reverse=True  # ordered by deepest to shallowest
    ))
    matches = glob_in_run_dir(run_dir, pattern, abs_symlink_dirs)
    if not matches:
        LOG.info(f"No files matching '{pattern}' in {run_dir}")
        return
    # First clean any matching symlink dirs
    for path in abs_symlink_dirs:
        if path in matches:
            remove_dir_and_target(path)
            if path == run_dir:
                # We have deleted the run dir
                return
            matches.remove(path)
    # Now clean the rest
    for path in matches:
        remove_dir_or_file(path)


def remote_clean(
    reg: str,
    platform_names: Iterable[str],
    rm_dirs: Optional[List[str]] = None,
    timeout: str = '120'
) -> None:
    """Run subprocesses to clean workflows on remote install targets
    (skip localhost), given a set of platform names to look up.

    Args:
        reg: Workflow name.
        platform_names: List of platform names to look up in the global
            config, in order to determine the install targets to clean on.
        rm_dirs: Sub dirs to remove instead of the whole run dir.
        timeout: Number of seconds to wait before cancelling.
    """
    try:
        install_targets_map = (
            get_install_target_to_platforms_map(platform_names))
    except PlatformLookupError as exc:
        raise PlatformLookupError(
            f"Cannot clean {reg} on remote platforms as the workflow database "
            f"is out of date/inconsistent with the global config - {exc}")
    queue: Deque[RemoteCleanQueueTuple] = deque()
    remote_clean_cmd = partial(
        _remote_clean_cmd, reg=reg, rm_dirs=rm_dirs, timeout=timeout
    )
    for target, platforms in install_targets_map.items():
        if target == get_localhost_install_target():
            continue
        shuffle(platforms)
        LOG.info(
            f"Cleaning {reg} on install target: "
            f"{platforms[0]['install target']}"
        )
        # Issue ssh command:
        queue.append(
            RemoteCleanQueueTuple(
                remote_clean_cmd(platform=platforms[0]), target, platforms
            )
        )
    failed_targets: Dict[str, PlatformError] = {}
    # Handle subproc pool results almost concurrently:
    while queue:
        item = queue.popleft()
        ret_code = item.proc.poll()
        if ret_code is None:  # proc still running
            queue.append(item)
            continue
        out, err = item.proc.communicate()
        if out:
            LOG.info(f"[{item.install_target}]\n{out}")
        if ret_code:
            this_platform = item.platforms.pop(0)
            excp = PlatformError(
                PlatformError.MSG_TIDY,
                this_platform['name'],
                cmd=item.proc.args,
                ret_code=ret_code,
                out=out,
                err=err,
            )
            if ret_code == 255 and item.platforms:
                # SSH error; try again using the next platform for this
                # install target
                LOG.debug(excp)
                queue.append(
                    item._replace(
                        proc=remote_clean_cmd(platform=item.platforms[0])
                    )
                )
            else:  # Exhausted list of platforms
                failed_targets[item.install_target] = excp
        elif err:
            # Only show stderr from remote host in debug mode if ret code 0
            # because stderr often contains useless stuff like ssh login
            # messages
            LOG.debug(f"[{item.install_target}]\n{err}")
        sleep(0.2)
    if failed_targets:
        for target, excp in failed_targets.items():
            LOG.error(
                f"Could not clean {reg} on install target: {target}\n{excp}"
            )
        raise CylcError(f"Remote clean failed for {reg}")


def _remote_clean_cmd(
    reg: str,
    platform: Dict[str, Any],
    rm_dirs: Optional[List[str]],
    timeout: str
) -> 'Popen[str]':
    """Remove a stopped workflow on a remote host.

    Call "cylc clean --local-only" over ssh and return the subprocess.

    Args:
        reg: Workflow name.
        platform: Config for the platform on which to remove the workflow.
        rm_dirs: Sub dirs to remove instead of the whole run dir.
        timeout: Number of seconds to wait before cancelling the command.

    Raises:
        NoHostsError: If the platform is not contactable.

    """
    LOG.debug(
        f"Cleaning {reg} on install target: {platform['install target']} "
        f"(using platform: {platform['name']})"
    )
    cmd = ['clean', '--local-only', reg]
    if rm_dirs is not None:
        for item in rm_dirs:
            cmd.extend(['--rm', item])
    cmd = construct_ssh_cmd(
        cmd,
        platform,
        get_host_from_platform(platform),
        timeout=timeout,
        set_verbosity=True,
    )
    LOG.debug(" ".join(cmd))
    return Popen(  # nosec
        cmd,
        stdin=DEVNULL,
        stdout=PIPE,
        stderr=PIPE,
        text=True,
    )
    # * command constructed by internal interface


def remove_keys_on_server(keys):
    """Removes server-held authentication keys"""
    # WARNING, DESTRUCTIVE. Removes old keys if they already exist.
    for k in keys.values():
        if os.path.exists(k.full_key_path):
            os.remove(k.full_key_path)
    # Remove client public key folder
    client_public_key_dir = keys["client_public_key"].key_path
    if os.path.exists(client_public_key_dir):
        shutil.rmtree(client_public_key_dir, onerror=handle_rmtree_err)


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
    with open(get_flow_file(reg), 'r') as handle:
        for line in handle:
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


def get_platforms_from_db(run_dir):
    """Return the set of names of platforms (that jobs ran on) from the DB.

    Warning:
        This does NOT upgrade the workflow database!

        We could upgrade the DB for backward compatiblity, but we haven't
        got any upgraders for this table yet so there's no point.

        Note that upgrading the DB here would not help with forward
        compatibility. We can't apply upgraders which don't exist yet.

    Args:
        run_dir (str): The workflow run directory.

    Raises:
        sqlite3.OperationalError: in the event the table/field required for
        cleaning is not present.

    """
    workflow_db_mgr = WorkflowDatabaseManager(
        os.path.join(run_dir, WorkflowFiles.Service.DIRNAME))
    with workflow_db_mgr.get_pri_dao() as pri_dao:
        platform_names = pri_dao.select_task_job_platforms()

    return platform_names


def check_deprecation(path, warn=True):
    """Warn and turn on back-compat flag if Cylc 7 suite.rc detected.

    Path can point to config file or parent directory (i.e. workflow name).
    """
    if (
        path.resolve().name == WorkflowFiles.SUITE_RC
        or (path / WorkflowFiles.SUITE_RC).is_file()
    ):
        cylc.flow.flags.cylc7_back_compat = True
        if warn:
            LOG.warning(SUITERC_DEPR_MSG)


def validate_workflow_name(
    name: str, check_reserved_names: bool = False
) -> None:
    """Check workflow name/ID is valid and not an absolute path.

    Args:
        name: Workflow name or ID.
        check_reserved_names: If True, check that the name does not
            contain reserved dir names.

    Raise WorkflowFilesError if not valid.
    """
    is_valid, message = WorkflowNameValidator.validate(name)
    if not is_valid:
        raise WorkflowFilesError(
            f"invalid workflow name '{name}' - {message}"
        )
    if os.path.isabs(name):
        raise WorkflowFilesError(
            f"workflow name cannot be an absolute path: {name}"
        )
    name = os.path.normpath(name)
    if name.startswith(os.curdir):
        raise WorkflowFilesError(
            "Workflow name cannot be a path that points to the cylc-run "
            "directory or above"
        )
    if check_reserved_names:
        check_reserved_dir_names(name)


def check_reserved_dir_names(name: Union[Path, str]) -> None:
    """Check workflow/run name does not contain reserved dir names."""
    err_msg = (
        "Workflow/run name cannot contain a directory named '{}' "
        "(that filename is reserved)"
    )
    for dir_name in Path(name).parts:
        if dir_name in WorkflowFiles.RESERVED_NAMES:
            raise WorkflowFilesError(err_msg.format(dir_name))
        if re.match(r'^run\d+$', dir_name):
            raise WorkflowFilesError(err_msg.format('run<number>'))


def infer_latest_run_from_id(workflow_id: str) -> str:
    run_dir = Path(get_workflow_run_dir(workflow_id))
    _, reg = infer_latest_run(run_dir)
    return reg


def infer_latest_run(
    path: Path,
    implicit_runN: bool = True,
    warn_runN: bool = True,
) -> Tuple[Path, str]:
    """Infer the numbered run dir if the workflow has a runN symlink.

    Args:
        path: Absolute path to the workflow dir, run dir or runN dir.
        implicit_runN: If True, add runN on the end of the path if the path
            doesn't include it.
        warn_runN: If True, warn that explicit use of runN is unnecessary.

    Returns:
        path: Absolute path of the numbered run dir if applicable, otherwise
            the input arg path.
        reg: The workflow name (including the numbered run if applicable).

    Raises:
        - WorkflowFilesError if the runN symlink is not valid.
        - InputError if the path does not exist.
    """
    cylc_run_dir = get_cylc_run_dir()
    try:
        reg = str(path.relative_to(cylc_run_dir))
    except ValueError:
        raise ValueError(f"{path} is not in the cylc-run directory")
    if not path.exists():
        raise InputError(
            f'Workflow ID not found: {reg}\n(Directory not found: {path})'
        )
    if path.name == WorkflowFiles.RUN_N:
        runN_path = path
        if warn_runN:
            LOG.warning(
                f"You do not need to include {WorkflowFiles.RUN_N} in the "
                "workflow ID; Cylc will select the latest run if just the "
                "workflow name is used"
            )
    elif implicit_runN:
        runN_path = path / WorkflowFiles.RUN_N
        if not os.path.lexists(runN_path):
            return (path, reg)
    else:
        return (path, reg)
    if not runN_path.is_symlink() or not runN_path.is_dir():
        raise WorkflowFilesError(
            f"{runN_path} symlink not valid"
        )
    numbered_run = os.readlink(runN_path)
    if not re.match(r'run\d+$', numbered_run):
        # Note: the link should be relative. This means it won't work for
        # cylc 8.0b1 workflows where it was absolute (won't fix).
        raise WorkflowFilesError(
            f"{runN_path} symlink target not valid: {numbered_run}"
        )
    path = runN_path.parent / numbered_run
    reg = str(path.relative_to(cylc_run_dir))
    return (path, reg)


def check_nested_dirs(
    run_dir: Path,
    install_dir: Optional[Path] = None
) -> None:
    """Disallow nested dirs:

    - Nested installed run dirs
    - Nested installed workflow dirs

    Args:
        run_dir: Absolute workflow run directory path.
        install_dir: Absolute workflow install directory path
            (contains _cylc-install). If None, will not check for nested
            install dirs.

    Raises:
        WorkflowFilesError if reg dir is nested inside a run dir, or an
            install dirs are nested.
    """
    if install_dir is not None:
        install_dir = Path(os.path.normpath(install_dir))
    # Check parents:
    for parent_dir in run_dir.parents:
        # Stop searching at ~/cylc-run
        if parent_dir == Path(get_cylc_run_dir()):
            break
        # check for run directories:
        if is_valid_run_dir(parent_dir):
            raise WorkflowFilesError(
                NESTED_DIRS_MSG.format(
                    dir_type='run',
                    dest=run_dir,
                    existing=get_cylc_run_abs_path(parent_dir)
                )
            )
        # Check for install directories:
        if (
            install_dir
            and parent_dir in install_dir.parents
            and (parent_dir / WorkflowFiles.Install.DIRNAME).is_dir()
        ):
            raise WorkflowFilesError(
                NESTED_DIRS_MSG.format(
                    dir_type='install',
                    dest=run_dir,
                    existing=get_cylc_run_abs_path(parent_dir)
                )
            )

    if install_dir:
        # Search child tree for install directories:
        for depth in range(glbl_cfg().get(['install', 'max depth'])):
            search_pattern = f'*/{"*/" * depth}{WorkflowFiles.Install.DIRNAME}'
            for result in install_dir.glob(search_pattern):
                raise WorkflowFilesError(
                    NESTED_DIRS_MSG.format(
                        dir_type='install',
                        dest=run_dir,
                        existing=get_cylc_run_abs_path(result.parent)
                    )
                )


def is_valid_run_dir(path: Union[Path, str]) -> bool:
    """Return True if path is a valid, existing run directory, else False.

    Args:
        path: if this is a relative path, it is taken to be relative to
            the cylc-run directory.
    """
    path = get_cylc_run_abs_path(path)
    return (
        Path(path, WorkflowFiles.FLOW_FILE).is_file() or
        Path(path, WorkflowFiles.SUITE_RC).is_file() or
        Path(path, WorkflowFiles.Service.DIRNAME).is_dir()
    )


def get_cylc_run_abs_path(path: Union[Path, str]) -> Union[Path, str]:
    """Return the absolute path under the cylc-run directory for the specified
    relative path.

    If the specified path is already absolute, just return it.
    The path need not exist.
    """
    if os.path.isabs(path):
        return path
    return get_workflow_run_dir(path)


def _get_logger(rund, log_name, open_file=True):
    """Get log and create and open if necessary.

    Args:
        rund:
            The workflow run directory of the associated workflow.
        log_name:
            The name of the log to open.
        open_file:
            Open the appropriate log file and add it as a file handler to
            the logger. I.E. Start writing the log to a file if not already
            doing so.

    """
    logger = logging.getLogger(log_name)
    if logger.getEffectiveLevel != logging.INFO:
        logger.setLevel(logging.INFO)
    if open_file and not logger.hasHandlers():
        _open_install_log(rund, logger)
    return logger


def _open_install_log(rund, logger):
    """Open Cylc log handlers for install/reinstall."""
    rund = Path(rund).expanduser()
    log_type = logger.name[logger.name.startswith('cylc-') and len('cylc-'):]
    log_dir = Path(
        rund, WorkflowFiles.LogDir.DIRNAME, WorkflowFiles.LogDir.INSTALL)
    log_files = get_sorted_logs_by_time(log_dir, '*.log')
    log_num = get_next_log_number(log_files[-1]) if log_files else 1
    log_path = Path(log_dir, f"{log_num:02d}-{log_type}.log")
    log_parent_dir = log_path.parent
    log_parent_dir.mkdir(exist_ok=True, parents=True)
    handler = logging.FileHandler(log_path)
    handler.setFormatter(CylcLogFormatter())
    logger.addHandler(handler)


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
    rsync_cmd = shlex.split(
        glbl_cfg().get(['platforms', 'localhost', 'rsync command'])
    )
    rsync_cmd += DEFAULT_RSYNC_OPTS
    if dry_run:
        rsync_cmd.append("--dry-run")
    if reinstall:
        rsync_cmd.append('--delete')

    exclusions = [
        '.git',
        '.svn',
        '.cylcignore',
        'opt/rose-suite-cylc-install.conf',
        WorkflowFiles.LogDir.DIRNAME,
        WorkflowFiles.WORK_DIR,
        WorkflowFiles.SHARE_DIR,
        WorkflowFiles.Install.DIRNAME,
        WorkflowFiles.Service.DIRNAME
    ]

    # This is a hack to make sure that changes to rose-suite.conf
    # are considered when re-installing.
    # It should be removed after https://github.com/cylc/cylc-rose/issues/149
    if not dry_run:
        exclusions.append('rose-suite.conf')

    for exclude in exclusions:
        if (
            Path(src).joinpath(exclude).exists() or
            Path(dst).joinpath(exclude).exists()
        ):
            # Note '/' is the rsync "anchor" to the top level:
            rsync_cmd.append(f"--exclude=/{exclude}")
    cylcignore_file = Path(src).joinpath('.cylcignore')
    if cylcignore_file.exists():
        rsync_cmd.append(f"--exclude-from={cylcignore_file}")
    rsync_cmd.append(f"{src}/")
    rsync_cmd.append(f"{dst}/")

    return rsync_cmd


def reinstall_workflow(
    source: Path,
    named_run: str,
    rundir: Path,
    dry_run: bool = False
) -> str:
    """Reinstall workflow.

    Args:
        source: source directory
        named_run: name of the run e.g. my-flow/run1
        rundir: run directory
        dry_run: if True, will not execute the file transfer but report what
            would be changed.

    Raises:
        WorkflowFilesError:
            If rsync returns non-zero.

    Returns:
        Stdout from the rsync command.

    """
    validate_source_dir(source, named_run)
    check_nested_dirs(rundir)
    reinstall_log = _get_logger(
        rundir,
        'cylc-reinstall',
        open_file=not dry_run,  # don't open the log file for --dry-run
    )
    reinstall_log.info(
        f'Reinstalling "{named_run}", from "{source}" to "{rundir}"'
    )
    rsync_cmd = get_rsync_rund_cmd(
        source,
        rundir,
        reinstall=True,
        dry_run=dry_run,
    )

    # Add '+++' to -out-format to mark lines passed through formatter.
    rsync_cmd.append('--out-format=+++%o %n%L+++')

    # Run rsync command:
    reinstall_log.info(cli_format(rsync_cmd))
    LOG.debug(cli_format(rsync_cmd))
    proc = Popen(rsync_cmd, stdout=PIPE, stderr=PIPE, text=True)  # nosec
    # * command is constructed via internal interface
    stdout, stderr = proc.communicate()

    # Strip unwanted output.
    stdout = ('\n'.join(re.findall(r'\+\+\+(.*)\+\+\+', stdout))).strip()
    stderr = stderr.strip()

    if proc.returncode != 0:
        raise WorkflowFilesError(
            f'An error occurred reinstalling from {source} to {rundir}'
            f'\n{stderr}'
        )

    check_flow_file(rundir)
    reinstall_log.info(f'REINSTALLED {named_run} from {source}')
    print(
        f'REINSTALL{"ED" if not dry_run else ""} {named_run} from {source}'
    )
    close_log(reinstall_log)
    return stdout


def abort_if_flow_file_in_path(source: Path) -> None:
    """Raise an exception if a flow file is found in a source path.

    This allows us to avoid seemingly silly warnings that "path/flow.cylc"
    is not a valid workflow ID, when "path" is valid and the user was just
    (erroneously) trying to (e.g.) validate the config file directly.

    """
    if source.name in {WorkflowFiles.FLOW_FILE, WorkflowFiles.SUITE_RC}:
        raise InputError(
            f"Not a valid workflow ID or source directory: {source}"
            f"\n(Note you should not include {source.name}"
            " in the workflow source path)"
        )


def install_workflow(
    source: Path,
    workflow_name: Optional[str] = None,
    run_name: Optional[str] = None,
    no_run_name: bool = False,
    cli_symlink_dirs: Optional[Dict[str, Dict[str, Any]]] = None
) -> Tuple[Path, Path, str, str]:
    """Install a workflow, or renew its installation.

    Install workflow into new run directory.
    Create symlink to workflow source location, creating any symlinks for run,
    work, log, share, share/cycle directories.

    Args:
        source: absolute path to workflow source directory.
        workflow_name: workflow name, default basename($PWD).
        run_name: name of the run, overrides run1, run2, run 3 etc...
            If specified, cylc install will not create runN symlink.
        rundir: for overriding the default cylc-run directory.
        no_run_name: Flag as True to install workflow into
            ~/cylc-run/<workflow_name>
        cli_symlink_dirs: Symlink dirs, if entered on the cli.

    Return:
        source: absolute path to source directory.
        rundir: absolute path to run directory, where the workflow has been
            installed into.
        workflow_name: installed workflow name (which may be computed here).
        named_run: Name of the run.

    Raise:
        WorkflowFilesError:
            No flow.cylc file found in source location.
            Illegal name (can look like a relative path, but not absolute).
            Another workflow already has this name.
            Trying to install a workflow that is nested inside of another.
    """
    abort_if_flow_file_in_path(source)
    source = Path(expand_path(source)).resolve()
    if not workflow_name:
        workflow_name = get_source_workflow_name(source)
    validate_workflow_name(workflow_name, check_reserved_names=True)
    if run_name is not None:
        if len(Path(run_name).parts) != 1:
            raise WorkflowFilesError(
                f'Run name cannot be a path. (You used {run_name})'
            )
        check_reserved_dir_names(run_name)
    validate_source_dir(source, workflow_name)
    run_path_base = Path(get_workflow_run_dir(workflow_name))
    relink, run_num, rundir = get_run_dir_info(
        run_path_base, run_name, no_run_name
    )
    max_scan_depth = glbl_cfg().get(['install', 'max depth'])
    workflow_id = rundir.relative_to(get_cylc_run_dir())
    if len(workflow_id.parts) > max_scan_depth:
        raise WorkflowFilesError(
            f"Cannot install: workflow ID '{workflow_id}' would exceed "
            f"global.cylc[install]max depth = {max_scan_depth}"
        )
    check_nested_dirs(rundir, run_path_base)
    if rundir.exists():
        raise WorkflowFilesError(
            f"'{rundir}' already exists\n"
            "To reinstall, use `cylc reinstall`"
        )
    symlinks_created = {}
    named_run = workflow_name
    if run_name:
        named_run = os.path.join(named_run, run_name)
    elif run_num:
        named_run = os.path.join(named_run, f'run{run_num}')
    symlinks_created = make_localhost_symlinks(
        rundir, named_run, symlink_conf=cli_symlink_dirs)
    install_log = _get_logger(rundir, 'cylc-install')
    if symlinks_created:
        for target, symlink in symlinks_created.items():
            install_log.info(f"Symlink created: {symlink} -> {target}")
    try:
        rundir.mkdir(exist_ok=True, parents=True)
    except FileExistsError:
        # This occurs when the file exists but is _not_ a directory.
        raise WorkflowFilesError(
            f"Cannot install as there is an existing file at {rundir}."
        )
    if relink:
        link_runN(rundir)
    rsync_cmd = get_rsync_rund_cmd(source, rundir)
    proc = Popen(rsync_cmd, stdout=PIPE, stderr=PIPE, text=True)  # nosec
    # * command is constructed via internal interface
    stdout, stderr = proc.communicate()
    install_log.info(
        f"Copying files from {source} to {rundir}"
        f"\n{stdout}"
    )
    if proc.returncode != 0:
        install_log.warning(
            f"An error occurred when copying files from {source} to {rundir}")
        install_log.warning(f" Warning: {stderr}")
    cylc_install = Path(rundir.parent, WorkflowFiles.Install.DIRNAME)
    check_deprecation(check_flow_file(rundir))
    if no_run_name:
        cylc_install = Path(rundir, WorkflowFiles.Install.DIRNAME)
    source_link = cylc_install.joinpath(WorkflowFiles.Install.SOURCE)
    # check source link matches the source symlink from workflow dir.
    cylc_install.mkdir(parents=True, exist_ok=True)
    if not source_link.exists():
        if source_link.is_symlink():
            # Condition represents a broken symlink.
            raise WorkflowFilesError(
                f'Symlink broken: {source_link} -> {source_link.resolve()}.'
            )
        install_log.info(f"Creating symlink from {source_link}")
        source_link.symlink_to(source.resolve())
    else:
        if source_link.resolve() != source.resolve():
            raise WorkflowFilesError(
                f"Failed to install from {source.resolve()}: "
                f"previous installations were from {source_link.resolve()}"
            )
        install_log.info(
            f'Symlink from "{source_link}" to "{source}" in place.')
    install_log.info(f'INSTALLED {named_run} from {source}')
    print(f'INSTALLED {named_run} from {source}')
    close_log(install_log)
    return source, rundir, workflow_name, named_run


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
        if run_path_base.exists() and detect_flow_exists(run_path_base, True):
            raise WorkflowFilesError(
                f"--run-name option not allowed as '{run_path_base}' contains "
                "installed numbered runs."
            )
    else:
        run_num = get_next_rundir_number(run_path_base)
        rundir = Path(run_path_base, f'run{run_num}')
        if run_path_base.exists() and detect_flow_exists(run_path_base, False):
            raise WorkflowFilesError(
                f"Path: \"{run_path_base}\" contains an installed"
                " workflow. Use --run-name to create a new run."
            )
        unlink_runN(run_path_base)
        relink = True
    return relink, run_num, rundir


def detect_both_flow_and_suite(path: Path) -> None:
    """Detects if both suite.rc and flow.cylc are in directory.

    Permits flow.cylc to be a symlink.
    Return true if present, raises error if flow.cylc path sent is a forbidden
    symlink.
    Raises:
        WorkflowFilesError: If both flow.cylc and suite.rc are in directory
    """
    flow_cylc = None
    msg = (f"Both {WorkflowFiles.FLOW_FILE} and {WorkflowFiles.SUITE_RC} "
           f"files are present in {path}. Please remove one and"
           " try again. For more information visit: https://cylc.github.io/"
           "cylc-doc/stable/html/7-to-8/summary.html#backward-compatibility")
    if path.resolve().name == WorkflowFiles.SUITE_RC:
        flow_cylc = path.parent / WorkflowFiles.FLOW_FILE
    elif (path / WorkflowFiles.SUITE_RC).is_file():
        flow_cylc = path / WorkflowFiles.FLOW_FILE
    if flow_cylc and flow_cylc.is_file() and is_forbidden(flow_cylc):
        raise WorkflowFilesError(msg)


def is_forbidden(flow_file: Path) -> bool:
    """Returns True for a forbidden file structure scenario.

    Forbidden criteria:
        A symlink elsewhere on file system but suite.rc also exists in the
        directory.
        flow.cylc and suite.rc in same directory but no symlink
    Args:
        flow_file : Absolute Path to the flow.cylc file
    """
    if not flow_file.is_symlink():
        if flow_file.parent.joinpath(WorkflowFiles.SUITE_RC).exists():
            return True
        return False
    link = flow_file.resolve()
    suite_rc = flow_file.parent.resolve() / WorkflowFiles.SUITE_RC
    if link == suite_rc:
        # link points within dir to suite.rc (permitted)
        return False
    # link points elsewhere, check that suite.rc does not also exist in dir
    if suite_rc.exists():
        return True
    return False


def detect_flow_exists(
    run_path_base: Union[Path, str], numbered: bool
) -> bool:
    """Returns True if installed flow already exists.

    Args:
        run_path_base: Absolute path of workflow directory,
            i.e ~/cylc-run/<workflow_name>
        numbered: If True, will detect if numbered runs exist. If False, will
            detect if non-numbered runs exist, i.e. runs installed
            by --run-name.
    """
    for entry in Path(run_path_base).iterdir():
        is_numbered = bool(re.search(r'^run\d+$', entry.name))
        if (
            entry.is_dir()
            and entry.name not in {
                WorkflowFiles.Install.DIRNAME, WorkflowFiles.RUN_N
            }
            and Path(entry, WorkflowFiles.FLOW_FILE).exists()
            and is_numbered == numbered
        ):
            return True
    return False


def check_flow_file(path: Union[Path, str]) -> Path:
    """Checks the path for a suite.rc or flow.cylc file.

    Raises:
        WorkflowFilesError
            - if no flow file in path sent
            - both suite.rc and flow.cylc in path sent.

    Args:
        path: Absolute path to check for a flow.cylc and/or suite.rc file.

    Returns the path of the flow file if present.
    """
    flow_file_path = Path(expand_path(path), WorkflowFiles.FLOW_FILE)
    suite_rc_path = Path(expand_path(path), WorkflowFiles.SUITE_RC)
    if flow_file_path.is_file():
        detect_both_flow_and_suite(Path(path))
        return flow_file_path
    if suite_rc_path.is_file():
        return suite_rc_path
    raise WorkflowFilesError(NO_FLOW_FILE_MSG.format(path))


def validate_source_dir(
    source: Union[Path, str], workflow_name: str
) -> None:
    """Ensure the source directory is valid:
        - has flow file
        - does not contain reserved dir names

    Args:
        source: Path to source directory
    Raises:
        WorkflowFilesError:
            If log, share, work or _cylc-install directories exist in the
            source directory.
    """
    # Source dir must not contain reserved run dir names (as file or dir).
    for dir_ in WorkflowFiles.RESERVED_DIRNAMES:
        if Path(source, dir_).exists():
            raise WorkflowFilesError(
                f"{workflow_name} installation failed "
                f"- {dir_} exists in source directory."
            )
    check_flow_file(source)


def parse_cli_sym_dirs(symlink_dirs: str) -> Dict[str, Dict[str, Any]]:
    """Converts command line entered symlink dirs to a dictionary.

    Args:
        symlink_dirs: As entered by user on cli,
                            e.g. "log=$DIR, share=$DIR2".

    Raises:
        WorkflowFilesError: If directory to be symlinked is not in permitted
                            dirs: run, log, share, work, share/cycle

    Returns:
        dict: In the same form as would be returned by global config.
            e.g. {'localhost': {'log': '$DIR',
                                'share': '$DIR2'
                                }
                }
    """
    # Ensures the same nested dict format which is returned by the glb cfg
    symdict: Dict[str, Dict[str, Any]] = {'localhost': {'run': None}}
    if symlink_dirs == "":
        return symdict
    symlist = symlink_dirs.strip(',').split(',')
    possible_symlink_dirs = set(WorkflowFiles.SYMLINK_DIRS.union(
        {WorkflowFiles.RUN_DIR})
    )
    possible_symlink_dirs.remove('')
    for pair in symlist:
        try:
            key, val = pair.split("=")
            key = key.strip()
        except ValueError:
            raise InputError(
                'There is an error in --symlink-dirs option:'
                f' {pair}. Try entering option in the form '
                '--symlink-dirs=\'log=$DIR, share=$DIR2, ...\''
            )
        if key not in possible_symlink_dirs:
            dirs = ', '.join(possible_symlink_dirs)
            raise InputError(
                f"{key} not a valid entry for --symlink-dirs. "
                f"Configurable symlink dirs are: {dirs}"
            )
        symdict['localhost'][key] = val.strip() or None

    return symdict


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
    with suppress(OSError):
        run_n.symlink_to(latest_run.name)


def search_install_source_dirs(workflow_name: Union[Path, str]) -> Path:
    """Return the path of a workflow source dir if it is present in the
    'global.cylc[install]source dirs' search path."""
    abort_if_flow_file_in_path(Path(workflow_name))
    search_path: List[str] = get_source_dirs()
    if not search_path:
        raise WorkflowFilesError(
            "Cannot find workflow as 'global.cylc[install]source dirs' "
            "does not contain any paths")
    for path in search_path:
        try:
            return check_flow_file(Path(path, workflow_name)).parent
        except WorkflowFilesError:
            continue
    raise WorkflowFilesError(
        f"Could not find workflow '{workflow_name}' in: "
        f"{', '.join(search_path)}")


def get_source_workflow_name(source: Path) -> str:
    """Return workflow name relative to configured source dirs if possible,
    else the basename of the given path.
    Note the source path provided should be fully expanded (user and env vars)
    and normalised.
    """
    for dir_ in get_source_dirs():
        try:
            return str(source.relative_to(Path(expand_path(dir_)).resolve()))
        except ValueError:
            continue
    return source.name


def get_source_dirs() -> List[str]:
    return glbl_cfg().get(['install', 'source dirs'])
