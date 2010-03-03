#!/usr/bin/python

import os
import re

class qsub( job_submit ):

    def __init__( self, task_name, task, cycle_time, queue, extra_vars=[] ):
        self.queue = queue
        job_submit.__init__( task_name, task, cycle_time, extra_vars )

    def construct_command( self ):
        
        command = ' qsub -q ' + self.queue + ' -z -v '
        command += ' CYLC_TIME=' + c_time
        command += ',CYLC_TASK='    + task_name
        command += ',CYLC_NS_HOST='  + os.environ['CYLC_NS_HOST']
        command += ',CYLC_NS_GROUP='  + os.environ['CYLC_NS_GROUP']
        # clock rate required for dummy mode operation
        command += ',CLOCK_RATE='   + os.environ['CLOCK_RATE']
        command += ',PYTHONPATH=' + os.environ['PYTHONPATH']

        for entry in extra_vars:
            [ var_name, value ] = entry
            command += ',' + var_name + '="' + value + '"'

        command += ' -k oe ' + self.task
