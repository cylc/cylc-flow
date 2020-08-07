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
"""Set up the cylc environment."""

import os
import logging


CYLC_LOG = 'cylc'
LOG = logging.getLogger(CYLC_LOG)
LOG.addHandler(logging.NullHandler())  # Start with a null handler

# Used widely with data element ID (internally and externally),
# scope may widen further with internal and CLI adoption.
ID_DELIM = '|'


def environ_init():
    """Initialise cylc environment."""
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

__version__ = '8.0a3.dev'
