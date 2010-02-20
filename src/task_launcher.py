#!/usr/bin/python

# Construct the command to run real or dummy external tasks, and run it.
# A single instance of this class is used for the whole system

# supported job launch methods:
#  (i) direct execution in the background ( 'task &' )
#  (ii) qsub

# TO DO: TASK-SPECIFIC LAUNCHER, LET TASKS OVERRIDE RUN METHOD.

import os
import re

class launcher:

    def __init__( self, config ):

        self.use_qsub = config.get('use_qsub')
        self.job_queue = config.get('job_queue')

    def run( self, owner, task_name, c_time, task, extra_vars=[] ):

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

            command += ' qsub -q ' + self.job_queue + ' -z'
            command += ' -v CYCLE_TIME=' + c_time
            command += ',TASK_NAME='    + task_name
            command += ',SYSTEM_NAME='  + os.environ['SYSTEM_NAME']
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
