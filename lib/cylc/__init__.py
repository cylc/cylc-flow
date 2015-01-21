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

# Set up the cylc environment.

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

        dirs = [os.path.join(cylc_dir, 'util'), os.path.join(cylc_dir, 'bin')]
        if os.getenv('CYLC_SUITE_DEF_PATH', ''):
            dirs.append(os.getenv('CYLC_SUITE_DEF_PATH'))
        environ_path_add(dirs)
        environ_path_add([os.path.join(cylc_dir, 'lib')], 'PYTHONPATH')

    # Python output buffering delays appearance of stdout and stderr
    # when output is not directed to a terminal (this occurred when
    # running pre-5.0 cylc via the posix nohup command; is it still the
    # case in post-5.0 daemon-mode cylc?)
    os.environ['PYTHONUNBUFFERED'] = 'true'

def environ_path_add(dirs, key='PATH'):
    """For each dir in dirs, add dir to the front of the PATH environment
    variable. If the 2nd argument key is specified, add each dir to the front of
    the named environment variable instead of PATH.
    """

    paths = os.getenv(key, '').split(os.pathsep)
    for dir in dirs:
        while dir in paths:
            paths.remove(dir)
        paths.insert(0, dir)
    os.environ[key] = os.pathsep.join(paths)


environ_init()
