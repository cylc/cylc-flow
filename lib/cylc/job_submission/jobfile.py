#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
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

from cylc.TaskID import TaskID

import re, os
import StringIO
from cylc.global_config import gcfg

class jobfile(object):

    def __init__( self, suite, log_root, job_submission_method, task_id, jobconfig ):

        self.log_root = log_root
        self.job_submission_method = job_submission_method
        self.task_id = task_id
        self.jobconfig = jobconfig
        self.suite = suite
        self.owner = jobconfig['task owner']
        self.host = jobconfig['task host']

        self.task_name, self.tag = task_id.split( TaskID.DELIM )

    def write( self, path ):
        ############# !!!!!!!! WARNING !!!!!!!!!!! #####################
        # BE EXTREMELY WARY OF CHANGING THE ORDER OF JOB SCRIPT SECTIONS
        # Users may be relying on the existing order (see for example
        # the comment below on suite bin path being required before
        # task runtime environment setup).
        ################################################################

        # Write each job script section in turn. 

        # Access to cylc must be configured before user environment so
        # that cylc commands can be used in defining user environment
        # variables: NEXT_CYCLE=$( cylc cycletime --offset-hours=6 )

        self.FILE = open( path, 'wb' )
        self.write_header()

        self.write_directives()

        self.write_task_job_script_starting()
        self.write_err_trap()

        self.write_cylc_access()
        self.write_initial_scripting()

        self.write_environment_1()
        self.write_enviro_scripting()

        # suite bin access must be before runtime environment
        # because suite bin commands may be used in variable
        # assignment expressions: FOO=$(command args).
        self.write_suite_bin_access()

        self.write_environment_2()
        self.write_task_started()

        self.write_work_directory_create()
        self.write_manual_environment()
        self.write_identity_scripting()

        self.write_pre_scripting()
        self.write_command_scripting()
        self.write_post_scripting()

        self.write_work_directory_remove()

        self.write_task_succeeded()
        self.write_eof()
        self.FILE.close()

    def write_header( self ):
        self.FILE.write( '#!' + self.jobconfig['job script shell'] )
        self.FILE.write( '\n\n# ++++ THIS IS A CYLC TASK JOB SCRIPT ++++' )
        self.FILE.write( '\n# Task: ' + self.task_id )
        self.FILE.write( '\n# To be submitted by method: \'' + self.job_submission_method + '\'' )

    def write_directives( self ):
        directives = self.jobconfig['directives']
        prefix = self.jobconfig['directive prefix']
        final = self.jobconfig['directive final']
        connector = self.jobconfig['directive connector']

        if len( directives.keys() ) == 0 or not prefix:
            return

        self.FILE.write( "\n\n# DIRECTIVES:" )
        for d in directives:
            self.FILE.write( '\n' + prefix + ' ' + d + connector + directives[ d ] )
        if final:
            self.FILE.write( '\n' + final )

    def write_task_job_script_starting( self ):
        self.FILE.write( '\n\necho "JOB SCRIPT STARTING"')

    def write_initial_scripting( self, BUFFER=None ):
        iscr = self.jobconfig['initial scripting']
        if not iscr:
            return
        if not BUFFER:
            BUFFER = self.FILE
        BUFFER.write( "\n\n# INITIAL SCRIPTING:\n" )
        BUFFER.write( iscr )

    def write_enviro_scripting( self, BUFFER=None ):
        escr = self.jobconfig['environment scripting']
        if not escr:
            return
        if not BUFFER:
            BUFFER = self.FILE
        BUFFER.write( "\n\n# ENVIRONMENT SCRIPTING:\n" )
        BUFFER.write( escr )

    def write_environment_1( self, BUFFER=None ):
        if not BUFFER:
            BUFFER = self.FILE

        # Override CYLC_SUITE_DEF_PATH for remotely hosted tasks
        rsp = self.jobconfig['remote suite path']
        cenv = self.jobconfig['cylc environment']
        if rsp:
            cenv['CYLC_SUITE_DEF_PATH'] = rsp
        else:
            # for remote tasks that don't specify a remote suite dir
            # default to replace home dir with literal '$HOME' (works
            # for local tasks too):
            cenv[ 'CYLC_SUITE_DEF_PATH' ] = re.sub( os.environ['HOME'], '$HOME', cenv['CYLC_SUITE_DEF_PATH'])

        work_dir  = os.path.join( gcfg.get_derived_host_item( self.suite, 'suite work directory', self.host, self.owner ), self.jobconfig['work sub-directory'] )

        use_login_shell = gcfg.get_host_item( 'use login shell', self.host, self.owner )

        use_ssh_messaging = gcfg.get_host_item( 'use ssh messaging', self.host, self.owner )

        BUFFER.write( "\n\n# CYLC LOCATION; SUITE LOCATION, IDENTITY, AND ENVIRONMENT:" )
        for var, val in cenv.items():
            BUFFER.write( "\nexport " + var + "=" + str(val) )
        if str(cenv.get('CYLC_UTC')) == 'True':
            BUFFER.write( "\nexport TZ=UTC" )

        BUFFER.write( "\n\n# CYLC TASK IDENTITY AND ENVIRONMENT:" )
        BUFFER.write( "\nexport CYLC_TASK_ID=" + self.task_id )
        BUFFER.write( "\nexport CYLC_TASK_NAME=" + self.task_name )
        BUFFER.write( "\nexport CYLC_TASK_IS_COLDSTART=" + str( self.jobconfig['is cold-start']) )
        BUFFER.write( "\nexport CYLC_TASK_CYCLE_TIME=" + self.tag )
        BUFFER.write( "\nexport CYLC_TASK_LOG_ROOT=" + self.log_root )
        BUFFER.write( '\nexport CYLC_TASK_NAMESPACE_HIERARCHY="' + ' '.join( self.jobconfig['namespace hierarchy']) + '"')
        BUFFER.write( "\nexport CYLC_TASK_TRY_NUMBER=" + str(self.jobconfig['try number']) )
        BUFFER.write( "\nexport CYLC_TASK_SSH_MESSAGING=" + str(use_ssh_messaging) )
        BUFFER.write( "\nexport CYLC_TASK_SSH_LOGIN_SHELL=" + str(use_login_shell) )
        BUFFER.write( "\nexport CYLC_TASK_WORK_DIR=" + work_dir )
        BUFFER.write( "\nexport CYLC_TASK_WORK_PATH=$CYLC_TASK_WORK_DIR # back compat") 

        BUFFER.write( r"""

# CYLC SUITE ENVIRONMENT FILE:
if (($# > 0)) && [[ $1 == '--write-suite-env' ]]; then
    shift 1
    {""" )
        for var in sorted(cenv):
            BUFFER.write( "\n        echo \"%(var)s=$%(var)s\"" %
                          {"var": var} )
        BUFFER.write( r"""
    } >$CYLC_SUITE_RUN_DIR/cylc-suite-env
    trap '' EXIT
    exit
fi
""" )

    def write_cylc_access( self, BUFFER=None ):
        if not BUFFER:
            BUFFER = self.FILE
        rcp = gcfg.get_host_item( 'cylc bin directory', self.host, self.owner )
        if rcp:
            BUFFER.write( "\n\n# ACCESS TO CYLC:" )
            BUFFER.write( "\nexport PATH=" + rcp + ":$PATH" )

    def write_suite_bin_access( self, BUFFER=None ):
        if not BUFFER:
            BUFFER = self.FILE
        BUFFER.write( "\n\n# ACCESS TO THE SUITE BIN DIRECTORY:" )
        BUFFER.write( "\nexport PATH=$CYLC_SUITE_DEF_PATH/bin:$PATH" )

    def write_err_trap( self ):
        self.FILE.write( r"""

# SET ERROR TRAPPING:
set -u # Fail when using an undefined variable
# Define the trap handler
SIGNALS="EXIT ERR TERM XCPU"
function HANDLE_TRAP() {
    local SIGNAL=$1
    echo "Received signal $SIGNAL"
    local S=
    for S in $SIGNALS; do
        trap "" $S
    done
    # SEND TASK FAILED MESSAGE
    if [[ -n ${CYLC_TASK_LOG_ROOT:-} ]]; then
        {
            echo "CYLC_JOB_EXIT=$SIGNAL"
            date -u +'CYLC_JOB_EXIT_TIME=%FT%H:%M:%SZ'
        } >>$CYLC_TASK_LOG_ROOT.status
    fi
    cylc task failed "Task job script received signal $@"
    exit 1
}
# Trap signals that could cause this script to exit:
for S in $SIGNALS; do
    trap "HANDLE_TRAP $S" $S
done""")

    def write_task_started( self ):
        self.FILE.write( r"""

# SEND TASK STARTED MESSAGE:
{
    echo "CYLC_JOB_PID=$$"
    date -u +'CYLC_JOB_INIT_TIME=%FT%H:%M:%SZ'
} >$CYLC_TASK_LOG_ROOT.status
cylc task started""" )

    def write_work_directory_create( self ):
        self.FILE.write( """

# SHARE DIRECTORY CREATE:
mkdir -p $CYLC_SUITE_SHARE_DIR || true

# WORK DIRECTORY CREATE:
mkdir -p $(dirname $CYLC_TASK_WORK_DIR) || true
mkdir -p $CYLC_TASK_WORK_DIR
cd $CYLC_TASK_WORK_DIR""" )

    def get_var_assign( self, var, value ):
        # generate an environment variable assignment expression
        # 'var=value' but with values quoted to handle internal spaces,
        # but escape initial tilde (quoting disables tilde expansion).
        value = str(value) # (needed?)
        match = re.match("^(~[^/\s]*/)(.*)$", value)
        if match:
            # ~foo/bar or ~/bar
            # write as ~foo/"bar" or ~/"bar"
            head, tail = match.groups()
            expr = '\n%s=%s"%s"' % ( var, head, tail )
        elif re.match("^~[^\s]*$", value):
            # plain ~foo or just ~
            # just leave unquoted as subsequent spaces don't
            # make sense in this case anyway
            expr = '\n%s=%s' % ( var, value )
        else:
            # Non tilde values - quote the lot.
            # This gets values like "~one ~two" too, but these
            # (in variable values) aren't expanded by the shell
            # anyway so it doesn't matter.
            expr = '\n%s="%s"' % ( var, value )

        # NOTE ON TILDE EXPANSION:
        # The code above handles the following correctly:
        #| ~foo/bar
        #| ~/bar
        #| ~/filename with spaces
        #| ~foo
        #| ~

        # NOTE: the reason for separate export of user-specified
        # variables is this: inline export does not activate the
        # error trap if sub-expressions fail, e.g. (note typo in
        # 'echo' command name):
        # export FOO=$( ecko foo )  # error not trapped!
        # FOO=$( ecko foo )  # error trapped

        return expr

    def write_environment_2( self ):
        env = self.jobconfig['runtime environment']
        if len( env.keys()) == 0:
            return

        # generate variable assignment expressions
        self.FILE.write( "\n\n# TASK RUNTIME ENVIRONMENT:" )
        for var, val in env.items():
            self.FILE.write( self.get_var_assign(var,val))

        # export them all now (see note)
        self.FILE.write( "\nexport" )
        for var in env:
            self.FILE.write( " " + var )

    def write_manual_environment( self ):
        # TODO - THIS METHOD NEEDS UPDATING FOR CURRENT SECTIONS
        if not self.jobconfig['use manual completion']:
            return
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
        pcs = self.jobconfig['pre-command scripting']
        if not pcs:
            return
        self.FILE.write( "\n\n# PRE-COMMAND SCRIPTING:" )
        self.FILE.write( "\n" + pcs )

    def write_command_scripting( self ):
        self.FILE.write( "\n\n# TASK COMMAND SCRIPTING:" )
        self.FILE.write( "\n" + self.jobconfig['command scripting'] )

    def write_post_scripting( self ):
        pcs = self.jobconfig['post-command scripting']
        if not pcs:
            return
        self.FILE.write( "\n\n# POST COMMAND SCRIPTING:" )
        self.FILE.write( "\n" + pcs )

    def write_work_directory_remove( self ):
        if self.jobconfig['use manual completion']:
            self.FILE.write( """

# (detaching task: cannot safely remove the WORK DIRECTORY here)""")
            return
        self.FILE.write( """

# EMPTY WORK DIRECTORY REMOVE:
cd
rmdir $CYLC_TASK_WORK_DIR 2>/dev/null || true""" )

    def write_task_succeeded( self ):
        if self.jobconfig['use manual completion']:
            self.FILE.write( r"""

echo 'JOB SCRIPT EXITING: THIS TASK HANDLES ITS OWN COMPLETION MESSAGING'
trap '' EXIT""")
        else:
            self.FILE.write( r"""

# SEND TASK SUCCEEDED MESSAGE:
{
    echo 'CYLC_JOB_EXIT=SUCCEEDED'
    date -u +'CYLC_JOB_EXIT_TIME=%FT%H:%M:%SZ'
} >>$CYLC_TASK_LOG_ROOT.status
cylc task succeeded

echo 'JOB SCRIPT EXITING (TASK SUCCEEDED)'
trap '' EXIT""" )

    def write_eof( self ):
        self.FILE.write( '\n\n#EOF' )
