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

# A function that emulates the shell's 'mkdir -p', i.e. it creates
# intermediate directories if necessary AND does not throw an exception
# if the directory path already exists.

# Python's standard os.makedirs() fails if the directory already exists.
# We can check to see if it exists before calling os.makedirs(), but
# this causes a potential race condition: if another process creates the
# target directory between the check and the call.

# Judging from discussion on the Python dev list in 2010, this problem
# will be fixed in Python 3.?.  For now we have to roll our own ...

import os, errno

def mkdir_p( path, mode=None ):
    if mode:
        # reset mode and get current value
        old_mode = os.umask( 0 )

    try:
        if mode:
            os.makedirs( path, int(mode, 8) )
        else:
            os.makedirs( path )

    except OSError, err:
        if err.errno != errno.EEXIST:
            raise
        else:
            # OK: path already exists
            pass

    if mode:
        os.umask( old_mode )
