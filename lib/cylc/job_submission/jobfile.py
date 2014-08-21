#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
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

import cylc.TaskID

import re, os
import StringIO
from copy import deepcopy
from cylc.cfgspec.globalcfg import GLOBAL_CFG
from cylc.command_env import cv_scripting_ml
import signal
from subprocess import Popen, PIPE
from time import time, sleep

class JobFile(object):

    # These are set by the scheduler object at start-up:
    suite_env = None       # static variables not be be changed below
    suite_task_env = None  # copy and change below

    def __init__( self, suite, log_root, job_submission_method, task_id, jobconfig ):

        self.log_root = log_root
        self.job_submission_method = job_submission_method
        self.task_id = task_id
        self.jobconfig = jobconfig
        self.suite = suite
        self.owner = jobconfig['task owner']
        self.host = jobconfig['task host']

        self.task_name, self.point_string = cylc.TaskID.split( task_id )

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
        # variables: NEXT_CYCLE=$( cylc cycle-point --offset-hours=6 )

        self.FILE = open( path, 'wb' )
        self.write_header()

        self.write_directives()

        self.write_prelude()
        self.write_err_trap()
        self.write_vacation_trap()

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
        self.FILE.write( "#!" + self.jobconfig['job script shell'] )
        self.FILE.write( "\n\n# ++++ THIS IS A CYLC TASK JOB SCRIPT ++++" )
        self.FILE.write( "\n# Task '" + self.task_id  + "' in suite '" + self.suite + "'" )
        self.FILE.write( "\n# Job submission method: '" + self.job_submission_method + "'" )

    def write_directives( self ):
        directives = self.jobconfig['directives']
        prefix = self.jobconfig['directive prefix']
        final = self.jobconfig['directive final']
        connector = self.jobconfig['directive connector']

        if len( directives.keys() ) == 0 or not prefix:
            return

        self.FILE.write( "\n\n# DIRECTIVES:" )
        for key, value in directives.items():
            if value:
                self.FILE.write( '\n' + prefix + ' ' + key + connector + value )
            else:
                self.FILE.write( '\n' + prefix + ' ' + key )
        if final:
            self.FILE.write( '\n' + final )

    def write_prelude( self ):
        self.FILE.write( '\n\necho "JOB SCRIPT STARTING"\n')
        # set cylc version and source profile scripts before turning on
        # error trapping so that profile errors do not abort the job
        self.FILE.write( cv_scripting_ml )

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

        BUFFER.write( "\n\n# CYLC SUITE ENVIRONMENT:" )

        # write the static suite variables
        for var, val in sorted(self.__class__.suite_env.items()):
            BUFFER.write( "\nexport " + var + "=" + str(val) )

        if str(self.__class__.suite_env.get('CYLC_UTC')) == 'True':
            BUFFER.write( "\nexport TZ=UTC" )

        BUFFER.write("\n")
        # override and write task-host-specific suite variables
        suite_work_dir = GLOBAL_CFG.get_derived_host_item( self.suite, 'suite work directory', self.host, self.owner )
        st_env = deepcopy( self.__class__.suite_task_env ) 
        st_env[ 'CYLC_SUITE_RUN_DIR'    ] = GLOBAL_CFG.get_derived_host_item( self.suite, 'suite run directory', self.host, self.owner )
        st_env[ 'CYLC_SUITE_WORK_DIR'   ] = suite_work_dir
        st_env[ 'CYLC_SUITE_SHARE_DIR'  ] = GLOBAL_CFG.get_derived_host_item( self.suite, 'suite share directory', self.host, self.owner )
        st_env[ 'CYLC_SUITE_SHARE_PATH' ] = '$CYLC_SUITE_SHARE_DIR' # DEPRECATED
        rsp = self.jobconfig['remote suite path']
        if rsp:
            st_env[ 'CYLC_SUITE_DEF_PATH' ] = rsp
        else:
            # replace home dir with '$HOME' for evaluation on the task host
            st_env[ 'CYLC_SUITE_DEF_PATH' ] = re.sub( os.environ['HOME'], '$HOME', st_env['CYLC_SUITE_DEF_PATH'] )
        for var, val in sorted(st_env.items()):
            BUFFER.write( "\nexport " + var + "=" + str(val) )

        task_work_dir  = os.path.join( suite_work_dir, self.jobconfig['work sub-directory'] )

        use_login_shell = GLOBAL_CFG.get_host_item( 'use login shell', self.host, self.owner )
        comms = GLOBAL_CFG.get_host_item( 'task communication method', self.host, self.owner )

        BUFFER.write( "\n\n# CYLC TASK ENVIRONMENT:" )
        BUFFER.write( "\nexport CYLC_TASK_COMMS_METHOD=" + comms )
        BUFFER.write( "\nexport CYLC_TASK_CYCLE_POINT=" + self.point_string )
        BUFFER.write( "\nexport CYLC_TASK_CYCLE_TIME=" + self.point_string )
        BUFFER.write( "\nexport CYLC_TASK_ID=" + self.task_id )
        BUFFER.write( "\nexport CYLC_TASK_IS_COLDSTART=" + str( self.jobconfig['is cold-start']) )
        BUFFER.write( "\nexport CYLC_TASK_LOG_ROOT=" + self.log_root )
        BUFFER.write( "\nexport CYLC_TASK_MSG_MAX_TRIES=" + str( GLOBAL_CFG.get( ['task messaging','maximum number of tries'])) )
        BUFFER.write( "\nexport CYLC_TASK_MSG_RETRY_INTVL=" + str( GLOBAL_CFG.get( ['task messaging','retry interval in seconds'])) )
        BUFFER.write( "\nexport CYLC_TASK_MSG_TIMEOUT=" + str( GLOBAL_CFG.get( ['task messaging','connection timeout in seconds'])) )
        BUFFER.write( "\nexport CYLC_TASK_NAME=" + self.task_name )
        BUFFER.write( '\nexport CYLC_TASK_NAMESPACE_HIERARCHY="' + ' '.join( self.jobconfig['namespace hierarchy']) + '"')
        BUFFER.write( "\nexport CYLC_TASK_SSH_LOGIN_SHELL=" + str(use_login_shell) )
        BUFFER.write( "\nexport CYLC_TASK_SUBMIT_NUMBER=" + str(self.jobconfig['absolute submit number']) )
        BUFFER.write( "\nexport CYLC_TASK_TRY_NUMBER=" + str(self.jobconfig['try number']) )
        BUFFER.write( "\nexport CYLC_TASK_WORK_DIR=" + task_work_dir )
        BUFFER.write( "\nexport CYLC_TASK_WORK_PATH=$CYLC_TASK_WORK_DIR") # DEPRECATED

    def write_suite_bin_access( self, BUFFER=None ):
        if not BUFFER:
            BUFFER = self.FILE
        BUFFER.write( "\n\n# ACCESS TO THE SUITE BIN DIRECTORY:" )
        BUFFER.write( "\nexport PATH=$CYLC_SUITE_DEF_PATH/bin:$PATH" )

    def write_err_trap( self ):
        """Write error trap.

        Note that all job-file scripting must be bash- and ksh-compatible,
        hence use of "typeset" below instead of the more sensible but
        bash-specific "local".

        """
        self.FILE.write( r"""

# TRAP ERROR SIGNALS:
set -u # Fail when using an undefined variable
FAIL_SIGNALS='EXIT ERR TERM XCPU'
TRAP_FAIL_SIGNAL() {
    typeset SIGNAL=$1
    echo "Received signal $SIGNAL" >&2
    typeset S=
    for S in ${VACATION_SIGNALS:-} $FAIL_SIGNALS; do
        trap "" $S
    done
    if [[ -n ${CYLC_TASK_LOG_ROOT:-} ]]; then
        {
            echo "CYLC_JOB_EXIT=$SIGNAL"
            date -u +'CYLC_JOB_EXIT_TIME=%FT%H:%M:%S'
        } >>$CYLC_TASK_LOG_ROOT.status
    fi
    cylc task failed "Task job script received signal $@"
    exit 1
}
for S in $FAIL_SIGNALS; do
    trap "TRAP_FAIL_SIGNAL $S" $S
done
unset S""")


    def write_vacation_trap( self ):
        """Write job vacation trap.

        Note that all job-file scripting must be bash- and ksh-compatible,
        hence use of "typeset" below instead of the more sensible but
        bash-specific "local".

        """
        if self.jobconfig['job vacation signal']:
            self.FILE.write( r"""

# TRAP VACATION SIGNALS:
VACATION_SIGNALS='""" + self.jobconfig['job vacation signal'] + r"""'
TRAP_VACATION_SIGNAL() {
    typeset SIGNAL=$1
    echo "Received signal $SIGNAL" >&2
    typeset S=
    for S in $VACATION_SIGNALS $FAIL_SIGNALS; do
        trap "" $S
    done
    if [[ -n ${CYLC_TASK_LOG_ROOT:-} && -f $CYLC_TASK_LOG_ROOT.status ]]; then
        rm -f $CYLC_TASK_LOG_ROOT.status
    fi
    cylc task message -p WARNING "Task job script vacated by signal $@"
    exit 1
}
S=
for S in $VACATION_SIGNALS; do
    trap "TRAP_VACATION_SIGNAL $S" $S
done
unset S""")

    def write_task_started( self ):
        self.FILE.write( r"""

# SEND TASK STARTED MESSAGE:
{
    echo "CYLC_JOB_PID=$$"
    date -u +'CYLC_JOB_INIT_TIME=%FT%H:%M:%S'
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
        # write a transferable environment for detaching tasks
        if not self.jobconfig['use manual completion']:
            return
        strio = StringIO.StringIO()
        self.write_environment_1( strio )
        # now escape quotes in the environment string
        str = strio.getvalue()
        strio.close()
        # set cylc version and source profiles in the detached job
        str += '\n' + cv_scripting_ml + '\n'
        str = re.sub('"', '\\"', str )
        self.FILE.write( '\n\n# TRANSPLANTABLE SUITE ENVIRONMENT FOR CUSTOM TASK WRAPPERS:')
        self.FILE.write( '\n# (contains embedded newlines, use may require "QUOTES")' )
        self.FILE.write( '\nexport CYLC_SUITE_ENVIRONMENT="' + str + '"' )

    def write_identity_scripting( self ):
        self.FILE.write( "\n\n# TASK SELF-IDENTIFY:" )
        self.FILE.write( '''
echo "cylc Suite and Task Identity:"
echo "  Suite Name  : $CYLC_SUITE_NAME"
echo "  Suite Host  : $CYLC_SUITE_HOST"
echo "  Suite Port  : $CYLC_SUITE_PORT"
echo "  Suite Owner : $CYLC_SUITE_OWNER"
echo "  Task ID     : $CYLC_TASK_ID"
if [[ $(uname) == AIX ]]; then
    # on AIX the hostname command has no '-f' option
    echo "  Task Host   : $(hostname).$(namerslv -sn 2>/dev/null | awk '{print $2}')"
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
        cs = self.jobconfig['command scripting']
        if not cs:
            return
        self.FILE.write( "\n\n# TASK COMMAND SCRIPTING:" )
        self.FILE.write( "\n" + cs )

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
    date -u +'CYLC_JOB_EXIT_TIME=%FT%H:%M:%S'
} >>$CYLC_TASK_LOG_ROOT.status
cylc task succeeded

echo 'JOB SCRIPT EXITING (TASK SUCCEEDED)'
trap '' EXIT""" )

    def write_eof( self ):
        self.FILE.write( '\n\n#EOF' )
