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

"""Functionality for (local) workflow installation."""

import logging
import os
import re
import shlex
from contextlib import suppress
from pathlib import Path
from subprocess import (
    PIPE,
    Popen,
)
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple,
    Union,
)

from cylc.flow import LOG
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.exceptions import (
    InputError,
    WorkflowFilesError,
)
from cylc.flow.loggingutil import (
    CylcLogFormatter,
    close_log,
    get_next_log_number,
    get_sorted_logs_by_time,
)
from cylc.flow.pathutil import (
    expand_path,
    get_cylc_run_dir,
    get_next_rundir_number,
    get_workflow_run_dir,
    make_localhost_symlinks,
)
from cylc.flow.remote import (
    DEFAULT_RSYNC_OPTS,
)
from cylc.flow.util import cli_format
from cylc.flow.workflow_files import (
    WorkflowFiles,
    abort_if_flow_file_in_path,
    check_deprecation,
    check_flow_file,
    get_cylc_run_abs_path,
    is_valid_run_dir,
    validate_workflow_name,
)


NESTED_DIRS_MSG = (
    "Nested {dir_type} directories not allowed - cannot install workflow"
    " in '{dest}' as '{existing}' is already a valid {dir_type} directory."
)


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
    if run_name is not None:
        if len(Path(run_name).parts) != 1:
            raise WorkflowFilesError(
                f'Run name cannot be a path. (You used {run_name})'
            )
        validate_workflow_name(
            os.path.join(workflow_name, run_name),
            check_reserved_names=True
        )
    else:
        validate_workflow_name(workflow_name, check_reserved_names=True)
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


def get_source_dirs() -> List[str]:
    return glbl_cfg().get(['install', 'source dirs'])


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


def detect_flow_exists(
    run_path_base: Union[Path, str], numbered: bool
) -> bool:
    """Returns True if installed flow already exists.

    Args:
        run_path_base: Absolute path of the parent of the workflow's run dir,
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
        WorkflowFilesError if run_dir is nested inside an existing run dir,
            or install dirs are nested.
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
