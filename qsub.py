#!/usr/bin/python

import os

def run( user_prefix, task_name, ref_time, task, extra_vars=[] ):

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

        command += ' -oe ' + task 

        os.system( command + ' &' )
