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

import re

class logfiles( object ):
    # we need task output logs file to be mutable (i.e. not just strings) so
    # that changes to log paths in the job submit class are reflected in
    # the task class.
    def __init__( self, path = None ):
        self.paths = []
        if path:
            self.paths.append( path )

    def add_path( self, path ):
        self.paths.append( path )

    def add_path_prepend( self, path ):
        self.paths = [ path ] + self.paths

    # NO LONGER NEEDED:
    #def replace_path( self, pattern, path, prepend=True ):
    #    # replace a path that matches a pattern with another path
    #    # (used to replace output logs when a failed task is reset)
    #    for item in self.paths:
    #        if re.match( pattern, item ):
    #            #print 'REPLACING', item, 'WITH', path
    #            self.paths.remove( item )
    #            break
    #    # add the new path even if a match to replace wasn't found
    #    if prepend:
    #        self.add_path_prepend( path )
    #    else:
    #        self.add_path( path )

    def get_paths( self ):
        return self.paths

    def empty( self ):
        self.paths = []
