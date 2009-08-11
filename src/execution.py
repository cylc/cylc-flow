#!/usr/bin/python

# Construct the command to run real or dummy external tasks, and run it.
# A single instance of this class is used for the whole system

# supported job launch methods:
#  (i) direct execution in the background ( 'task &' )
#  (ii) qsub


import os
import re

class launcher:

    def __init__( self, config ):

        self.system_name = config.get('system_name')
        self.clock_rate = config.get('dummy_clock_rate')
        self.clock_offset = config.get('dummy_clock_offset')
        self.dummy_mode = config.get('dummy_mode')
        self.use_qsub = config.get('use_qsub')
        self.job_queue = config.get('job_queue')

    def run( self, owner, task_name, ref_time, task, extra_vars=[] ):

        # who is running the control system
        cycon_owner = os.environ[ 'USER' ]

        # cycon environment script for this system
        cycon_env = os.environ[ 'CYCON_ENV' ]
        cycon_bin = os.environ[ 'CYCON_BIN' ]

        # ECOCONNECT: if the system is running on /test or /dvel then
        # replace the '_oper' owner postfix with '_test' or '_dvel'
        if re.search( '_test$', cycon_owner) or re.search( '_dvel$', cycon_owner ): 
            system = re.split( '_', cycon_owner )[-1]
            owner = re.sub( '_oper$', '_' + system, owner )

        # EXTERNAL PROGRAM TO RUN
        if self.dummy_mode:
            # dummy task
            external_program = cycon_bin + '/dummy-task.py'
        else:
            # real task
            external_program = task
            if not re.match( '^/', task ):
                # relative path: use tasks in the '<system>/tasks' sub-directory
                sysdir = re.sub( '[^/]*$', '', cycon_env )
                external_program = sysdir + 'tasks/' + task

        # CONSTRUCT THE FULL COMMAND TO RUN
        command = ''

        if not self.use_qsub:
            # DIRECT EXECUTION 
            command =  'export REFERENCE_TIME=' + ref_time + '; '
            command += 'export TASK_NAME='    + task_name + '; '
            command += 'export CYCON_ENV='  + cycon_env + '; '
            command += 'export SYSTEM_NAME='  + self.system_name + '; '
            command += 'export CLOCK_RATE='   + str(self.clock_rate) + '; '
            command += 'export CLOCK_OFFSET=' + str(self.clock_offset) + '; '

            for entry in extra_vars:
                [ var_name, value ] = entry
                command += 'export ' + var_name + '="' + value + '"; '

            command += external_program + ' &' 

        else:
            # QSUB EXECUTION

            if owner != cycon_owner: 
                # sudo run the task as its proper owner; only for qsub,
                # else owner needs sudo access to the task itself
                command  = 'sudo -u ' + owner 

            command += ' qsub -q ' + self.job_queue + ' -z'
            command += ' -v REFERENCE_TIME=' + ref_time
            command += ',TASK_NAME='    + task_name
            command += ',CYCON_ENV='  + cycon_env
            command += ',SYSTEM_NAME='  + self.system_name

            # the following required for dummy mode operation
            command += ',CLOCK_RATE='   + str(self.clock_rate)
            command += ',CLOCK_OFFSET=' + str(self.clock_offset)
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
            raise Exception( 'job launch failed: ' + task_name + ' ' + ref_time )
