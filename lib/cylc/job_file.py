#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 NIWA
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
"""Write task job files."""

import os
import re
import stat
import StringIO
from cylc.cfgspec.globalcfg import GLOBAL_CFG
from cylc.task_id import TaskID
from cylc.batch_sys_manager import BATCH_SYS_MANAGER


class JobFile(object):

    """Write task job files."""

    def __init__(self):
        self.suite_env = {}

    def set_suite_env(self, suite_env):
        """Configure suite environment for all job files."""
        self.suite_env.clear()
        self.suite_env.update(suite_env)

    def write(self, job_conf):
        """Write each job script section in turn."""

        ############# !!!!!!!! WARNING !!!!!!!!!!! #####################
        # BE EXTREMELY WARY OF CHANGING THE ORDER OF JOB SCRIPT SECTIONS
        # Users may be relying on the existing order (see for example
        # the comment below on suite bin path being required before
        # task runtime environment setup).
        ################################################################

        # Access to cylc must be configured before user environment so
        # that cylc commands can be used in defining user environment
        # variables: NEXT_CYCLE=$( cylc cycle-point --offset-hours=6 )

        handle = open(job_conf['local job file path'], 'wb')
        self._write_header(handle, job_conf)
        self._write_directives(handle, job_conf)
        self._write_prelude(handle, job_conf)
        self._write_err_trap(handle, job_conf)
        self._write_initial_scripting(handle, job_conf)
        self._write_environment_1(handle, job_conf)
        self._write_enviro_scripting(handle, job_conf)
        # suite bin access must be before runtime environment
        # because suite bin commands may be used in variable
        # assignment expressions: FOO=$(command args).
        self._write_suite_bin_access(handle, job_conf)
        self._write_environment_2(handle, job_conf)
        self._write_task_started(handle, job_conf)
        self._write_manual_environment(handle, job_conf)
        self._write_identity_scripting(handle, job_conf)
        self._write_command_scriptings(handle, job_conf)
        self._write_epilogue(handle, job_conf)
        handle.close()
        # make it executable
        mode = (
            os.stat(job_conf['local job file path']).st_mode |
            stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        os.chmod(job_conf['local job file path'], mode)

    @classmethod
    def _write_header(cls, handle, job_conf):
        """Write job script header."""
        handle.write("#!" + job_conf['job script shell'])
        handle.write("\n#\n# ++++ THIS IS A CYLC TASK JOB SCRIPT ++++")
        for prefix, value in [
                ("# Suite: ", job_conf['suite name']),
                ("# Task: ", job_conf['task id']),
                (BATCH_SYS_MANAGER.LINE_PREFIX_BATCH_SYS_NAME,
                 job_conf['batch system name']),
                (BATCH_SYS_MANAGER.LINE_PREFIX_BATCH_SUBMIT_CMD_TMPL,
                 job_conf['batch submit command template'])]:
            if value:
                handle.write("\n" + prefix + value)

    @classmethod
    def _write_directives(cls, handle, job_conf):
        """Job directives."""
        lines = BATCH_SYS_MANAGER.format_directives(job_conf)
        if lines:
            handle.write('\n\n# DIRECTIVES:')
            for line in lines:
                handle.write('\n' + line)

    @classmethod
    def _write_prelude(cls, handle, job_conf):
        """Job script prelude."""
        handle.write('\n\necho "JOB SCRIPT STARTING"')
        # set cylc version and source profile scripts before turning on
        # error trapping so that profile errors do not abort the job
        handle.write('\n\nprelude() {')
        keys = GLOBAL_CFG.get_host_item(
            'copyable environment variables',
            job_conf['host'], job_conf['owner'])
        for key in keys + ['CYLC_DIR', 'CYLC_VERSION']:
            if key in os.environ:
                handle.write("\n    export %s='%s'" % (key, os.environ[key]))
        handle.write(
            r'''
    for FILE_NAME in \
        "${HOME}/.cylc/job-init-env.sh" \
        "${CYLC_DIR}/conf/job-init-env.sh" \
        "${CYLC_DIR}/conf/job-init-env-default.sh"
    do
        if [[ -f "${FILE_NAME}" ]]; then
            . "${FILE_NAME}" 1>/dev/null 2>&1
            break
        fi
    done
}
prelude''')

    @classmethod
    def _write_err_trap(cls, handle, job_conf):
        """Write error trap.

        Note that all job-file scripting must be bash- and ksh-compatible,
        hence use of "typeset" below instead of the more sensible but
        bash-specific "local".

        """
        handle.write(r"""

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
            date -u +'CYLC_JOB_EXIT_TIME=%FT%H:%M:%SZ'
        } >>$CYLC_TASK_LOG_ROOT.status
    fi
    cylc task failed "Task job script received signal $@"
    exit 1
}
for S in $FAIL_SIGNALS; do
    trap "TRAP_FAIL_SIGNAL $S" $S
done
unset S""")

        vacation_signal = BATCH_SYS_MANAGER.get_vacation_signal(job_conf)
        if vacation_signal:
            handle.write(r"""

# TRAP VACATION SIGNALS:
VACATION_SIGNALS='""" + vacation_signal + r"""'
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

    @classmethod
    def _write_initial_scripting(cls, handle, job_conf):
        """Initial scripting."""
        global_initial_scripting = GLOBAL_CFG.get_host_item(
            'global initial scripting', job_conf["host"], job_conf["owner"])
        if global_initial_scripting:
            handle.write("\n\n# GLOBAL INITIAL SCRIPTING:\n")
            handle.write(global_initial_scripting)
        if not job_conf['initial scripting']:
            return
        handle.write("\n\n# INITIAL SCRIPTING:\n")
        handle.write(job_conf['initial scripting'])

    def _write_environment_1(self, handle, job_conf):
        """Suite and task environment."""
        handle.write("\n\n# CYLC SUITE ENVIRONMENT:")

        # write the static suite variables
        for var, val in sorted(self.suite_env.items()):
            handle.write("\nexport " + var + "=" + str(val))

        if str(self.suite_env.get('CYLC_UTC')) == 'True':
            handle.write("\nexport TZ=UTC")

        handle.write("\n")
        # override and write task-host-specific suite variables
        suite_work_dir = GLOBAL_CFG.get_derived_host_item(
            job_conf['suite name'], 'suite work directory',
            job_conf['host'], job_conf['owner'])
        st_env = {}
        st_env['CYLC_SUITE_RUN_DIR'] = GLOBAL_CFG.get_derived_host_item(
            job_conf['suite name'], 'suite run directory',
            job_conf['host'], job_conf['owner'])
        st_env['CYLC_SUITE_WORK_DIR'] = suite_work_dir
        st_env['CYLC_SUITE_SHARE_DIR'] = GLOBAL_CFG.get_derived_host_item(
            job_conf['suite name'], 'suite share directory',
            job_conf['host'], job_conf['owner'])
        # DEPRECATED
        st_env['CYLC_SUITE_SHARE_PATH'] = '$CYLC_SUITE_SHARE_DIR'
        rsp = job_conf['remote suite path']
        if rsp:
            st_env['CYLC_SUITE_DEF_PATH'] = rsp
        else:
            # replace home dir with '$HOME' for evaluation on the task host
            st_env['CYLC_SUITE_DEF_PATH'] = re.sub(
                os.environ['HOME'], '$HOME',
                self.suite_env['CYLC_SUITE_DEF_PATH_ON_SUITE_HOST'])
        for var, val in sorted(st_env.items()):
            handle.write("\nexport " + var + "=" + str(val))

        task_work_dir = os.path.join(
            suite_work_dir, job_conf['work sub-directory'])

        use_login_shell = GLOBAL_CFG.get_host_item(
            'use login shell', job_conf['host'], job_conf['owner'])
        comms = GLOBAL_CFG.get_host_item(
            'task communication method', job_conf['host'], job_conf['owner'])

        task_name, point_string = TaskID.split(job_conf['task id'])
        handle.write("\n\n# CYLC TASK ENVIRONMENT:")
        handle.write("\nexport CYLC_TASK_COMMS_METHOD=" + comms)
        handle.write("\nexport CYLC_TASK_CYCLE_POINT=" + point_string)
        handle.write("\nexport CYLC_TASK_CYCLE_TIME=" + point_string)
        handle.write("\nexport CYLC_TASK_ID=" + job_conf['task id'])
        handle.write(
            "\nexport CYLC_TASK_IS_COLDSTART=" +
            str(job_conf['is cold-start']))
        handle.write(
            "\nexport CYLC_TASK_LOG_ROOT=" + job_conf['job file path'])
        handle.write(
            "\nexport CYLC_TASK_MSG_MAX_TRIES=" +
            str(GLOBAL_CFG.get(['task messaging', 'maximum number of tries'])))
        handle.write(
            "\nexport CYLC_TASK_MSG_RETRY_INTVL=" + str(GLOBAL_CFG.get(
                ['task messaging', 'retry interval'])))
        handle.write(
            "\nexport CYLC_TASK_MSG_TIMEOUT=" + str(GLOBAL_CFG.get(
                ['task messaging', 'connection timeout'])))
        handle.write("\nexport CYLC_TASK_NAME=" + task_name)
        handle.write(
            '\nexport CYLC_TASK_NAMESPACE_HIERARCHY="' +
            ' '.join(job_conf['namespace hierarchy']) + '"')
        handle.write(
            "\nexport CYLC_TASK_SSH_LOGIN_SHELL=" + str(use_login_shell))
        handle.write(
            "\nexport CYLC_TASK_SUBMIT_NUMBER=" +
            str(job_conf['absolute submit number']))
        handle.write(
            "\nexport CYLC_TASK_TRY_NUMBER=" +
            str(job_conf['try number']))
        handle.write("\nexport CYLC_TASK_WORK_DIR=" + task_work_dir)
        # DEPRECATED
        handle.write("\nexport CYLC_TASK_WORK_PATH=$CYLC_TASK_WORK_DIR")

    @classmethod
    def _write_enviro_scripting(cls, handle, job_conf):
        """Environment scripting."""
        if not job_conf['environment scripting']:
            return
        handle.write("\n\n# ENVIRONMENT SCRIPTING:\n")
        handle.write(job_conf['environment scripting'])

    @classmethod
    def _write_suite_bin_access(cls, handle, _):
        """Suite bin/ directory access."""
        handle.write(
            "\n\n# ACCESS TO THE SUITE BIN DIRECTORY:" +
            "\nexport PATH=$CYLC_SUITE_DEF_PATH/bin:$PATH")

    def _write_environment_2(self, handle, job_conf):
        """Run time environment part 2."""
        env = job_conf['runtime environment']
        if not env:
            return

        # generate variable assignment expressions
        handle.write("\n\n# TASK RUNTIME ENVIRONMENT:")
        for var, val in env.items():
            handle.write(self._get_var_assign(var, val))

        # export them all now (see note)
        handle.write("\nexport")
        for var in env:
            handle.write(" " + var)

    @classmethod
    def _get_var_assign(cls, var, value):
        """Generate an environment variable assignment expression 'var=value'.

        Values are quoted to handle internal spaces, but escape initial tilde
        (quoting disables tilde expansion).

        """
        value = str(value)  # (needed?)
        match = re.match(r"^(~[^/\s]*/)(.*)$", value)
        if match:
            # ~foo/bar or ~/bar
            # write as ~foo/"bar" or ~/"bar"
            head, tail = match.groups()
            expr = '\n%s=%s"%s"' % (var, head, tail)
        elif re.match(r"^~[^\s]*$", value):
            # plain ~foo or just ~
            # just leave unquoted as subsequent spaces don't
            # make sense in this case anyway
            expr = '\n%s=%s' % (var, value)
        else:
            # Non tilde values - quote the lot.
            # This gets values like "~one ~two" too, but these
            # (in variable values) aren't expanded by the shell
            # anyway so it doesn't matter.
            expr = '\n%s="%s"' % (var, value)

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

    @classmethod
    def _write_task_started(cls, handle, _):
        """Script to send start message and create work directory."""
        handle.write(r"""

# SEND TASK STARTED MESSAGE:
{
    echo "CYLC_JOB_PID=$$"
    date -u +'CYLC_JOB_INIT_TIME=%FT%H:%M:%SZ'
} >>$CYLC_TASK_LOG_ROOT.status
cylc task started

# SHARE DIRECTORY CREATE:
mkdir -p $CYLC_SUITE_SHARE_DIR || true

# WORK DIRECTORY CREATE:
mkdir -p $(dirname $CYLC_TASK_WORK_DIR) || true
mkdir -p $CYLC_TASK_WORK_DIR
cd $CYLC_TASK_WORK_DIR""")

    def _write_manual_environment(self, handle, job_conf):
        """Write a transferable environment for detaching tasks."""
        if not job_conf['use manual completion']:
            return
        strio = StringIO.StringIO()
        self._write_environment_1(strio, job_conf)
        # now escape quotes in the environment string
        value = strio.getvalue()
        strio.close()
        # set cylc version and source profiles in the detached job
        value += '\n$(declare -f prelude)\nprelude\n'
        value = re.sub('"', '\\"', value)
        handle.write(
            '\n\n# TRANSPLANTABLE SUITE ENVIRONMENT FOR CUSTOM TASK WRAPPERS:')
        handle.write(
            '\n# (contains embedded newlines, use may require "QUOTES")')
        handle.write('\nexport CYLC_SUITE_ENVIRONMENT="' + value + '"')

    @classmethod
    def _write_identity_scripting(cls, handle, _):
        """Write script for suite and task identity."""
        handle.write(r"""

# TASK SELF-IDENTIFY:
echo "cylc Suite and Task Identity:"
echo "  Suite Name  : $CYLC_SUITE_NAME"
echo "  Suite Host  : $CYLC_SUITE_HOST"
echo "  Suite Port  : $CYLC_SUITE_PORT"
echo "  Suite Owner : $CYLC_SUITE_OWNER"
echo "  Task ID     : $CYLC_TASK_ID"
if [[ $(uname) == AIX ]]; then
    # on AIX the hostname command has no '-f' option
    __TMP_DOMAIN=$(namerslv -sn 2>/dev/null | awk '{print $2}')
    echo "  Task Host   : $(hostname).${__TMP_DOMAIN}"
else
    echo "  Task Host   : $(hostname -f)"
fi
echo "  Task Owner  : $USER"
echo "  Task Try No.: $CYLC_TASK_TRY_NUMBER"
echo""")

    @classmethod
    def _write_command_scriptings(cls, handle, job_conf):
        """Write pre-command, command and post-command scriptings."""
        for prefix in ['pre-', '', 'post-']:
            value = job_conf[prefix + 'command scripting']
            if value:
                handle.write("\n\n# %sCOMMAND SCRIPTING:\n%s" % (
                    prefix.upper(), value))

    @classmethod
    def _write_epilogue(cls, handle, job_conf):
        """Write epilogue."""
        if job_conf['use manual completion']:
            handle.write(r"""

# (detaching task: cannot safely remove the WORK DIRECTORY here)

echo 'JOB SCRIPT EXITING: THIS TASK HANDLES ITS OWN COMPLETION MESSAGING'
trap '' EXIT

#EOF""")
        else:
            handle.write(r"""

# EMPTY WORK DIRECTORY REMOVE:
cd
rmdir $CYLC_TASK_WORK_DIR 2>/dev/null || true

# SEND TASK SUCCEEDED MESSAGE:
{
    echo 'CYLC_JOB_EXIT=SUCCEEDED'
    date -u +'CYLC_JOB_EXIT_TIME=%FT%H:%M:%SZ'
} >>$CYLC_TASK_LOG_ROOT.status
cylc task succeeded

echo 'JOB SCRIPT EXITING (TASK SUCCEEDED)'
trap '' EXIT

#EOF""")


JOB_FILE = JobFile()
