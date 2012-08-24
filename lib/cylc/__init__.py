#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

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

    cylc_dir = os.path.dirname(os.path.dirname(os.path.abspath(argv0)))
    if cylc_dir != os.getenv('CYLC_DIR', ''):
        os.environ['CYLC_DIR'] = cylc_dir

    dirs = [os.path.join(cylc_dir, 'util'), os.path.join(cylc_dir, 'bin')]
    if os.getenv('CYLC_SUITE_DEF_PATH', ''):
        dirs.append(os.getenv('CYLC_SUITE_DEF_PATH'))
    environ_path_add(dirs)
    environ_path_add([os.path.join(cylc_dir, 'lib')], 'PYTHONPATH')

    # Python output buffering delays appearance of stdout and stderr
    # when output is not directed to a terminal - e.g. when running a
    # suite via the posix nohup command.
    os.environ['PYTHONUNBUFFERED'] = 'true'
    
    # Export $HOSTNAME for use in the default lockserver config (see
    # $CYLC_DIR/conf/lockserver.conf). HOSTNAME is a bash variable (see
    # man bash) that is defined but not exported; in other shells it may
    # not even be defined.
    if not os.getenv('HOSTNAME', ''):
        os.environ['HOSTNAME'] = socket.gethostname()

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
