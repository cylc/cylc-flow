#!/usr/bin/python

import os
import re
import config

# TO DO: EXTERNAL PROGRAMS AND MODULE LOCATIONS
# path = config.task_launch_dir

def run( owner, task_name, ref_time, task, extra_vars=[] ):

    # who is running the control system
    sequenz_owner = os.environ[ 'USER' ]

    if re.search( '_test$', sequenz_owner) or re.search( '_dvel$', sequenz_owner ): 
        # for ecoconnect, if the system running on /test or /dvel
        # then replace '_oper' owner postfix with '_test' or '_dvel'
            system = re.split( '_', sequenz_owner )[-1]
            owner = re.sub( '_oper$', '_' + system, owner )

    command = ''
    if owner != sequenz_owner and config.dummy_mode != True and config.job_launch_method == 'qsub': 
        # run the task as its proper owner
	#  + SUDO QSUB MUST BE ALLOWED
        #  + NOT FOR DIRECT JOB LAUNCH (assuming 'sudo task' not allowed in general)
	#  + NOT FOR DUMMY MODE (other owners may not have dummy_task.py in $PATH)
        command  = 'sudo -u ' + owner 

    if config.dummy_mode or task_name in config.dummy_out:
        # substitute the dummy task program for the real task
        external_task = 'dummy_task.py'
    else:
        # run the real task
        # external_task = path + '/' + task
        external_task = task

    if config.job_launch_method == 'direct':
        # run the task directly (i.e. not in the queue) in the background 
        command =  'export REFERENCE_TIME=' + ref_time + '; '
        command += 'export TASK_NAME=' + task_name + '; '
        for entry in extra_vars:
            [ var_name, value ] = entry
            command += 'export ' + var_name + '=' + value + '; '
        command += external_task + ' ' + task_name + ' ' + ref_time + ' ' + config.pyro_ns_group + ' ' + str( config.dummy_mode ) + ' ' + str( config.dummy_clock_rate ) + ' ' + str( config.dummy_clock_offset ) + ' &' 

    elif config.job_launch_method == 'qsub':
        # command += ' qsub -q ' + system + ' -z'
        print 'job_submit.py: using HARDWIRED TOPNET_TEST queue'
        command += ' qsub -q topnet_test -z'

        command += ' -v REFERENCE_TIME=' + ref_time
        command += ',TASK_NAME=' + task_name

        for entry in extra_vars:
            [ var_name, value ] = entry
            command += ',' + var_name + '=' + value

        command += ' -k oe ' + external_task

    else:
        print 'ERROR: UNKNOWN JOB LAUNCH METHOD: ' + config.job_launch_method
        raise Exception( 'job launch failed: ' + task_name + ' ' + ref_time )

    # RUN THE EXTERNAL TASK
    if os.system( command ) != 0:
        # NOTE: this means JOB LAUNCH failed, i.e. 
        # the job itself did not begin to execute.
	print command
        raise Exception( 'job launch failed: ' + task_name + ' ' + ref_time )
