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
    InputError, WorkflowFilesError, handle_rmtree_err
)
from cylc.flow.platforms import get_localhost_install_target


# Note: do not import this elsewhere, as it might bypass unit test
# monkeypatching:
_CYLC_RUN_DIR = os.path.join('$HOME', 'cylc-run')

EXPLICIT_RELATIVE_PATH_REGEX = re.compile(
    rf'''
    ^({re.escape(os.curdir)}|{re.escape(os.pardir)})
    ({re.escape(os.sep)}|$)
    ''',
    re.VERBOSE
)
"""Matches relative paths that are explicit (starts with ./)"""

SHELL_ENV_VARS = re.compile(r'\$[^$/]*')


def expand_path(*args: Union[Path, str]) -> str:
    """Expand both vars and user in path and normalise it, joining any
    extra args."""
    return os.path.normpath(os.path.expanduser(os.path.expandvars(
        os.path.join(*args)
    )))


def get_remote_workflow_run_dir(
    workflow_name: Union[Path, str], *args: Union[Path, str]
) -> str:
    """Return remote workflow run directory, joining any extra args,
    NOT expanding vars or user."""
    return os.path.join(_CYLC_RUN_DIR, workflow_name, *args)


def get_remote_workflow_run_job_dir(
    workflow_name: Union[Path, str], *args: Union[Path, str]
) -> str:
    """Return remote workflow job log directory, joining any extra args,
    NOT expanding vars or user."""
    return get_remote_workflow_run_dir(workflow_name, 'log', 'job', *args)


def get_cylc_run_dir() -> str:
    """Return the cylc-run dir path with vars/user expanded."""
    return expand_path(_CYLC_RUN_DIR)


def get_workflow_run_dir(
    workflow_name: Union[Path, str], *args: Union[Path, str]
) -> str:
    """Return local workflow run directory, joining any extra args, and
    expanding vars and user.

    Does not check that the directory exists.
    """
    return expand_path(_CYLC_RUN_DIR, workflow_name, *args)


def get_workflow_run_job_dir(workflow, *args):
    """Return workflow run job (log) directory, join any extra args."""
    return get_workflow_run_dir(workflow, 'log', 'job', *args)


def get_workflow_run_scheduler_log_dir(workflow, *args):
    """Return workflow run log directory, join any extra args."""
    return get_workflow_run_dir(workflow, 'log', 'scheduler', *args)


def get_workflow_run_scheduler_log_path(workflow):
    """Return workflow run log file path."""
    return get_workflow_run_scheduler_log_dir(workflow, 'log')


def get_workflow_file_install_log_dir(workflow, *args):
    """Return workflow file install log file dir, join any extra args."""
    return get_workflow_run_dir(
        workflow, 'log', 'remote-install', *args
    )


def get_workflow_run_config_log_dir(workflow, *args):
    """Return workflow run flow.cylc log directory, join any extra args."""
    return get_workflow_run_dir(workflow, 'log', 'config', *args)


def get_workflow_run_pub_db_path(workflow):
    """Return workflow run public database file path."""
    return get_workflow_run_dir(workflow, 'log', 'db')


def get_workflow_run_share_dir(workflow, *args):
    """Return local workflow work/share directory, join any extra args."""
    return get_workflow_run_dir(workflow, 'share', *args)


def get_workflow_run_work_dir(workflow, *args):
    """Return local workflow work/work directory, join any extra args."""
    return get_workflow_run_dir(workflow, 'work', *args)


def get_workflow_test_log_path(workflow):
    """Return workflow run ref test log file path."""
    return get_workflow_run_scheduler_log_dir(workflow, 'reftest.log')


def make_workflow_run_tree(workflow):
    """Create all top-level cylc-run output dirs on the workflow host."""
    for dir_ in (
        get_workflow_run_dir(workflow),
        get_workflow_run_scheduler_log_dir(workflow),
        get_workflow_run_job_dir(workflow),
        get_workflow_run_config_log_dir(workflow),
        get_workflow_run_share_dir(workflow),
        get_workflow_run_work_dir(workflow),
    ):
        if not Path(dir_).is_dir():
            os.makedirs(dir_)
            LOG.debug(f'{dir_}: directory created')


