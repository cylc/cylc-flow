#!/usr/bin/env python

# Implements a simple rolling archive based on a given base filename.
# Used for cylc state dump files. 

import os

class rolling_archive:
    def __init__( self, filename, archive_length=10 ):
        self.base_filename = filename
        self.archive_length = archive_length

    def __filename( self, index ):
        return self.base_filename + '-' + str( index )

    def roll_open( self ):
        # roll the archive

        if os.path.exists( self.__filename( self.archive_length )):
            os.unlink( self.__filename( self.archive_length ))

        for i in reversed( range( 1, self.archive_length )):
            if os.path.exists( self.__filename( i )):
                os.rename( self.__filename(i), self.__filename(i+1) )

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
