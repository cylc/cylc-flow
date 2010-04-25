#!/usr/bin/python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# job submission (external task execution) base class

# specific submission methods should be formulated as derived classes in
# the job_submit sub-directory of the main cylc installation or of the
# task definition directories for specific cylc systems.

import re, os, sys
import subprocess
import cycle_time

class job_submit:

    def __init__( self, task_name, task, cycle_time, extra_vars, host = None ):

        self.task = ext_task
        self.remote_host = host
        self.owner = owner
        self.config = config

        self.task_id = task_id
        self.extra_vars = extra_vars

        # extract cycle time
        ( self.task_name, tag ) = task_id.split( '%' )
        if cycle_time.is_valid( tag ):
            self.cycle_time = tag
        else:
            self.tag = tag

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
        os.environ['TASK_NAME'] = self.task_name
        if self.cycle_time:
            os.environ['CYCLE_TIME'] = self.cycle_time
        else:
            os.environ['TAG'] = self.tag

        os.environ['TASK_ID'] = self.task_id
        # and any extra variables
        for entry in self.extra_vars:
            [ var_name, value ] = entry
            value = self.interpolate( value )
            os.environ[var_name] = value

    def write_local_environment( self, file ):
        file.write("export CYCLE_TIME=" + self.cycle_time + "\n" )
        file.write("export TASK_NAME=" + self.task_name + "\n" )
        file.write("export CYLC_DIR=" + os.environ[ 'CYLC_DIR' ] + "\n" )
        file.write(". $CYLC_DIR/cylc-env.sh\n")
        file.write("export PATH=" + os.environ['PATH'] + "\n" )  # for system scripts dir

        # global variables
        if 'CYLC_ON' in os.environ.keys():
            file.write("export CYLC_ON=true\n" )
        file.write("export CYLC_NS_GROUP=" + os.environ[ 'CYLC_NS_GROUP' ] + "\n" )
        file.write("export CYLC_NS_HOST=" + os.environ[ 'CYLC_NS_HOST' ] + "\n" )

        # system-specific global variables
        env = self.config.get('environment')
        for VAR in env.keys():
            file.write("export " + VAR + "=" + str( env[VAR] ) + "\n" )

        # extra task-specific variables
        for entry in self.extra_vars:
            [ var_name, value ] = entry
            value = self.interpolate( value )
            file.write("export " + var_name + "=" + value + "\n" )

    def remote_environment_string( self ):
        # export cycle time and task id
        if self.cycle_time:
            env = 'export CYCLE_TIME=' + self.cycle_time
        else:
            env = 'export TAG=' + self.tag

        env += ' TASK_ID=' + self.task_id
        # and system name and CYLC_NS_HOST for this system
        env += ' CYLC_NS_GROUP=' + os.environ[ 'CYLC_NS_GROUP' ]
        # TO DO: THIS WILL FAIL FOR localhost!!!!!!!!!!!!!!!!!
        env += ' CYLC_NS_HOST=' + os.environ[ 'CYLC_NS_HOST' ]

        if 'CYLC_ON' in os.environ.keys():
            # distinguish between cylc and and run-task invocations
            env += ' CYLC_ON=true'

        # and any extra variables
        for entry in self.extra_vars:
            ( var_name, value ) = entry
            # interpolate remote vars locally!
            value = self.interpolate( value )
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
