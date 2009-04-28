#!/usr/bin/python

# Construct the command to run real or dummy external tasks, and run it.

# supported job launch methods:
#  (i) direct execution in the background ( 'task &' )
#  (ii) qsub

# dummy tasks are always run directly because the dummy task script 
# currently requires commandline arguments (not supported by qsub).

import os
import re

class launcher:

    def __init__( self, config ):
        self.config = config

    def run( self, owner, task_name, ref_time, task, extra_vars=[] ):

        # who is running the control system
        sequenz_owner = os.environ[ 'USER' ]

        # sequenz environment script for this system
        sequenz_env = os.environ[ 'SEQUENZ_ENV' ]

        if re.search( '_test$', sequenz_owner) or re.search( '_dvel$', sequenz_owner ): 
            # for ecoconnect, if the system running on /test or /dvel
            # then replace '_oper' owner postfix with '_test' or '_dvel'
            system = re.split( '_', sequenz_owner )[-1]
            owner = re.sub( '_oper$', '_' + system, owner )

        command = ''
        if owner != sequenz_owner and not self.config.get('dummy_mode') and self.config.get('use_qsub'): 
            # run the task as its proper owner
	        #  + SUDO QSUB MUST BE ALLOWED
            #  + NOT FOR DIRECT JOB LAUNCH (assuming 'sudo task' not allowed in general)
	        #  + NOT FOR DUMMY MODE (other owners may not have dummy-task.py in $PATH)
            command  = 'sudo -u ' + owner 

        if self.config.get('dummy_mode') or task_name in self.config.get('dummy_out'):
            if not self.config.get( 'dummy_mode' ) and task_name in self.config.get('dummy_out'):
                self.log.warning( "dummying out " + self.identity + " in real mode")

            # substitute the dummy task program for the real task
            external_task = 'dummy-task.py'
        else:
            # run the real task
            if not re.match( '^/', task ):
                # relative path implies use sequenz 'tasks' subdir for this system
                sequenz_env = os.environ[ 'SEQUENZ_ENV' ]
                sysdir = re.sub( '[^/]*$', '', sequenz_env )
                external_task = sysdir + 'tasks/' + task
            else:
                # full task path given
                external_task = task

        if not self.config.get('use_qsub'):
            # run the task directly (i.e. not in the queue) in the background 
            command =  'export REFERENCE_TIME=' + ref_time + '; '
            command += 'export TASK_NAME=' + task_name + '; '
            for entry in extra_vars:
                [ var_name, value ] = entry
                command += 'export ' + var_name + '=' + value + '; '
            command += external_task + ' ' + task_name + ' ' + ref_time + ' ' + self.config.get('pyro_ns_group') + ' ' + str( self.config.get('dummy_mode') ) + ' ' + str( self.config.get('dummy_clock_rate') ) + ' ' + str( self.config.get('dummy_clock_offset') ) + ' &' 

        else:
            command += ' qsub -q ' + self.config.get('job_queue') + ' -z'

            command += ' -v REFERENCE_TIME=' + ref_time
            command += ',TASK_NAME=' + task_name
            command += ',SEQUENZ_ENV=' + sequenz_env
            #command += ',PYTHONPATH=' + os.environ['PYTHONPATH']

            for entry in extra_vars:
                [ var_name, value ] = entry
                command += ',' + var_name + '=' + value

            command += ' -k oe ' + external_task

        # RUN THE EXTERNAL TASK
        if os.system( command ) != 0:
            # NOTE: this means JOB LAUNCH failed, i.e. 
            # the job itself did not begin to execute.
            raise Exception( 'job launch failed: ' + task_name + ' ' + ref_time )
