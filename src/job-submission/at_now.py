#!/usr/bin/python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


from job_submit import job_submit

class at_now( job_submit ):
    # This class overrides job submission command construction so that
    # the cylc task execution file will be submitted to the Unix 'at'
    # scheduler ('at -f FILE now').

    def construct_command( self ):
        self.command = 'at -f ' + self.jobfile_path + ' now'
