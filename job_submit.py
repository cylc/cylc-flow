#!/usr/bin/python

import os
import config

# TO DO: WHERE TO KEEP EXTERNAL PROGRAMS AND HOW TO REFER TO THEM
path = '/test/ecoconnect_test/ecocontroller/external'

def run( user_prefix, task_name, ref_time, task, extra_vars=[] ):

    if config.dummy_mode or task_name in config.dummy_out:
        # DUMMY MODE
        if os.system( './dummy_task.py ' + task_name + " " + ref_time + " &" ) != 0:
            raise Exception( 'dummy_task.py failed: ' + task_name + ' ' + ref_time )

    else:
        # REAL MODE
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

        command += ' -k oe ' + path + '/' + task 

        if os.system( command ) != 0:
            raise Exception( 'qsub failed: ' + task_name + ' ' + ref_time )
