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
"""Functions to return paths to common workflow files and directories."""

import os
from pathlib import Path
import re
from shutil import rmtree
from typing import Dict, Iterable, Set, Union, Optional, Any

from cylc.flow import LOG
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.exceptions import (
    UserInputError, WorkflowFilesError, handle_rmtree_err
)
from cylc.flow.platforms import get_localhost_install_target

# Note: do not import this elsewhere, as it might bypass unit test
# monkeypatching:
_CYLC_RUN_DIR = os.path.join('$HOME', 'cylc-run')


def expand_path(*args: Union[Path, str]) -> str:
    """Expand both vars and user in path, joining any extra args."""
    return os.path.expanduser(os.path.expandvars(
        os.path.join(*args)
    ))


def get_remote_workflow_run_dir(
    flow_name: Union[Path, str], *args: Union[Path, str]
) -> str:
    """Return remote workflow run directory, joining any extra args,
    NOT expanding vars or user."""
    return os.path.join(_CYLC_RUN_DIR, flow_name, *args)


def get_remote_workflow_run_job_dir(
    flow_name: Union[Path, str], *args: Union[Path, str]
) -> str:
    """Return remote workflow job log directory, joining any extra args,
    NOT expanding vars or user."""
    return get_remote_workflow_run_dir(flow_name, 'log', 'job', *args)


def get_workflow_run_dir(
    flow_name: Union[Path, str], *args: Union[Path, str]
) -> str:
    """Return local workflow run directory, joining any extra args, and
    expanding vars and user.

    Does not check that the directory exists.
    """
    return expand_path(_CYLC_RUN_DIR, flow_name, *args)


def get_workflow_run_job_dir(workflow, *args):
    """Return workflow run job (log) directory, join any extra args."""
    return get_workflow_run_dir(workflow, 'log', 'job', *args)


def get_workflow_run_log_dir(workflow, *args):
    """Return workflow run log directory, join any extra args."""
    return get_workflow_run_dir(workflow, 'log', 'workflow', *args)


def get_workflow_run_log_name(workflow):
    """Return workflow run log file path."""
    return get_workflow_run_dir(workflow, 'log', 'workflow', 'log')


def get_workflow_file_install_log_name(workflow):
    """Return workflow file install log file path."""
    return get_workflow_run_dir(
        workflow, 'log', 'workflow', 'file-installation-log'
    )


def get_workflow_run_config_log_dir(workflow, *args):
    """Return workflow run flow.cylc log directory, join any extra args."""
    return get_workflow_run_dir(workflow, 'log', 'flow-config', *args)


def get_workflow_run_pub_db_name(workflow):
    """Return workflow run public database file path."""
    return get_workflow_run_dir(workflow, 'log', 'db')


def get_workflow_run_share_dir(workflow, *args):
    """Return local workflow work/share directory, join any extra args."""
    return get_workflow_run_dir(workflow, 'share', *args)


def get_workflow_run_work_dir(workflow, *args):
    """Return local workflow work/work directory, join any extra args."""
    return get_workflow_run_dir(workflow, 'work', *args)


def get_workflow_test_log_name(workflow):
    """Return workflow run ref test log file path."""
    return get_workflow_run_dir(workflow, 'log', 'workflow', 'reftest.log')


def make_workflow_run_tree(workflow):
    """Create all top-level cylc-run output dirs on the workflow host."""
    for dir_ in (
        get_workflow_run_dir(workflow),
        get_workflow_run_log_dir(workflow),
        get_workflow_run_job_dir(workflow),
        get_workflow_run_config_log_dir(workflow),
        get_workflow_run_share_dir(workflow),
        get_workflow_run_work_dir(workflow),
    ):
        if dir_:
            os.makedirs(dir_, exist_ok=True)
            LOG.debug(f'{dir_}: directory created')


def make_localhost_symlinks(
    rund: Union[Path, str],
    named_sub_dir: str,
    symlink_conf: Optional[Dict[str, Dict[str, str]]] = None
) -> Dict[str, Union[Path, str]]:
    """Creates symlinks for any configured symlink dirs from glbl_cfg.
    Args:
        rund: the entire run directory path
        named_sub_dir: e.g flow_name/run1
        symlink_conf: Symlinks dirs configuration passed from cli

    Returns:
        Dictionary of symlinks with sources as keys and
        destinations as values: ``{source: destination}``

    """
    symlinks_created = {}
    dirs_to_symlink = get_dirs_to_symlink(
        get_localhost_install_target(),
        named_sub_dir, symlink_conf=symlink_conf
    )
    for key, value in dirs_to_symlink.items():
        if value is None:
            continue
        if key == 'run':
            symlink_path = rund
        else:
            symlink_path = os.path.join(rund, key)
        target = expand_path(value)
        if '$' in target:
            raise WorkflowFilesError(
                f'Unable to create symlink to {target}.'
                f' \'{value}\' contains an invalid environment variable.'
                ' Please check configuration.')
        symlink_success = make_symlink(symlink_path, target)
        # Symlink info returned for logging purposes. Symlinks should be
        # created before logs as the log dir may be a symlink.
        if symlink_success:
            symlinks_created[target] = symlink_path
    return symlinks_created


