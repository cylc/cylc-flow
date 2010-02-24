#!/usr/bin/python

# job submission (external task execution) base class

# specific submission methods should be formulated as derived classes in
# the job_submit sub-directory of the main cylc installation or of the
# task definition directories for specific cylc systems.

import re
import os
import sys
import subprocess

class job_submit:

    def __init__( self, task_name, task, cycle_time, extra_vars=[] ):

        self.task = task
        self.task_name = task_name
        self.cycle_time = cycle_time
        self.extra_vars = extra_vars

    def construct_command( self ):
        print >> sys.stderr, 'ERROR: use a job submission derived class'
        sys.exit(1)

    def interpolate( self, string ):

        # $VARNAME
        m = re.findall( "\$([a-zA-Z0-9_]+)", string )
        for var in m:
            if var in os.environ:
                # replace value with the env value
                val = os.environ[ var ]
                string = re.sub( '\$' + var, val, string )

        # ${VARNAME}
        m = re.findall( "\$\{([a-zA-Z0-9_]+)\}", string )
        for var in m:
            if var in os.environ:
                # replace value with the env value
                val = os.environ[ var ]
                string = re.sub( '\$\{' + var + '\}', val, string )

        return string

    def set_job_environment( self ):
        # export cycle time and task name
        os.environ['CYCLE_TIME'] = self.cycle_time
        os.environ['TASK_NAME'] = self.task_name
        # and any extra variables
        for entry in self.extra_vars:
            [ var_name, value ] = entry
            value = self.interpolate( value )
            os.environ[var_name] = value

    def submit( self ):

        command = self.construct_command() 
        self.set_job_environment()
    
        # subprocess.call() takes a list: [ command, arg1, arg2, ...]
        #execute = [ command ]
        #for f in command_options:
        #execute.append( f )

        try:
            retcode = subprocess.call( command, shell=True )
            if retcode != 0:
                # the command returned non-zero exist status
                print >> sys.stderr, execute.join( ' ' ) + ' failed: ', retcode
                sys.exit(1)

        except OSError:
            # the command was not invoked
            print >> sys.stderr, 'ERROR: unable to execute ' + command
            print >> sys.stderr, ' * Is [cylc]/bin in your $PATH?'
            print >> sys.stderr, " * Are all cylc scripts executable?"
            print >> sys.stderr, " * Have you run 'cylc configure' yet?"

            #raise Exception( 'job launch failed: ' + task_name + ' ' + c_time )
