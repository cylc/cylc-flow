#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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
"""Set up the cylc environment."""

import os
import socket
import sys


def environ_init(argv0=None):
    """Initialise cylc environment."""

    if not argv0:
        argv0 = sys.argv[0]
    # NOTE: the above works if invoked via top level cylc or gcylc
    # command but not for this:
    # BAZ=$(python -c 'from cylc.foo import bar; print bar')
    # where argv0 will be '-c'.

    if argv0 and argv0 != "-":
        cylc_dir = os.path.dirname(os.path.dirname(os.path.realpath(argv0)))
        if cylc_dir != os.getenv('CYLC_DIR', ''):
            os.environ['CYLC_DIR'] = cylc_dir

        cylc_dir_lib = os.path.join(cylc_dir, 'lib')
        my_lib = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        if cylc_dir_lib == my_lib:
            dirs = []
        else:
            # For backward compat, old versions of "cylc" may end up loading an
            # incorrect version of this file.
            dirs = [os.path.join(cylc_dir, 'bin')]
        if os.getenv('CYLC_SUITE_DEF_PATH', ''):
            dirs.append(os.getenv('CYLC_SUITE_DEF_PATH'))
        environ_path_add(dirs)
        environ_path_add([cylc_dir_lib], 'PYTHONPATH')

    # Python output buffering delays appearance of stdout and stderr
    # when output is not directed to a terminal (this occurred when
    # running pre-5.0 cylc via the posix nohup command; is it still the
    # case in post-5.0 daemon-mode cylc?)
    os.environ['PYTHONUNBUFFERED'] = 'true'


def environ_path_add(dirs, key='PATH'):
    """For each dir_ in dirs, prepend dir_ to the PATH environment variable.

    If key is specified, prepend dir_ to the named environment variable instead
    of PATH.

    """

    paths_str = os.getenv(key, '')
    # ''.split(os.pathsep) gives ['']
    if paths_str.strip():
        paths = paths_str.split(os.pathsep)
    else:
        paths = []
    for dir_ in dirs:
        while dir_ in paths:
            paths.remove(dir_)
        paths.insert(0, dir_)
    os.environ[key] = os.pathsep.join(paths)


environ_init()
