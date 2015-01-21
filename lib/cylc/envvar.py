#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2015 NIWA
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

""" environment variable utility functions """

import os, re, sys

class EnvVarError( Exception ):
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)

def check_varnames( env ):
    """ check a bunch of putative environment names for legality,
    returns a list of bad names (empty implies success)."""
    bad = []
    for varname in env:
        if not re.match( '^[a-zA-Z_][\w]*$', varname ):
            bad.append(varname)
    return bad

def expandvars( item, owner=None ):
    if owner:
        homedir = os.path.expanduser( '~' + owner )
    else:
        homedir = os.environ[ 'HOME' ]
    # first replace '$HOME' with actual home dir
    item = item.replace( '$HOME', homedir )
    # now expand any other environment variable or tilde-username
    item = os.path.expandvars( os.path.expanduser( item ))
    return item
