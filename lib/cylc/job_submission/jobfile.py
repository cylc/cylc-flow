#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
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
import StringIO
from copy import deepcopy

class jobfile(object):

    def __init__( self, task_id, cylc_env, task_env, ns_hier,
            directive_prefix, directive_connector, directives,
            final_directive, manual_messaging, initial_scripting,
            precommand_scripting, command_scripting, try_number,
            postcommand_scripting, remote_cylc_dir, remote_suite_dir,
            shell, share_dir, work_dir, log_root, simulation_mode,
            job_submission_method, ssh_messaging ):

        self.task_id = task_id
        self.cylc_env = deepcopy(cylc_env)  # deep copy as may be modified below
        self.task_env = task_env
        self.directive_prefix = directive_prefix
        self.directive_connector = directive_connector
        self.final_directive = final_directive
        self.directives = directives
        self.initial_scripting = initial_scripting
        self.precommand_scripting = precommand_scripting
        self.command_scripting = command_scripting
        self.try_number = try_number
        self.postcommand_scripting = postcommand_scripting
        self.shell = shell
        self.share_dir = share_dir
        self.work_dir = work_dir
        self.log_root = log_root
        self.simulation_mode = simulation_mode
        self.job_submission_method = job_submission_method
        self.remote_cylc_dir = remote_cylc_dir
        self.remote_suite_dir = remote_suite_dir
        self.manual_messaging = manual_messaging
        self.namespace_hierarchy = ns_hier
        self.ssh_messaging = ssh_messaging

        # Get NAME%CYCLE (cycling tasks) or NAME%TAG (asynchronous tasks)
        ( self.task_name, tag ) = task_id.split( '%' )
        # TO DO: asynchronous tasks
        self.cycle_time = tag

    def write( self, path ):
        # Write each job script section in turn. In simulation mode,
        # omit anything not required for local submission of dummy tasks
        # (initial scripting or user-defined environment etc. may cause
        # trouble in sim mode by referencing undefined variables or
        # sourcing scripts that are not available locally).

        # Access to cylc must be configured before user environment so
        # that cylc commands can be used in defining user environment
        # variables: NEXT_CYCLE=$( cylc cycletime --offset-hours=6 )

        self.FILE = open( path, 'wb' )
        self.write_header()

        if not self.simulation_mode:
            self.write_directives()

        self.write_task_job_script_starting()

        self.write_err_trap()

        if not self.simulation_mode:
            self.write_cylc_access()
            self.write_initial_scripting()

        self.write_task_started()
        self.write_environment_1()
        if not self.simulation_mode:
            self.write_environment_2()
            self.write_suite_bin_access()

        if self.simulation_mode:
            key = "CYLC_TASK_DUMMY_RUN_LENGTH"
            self.FILE.write( "\n%s=%s" % ( key, self.task_env[key] ) )
        else:
            self.write_work_directory_create()
            self.write_manual_environment()
            self.write_identity_scripting()
            self.write_pre_scripting()

        self.write_command_scripting()

        if not self.simulation_mode:
            self.write_post_scripting()
            self.write_work_directory_remove()

        self.write_task_succeeded()
        self.write_eof()
        self.FILE.close()

    def write_header( self ):
        self.FILE.write( '#!' + self.shell )
        self.FILE.write( '\n\n# ++++ THIS IS A CYLC TASK JOB SCRIPT ++++' )
        if self.simulation_mode:
            self.FILE.write( '\n# SIMULATION MODE: some sections omitted.' )
        self.FILE.write( '\n# Task: ' + self.task_id )
        self.FILE.write( '\n# To be submitted by method: \'' + self.job_submission_method + '\'')

    def write_directives( self ):
        if len( self.directives.keys() ) == 0 or not self.directive_prefix:
            return
        self.FILE.write( "\n\n# DIRECTIVES:" )
        for d in self.directives:
            self.FILE.write( '\n' + self.directive_prefix + ' ' + d + self.directive_connector + self.directives[ d ] )
        if self.final_directive:
            self.FILE.write( '\n' + self.final_directive )

    def write_task_job_script_starting( self ):
        self.FILE.write( '\n\necho "JOB SCRIPT STARTING"')

    def write_initial_scripting( self, BUFFER=None ):
        if not self.initial_scripting:
            # ignore initial scripting in simulation mode
            return
        if not BUFFER:
            BUFFER = self.FILE
        BUFFER.write( "\n\n# INITIAL SCRIPTING:\n" )
        BUFFER.write( self.initial_scripting )

    def write_environment_1( self, BUFFER=None ):
        if not BUFFER:
            BUFFER = self.FILE

        # Override CYLC_SUITE_DEF_PATH for remotely hosted tasks
        if self.remote_suite_dir:
            self.cylc_env['CYLC_SUITE_DEF_PATH'] = self.remote_suite_dir

        BUFFER.write( "\n\n# CYLC LOCATION; SUITE LOCATION, IDENTITY, AND ENVIRONMENT:" )
        for var in self.cylc_env:
            BUFFER.write( "\nexport " + var + "=" + str( self.cylc_env[var] ) )

        BUFFER.write( "\n\n# CYLC TASK IDENTITY AND ENVIRONMENT:" )
        BUFFER.write( "\nexport CYLC_TASK_ID=" + self.task_id )
        BUFFER.write( "\nexport CYLC_TASK_NAME=" + self.task_name )
        BUFFER.write( "\nexport CYLC_TASK_CYCLE_TIME=" + self.cycle_time )
        BUFFER.write( "\nexport CYLC_TASK_LOG_ROOT=" + self.log_root )
        BUFFER.write( '\nexport CYLC_TASK_NAMESPACE_HIERARCHY="' + ' '.join( self.namespace_hierarchy) + '"')
        BUFFER.write( "\nexport CYLC_TASK_TRY_NUMBER=" + str(self.try_number) )
        BUFFER.write( "\nexport CYLC_TASK_SSH_MESSAGING=" + str(self.ssh_messaging) )
        BUFFER.write( "\nexport CYLC_TASK_WORK_PATH=" + self.work_dir )
        BUFFER.write( "\n# Note the suite share path may actually be family- or task-specific:" )
        BUFFER.write( "\nexport CYLC_SUITE_SHARE_PATH=" + self.share_dir )

    def write_cylc_access( self, BUFFER=None ):
        if not BUFFER:
            BUFFER = self.FILE
        if self.remote_cylc_dir:
            BUFFER.write( "\n\n# ACCESS TO CYLC:" )
            BUFFER.write( "\nexport PATH=" + self.remote_cylc_dir + "/bin:$PATH" )

    def write_suite_bin_access( self, BUFFER=None ):
        if not BUFFER:
            BUFFER = self.FILE
        BUFFER.write( "\n\n# ACCESS TO THE SUITE BIN DIRECTORY:" )
        BUFFER.write( "\nexport PATH=$CYLC_SUITE_DEF_PATH/bin:$PATH" )

    def write_err_trap( self ):
        self.FILE.write( '\n\n# SET ERROR TRAPPING:' )
        self.FILE.write( '\nset -u # Fail when using an undefined variable' )
        self.FILE.write( '\n# Define the trap handler' )
        self.FILE.write( '\nHANDLE_TRAP() {' )
        self.FILE.write( '\n  echo Received signal "$@"' )
        self.FILE.write( '\n  # SEND TASK FAILED MESSAGE' )
        self.FILE.write( '\n  cylc task failed "Task job script received signal $@"' )
        self.FILE.write( '\n  trap "" EXIT' )
        self.FILE.write( '\n  exit 0' )
        self.FILE.write( '\n}' )
        self.FILE.write( '\n# Trap signals that could cause this script to exit:' )
        self.FILE.write( '\ntrap "HANDLE_TRAP EXIT" EXIT' )
        self.FILE.write( '\ntrap "HANDLE_TRAP ERR"  ERR' )
        self.FILE.write( '\ntrap "HANDLE_TRAP TERM" TERM' )
        self.FILE.write( '\ntrap "HANDLE_TRAP XCPU" XCPU' )

    def write_task_started( self ):
        self.FILE.write( """

# SEND TASK STARTED MESSAGE:
cylc task started""" )

    def write_work_directory_create( self ):
        self.FILE.write( """

# SHARE DIRECTORY CREATE:
mkdir -p $CYLC_SUITE_SHARE_PATH || true

# WORK DIRECTORY CREATE:
mkdir -p $(dirname $CYLC_TASK_WORK_PATH) || true
mkdir -p $CYLC_TASK_WORK_PATH
cd $CYLC_TASK_WORK_PATH""" )

    def write_environment_2( self ):

        if len( self.task_env.keys()) > 0:
            self.FILE.write( "\n\n# TASK RUNTIME ENVIRONMENT:" )
            for var in self.task_env:
                # Write each variable assignment expression, with
                # values quoted to handle spaces.
                value = str( self.task_env[var] )
                # But first check for an initial tilde as shell tilde
                # expansion is broken by quoting.
                match = re.match("^(~[^/\s]*/)(.*)$", value)
                if match:
                    # ~foo/bar or ~/bar
                    # write as ~foo/"bar" or ~/"bar"
                    head, tail = match.groups()
                    self.FILE.write( '\n%s=%s"%s"' % ( var, head, tail ) )
                elif re.match("^~[^\s]*$", value):
                    # plain ~foo or just ~
                    # just leave unquoted as subsequent spaces don't
                    # make sense in this case anyway
                    self.FILE.write( '\n%s=%s' % ( var, value ) )
                else:
                    # Non tilde values - quote the lot.
                    # This gets values like "~one ~two" too, but these
                    # (in variable values) aren't expanded by the shell
                    # anyway so it doesn't matter.
                    self.FILE.write( '\n%s="%s"' % ( var, value ) )
            # export them all (see note below)
            self.FILE.write( "\nexport" )
            for var in self.task_env:
                self.FILE.write( " " + var )

            # NOTE: the reason for separate export of user-specified
            # variables is this: inline export does not activate the
            # error trap if sub-expressions fail, e.g. (note typo in
            # 'echo' command name):
            # export FOO=$( ecko foo )  # error not trapped!
            # FOO=$( ecko foo )  # error trapped

            # NOTE ON TILDE EXPANSION:
            # The code above handles the following correctly:
            #| ~foo/bar
            #| ~/bar
            #| ~/filename with spaces
            #| ~foo
            #| ~

    def write_manual_environment( self ):
        if self.manual_messaging:
            strio = StringIO.StringIO()
            self.write_initial_scripting( strio )
            self.write_environment_1( strio )
            self.write_cylc_access( strio )
            # now escape quotes in the environment string
            str = strio.getvalue()
            strio.close()
            str = re.sub('"', '\\"', str )
            self.FILE.write( '\n\n# SUITE AND TASK IDENTITY FOR CUSTOM TASK WRAPPERS:')
            self.FILE.write( '\n# (contains embedded newlines so usage may require "QUOTES")' )
            self.FILE.write( '\nexport CYLC_SUITE_ENVIRONMENT="' + str + '"' )

    def write_identity_scripting( self ):
        self.FILE.write( "\n\n# TASK IDENTITY SCRIPTING:" )
        self.FILE.write( '''
echo "cylc Suite and Task Identity:"
echo "  Suite Name  : $CYLC_SUITE_REG_NAME"
echo "  Suite Host  : $CYLC_SUITE_HOST"
echo "  Suite Port  : $CYLC_SUITE_PORT"
echo "  Suite Owner : $CYLC_SUITE_OWNER"
echo "  Task ID     : $CYLC_TASK_ID"
if [[ $(uname) == AIX ]]; then
   # on AIX the hostname command has no '-f' option
   echo "  Task Host   : $(hostname).$(namerslv -sn | awk '{print $2}')"
else
    echo "  Task Host   : $(hostname -f)"
fi
echo "  Task Owner  : $USER"
echo "  Task Try No.: $CYLC_TASK_TRY_NUMBER"
echo ""''')

    def write_pre_scripting( self ):
        if not self.precommand_scripting:
            return
        self.FILE.write( "\n\n# PRE-COMMAND SCRIPTING:" )
        self.FILE.write( "\n" + self.precommand_scripting )

    def write_command_scripting( self ):
        self.FILE.write( "\n\n# TASK COMMAND SCRIPTING:" )
        self.FILE.write( "\n" + self.command_scripting )

    def write_post_scripting( self ):
        if not self.postcommand_scripting:
            return
        self.FILE.write( "\n\n# POST COMMAND SCRIPTING:" )
        self.FILE.write( "\n" + self.postcommand_scripting )

    def write_work_directory_remove( self ):
        if self.manual_messaging:
            self.FILE.write( """

# (detaching task: cannot safely remove the WORK DIRECTORY here)""")
            return
        self.FILE.write( """

# EMPTY WORK DIRECTORY REMOVE:
cd
rmdir $CYLC_TASK_WORK_PATH 2>/dev/null || true""" )

    def write_task_succeeded( self ):
        if self.manual_messaging:
            if self.simulation_mode:
                self.FILE.write( '\n\n# SEND TASK SUCCEEDED MESSAGE:')
                self.FILE.write( '\n# (this task handles its own completion messaging in live mode)"')
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
