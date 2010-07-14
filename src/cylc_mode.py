#/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|

import os

class mode:
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
