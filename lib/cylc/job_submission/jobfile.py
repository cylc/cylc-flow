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

import re
import tempfile
import StringIO
from cylc import cycle_time
from OrderedDict import OrderedDict

class jobfile(object):

    def __init__( self, task_id, cylc_env, task_env, ns_hier, 
            directive_prefix, directives, final_directive,
            manual_messaging, precommand_scripting, command_scripting,
            postcommand_scripting, remote_cylc_dir, remote_suite_dir,
            shell, share_dir, work_dir, simulation_mode, job_submission_method ):

        self.task_id = task_id
        self.cylc_env = cylc_env
        self.task_env = task_env
        self.directive_prefix = directive_prefix
        self.final_directive = final_directive
        self.directives = directives
        self.precommand_scripting = precommand_scripting
        self.command_scripting = command_scripting
        self.postcommand_scripting = postcommand_scripting
        self.shell = shell
        self.share_dir = share_dir
        self.work_dir = work_dir
        self.simulation_mode = simulation_mode
        self.job_submission_method = job_submission_method
        self.remote_cylc_dir = remote_cylc_dir
        self.remote_suite_dir = remote_suite_dir
        self.manual_messaging = manual_messaging
        self.namespace_hierarchy = ns_hier

        # Get NAME%CYCLE (cycling tasks) or NAME%TAG (asynchronous tasks)
        ( self.task_name, tag ) = task_id.split( '%' )
        # TO DO: asynchronous tasks
        self.cycle_time = tag

    def write( self, path ):
        self.FILE = open( path, 'wb' )
        self.write_header()
        self.write_directives()
        self.write_task_job_script_starting()
        self.write_environment_1()
        self.write_cylc_access()
        self.write_err_trap()
        self.write_task_started()
        self.write_work_directory_create()
        self.write_environment_2()
        self.write_manual_environment()
        self.write_pre_scripting()
        self.write_command_scripting()
        self.write_post_scripting()
        self.write_work_directory_remove()
        self.write_task_succeeded()
        self.write_eof()
        self.FILE.close()
        return

    def write_header( self ):
        self.FILE.write( '#!' + self.shell )
        self.FILE.write( '\n\n# ++++ THIS IS A CYLC TASK JOB SCRIPT ++++' )
        self.FILE.write( '\n# Task: ' + self.task_id )
        self.FILE.write( '\n# To be submitted by method: \'' + self.job_submission_method + '\'')

    def write_directives( self ):
        if len( self.directives.keys() ) == 0:
            return
        self.FILE.write( "\n\n# BATCH QUEUE SCHEDULER DIRECTIVES:" )
        for d in self.directives:
            self.FILE.write( '\n' + self.directive_prefix + d + " = " + self.directives[ d ] )
        self.FILE.write( '\n' + self.final_directive )

    def write_task_job_script_starting( self ):
        self.FILE.write( '\n\necho "TASK JOB SCRIPT STARTING"')

    def write_environment_1( self, BUFFER=None ):
        if not BUFFER:
            BUFFER = self.FILE

        # Override $CYLC_DIR and CYLC_SUITE_DEF_PATH for remotely hosted tasks
        if self.remote_cylc_dir:
            self.cylc_env['CYLC_DIR'] = self.remote_cylc_dir
        if self.remote_suite_dir:
            self.cylc_env['CYLC_SUITE_DEF_PATH'] = self.remote_suite_dir

        BUFFER.write( "\n\n# CYLC LOCATION, SUITE LOCATION, SUITE IDENTITY:" )
        for var in self.cylc_env:
            BUFFER.write( "\nexport " + var + "=" + str( self.cylc_env[var] ) )

        BUFFER.write( "\n\n# TASK IDENTITY:" )
        BUFFER.write( "\nexport CYLC_TASK_ID=" + self.task_id )
        BUFFER.write( "\nexport CYLC_TASK_NAME=" + self.task_name )
        BUFFER.write( "\nexport CYLC_TASK_CYCLE_TIME=" + self.cycle_time )
        BUFFER.write( '\nexport CYLC_TASK_NAMESPACE_HIERARCHY="' + ' '.join( self.namespace_hierarchy) + '"')

    def write_cylc_access( self, BUFFER=None ):
        # configure access to cylc first so that cylc commands can be
        # used in defining user environment variables, e.g.:
        #    NEXT_CYCLE=$( cylc util cycletime --add=6 )
        if not BUFFER:
            BUFFER = self.FILE
        BUFFER.write( "\n\n# ACCESS TO CYLC:" )
        BUFFER.write( "\nPATH=$CYLC_DIR/bin:$PATH" )
        BUFFER.write( "\n# Access to the suite bin dir:" )
        BUFFER.write( "\nPATH=$CYLC_SUITE_DEF_PATH/bin:$PATH" )
        BUFFER.write( "\nexport PATH" )

    def write_err_trap( self ):
        self.FILE.write( '\n\n# SET ERROR TRAPPING:' )
        self.FILE.write( '\nset -u # Fail when using an undefined variable' )
        self.FILE.write( '\n# Define the trap handler' )
        self.FILE.write( '\nHANDLE_TRAP() {' )
        self.FILE.write( '\n  echo Received signal "$@"' )
        self.FILE.write( '\n  cylc task failed "Task job script received signal $@"' )
        self.FILE.write( '\n  trap "" EXIT' )
        self.FILE.write( '\n  exit 0' )
        self.FILE.write( '\n}' )
        self.FILE.write( '\n# Trap any signals which could cause the script to exit' )
        self.FILE.write( '\ntrap "HANDLE_TRAP EXIT" EXIT' )
        self.FILE.write( '\ntrap "HANDLE_TRAP ERR"  ERR' )
        self.FILE.write( '\ntrap "HANDLE_TRAP TERM" TERM' )
        self.FILE.write( '\ntrap "HANDLE_TRAP XCPU" XCPU' )

    def write_task_started( self ):
        self.FILE.write( """

# SEND TASK STARTED MESSAGE:
cylc task started || exit 1""" )

    def write_work_directory_create( self ):
        data = { "share_dir": self.share_dir,  "work_dir": self.work_dir }
        self.FILE.write( """

# SHARE DIRECTORY CREATE
CYLC_SUITE_SHARE_PATH=%(share_dir)s
export CYLC_SUITE_SHARE_PATH
mkdir -p $CYLC_SUITE_DEF_PATH/share || true

# WORK DIRECTORY CREATE
CYLC_TASK_WORK_PATH=%(work_dir)s
export CYLC_TASK_WORK_PATH
mkdir -p $(dirname $CYLC_TASK_WORK_PATH) || true
mkdir -p $CYLC_TASK_WORK_PATH
cd $CYLC_TASK_WORK_PATH""" % data )

    def write_environment_2( self ):
        if len( self.task_env.keys()) > 0:
            self.FILE.write( "\n\n# ENVIRONMENT:" )
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

    def write_manual_environment( self ):
        if self.manual_messaging:
            strio = StringIO.StringIO()
            self.write_environment_1( strio )
            self.write_cylc_access( strio )
            # now escape quotes in the environment string
            str = strio.getvalue()
            strio.close()
            str = re.sub('"', '\\"', str )
            self.FILE.write( '\n\n# SUITE AND TASK IDENTITY FOR CUSTOM TASK WRAPPERS:')
            self.FILE.write( '\n# (contains embedded newlines so usage may require "QUOTES")' )
            self.FILE.write( '\nexport CYLC_SUITE_ENVIRONMENT="' + str + '"' )

    def write_pre_scripting( self ):
        if self.simulation_mode or not self.precommand_scripting:
            # ignore extra scripting in simulation mode
            return
        self.FILE.write( "\n\n# PRE-COMMAND SCRIPTING:" )
        self.FILE.write( "\n" + self.precommand_scripting )

    def write_command_scripting( self ):
        self.FILE.write( "\n\n# TASK COMMAND SCRIPTING:" )
        self.FILE.write( "\n" + self.command_scripting )

    def write_post_scripting( self ):
        if self.simulation_mode or not self.postcommand_scripting:
            # ignore extra scripting in simulation mode
            return
        self.FILE.write( "\n\n# POST COMMAND SCRIPTING:" )
        self.FILE.write( "\n" + self.postcommand_scripting )

    def write_work_directory_remove( self ):
        if self.manual_messaging:
            # don't remove the running directory of detaching tasks
            return
        self.FILE.write( """

# WORK DIRECTORY REMOVE
cd
rmdir $CYLC_TASK_WORK_PATH 2>/dev/null || true""" )

    def write_task_succeeded( self ):
        if self.manual_messaging:
            if self.simulation_mode:
                self.FILE.write( '\n\n# SEND TASK SUCCEEDED MESSAGE:')
                self.FILE.write( '\n# (this task handles its own completion messaging in real mode)"')
                self.FILE.write( '\ncylc task succeeded' )
                self.FILE.write( '\n\necho "JOB SCRIPT EXITING (TASK SUCCEEDED)"')
            else:
                self.FILE.write( '\n\necho "JOB SCRIPT EXITING: THIS TASK HANDLES ITS OWN COMPLETION MESSAGING"')
        else:
            self.FILE.write( '\n\n# SEND TASK SUCCEEDED MESSAGE:')
            self.FILE.write( '\ncylc task succeeded' )
            self.FILE.write( '\n\necho "JOB SCRIPT EXITING (TASK SUCCEEDED)"')
        self.FILE.write( '\ntrap "" EXIT' )

    def write_eof( self ):
        self.FILE.write( '\n\n#EOF' )
