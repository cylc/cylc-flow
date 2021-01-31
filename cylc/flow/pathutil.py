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
"""Functions to return paths to common suite files and directories."""

import os
from os.path import expandvars
import re
from shutil import rmtree

from cylc.flow import LOG
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.exceptions import WorkflowFilesError
from cylc.flow.platforms import get_platform


def get_remote_suite_run_dir(platform, suite, *args):
    """Return remote suite run directory, join any extra args."""
    return os.path.join(
        platform['run directory'], suite, *args)


def get_remote_suite_run_job_dir(platform, suite, *args):
    """Return remote suite run directory, join any extra args."""
    return get_remote_suite_run_dir(
        platform, suite, 'log', 'job', *args)


def get_remote_suite_work_dir(platform, suite, *args):
    """Return remote suite work directory root, join any extra args."""
    return os.path.join(
        platform['work directory'],
        suite,
        *args
    )


def get_workflow_run_dir(flow_name, *args):
    """Return local workflow run directory, join any extra args."""
    return expandvars(
        os.path.join(
            get_platform()['run directory'], flow_name, *args
        )
    )


def get_suite_run_job_dir(suite, *args):
    """Return suite run job (log) directory, join any extra args."""
    return expandvars(
        get_workflow_run_dir(suite, 'log', 'job', *args)
    )


def get_suite_run_log_dir(suite, *args):
    """Return suite run log directory, join any extra args."""
    return expandvars(get_workflow_run_dir(suite, 'log', 'suite', *args))


def get_suite_run_log_name(suite):
    """Return suite run log file path."""
    path = get_workflow_run_dir(suite, 'log', 'suite', 'log')
    return expandvars(path)


def get_suite_file_install_log_name(suite):
    """Return suite file install log file path."""
    path = get_workflow_run_dir(suite, 'log', 'suite', 'file-installation-log')
    return expandvars(path)


def get_suite_run_config_log_dir(suite, *args):
    """Return suite run flow.cylc log directory, join any extra args."""
    return expandvars(get_workflow_run_dir(suite, 'log', 'flow-config', *args))


def get_suite_run_pub_db_name(suite):
    """Return suite run public database file path."""
    return expandvars(get_workflow_run_dir(suite, 'log', 'db'))


def get_suite_run_share_dir(suite, *args):
    """Return local suite work/share directory, join any extra args."""
    return expandvars(os.path.join(
        get_platform()['work directory'], suite, 'share', *args
    ))


def get_suite_run_work_dir(suite, *args):
    """Return local suite work/work directory, join any extra args."""
    return expandvars(os.path.join(
        get_platform()['work directory'], suite, 'work', *args
    ))


def get_suite_test_log_name(suite):
    """Return suite run ref test log file path."""
    return expandvars(
        get_workflow_run_dir(suite, 'log', 'suite', 'reftest.log'))


def make_suite_run_tree(suite):
    """Create all top-level cylc-run output dirs on the suite host."""
    cfg = glbl_cfg().get()
    # Roll archive
    archlen = cfg['scheduler']['run directory rolling archive length']
    dir_ = os.path.expandvars(get_workflow_run_dir(suite))
    for i in range(archlen, -1, -1):  # archlen...0
        if i > 0:
            dpath = f'{dir_}.{i}'
        else:
            dpath = dir_
        if os.path.exists(dpath):
            if i >= archlen:
                # remove oldest backup
                rmtree(dpath)
            else:
                # roll others over
                os.rename(dpath, f'{dir_}.{i + 1}')
    # Create
    for dir_ in (
        get_workflow_run_dir(suite),
        get_suite_run_log_dir(suite),
        get_suite_run_job_dir(suite),
        get_suite_run_config_log_dir(suite),
        get_suite_run_share_dir(suite),
        get_suite_run_work_dir(suite),
    ):
        dir_ = os.path.expandvars(dir_)
        if dir_:
            os.makedirs(dir_, exist_ok=True)
            LOG.debug(f'{dir_}: directory created')


def make_localhost_symlinks(rund, named_sub_dir):
    """Creates symlinks for any configured symlink dirs from glbl_cfg.
    Args:
        rund: the entire run directory path
        named_sub_dir: e.g flow_name/run1

    Returns:
         dict - A dictionary of Symlinks with sources as keys and
         destinations as values: ``{source: destination}``

    """
    dirs_to_symlink = get_dirs_to_symlink('localhost', named_sub_dir)
    symlinks_created = {}
    for key, value in dirs_to_symlink.items():
        if key == 'run':
            dst = rund
        else:
            dst = os.path.join(rund, key)
        src = os.path.expandvars(value)
        if '$' in src:
            raise WorkflowFilesError(
                f'Unable to create symlink to {src}.'
                f' \'{value}\' contains an invalid environment variable.'
                ' Please check configuration.')
        make_symlink(src, dst)
        # symlink info returned for logging purposes, symlinks created
        # before logs as this dir may be a symlink.
        symlinks_created[src] = dst
    return symlinks_created


def get_dirs_to_symlink(install_target, flow_name):
    """Returns dictionary of directories to symlink from glbcfg."""
    dirs_to_symlink = {}
    symlink_conf = glbl_cfg().get(['symlink dirs'])

    if install_target not in symlink_conf.keys():
        return dirs_to_symlink
    base_dir = symlink_conf[install_target]['run']
    if base_dir is not None:
        dirs_to_symlink['run'] = os.path.join(base_dir, 'cylc-run', flow_name)
    for dir_ in ['log', 'share', 'share/cycle', 'work']:
        link = symlink_conf[install_target][dir_]
        if link is None or link == base_dir:
            continue
        dirs_to_symlink[dir_] = os.path.join(link, 'cylc-run', flow_name, dir_)
    return dirs_to_symlink


def make_symlink(src, dst):
    """Makes symlinks for directories.
    Args:
        src (str): target path, where the files are to be stored.
        dst (str): full path of link that will point to src.
    """
    if os.path.exists(dst):
        if os.path.islink(dst) and os.path.samefile(dst, src):
            # correct symlink already exists
            return
        # symlink name is in use by a physical file or directory
        raise WorkflowFilesError(
            f"Error when symlinking. The path {dst} already exists.")
    elif os.path.islink(dst):
        # remove a bad symlink.
        try:
            os.unlink(dst)
        except Exception:
            raise WorkflowFilesError(
                f"Error when symlinking. Failed to unlink bad symlink {dst}.")
    os.makedirs(src, exist_ok=True)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        os.symlink(src, dst, target_is_directory=True)
    except Exception as exc:
        raise WorkflowFilesError(f"Error when symlinking\n{exc}")


def remove_dir(path):
    """Delete a directory including contents, including the target directory
    if the specified path is a symlink.

    Args:
        path (str): the absolute path of the directory to delete.
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
            rmtree(target)
            LOG.debug(f'Removing symlink: {path}')
        else:
            LOG.debug(f'Removing broken symlink: {path}')
        os.remove(path)
    elif not os.path.exists(path):
        raise FileNotFoundError(path)
    else:
        LOG.debug(f'Removing directory: {path}')
        rmtree(path)


def get_next_rundir_number(run_path):
    """Return the new run number"""
    run_n_path = os.path.expanduser(os.path.join(run_path, "runN"))
    try:
        old_run_path = os.readlink(run_n_path)
        last_run_num = re.search(r'(?:run)(\d*$)', old_run_path).group(1)
        return int(last_run_num) + 1
    except OSError:
        return 1
