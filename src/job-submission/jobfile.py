#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2011 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

import tempfile
import cycle_time
from OrderedDict import OrderedDict

class jobfile(object):

    def __init__( self, task_id, cylc_env, global_env, task_env, 
            global_pre_scripting, global_post_scripting, 
            directive_prefix, global_dvs, directives, final_directive, 
            manual_messaging, task_command, remote_cylc_dir, remote_suite_dir,
            shell, simulation_mode, job_submission_method):

        self.task_id = task_id
        self.cylc_env = cylc_env
        self.global_env = global_env
        self.task_env = task_env
        self.global_pre_scripting = global_pre_scripting
        self.global_post_scripting = global_post_scripting
        self.directive_prefix = directive_prefix
        self.final_directive = final_directive
        self.global_dvs = global_dvs
        self.directives = directives
        self.task_command = task_command
        self.shell = shell
        self.simulation_mode = simulation_mode
        self.job_submission_method = job_submission_method
        self.remote_cylc_dir = remote_cylc_dir
        self.remote_suite_dir = remote_suite_dir
        self.manual_messaging = manual_messaging

        # Get NAME%CYCLETIME (cycling tasks) or NAME%TAG (asynchronous tasks)
        ( self.task_name, tag ) = task_id.split( '%' )
        if cycle_time.is_valid( tag ):
            self.cycle_time = tag

    def write( self ):
        # Get a new temp filename, open it, and write the task job script to it.

        # TO DO: use [,dir=] argument and allow user to configure the
        # temporary directory (default reads $TMPDIR, $TEMP, or $TMP)
        path = tempfile.mktemp( prefix='cylc-' + self.task_id + '-' ) 

        self.FILE = open( path, 'wb' )
        self.write_header()
        self.write_directives()
        self.write_environment_1()
        self.write_err_trap()
        self.write_task_started()
        self.write_environment_2()
        self.write_pre_scripting()
        self.write_task_command()
        self.write_post_scripting()
        self.write_task_succeeded()
        return path

    def write_task_succeeded( self ):
        if self.manual_messaging:
            self.FILE.write( '\n\n# THIS TASK HANDLES FINISHED MESSAGING ITSELF')
        else:
            self.FILE.write( '\n\n# SEND THE TASK SUCCEEDED MESSAGE')
            self.FILE.write( '\n cylc task succeeded' )
            self.FILE.write( '\n\n#EOF' )
            self.FILE.close() 

    def write_header( self ):
        self.FILE.write( '#!' + self.shell )
        self.FILE.write( '\n\n# ++++ THIS IS A CYLC TASK JOB SCRIPT ++++' )
        self.FILE.write( '\n# Task: ' + self.task_id )
        self.FILE.write( '\n# To be submitted by method: \'' + self.job_submission_method + '\'')

    def write_directives( self ):
        # override global with task-specific directives
        dvs = OrderedDict()
        if self.global_dvs:
            for var in self.global_dvs.keys():
                dvs[var] = self.global_dvs[var]
        if self.directives:
            for var in self.directives:
                dvs[var] = self.directives[var]
        if len( dvs.keys() ) == 0:
            return
        self.FILE.write( "\n\n# BATCH QUEUE SCHEDULER DIRECTIVES:" )
        for d in dvs:
            self.FILE.write( '\n' + self.directive_prefix + d + " = " + dvs[ d ] )
        self.FILE.write( '\n' + self.final_directive )

    def write_environment_1( self ):
        # Task-specific variables may reference other previously-defined
        # task-specific variables, or global variables. Thus we ensure
        # that the order of definition is preserved (and pass any such
        # references through as-is to the task job script).

        # Override $CYLC_DIR and CYLC_SUITE_DIR for remotely hosted tasks
        if self.remote_cylc_dir:
            self.cylc_env['CYLC_DIR'] = self.remote_cylc_dir
        if self.remote_suite_dir:
            self.cylc_env['CYLC_SUITE_DIR'] = self.remote_suite_dir

        self.FILE.write( "\n\n# CYLC LOCATION, SUITE LOCATION, SUITE IDENTITY:" )
        for var in self.cylc_env:
            self.FILE.write( "\nexport " + var + "=\"" + str( self.cylc_env[var] ) + "\"" )

        self.FILE.write( "\n\n# TASK IDENTITY:" )
        self.FILE.write( "\nexport TASK_ID=" + self.task_id )
        self.FILE.write( "\nexport TASK_NAME=" + self.task_name )
        self.FILE.write( "\nexport CYCLE_TIME=" + self.cycle_time )

    def write_err_trap( self ):
        self.FILE.write( """

# SET THE ERROR TRAP 
set -e; trap 'cylc task failed \"error trapped\"' ERR""" )

    def write_task_started( self ):
        self.FILE.write( """

# SEND THE TASK STARTED MESSAGE
cylc task started || exit 1""" )

    def write_environment_2( self ):
        # configure access to cylc now so that cylc commands can be used
        # in global and local environment variables, e.g.: 
        #    NEXT_CYCLE=$( cylc util cycletime --add=6 )
        self.FILE.write( "\n\n# ACCESS TO CYLC:" )
        self.FILE.write( "\n. $CYLC_DIR/environment.sh" )

        if len( self.global_env.keys()) > 0:
            self.FILE.write( "\n\n# GLOBAL VARIABLES:" )
            for var in self.global_env:
                self.FILE.write( "\n" + var + "=\"" + str( self.global_env[var] ) + "\"" )
            # export them all (see note below)
            self.FILE.write( "\nexport" )
            for var in self.global_env:
                self.FILE.write( " " + var )

        if len( self.task_env.keys()) > 0:
            self.FILE.write( "\n\n# LOCAL VARIABLES:" )
            for var in self.task_env:
                self.FILE.write( "\n" + var + "=\"" + str( self.task_env[var] ) + "\"" )
            # export them all (see note below)
            self.FILE.write( "\nexport" )
            for var in self.task_env:
                self.FILE.write( " " + var )

            # NOTE: the reason for separate export of user-specified
            # variables is this: inline export does not activate the
            # error trap if sub-expressions fail, e.g. (not typo in
            # 'echo' command name):
            # export FOO=$( ecko foo )  # error not trapped!
            # FOO=$( ecko foo )  # error trapped

    def write_pre_scripting( self ):
        if self.simulation_mode:
            # ignore extra scripting in simulation mode
            return
        if self.global_pre_scripting:
            self.FILE.write( "\n\n# GLOBAL PRE-COMMAND SCRIPTING:" )
            self.FILE.write( "\n" + self.global_pre_scripting )

    def write_task_command( self ):
        self.FILE.write( "\n\n# EXECUTE THE TASK:" )
        self.FILE.write( "\n" + self.task_command )

    def write_post_scripting( self ):
        if self.simulation_mode:
            # ignore extra scripting in simulation mode
            return
        if self.global_post_scripting:
            self.FILE.write( "\n\n# GLOBAL POST-COMMAND SCRIPTING:" )
            self.FILE.write( "\n" + self.global_post_scripting )
