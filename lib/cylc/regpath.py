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

class IllegalRegPathError( Exception ):
    def __init__( self, suite, owner=None ):
        self.msg = "ERROR, illegal suite name: " + suite
        if owner:
            self.msg += ' (' + owner + ')'
    def __str__( self ):
        return repr(self.msg)

class RegPath(object):
    # This class contains common code for checking suite registration
    # name correctness, and manipulating said names. It is currently
    # used piecemeal to do checking and conversions in-place. Eventually
    # we should just pass around RegPath objects instead of strings.
    delimiter = '.'
    delimiter_re = '\.'

    def __init__( self, rpath ):
        # Suite registration paths may contain [a-zA-Z0-9_.-]. They may
        # not contain colons, which would interfere with PATH variables.
        if re.search( '[^\w.-]', rpath ):
            raise IllegalRegPathError( rpath )
        # If the path ends in delimiter it must be a group, otherwise it
        # may refer to a suite or a group. NOTE: this information is not
        # currently used.
        if re.match( '.*' + self.__class__.delimiter_re + '$', rpath ):
            self.is_definitely_a_group = True
            rpath = rpath.strip(self.__class__.delimiter_re)
        else:
            self.is_definitely_a_group = False
        self.rpath = rpath

    def get( self ):
        return self.rpath

    def get_list( self ):
        return self.rpath.split(self.__class__.delimiter)

    def get_fpath( self ):
        return re.sub( self.__class__.delimiter_re, '/', self.rpath )

    def basename( self ):
        # return baz from foo.bar.baz
        return self.rpath.split(self.__class__.delimiter)[-1]

    def groupname( self ):
        # return foo.bar from foo.bar.baz
        return self.__class__.delimiter.join( self.rpath.split(self.__class__.delimiter)[0:-1])

    def append( self, rpath2 ):
        # join on another rpath
        return RegPath( self.rpath + self.__class__.delimiter + rpath2.rpath )
