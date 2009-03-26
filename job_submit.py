#!/usr/bin/python

import os
import re
import config

# TO DO: EXTERNAL PROGRAMS AND MODULE LOCATIONS
path = config.task_launch_dir

def run( owner, task_name, ref_time, task, extra_vars=[] ):

    external_task = path + '/' + task
    if config.dummy_mode or task_name in config.dummy_out:
        # RUN AN EXTERNAL DUMMY TASK
        external_task = "./dummy_task.py"

        if config.dummy_job_launch == "direct":
            command =  'export REFERENCE_TIME=' + ref_time + '; '
            command += 'export TASK_NAME=' + task_name + '; '
            command += external_task + ' ' + task_name + ' ' + ref_time + ' &' 

            if os.system( command ) != 0:
                raise Exception( 'dummy_task.py failed: ' + task_name + ' ' + ref_time )
            return

    # ECOCONNECT: modify owner if we're running on /test or /dvel
    sequenz_owner = os.environ[ 'USER' ]
    if re.search( '_test$', sequenz_owner) or re.search( '_dvel$', sequenz_owner ): 
            system = re.split( '_', sequenz_owner )[-1]
            owner = re.sub( '_oper$', '_' + system, owner )

    if owner == sequenz_owner: 
        command = owner
    else:
        command  = 'sudo -u ' + owner 

    print "job_submit.py: TEMPORARILY using topnet_test queue"
    # command += ' qsub -q ' + system + ' -z'
    command += ' qsub -q topnet_test -z'

    command += ' -v REFERENCE_TIME=' + ref_time
    command += ',TASK_NAME=' + task_name

    for entry in extra_vars:
        [ var_name, value ] = entry
        command += ',' + var_name + '=' + value

    command += ' -k oe ' + external_task

    if os.system( command ) != 0:
        raise Exception( 'job launch failed: ' + task_name + ' ' + ref_time )