def get_dirs_to_symlink(
    install_target: str,
    flow_name: str,
    symlink_conf: Optional[Dict[str, Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Returns dictionary of directories to symlink.

    Note the paths should remain unexpanded, to be expanded on the remote.
    Args:
        install_target: Symlinks to be created on this install target
        flow_name: full name of the run, e.g. myflow/run1
        symlink_conf: Symlink dirs, if sent on the cli.
            Defaults to None, in which case global config symlink dirs will
            be applied.

    Returns:
        dirs_to_symlink: [directory: symlink_path]
    """
    dirs_to_symlink: Dict[str, Any] = {}
    if symlink_conf is None:
        symlink_conf = glbl_cfg().get(['install', 'symlink dirs'])
    if install_target not in symlink_conf.keys():
        return dirs_to_symlink
    base_dir = symlink_conf[install_target]['run']
    if base_dir:
        dirs_to_symlink['run'] = os.path.join(base_dir, 'cylc-run', flow_name)
    for dir_ in ['log', 'share', 'share/cycle', 'work']:
        link = symlink_conf[install_target].get(dir_, None)
        if (not link) or link == base_dir:
            continue
        dirs_to_symlink[dir_] = os.path.join(link, 'cylc-run', flow_name, dir_)
    return dirs_to_symlink


def make_symlink(path: Union[Path, str], target: Union[Path, str]) -> bool:
    """Makes symlinks for directories.

    Args:
        path: Absolute path of the desired symlink.
        target: Absolute path of the symlink's target directory.
    """
    path = Path(path)
    target = Path(target)
    if path.exists():
        # note all three checks are needed here due to case where user has set
        # their own symlink which does not match the global config set one.
        if path.is_symlink() and target.exists() and path.samefile(target):
            # correct symlink already exists
            return False
        # symlink name is in use by a physical file or directory
        # log and return
        LOG.debug(
            f"Unable to create symlink to {target}. "
            f"The path {path} already exists.")
        return False
    elif path.is_symlink():
        # remove a bad symlink.
        try:
            path.unlink()
        except OSError:
            raise WorkflowFilesError(
                f"Error when symlinking. Failed to unlink bad symlink {path}.")
    target.mkdir(parents=True, exist_ok=True)

    # This is needed in case share and share/cycle have the same symlink dir:
    if path.exists():
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.symlink_to(target)
        return True
    except OSError as exc:
        raise WorkflowFilesError(f"Error when symlinking\n{exc}")


def remove_dir_and_target(path: Union[Path, str]) -> None:
    """Delete a directory tree (i.e. including contents), as well as the
    target directory tree if the specified path is a symlink.

    Args:
        path: the absolute path of the directory to delete.
    """
    if not os.path.isabs(path):
        raise ValueError('Path must be absolute')
    if os.path.exists(path) and not os.path.isdir(path):
        raise NotADirectoryError(path)
    if os.path.islink(path):
        if os.path.exists(path):
            target = os.path.realpath(path)
            LOG.debug(
                f'Removing symlink target directory: ({path} ->) {target}')
            rmtree(target, onerror=handle_rmtree_err)
            LOG.debug(f'Removing symlink: {path}')
        else:
            LOG.debug(f'Removing broken symlink: {path}')
        os.remove(path)
    elif not os.path.exists(path):
        raise FileNotFoundError(path)
    else:
        LOG.debug(f'Removing directory: {path}')
        rmtree(path, onerror=handle_rmtree_err)


def remove_dir_or_file(path: Union[Path, str]) -> None:
    """Delete a directory tree, or a file, or a symlink.
    Does not follow symlinks.

    Args:
        path: the absolute path of the directory/file/symlink to delete.
    """
    if not os.path.isabs(path):
        raise ValueError("Path must be absolute")
    if os.path.islink(path):
        LOG.debug(f"Removing symlink: {path}")
        os.remove(path)
    elif os.path.isfile(path):
        LOG.debug(f"Removing file: {path}")
        os.remove(path)
    else:
        LOG.debug(f"Removing directory: {path}")
        rmtree(path, onerror=handle_rmtree_err)


def get_next_rundir_number(run_path):
    """Return the new run number"""
    run_n_path = os.path.expanduser(os.path.join(run_path, "runN"))
    try:
        old_run_path = os.readlink(run_n_path)
        last_run_num = re.search(r'(?:run)(\d*$)', old_run_path).group(1)
        return int(last_run_num) + 1
    except OSError:
        return 1


def parse_rm_dirs(rm_dirs: Iterable[str]) -> Set[str]:
    """Parse a list of possibly colon-separated dirs (or files or globs).
    Return the set of all the dirs.

    Used by cylc clean with the --rm option.
    """
    result: Set[str] = set()
    for item in rm_dirs:
        for part in item.split(':'):
            part = part.strip()
            if not part:
                continue
            is_dir = part.endswith(os.sep)
            part = os.path.normpath(part)
            if os.path.isabs(part):
                raise UserInputError("--rm option cannot take absolute paths")
            if part == '.' or part.startswith(f'..{os.sep}'):
                raise UserInputError(
                    "--rm option cannot take paths that point to the "
                    "run directory or above"
                )
            if is_dir:
                # Preserve trailing slash to ensure it only matches dirs,
                # not files, when globbing
                part += os.sep
            result.add(part)
    return result


def is_relative_to(path1: Union[Path, str], path2: Union[Path, str]) -> bool:
    """Return whether or not path1 is relative to path2."""
    # In future, we can just use pathlib.Path.is_relative_to()
    # when Python 3.9 becomes the minimum supported version
    try:
        Path(os.path.normpath(path1)).relative_to(os.path.normpath(path2))
    except ValueError:
        return False
    return True
