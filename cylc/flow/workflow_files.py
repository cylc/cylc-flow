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

"""Files which define workflows or are created by Cylc.

See also:
* cylc.flow.install - for installing files from source dirs into the run dir.
* cylc.flow.clean - for removing files from the run dir.

"""

from contextlib import suppress
from enum import Enum
import errno
from queue import deque
import os
from pathlib import Path
import re
import shutil
from subprocess import (
    PIPE,
    Popen,
    TimeoutExpired,
)
from typing import (
    Callable,
    Dict,
    Optional,
    Tuple,
    Union,
    NoReturn,
    Type,
)

import cylc.flow.flags
from cylc.flow import LOG
from cylc.flow.async_util import make_async
from cylc.flow.exceptions import (
    ContactFileExists,
    CylcError,
    InputError,
    ServiceFileError,
    WorkflowFilesError,
    FileRemovalError,
)
from cylc.flow.hostuserutil import (
    get_user,
    is_remote_host,
)
from cylc.flow.pathutil import (
    SYMLINKABLE_LOCATIONS,
    expand_path,
    get_cylc_run_dir,
    get_workflow_run_dir,
    get_alt_workflow_run_dir,
    make_localhost_symlinks,
)
from cylc.flow.unicode_rules import WorkflowNameValidator
from cylc.flow.util import cli_format


def handle_rmtree_err(
    function: Callable,
    path: str,
    excinfo: Tuple[Type[Exception], Exception, object]
) -> NoReturn:
    """Error handler for shutil.rmtree."""
    exc = excinfo[1]
    if isinstance(exc, OSError) and exc.errno == errno.ENOTEMPTY:
        # "Directory not empty", likely due to filesystem lag
        raise FileRemovalError(exc)
    raise exc


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

    def __init__(
        self,
        key_type: KeyType,
        key_owner: KeyOwner,
        full_key_path: Optional[str] = None,
        workflow_srv_dir: Optional[str] = None,
        install_target: Optional[str] = None,
        server_held: bool = True
    ):
        self.key_type = key_type
        self.key_owner = key_owner
        self.workflow_srv_dir = workflow_srv_dir
        self.install_target = install_target
        if full_key_path is not None:
            self.key_path, self.file_name = os.path.split(full_key_path)
        elif self.workflow_srv_dir is not None:  # noqa: SIM106
            # Build key filename
            file_name = key_owner.value

            # Add optional install target name
            if (key_owner is KeyOwner.CLIENT
                and key_type is KeyType.PUBLIC
                    and self.install_target is not None):
                file_name = f"{file_name}_{self.install_target}"

            if key_type is KeyType.PRIVATE:
                file_extension = WorkflowFiles.Service.PRIVATE_FILE_EXTENSION
            else:
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

        DB = 'db'
        """The public database"""

        JOB = 'job'
        """The job log directory."""

    LOG_JOB_DIR = os.path.join(LogDir.DIRNAME, LogDir.JOB)

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

    SYMLINK_DIRS = frozenset(list(SYMLINKABLE_LOCATIONS) + [''])
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


REG_DELIM = "/"

NO_TITLE = "No title provided"
REC_TITLE = re.compile(r"^\s*title\s*=\s*(.*)\s*$")

CONTACT_FILE_EXISTS_MSG = r"""workflow contact file exists: %(fname)s

Workflow "%(workflow)s" is already running, listening at "%(host)s:%(port)s".

If you like, you can stop it with one or more of the following commands:
* cylc stop %(workflow)s              # wait for active tasks/event handlers
* cylc stop --kill %(workflow)s       # kill active tasks and wait
* cylc stop --now %(workflow)s        # don't wait for active tasks
* cylc stop --now --now %(workflow)s  # don't wait for tasks or handlers
* ssh -n "%(host)s" kill %(pid)s      # final brute force!
"""

SUITERC_DEPR_MSG = "Backward compatibility mode ON"

