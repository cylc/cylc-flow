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
from job_submit import job_submit

class background( job_submit ):
    def __init__( self, task_id, ext_task, config, extra_vars, extra_directives, owner, host ):
        job_submit.__init__( self, task_id, ext_task, config, extra_vars, extra_directives, owner, host )
        self.method_description = 'in the background [&]'

    def construct_command( self ):
        self.command = self.jobfilename + ' > ' + self.task_id + '-$$.log 2>&1 &'
