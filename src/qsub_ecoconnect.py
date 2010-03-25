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
import re

# !!!!!!!!!!!!!!!!!!!!!OUT OF DATE!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

class qsub_ecoconnect( qsub, as_owner ):

    def __init__( self, task_name, task, cycle_time, queue, owner, extra_vars=[] ):
        qsub.__init__( task_name, task, cycle_time, extra_vars )

    def construct_command( self ):

        # who is running the control system
        cylc_owner = os.environ[ 'USER' ]

        # ECOCONNECT: if the system is running on /test or /dvel then
        # replace the '_oper' owner postfix with '_test' or '_dvel'
        if re.search( '_test$', cylc_owner) or re.search( '_dvel$', cylc_owner ): 
            system = re.split( '_', cylc_owner )[-1]
            owner = re.sub( '_oper$', '_' + system, owner )

        # EXTERNAL PROGRAM TO RUN
        external_program = task

        # CONSTRUCT THE FULL COMMAND TO RUN
        command = ''

        if not self.use_qsub:
            # DIRECT EXECUTION 
            os.environ['CYCLE_TIME'] = c_time
            os.environ['TASK_NAME'] = task_name

            for entry in extra_vars:
                [ var_name, value ] = entry
                os.environ[var_name] = value

            command += external_program + ' &' 

        else:
            # QSUB EXECUTION

            if owner != cylc_owner: 
                # sudo run the task as its proper owner; only for qsub,
                # else owner needs sudo access to the task itself
                command  = 'sudo -u ' + owner 

            command += ' qsub -q ' + self.job_queue + ' -z -v '
            command += ' CYCLE_TIME=' + c_time
            command += ',TASK_NAME='  + task_name
            command += ',CYLC_NS_HOST='  + os.environ['CYLC_NS_HOST']
            command += ',CYLC_NS_GROUP='  + os.environ['CYLC_NS_GROUP']
            # clock rate required for dummy mode operation
            command += ',CLOCK_RATE='   + os.environ['CLOCK_RATE']
            command += ',PYTHONPATH=' + os.environ['PYTHONPATH']

            for entry in extra_vars:
                [ var_name, value ] = entry
                command += ',' + var_name + '="' + value + '"'

            command += ' -k oe ' + external_program

        # RUN THE COMMAND
        # print command
        if os.system( command ) != 0:
            # NOTE: this means JOB LAUNCH failed, i.e. 
            # the job itself did not begin to execute.

            # TO DO: PRINT OUT ACTUAL COMMAND THAT FAILED

            raise Exception( 'job launch failed: ' + task_name + ' ' + c_time )