NO_FLOW_FILE_MSG = (
    f"No {WorkflowFiles.FLOW_FILE} or {WorkflowFiles.SUITE_RC} "
    "in {}"
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
    from cylc.flow.remote import construct_cylc_server_ssh_cmd
    from cylc.flow.terminal import parse_dirty_json

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
            f'Attempt to determine whether workflow is running on {host}'
            ' timed out after 10 seconds.'
        ) from None

    if proc.returncode == 2:
        # the psutil call failed to gather metrics on the process
        # because the process does not exist
        return False

    error = False
    if proc.returncode:
        # the psutil call failed in some other way e.g. network issues
        LOG.warning(
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
    id_: str, contact_data=None
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
      ContactFileExists.

    Args:
        id_: workflow ID
        contact_date:

    Raises:
        CylcError:
            If it is not possible to tell for sure if the workflow is running
            or not.
        ContactFileExists:
            If old contact file exists and the workflow process still alive.
        ServiceFileError:
            For corrupt / incompatible contact files.

    """
    # An old workflow of the same name may be running if a contact file exists
    # and can be loaded.
    if not contact_data:
        try:
            contact_data = load_contact_file(id_)
        except (IOError, ValueError, ServiceFileError):
            # Contact file does not exist or corrupted, workflow should be dead
            return

    try:
        old_host: str = contact_data[ContactFileFields.HOST]
        old_port: str = contact_data[ContactFileFields.PORT]
        old_pid: str = contact_data[ContactFileFields.PID]
        old_cmd: str = contact_data[ContactFileFields.COMMAND]
    except KeyError as exc:
        # this can happen if contact file is from an outdated version of Cylc
        raise ServiceFileError(
            f'Found contact file with incomplete data:\n{exc}.'
        ) from None

    # check if the workflow process is running ...
    # NOTE: can raise CylcError
    process_is_running = _is_process_running(old_host, old_pid, old_cmd)

    fname = get_contact_file_path(id_)
    if process_is_running:
        # ... the process is running, raise an exception
        raise ContactFileExists(
            CONTACT_FILE_EXISTS_MSG % {
                "host": old_host,
                "port": old_port,
                "pid": old_pid,
                "fname": fname,
                "workflow": id_,
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
                f'Failed to remove contact file for {id_}:\n{exc}'
            )
        else:
            LOG.info(
                f'Removed contact file for {id_}'
                ' (workflow no longer running).'
            )


def dump_contact_file(id_, data):
    """Create contact file. Data should be a key=value dict."""
    # Note:
    # 1st fsync for writing the content of the contact file to disk.
    # 2nd fsync for writing the file metadata of the contact file to disk.
    # The double fsync logic ensures that if the contact file is written to
    # a shared file system e.g. via NFS, it will be immediately visible
    # from by a process on other hosts after the current process returns.
    with open(get_contact_file_path(id_), "wb") as handle:
        for key, value in sorted(data.items()):
            handle.write(("%s=%s\n" % (key, value)).encode())
        os.fsync(handle.fileno())
    dir_fileno = os.open(get_workflow_srv_dir(id_), os.O_DIRECTORY)
    os.fsync(dir_fileno)
    os.close(dir_fileno)


def get_contact_file_path(id_: str) -> str:
    """Return name of contact file."""
    return os.path.join(
        get_workflow_srv_dir(id_), WorkflowFiles.Service.CONTACT)


def get_flow_file(id_: str) -> Path:
    """Return the path of a workflow's flow.cylc file."""
    run_dir = get_workflow_run_dir(id_)
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


def get_workflow_srv_dir(id_):
    """Return service directory of a workflow."""
    run_d = os.getenv("CYLC_WORKFLOW_RUN_DIR")
    if (
        not run_d
        or os.getenv("CYLC_WORKFLOW_ID") != id_
        or os.getenv("CYLC_WORKFLOW_OWNER") != get_user()
    ):
        run_d = get_workflow_run_dir(id_)
    return os.path.join(run_d, WorkflowFiles.Service.DIRNAME)


def refresh_nfs_cache(path: Path):
    """Refresh NFS cache for dirs between ~/cylc-run and <path> inclusive.

    On NFS filesystems, the non-existence of files/directories may become
    cashed. To work around this, we can list the contents of these directories
    which refreshes the NFS cache.

    See: https://github.com/cylc/cylc-flow/issues/6506

    Arguments:
        path: The directory to refresh.

    Raises:
        FileNotFoundError: If any of the directories between ~/cylc-run and
        this directory (inclsive) are not present.

    """
    cylc_run_dir = get_cylc_run_dir()
    for subdir in reversed(path.relative_to(cylc_run_dir).parents):
        deque((cylc_run_dir / subdir).iterdir(), maxlen=0)


def load_contact_file(id_: str, run_dir=None) -> Dict[str, str]:
    if not run_dir:
        path = Path(get_contact_file_path(id_))
    else:
        path = Path(
            run_dir,
            WorkflowFiles.Service.DIRNAME,
            WorkflowFiles.Service.CONTACT
        )

    if not path.exists():
        # work around NFS caching issues
        try:
            refresh_nfs_cache(path)
        except FileNotFoundError as exc:
            raise ServiceFileError("Couldn't load contact file") from exc

    try:
        with open(path) as f:
            file_content = f.read()
    except IOError as exc:
        raise ServiceFileError("Couldn't load contact file") from exc
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


load_contact_file_async = make_async(load_contact_file)


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


def get_symlink_dirs(id_: str, run_dir: Union[Path, str]) -> Dict[str, Path]:
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
            expected_end = str(Path('cylc-run', id_, _dir))
            if not str(target).endswith(expected_end):
                raise WorkflowFilesError(
                    f'Invalid symlink at {path}\n'
                    f'The target should end with "{expected_end}"'
                )
            ret[_dir] = target
    return ret


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
    """Create or renew authentication keys for workflow 'id_' in the .service
     directory.
     Generate a pair of ZMQ authentication keys"""
    import zmq.auth

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


def get_workflow_title(id_):
    """Return the the workflow title without a full file parse

    Limitations:
    * 1st line of title only.
    * Assume title is not in an include-file.
    """
    title = NO_TITLE
    with open(get_flow_file(id_), 'r') as handle:
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


def check_deprecation(path, warn=True, force_compat_mode=False):
    """Warn and turn on back-compat flag if Cylc 7 suite.rc detected.

    Path can point to config file or parent directory (i.e. workflow name).

    Args:
        warn:
            If True, then a warning will be logged when compatibility
            mode is activated.
        force_compat_mode:
            If True, forces Cylc to use compatibility mode
            overriding compatibility mode checks.
            See https://github.com/cylc/cylc-rose/issues/319
    """
    if (
        # Don't want to log if it's already been set True.
        not cylc.flow.flags.cylc7_back_compat
        and (
            path.resolve().name == WorkflowFiles.SUITE_RC
            or (path / WorkflowFiles.SUITE_RC).is_file()
            or force_compat_mode
        )
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


def infer_latest_run_from_id(
    workflow_id: str, alt_run_dir: Optional[str] = None
) -> str:
    """Wrapper to make the workflow run-dir absolute."""
    if alt_run_dir is not None:
        run_dir = Path(get_alt_workflow_run_dir(alt_run_dir, workflow_id))
    else:
        run_dir = Path(get_workflow_run_dir(workflow_id))
    _, id_ = infer_latest_run(run_dir, alt_run_dir=alt_run_dir)
    return id_


def infer_latest_run(
    path: Path,
    implicit_runN: bool = True,
    warn_runN: bool = True,
    alt_run_dir: Optional[str] = None,
) -> Tuple[Path, str]:
    """Infer the numbered run dir if the workflow has a runN symlink.

    Args:
        path: Absolute path to the workflow dir, run dir or runN dir.
        implicit_runN: If True, add runN on the end of the path if the path
            doesn't include it.
        warn_runN: If True, warn that explicit use of runN is unnecessary.
        alt_run_dir: Path to alternate cylc-run location (e.g. for other user).

    Returns:
        path: Absolute path of the numbered run dir if applicable, otherwise
            the input arg path.
        id_: The workflow name (including the numbered run if applicable).

    Raises:
        - WorkflowFilesError if the runN symlink is not valid.
        - InputError if the path does not exist.
    """
    cylc_run_dir = get_cylc_run_dir(alt_run_dir)
    try:
        id_ = str(path.relative_to(cylc_run_dir))
    except ValueError:
        raise ValueError(f"{path} is not in the cylc-run directory") from None

    if not path.exists():
        # work around NFS caching issues
        with suppress(FileNotFoundError):
            refresh_nfs_cache(path)

    if not path.exists():
        raise InputError(
            f'Workflow ID not found: {id_}\n(Directory not found: {path})'
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
            return (path, id_)
    else:
        return (path, id_)
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
    id_ = str(path.relative_to(cylc_run_dir))
    return (path, id_)


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
