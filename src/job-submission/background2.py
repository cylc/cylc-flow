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

    def __init__( self, task_id, ext_task, config, extra_vars, extra_directives, owner, host ):
        background.__init__( self, task_id, ext_task, config, extra_vars, extra_directives, owner, host )
        self.method_description = 'in the background [&], VERSION 2'


    def construct_command( self ):
        background.construct_command( self )