def make_localhost_symlinks(
    rund: Union[Path, str],
    named_sub_dir: str,
    symlink_conf: Optional[Dict[str, Dict[str, str]]] = None
) -> Dict[str, Union[Path, str]]:
    """Creates symlinks for any configured symlink dirs from glbl_cfg.
    Args:
        rund: the entire run directory path
        named_sub_dir: e.g workflow_name/run1
        symlink_conf: Symlinks dirs configuration passed from cli

    Returns:
        Dictionary of symlinks with sources as keys and
        destinations as values: ``{target: symlink}``

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
        env_vars = SHELL_ENV_VARS.findall(target)
        if env_vars:
            raise WorkflowFilesError(
                f"Can't symlink to {target}\n"
                "Undefined variables, check "
                f"global config: {', '.join(env_vars)}")

        symlink_success = make_symlink_dir(symlink_path, target)
        # Symlink info returned for logging purposes. Symlinks should be
        # created before logs as the log dir may be a symlink.
        if symlink_success:
            symlinks_created[target] = symlink_path
    return symlinks_created


def get_dirs_to_symlink(
    install_target: str,
    workflow_name: str,
    symlink_conf: Optional[Dict[str, Dict[str, Any]]] = None
) -> Dict[str, str]:
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
    dirs_to_symlink: Dict[str, str] = {}
    if symlink_conf is None:
        symlink_conf = glbl_cfg().get(['install', 'symlink dirs'])
    if install_target not in symlink_conf.keys():
        return dirs_to_symlink
    base_dir = symlink_conf[install_target]['run']
    if base_dir:
        dirs_to_symlink['run'] = os.path.join(
            base_dir, 'cylc-run', workflow_name)
    for dir_ in ['log', 'share', 'share/cycle', 'work']:
        link = symlink_conf[install_target].get(dir_, None)
        if (not link) or link == base_dir:
            continue
        dirs_to_symlink[dir_] = os.path.join(
            link, 'cylc-run', workflow_name, dir_)
    return dirs_to_symlink


def make_symlink_dir(path: Union[Path, str], target: Union[Path, str]) -> bool:
    """Makes symlinks for directories.

    Args:
        path: Absolute path of the desired symlink.
        target: Absolute path of the symlink's target directory.

    Returns True if symlink created, or False if skipped.
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
    try:
        target.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        raise WorkflowFilesError(
            f"Symlink dir target already exists: ({path} ->) {target}\n"
            "Tip: in future, use 'cylc clean' instead of manually deleting "
            "workflow run dirs."
        )

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
            LOG.info(
                "Removing symlink and its target directory: "
                f"{path} -> {target}"
            )
            rmtree(target, onerror=handle_rmtree_err)
        else:
            LOG.info(f'Removing broken symlink: {path}')
        os.remove(path)
    elif not os.path.exists(path):
        raise FileNotFoundError(path)
    else:
        LOG.info(f'Removing directory: {path}')
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
        LOG.info(f"Removing symlink: {path}")
        os.remove(path)
    elif os.path.isfile(path):
        LOG.info(f"Removing file: {path}")
        os.remove(path)
    else:
        LOG.info(f"Removing directory: {path}")
        rmtree(path, onerror=handle_rmtree_err)


def remove_empty_parents(
    path: Union[Path, str], tail: Union[Path, str]
) -> None:
    """Work our way up the tail of path, removing empty dirs only.

    Args:
        path: Absolute path to the directory, e.g. /foo/bar/a/b/c
        tail: The tail of the path to work our way up, e.g. a/b/c

    Example:
        remove_empty_parents('/foo/bar/a/b/c', 'a/b/c') would remove
        /foo/bar/a/b (assuming it's empty), then /foo/bar/a (assuming it's
        empty).
    """
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('path must be absolute')
    tail = Path(tail)
    if tail.is_absolute():
        raise ValueError('tail must not be an absolute path')
    if not str(path).endswith(str(tail)):
        raise ValueError(f"path '{path}' does not end with '{tail}'")
    depth = len(tail.parts) - 1
    for i in range(depth):
        parent = path.parents[i]
        if not parent.is_dir():
            continue
        try:
            parent.rmdir()
            LOG.info(f'Removing directory: {parent}')
        except OSError:
            break


def get_next_rundir_number(run_path: Union[str, Path]) -> int:
    """Return the next run number for a new install.

    Args:
        run_path: Top level installed workflow dir
        (often ``~/cylc-run/workflow``).

    """
    re_runX = re.compile(r'run(\d+)$')
    run_n_path = Path(os.path.expanduser(os.path.join(run_path, "runN")))
    if run_n_path.exists() and run_n_path.is_symlink():
        old_run_path = os.readlink(run_n_path)
        # Line below could in theory not return a match group, so mypy objects.
        # This function unlikely to be called in circumstances where this will
        # be a problem.
        last_run_num = re_runX.search(  # type: ignore
            old_run_path).group(1)
        last_run_num = int(last_run_num)
    else:
        # If the ``runN`` symlink has been removed, get next numbered run from
        # file names:
        paths = Path(run_path).glob('run[0-9]*')
        run_numbers = (
            int(m.group(1)) for m in (
                re_runX.search(i.name) for i in paths
            ) if m
        )
        last_run_num = max(run_numbers, default=0)

    return last_run_num + 1


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
                raise InputError("--rm option cannot take absolute paths")
            if (
                part in {os.curdir, os.pardir} or
                part.startswith(f"{os.pardir}{os.sep}")  # '../'
            ):
                raise InputError(
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
    """Return whether or not path1 is relative to path2.

    Normalizes both paths to avoid trickery with paths containing `..`
    somewhere in them.
    """
    # In future, we can just use pathlib.Path.is_relative_to()
    # when Python 3.9 becomes the minimum supported version
    try:
        Path(os.path.normpath(path1)).relative_to(os.path.normpath(path2))
    except ValueError:
        return False
    return True


def get_workflow_name_from_id(workflow_id: str) -> str:
    """Workflow name is the ID shorn of the runN directory name.
    """
    cylc_run_dir = Path(get_cylc_run_dir())
    if Path(workflow_id).is_absolute():
        # this is a source directory, not an install dir:
        return workflow_id
    else:
        id_path = cylc_run_dir / workflow_id
    name_path = id_path

    # Look for ``id_path.parent/_cylc_install`` first because expected to
    # be most common:
    if (id_path.parent / '_cylc-install').is_dir():
        name_path = Path(id_path).parent
    elif (id_path / '_cylc-install').is_dir():
        name_path = id_path

    return str(name_path.relative_to(cylc_run_dir))
