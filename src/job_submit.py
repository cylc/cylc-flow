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

    def __init__( self, task_name, task, cycle_time, extra_vars, host = None ):

        self.task = task
        if host:
            self.remote_host = host
        self.task_name = task_name
        self.cycle_time = cycle_time
        self.extra_vars = extra_vars

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

    def set_local_environment( self ):
        # export cycle time and task name
        os.environ['CYCLE_TIME'] = self.cycle_time
        os.environ['TASK_NAME'] = self.task_name
        # and any extra variables
        for entry in self.extra_vars:
            [ var_name, value ] = entry
            value = self.interpolate( value )
            os.environ[var_name] = value

    def remote_environment_string( self ):
        # export cycle time and task name
        env = 'export CYCLE_TIME=' + self.cycle_time
        env += ' TASK_NAME=' + self.task_name
        # and system name and PNSHOST for this system
        env += ' PNS_GROUP=' + os.environ[ 'PNS_GROUP' ]
        # TO DO: THIS WILL FAIL FOR localhost!!!!!!!!!!!!!!!!!
        env += ' PNS_HOST=' + os.environ[ 'PNS_HOST' ]

        # and any extra variables
        for entry in self.extra_vars:
            [ var_name, value ] = entry
            # don't interpolate remote vars!
            env += ' ' + var_name + '=' + value
        return env

    def submit( self ):
        # OVERRIDE ME TO CONSTRUCT THE COMMAND TO EXECUTE
        # AND EITHER SET THE LOCAL ENVIRONMENT OR ADD
        # REMOTE ENVIRONMENT STRING TO THE COMMAND.
        print "ERROR jobs_submit: base class"
        sys.exit(1)

    def execute_local( self, command ):

        try:
            os.system( command + ' &' )
            #if retcode != 0:
            #    # the command returned non-zero exist status
            #    print >> sys.stderr, ' '.join( command_list ) + ' failed: ', retcode
            #    sys.exit(1)

        except:
            raise
            # the command was not invoked
            #print >> sys.stderr, 'ERROR: unable to execute ' + command_list
            #print >> sys.stderr, ' * Is [cylc]/bin in your $PATH?'
            #print >> sys.stderr, " * Are all cylc scripts executable?"
            #print >> sys.stderr, " * Have you run 'cylc configure' yet?"

            #raise Exception( 'job launch failed: ' + task_name + ' ' + c_time )

    def execute_local_BROKEN( self, command_list ):

        #for entry in command_list:
        #    print '---' + entry + '---'

        # command_list must be: [ command, arg1, arg2, ...]
        try:
            retcode = subprocess.call( command_list, shell=True )
            if retcode != 0:
                # the command returned non-zero exist status
                print >> sys.stderr, ' '.join( command_list ) + ' failed: ', retcode
                sys.exit(1)

        except OSError:
            # the command was not invoked
            print >> sys.stderr, 'ERROR: unable to execute ' + command_list
            print >> sys.stderr, ' * Is [cylc]/bin in your $PATH?'
            print >> sys.stderr, " * Are all cylc scripts executable?"
            print >> sys.stderr, " * Have you run 'cylc configure' yet?"

            #raise Exception( 'job launch failed: ' + task_name + ' ' + c_time )
