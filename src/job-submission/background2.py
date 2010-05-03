#!/usr/bin/python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


import os
from background import background

class background2( background ):
    # A minimalist alternative job submission class: print a message to
    # stdout before submitting the job in the background; allows a very
    # simple test of systems with multiple job submission methods. 

    def execute_command( self ):
        print 'Background2 Job Submit: ', self.task_id
        background.execute( self )
