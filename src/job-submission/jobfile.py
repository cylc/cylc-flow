#!/usr/bin/env python

import tempfile
import cycle_time

class jobfile(object):

    def __init__( self, task_id, cylc_env, global_env, task_env, 
            global_pre_scripting, global_post_scripting, 
            task_pre_scripting, task_post_scripting, 
            directive_prefix, directives, task_command, 
            shell, dummy_mode, job_submission_method):

        self.task_id = task_id
        self.cylc_env = cylc_env
        self.global_env = global_env
        self.task_env = task_env
        self.global_pre_scripting = global_pre_scripting
        self.global_post_scripting = global_post_scripting
        self.task_pre_scripting = task_pre_scripting
        self.task_post_scripting = task_post_scripting
        self.directive_prefix = directive_prefix
        self.directives = directives
        self.task_command = task_command
        self.shell = shell
        self.dummy_mode = dummy_mode
        self.job_submission_method = job_submission_method

        # Get NAME%CYCLETIME (cycling tasks) or NAME%TAG (asynchronous tasks)
        ( self.task_name, tag ) = task_id.split( '%' )
        if cycle_time.is_valid( tag ):
            self.cycle_time = tag

    def write( self ):
        # Get a new temp filename, open it, and write the job script to it.

        # TO DO: use [,dir=] argument and allow user to configure the
        # temporary directory (default reads $TMPDIR, $TEMP, or $TMP)
        path = tempfile.mktemp( prefix='cylc-' + self.task_id + '-' ) 

        self.FILE = open( path, 'wb' )
        self.write_header()
        self.write_directives()
        self.write_environment()
        self.write_pre_scripting()
        self.write_task_command()
        self.write_post_scripting()
        self.FILE.write( '\n\n#EOF' )
        self.FILE.close() 

        return path

    def write_header( self ):
        self.FILE.write( '#!' + self.shell )
        self.FILE.write( '\n\n# ++++ THIS IS A CYLC TASK JOB SUBMISSION FILE ++++' )
        self.FILE.write( '\n# Task: ' + self.task_id )
        self.FILE.write( '\n# To be submitted by method: \'' + self.job_submission_method + '\'')

    def write_directives( self ):
        if len( self.directives.keys() ) == 0:
            return
        self.FILE.write( "\n\n# BATCH QUEUE SCHEDULER DIRECTIVES:" )
        for d in self.directives:
            self.FILE.write( '\n' + self.directive_prefix + d + " = " + self.directives[ d ] )
        self.FILE.write( '\n' + self.final_directive )

    def write_environment( self ):
        # Task-specific variables may reference other previously-defined
        # task-specific variables, or global variables. Thus we ensure
        # that the order of definition is preserved (and pass any such
        # references through as-is to the job script).

        # If the task overrides $CYLC_DIR and CYLC_SUITE_DIR
        # replace them in the global cylc environment (used by tasks
        # running on a remote host, to specify the remote cylc
        # installation and remote suite definition directory locations)
        if 'CYLC_DIR' in self.task_env:
            self.cylc_env['CYLC_DIR'] = self.task_env['CYLC_DIR']
        if 'CYLC_SUITE_DIR' in self.task_env:
            self.cylc_env['CYLC_SUITE_DIR'] = self.task_env['CYLC_SUITE_DIR']

        self.FILE.write( "\n\n# CYLC SUITE ENVIRONMENT:" )
        for var in self.cylc_env:
            self.FILE.write( "\nexport " + var + "=\"" + str( self.cylc_env[var] ) + "\"" )
        self.FILE.write( "\n\n# CYLC ENVIRONMENT:" )
        self.FILE.write( "\n. $CYLC_DIR/cylc-env.sh" )

        self.FILE.write( "\n\n# TASK IDENTITY:" )
        self.FILE.write( "\nexport TASK_ID=" + self.task_id )
        self.FILE.write( "\nexport TASK_NAME=" + self.task_name )
        self.FILE.write( "\nexport CYCLE_TIME=" + self.cycle_time )

        if len( self.global_env.keys()) > 0:
            self.FILE.write( "\n\n# SUITE GLOBAL VARIABLES:" )
            for var in self.global_env:
                self.FILE.write( "\nexport " + var + "=\"" + str( self.global_env[var] ) + "\"" )

        if len( self.task_env.keys()) > 0:
            self.FILE.write( "\n\n# TASK LOCAL VARIABLES:\n" )
            for var in self.task_env:
                self.FILE.write( "\nexport " + var + "=\"" + str( self.task_env[var] ) + "\"" )

    def write_pre_scripting( self ):
        if self.dummy_mode:
            # ignore extra scripting in dummy mode
            return
        if self.global_pre_scripting:
            self.FILE.write( "\n\n# GLOBAL PRE-COMMAND SCRIPTING:" )
            self.FILE.write( "\n" + self.global_pre_scripting )
        if self.task_pre_scripting:
            self.FILE.write( "\n\n# TASK PRE-COMMAND SCRIPTING:" )
            self.FILE.write( "\n" + self.task_pre_scripting )
 
    def write_task_command( self ):
        self.FILE.write( "\n\n# EXECUTE THE TASK:" )
        self.FILE.write( "\n" + self.task_command )

    def write_post_scripting( self ):
        if self.dummy_mode:
            # ignore extra scripting in dummy mode
            return
        if self.global_post_scripting:
            self.FILE.write( "\n\n# GLOBAL POST-COMMAND SCRIPTING:" )
            self.FILE.write( "\n" + self.global_post_scripting )
        if self.task_post_scripting:
            self.FILE.write( "\n\n# TASK POST-COMMAND SCRIPTING:" )
            self.FILE.write( "\n" + self.task_post_scripting )
 
