#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
import sys
from parsec import LOG


def environ_init():
    """Initialise cylc environment."""
    cylc_dir_lib = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    environ_path_add([cylc_dir_lib], 'PYTHONPATH')
    # Ensure cylc library is at the front of "sys.path".
    if sys.path[0:1] != [cylc_dir_lib]:
        if cylc_dir_lib in sys.path:
            sys.path.remove(cylc_dir_lib)
        sys.path.insert(0, cylc_dir_lib)
    os.environ['CYLC_DIR'] = os.path.dirname(cylc_dir_lib)
    if os.getenv('CYLC_SUITE_DEF_PATH', ''):
        environ_path_add([os.getenv('CYLC_SUITE_DEF_PATH')])

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

__version__ = "8.0a0"
