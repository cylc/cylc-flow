#!/usr/bin/python

# Construct the command to run real or dummy external tasks, and run it.
# A single instance of this class is used for the whole system

# supported job launch methods:
#  (i) direct execution in the background ( 'task &' )
#  (ii) qsub


import os
import re

class launcher:

    def __init__( self, config, dummy_mode, clock_rate, failout_task = None ):

        self.dummy_mode = dummy_mode

        self.system_name = config.get('system_name')

        # The clock rate determines how fast dummy tasks run.
        self.clock_rate = clock_rate

        self.use_qsub = config.get('use_qsub')
        self.job_queue = config.get('job_queue')

        self.failout = False
        self.failout_task = failout_task
        if failout_task:
            self.failout = True
            print "FAILOUT TASK: " + failout_task
            if not self.dummy_mode:
                print 'WARNING: failout only affects dummy mode'

    def run( self, owner, task_name, ref_time, task, dummy_out, extra_vars=[] ):

        # who is running the control system
        cylon_owner = os.environ[ 'USER' ]

        # cylon environment script for this system
        cylon_env = os.environ[ 'CYLON_ENV' ]
        cylon_bin = os.environ[ 'CYLON_BIN' ]

        # ECOCONNECT: if the system is running on /test or /dvel then
        # replace the '_oper' owner postfix with '_test' or '_dvel'
        if re.search( '_test$', cylon_owner) or re.search( '_dvel$', cylon_owner ): 
            system = re.split( '_', cylon_owner )[-1]
            owner = re.sub( '_oper$', '_' + system, owner )

        # EXTERNAL PROGRAM TO RUN
        if self.dummy_mode or dummy_out:
            # dummy task
            # explicit path not required thanks to environment.sh
            # external_program = 'dummy-task.py'
            external_program = cylon_bin + '/dummy-task.py'
            if self.failout:
                if self.failout_task == task_name + '%' + ref_time:
                    external_program += ' --fail'
                    # now turn failout off, in case the task gets reinserted
                    self.failout = False
        else:
            # real task
            external_program = task
            if not re.match( '^/', task ):
                # relative path: use scripts in the '<system>/scripts' sub-directory
                sysdir = re.sub( '[^/]*$', '', cylon_env )
                external_program = sysdir + 'scripts/' + task

        # CONSTRUCT THE FULL COMMAND TO RUN
        command = ''

        if not self.use_qsub:
            # DIRECT EXECUTION 
            command =  'export REFERENCE_TIME=' + ref_time + '; '
            command += 'export TASK_NAME='    + task_name + '; '
            command += 'export CYLON_ENV='  + cylon_env + '; '
            command += 'export SYSTEM_NAME='  + self.system_name + '; '
            command += 'export CLOCK_RATE='   + str(self.clock_rate) + '; '

            for entry in extra_vars:
                [ var_name, value ] = entry
                command += 'export ' + var_name + '="' + value + '"; '

            command += external_program + ' &' 

        else:
            # QSUB EXECUTION

            if owner != cylon_owner: 
                # sudo run the task as its proper owner; only for qsub,
                # else owner needs sudo access to the task itself
                command  = 'sudo -u ' + owner 

            command += ' qsub -q ' + self.job_queue + ' -z'
            command += ' -v REFERENCE_TIME=' + ref_time
            command += ',TASK_NAME='    + task_name
            command += ',CYLON_ENV='  + cylon_env
            command += ',SYSTEM_NAME='  + self.system_name

            # the following required for dummy mode operation
            command += ',CLOCK_RATE='   + str(self.clock_rate)
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
