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

# Implements a simple rolling archive based on a given base filename.
# Used for cylc state dump files.

import os

class rolling_archive(object):

    def __init__( self, filename, archive_length=10, sep='-' ):
        self.sep = sep
        self.base_filename = filename
        self.archive_length = archive_length

    def __filename( self, index ):
        return self.base_filename + self.sep + str( index )

    def roll( self ):
        # roll the archive

        if os.path.exists( self.__filename( self.archive_length )):
            os.unlink( self.__filename( self.archive_length ))

        for i in reversed( range( 1, self.archive_length )):
            if os.path.exists( self.__filename( i )):
                try:
                    os.rename( self.__filename(i), self.__filename(i+1) )
                except OSError:
                    raise

        if os.path.exists( self.base_filename):
            os.rename( self.base_filename, self.__filename(1) )

        self.file_handle = open( self.base_filename, 'w' )
        return self.file_handle

if __name__ == '__main__':

    munge = rolling_archive( 'munge', 5 )
    for i in range(1,20):
        FILE = munge.roll_open()
        FILE.write( "This is munge " + str( i ) + "\n" )
        FILE.close()
