#/usr/bin/env python

import os

class mode( object ):
    def __init__( self ):

        self.mode = 'raw'
        if 'CYLC_MODE' in os.environ:
            self.mode = os.environ[ 'CYLC_MODE' ]
            # 'scheduler' or 'submit'

    def is_raw( self ):
        return self.mode == 'raw'

    def is_scheduler( self ):
        return self.mode == 'scheduler'

    def is_submit( self ):
        return self.mode == 'submit'
