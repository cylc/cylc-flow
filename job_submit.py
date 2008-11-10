#!/usr/bin/python

import os
import config

# TO DO: EXTERNAL PROGRAMS AND MODULE LOCATIONS
path = '/test/ecoconnect_test/ecocontroller/external'

def run( user_prefix, task_name, ref_time, task, extra_vars=[] ):

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


    # QSUB AS THE DESIGNATED USER
    temp = os.environ[ 'USER' ].split('_')
    system = temp[ len(temp) - 1 ] # oper, test, dvel
    user = user_prefix + '_' + system

    command  = 'sudo -u ' + user 
    command += ' qsub -q ' + system + ' -z'
    command += ' -v REFERENCE_TIME=' + ref_time
    command += ',TASK_NAME=' + task_name

    for entry in extra_vars:
        [ var_name, value ] = entry
        command += ',' + var_name + '=' + value

    command += ' -k oe ' + external_task

    if os.system( command ) != 0:
        raise Exception( 'job launch failed: ' + task_name + ' ' + ref_time )
