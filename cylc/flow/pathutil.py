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
from shutil import rmtree


from cylc.flow import LOG
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.platform_lookup import forward_lookup


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


def get_suite_run_dir(suite, *args):
    """Return local suite run directory, join any extra args."""
    return os.path.expandvars(
        os.path.join(
            forward_lookup()['run directory'], suite, *args
        )
    )


def get_suite_run_job_dir(suite, *args):
    """Return suite run job (log) directory, join any extra args."""
    return get_suite_run_dir(suite, 'log', 'job', *args)


def get_suite_run_log_dir(suite, *args):
    """Return suite run log directory, join any extra args."""
    return get_suite_run_dir(suite, 'log', 'suite', *args)


def get_suite_run_log_name(suite):
    """Return suite run log file path."""
    path = get_suite_run_dir(suite, 'log', 'suite', 'log')
    return os.path.expandvars(path)


def get_suite_run_rc_dir(suite, *args):
    """Return suite run suite.rc log directory, join any extra args."""
    return get_suite_run_dir(suite, 'log', 'suiterc', *args)


def get_suite_run_pub_db_name(suite):
    """Return suite run public database file path."""
    return get_suite_run_dir(suite, 'log', 'db')


def get_suite_run_share_dir(suite, *args):
    """Return local suite work/share directory, join any extra args."""
    return os.path.expandvars(
        os.path.join(
            forward_lookup()['work directory'], suite, 'share', *args
        )
    )


def get_suite_run_work_dir(suite, *args):
    """Return local suite work/work directory, join any extra args."""
    return os.path.expandvars(
        os.path.join(
            forward_lookup()['work directory'], suite, 'work', *args
        )
    )


def get_suite_test_log_name(suite):
    """Return suite run ref test log file path."""
    return get_suite_run_dir(suite, 'log', 'suite', 'reftest.log')


def make_suite_run_tree(suite):
    """Create all top-level cylc-run output dirs on the suite host."""
    cfg = glbl_cfg().get()
    # Roll archive
    archlen = cfg['run directory rolling archive length']
    dir_ = get_suite_run_dir(suite)
    for i in range(archlen, -1, -1):  # archlen...0
        if i > 0:
            dpath = dir_ + '.' + str(i)
        else:
            dpath = dir_
        if os.path.exists(dpath):
            if i >= archlen:
                # remove oldest backup
                rmtree(dpath)
            else:
                # roll others over
                os.rename(dpath, dir_ + '.' + str(i + 1))
    # Create
    for dir_ in (
        get_suite_run_dir(suite),
        get_suite_run_log_dir(suite),
        get_suite_run_job_dir(suite),
        get_suite_run_rc_dir(suite),
        get_suite_run_share_dir(suite),
        get_suite_run_work_dir(suite),
    ):
        if dir_:
            dir_ = os.path.expandvars(dir_)
            os.makedirs(dir_, exist_ok=True)
            LOG.debug('%s: directory created', dir_)
