#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
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

# A function that emulates the shell's 'mkdir -p', i.e. it creates
# intermediate directories if necessary AND does not throw an exception
# if the directory path already exists.

# Python's standard os.makedirs() fails if the directory already exists.
# We can check to see if it exists before calling os.makedirs(), but
# this causes a potential race condition: if another process creates the
# target directory between the check and the call.  In fact I've run
# into this exact problem with simultaneous use of 'cute checkvars -c'
# in a family of similar tasks.

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
