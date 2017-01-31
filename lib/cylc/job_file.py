#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Write task job files."""

import os
import re
import stat
from cylc.batch_sys_manager import BATCH_SYS_MANAGER
from cylc.cfgspec.globalcfg import GLOBAL_CFG
import cylc.flags
from cylc.task_id import TaskID
from cylc.task_message import TaskMessage
from cylc.task_outputs import (
    TASK_OUTPUT_STARTED, TASK_OUTPUT_SUCCEEDED, TASK_OUTPUT_FAILED)


class JobFile(object):

    """Write task job files."""

    _INSTANCE = None

    @classmethod
    def get_inst(cls):
        """Return a unique instance of this class."""
        if cls._INSTANCE is None:
            cls._INSTANCE = cls()
        return cls._INSTANCE

    def __init__(self):
        self.suite_env = {}

    def set_suite_env(self, suite_env):
        """Configure suite environment for all job files."""
        self.suite_env.clear()
        self.suite_env.update(suite_env)

    def write(self, local_job_file_path, job_conf):
        """Write each job script section in turn."""

        # ########### !!!!!!!! WARNING !!!!!!!!!!! #####################
        # BE EXTREMELY WARY OF CHANGING THE ORDER OF JOB SCRIPT SECTIONS
        # Users may be relying on the existing order (see for example
        # the comment below on suite bin path being required before
        # task runtime environment setup).
        # ##############################################################

        # Access to cylc must be configured before user environment so
        # that cylc commands can be used in defining user environment
        # variables: NEXT_CYCLE=$( cylc cycle-point --offset-hours=6 )

        handle = open(local_job_file_path, 'wb')
        self._write_header(handle, job_conf)
        self._write_directives(handle, job_conf)
        self._write_prelude(handle, job_conf)
        self._write_err_trap(handle, job_conf)
        self._write_identity_script(handle, job_conf)
        self._write_init_script(handle, job_conf)
        self._write_environment_1(handle, job_conf)
        self._write_env_script(handle, job_conf)
        # suite bin access must be before runtime environment
        # because suite bin commands may be used in variable
        # assignment expressions: FOO=$(command args).
        self._write_suite_bin_access(handle, job_conf)
        self._write_environment_2(handle, job_conf)
        self._write_create_dirs(handle, job_conf)
        self._write_script(handle, job_conf)
        self._write_epilogue(handle, job_conf)
        handle.close()
        # make it executable
        mode = (
            os.stat(local_job_file_path).st_mode |
            stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        os.chmod(local_job_file_path, mode)

    @classmethod
    def _get_derived_host_item(cls, job_conf, key):
        """Return derived host item from GLOBAL_CFG."""
        return GLOBAL_CFG.get_derived_host_item(
            job_conf['suite_name'], key, job_conf["host"], job_conf["owner"])

    @classmethod
    def _get_host_item(cls, job_conf, key):
        """Return host item from GLOBAL_CFG."""
        return GLOBAL_CFG.get_host_item(
            key, job_conf["host"], job_conf["owner"])

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
        # | ~foo/bar
        # | ~/bar
        # | ~/filename with spaces
        # | ~foo
        # | ~

        # NOTE: the reason for separate export of user-specified
        # variables is this: inline export does not activate the
        # error trap if sub-expressions fail, e.g. (note typo in
        # 'echo' command name):
        # export FOO=$( ecko foo )  # error not trapped!
        # FOO=$( ecko foo )  # error trapped

        return expr

    @classmethod
    def _write_header(cls, handle, job_conf):
        """Write job script header."""
        handle.write("#!" + job_conf['shell'])
        handle.write("\n#\n# ++++ THIS IS A CYLC TASK JOB SCRIPT ++++")
        for prefix, value in [
                ("# Suite: ", job_conf['suite_name']),
                ("# Task: ", job_conf['task_id']),
                (BATCH_SYS_MANAGER.LINE_PREFIX_JOB_LOG_DIR, job_conf['job_d']),
                (BATCH_SYS_MANAGER.LINE_PREFIX_BATCH_SYS_NAME,
                 job_conf['batch_system_name']),
                (BATCH_SYS_MANAGER.LINE_PREFIX_BATCH_SUBMIT_CMD_TMPL,
                 job_conf['batch_submit_command_template']),
                (BATCH_SYS_MANAGER.LINE_PREFIX_EXECUTION_TIME_LIMIT,
                 job_conf['execution_time_limit'])]:
            if value:
                handle.write("\n%s%s" % (prefix, value))

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
        handle.write('\n\n# PRELUDE')
        if cylc.flags.debug:
            if 'bash' in job_conf['shell']:
                handle.write("\nPS4='+[\D{%Y%m%dT%H%M%S%z}]\u@\h '\nset -x")
            else:
                handle.write('\nset -x')
        # set cylc version and source profile scripts before turning on
        # error trapping so that profile errors do not abort the job
        for key in (
                cls._get_host_item(
                    job_conf, 'copyable environment variables') +
                ['CYLC_DIR', 'CYLC_VERSION']):
            if key in os.environ:
                handle.write("\nexport %s='%s'" % (key, os.environ[key]))
        handle.write(r'''
for FILE_NAME in \
    "${HOME}/.cylc/job-init-env.sh" \
    "${CYLC_DIR}/conf/job-init-env.sh" \
    "${CYLC_DIR}/conf/job-init-env-default.sh"
do
    if [[ -f "${FILE_NAME}" ]]; then
        . "${FILE_NAME}" 1>'/dev/null' 2>&1
        break
    fi
done
unset FILE_NAME''')

    @classmethod
    def _write_err_trap(cls, handle, job_conf):
        """Write error trap.

        Note that the job script must be bash- and ksh-compatible, hence use of
        "typeset" below instead of the more sensible but bash-specific "local".

        """
        args = {
            "signals_str": " ".join(
                BATCH_SYS_MANAGER.get_fail_signals(job_conf)),
            "priority": TaskMessage.CRITICAL,
            "message1": TASK_OUTPUT_FAILED,
            "message2": TaskMessage.FAIL_MESSAGE_PREFIX}
        handle.write(r"""

# TRAP ERROR SIGNALS:
FAIL_SIGNALS='%(signals_str)s'
cylcjob::trap_err() {
    typeset SIGNAL="$1"
    echo "Received signal $SIGNAL" >&2
    typeset S=
    for S in ${VACATION_SIGNALS:-} ${FAIL_SIGNALS}; do
        trap "" "${S}"
    done
    if [[ -n "${CYLC_TASK_MESSAGE_STARTED_PID:-}" ]]; then
        wait "${CYLC_TASK_MESSAGE_STARTED_PID}" 2'>/dev/null' || true
    fi
    cylc task message -p '%(priority)s' "%(message2)s${SIGNAL}" '%(message1)s'
    exit 1
}
S=
for S in ${FAIL_SIGNALS}; do
    trap "cylcjob::trap_err ${S}" "${S}"
done
unset S""" % args)

        vacation_signal = BATCH_SYS_MANAGER.get_vacation_signal(job_conf)
        if vacation_signal:
            args = {
                "signals_str": vacation_signal,
                "priority": TaskMessage.WARNING,
                "message": TaskMessage.VACATION_MESSAGE_PREFIX}
            handle.write(r"""

# TRAP VACATION SIGNALS:
VACATION_SIGNALS='%(signals_str)s'
cylcjob::trap_vac() {
    typeset SIGNAL="$1"
    echo "Received signal $SIGNAL" >&2
    typeset S=
    for S in ${VACATION_SIGNALS} ${FAIL_SIGNALS}; do
        trap "" "${S}"
    done
    if [[ -n "${CYLC_TASK_MESSAGE_STARTED_PID:-}" ]]; then
        wait "${CYLC_TASK_MESSAGE_STARTED_PID}" 2>'/dev/null' || true
    fi
    cylc task message -p '%(priority)s' "%(message)s${SIGNAL}"
    exit 1
}
S=
for S in ${VACATION_SIGNALS}; do
    trap "cylcjob::trap_vac ${S}" "${S}"
done
unset S""" % args)

        if 'bash' in job_conf['shell']:
            handle.write("\n\nset -o pipefail\nset -u")

    @classmethod
    def _write_identity_script(cls, handle, job_conf):
        """Write script for suite and task identity."""
        handle.write(r"""

# TASK JOB SELF-IDENTIFY:
USER="${USER:-$(whoami)}"
if [[ "$(uname)" == 'AIX' ]]; then
    # on AIX the hostname command has no '-f' option
    HOSTNAME="$(hostname).$(namerslv -sn 2>'/dev/null' | awk '{print $2}')"
else
    HOSTNAME="$(hostname -f)"
fi
cat <<__OUT__
Suite       : %(suite_name)s
Task ID     : %(task_id)s
Submit (Try): %(submit_num)d (%(try_num)d)
User@Host   : ${USER}@${HOSTNAME}
__OUT__
echo""" % job_conf)

    @classmethod
    def _write_init_script(cls, handle, job_conf):
        """Init-script."""
        global_init_script = cls._get_host_item(
            job_conf, 'global init-script')
        if global_init_script:
            handle.write("\n\n# GLOBAL INIT-SCRIPT:\n")
            handle.write(global_init_script)
        if job_conf['init-script']:
            handle.write("\n\n# INIT-SCRIPT:\n")
            handle.write(job_conf['init-script'])

    def _write_environment_1(self, handle, job_conf):
        """Suite and task environment."""
        handle.write("\n\n# CYLC SUITE ENVIRONMENT:")

        # write the static suite variables
        for item in sorted(self.suite_env.items()):
            handle.write('\nexport %s="%s"' % item)

        if str(self.suite_env.get('CYLC_UTC')) == 'True':
            handle.write('\nexport TZ="UTC"')

        handle.write('\n')
        # override and write task-host-specific suite variables
        handle.write(
            '\nexport CYLC_SUITE_RUN_DIR="%s"' %
            self._get_derived_host_item(job_conf, 'suite run directory'))
        # TODO: Is this necessary?
        handle.write(
            '\nexport CYLC_SUITE_LOG_DIR="%s"' %
            self._get_derived_host_item(job_conf, 'suite log directory'))
        handle.write(
            '\nexport CYLC_SUITE_SHARE_DIR="%s"' %
            self._get_derived_host_item(job_conf, 'suite share directory'))
        handle.write(
            '\nexport CYLC_SUITE_WORK_DIR="%s"' %
            self._get_derived_host_item(job_conf, 'suite work directory'))
        if job_conf['remote_suite_d']:
            handle.write(
                '\nexport CYLC_SUITE_DEF_PATH="%s"' %
                job_conf['remote_suite_d'])
        else:
            # replace home dir with '$HOME' for evaluation on the task host
            handle.write(
                '\nexport CYLC_SUITE_DEF_PATH="%s"' %
                os.environ['CYLC_SUITE_DEF_PATH'].replace(
                    os.environ['HOME'], '${HOME}'))
        handle.write(
            '\nexport CYLC_SUITE_DEF_PATH_ON_SUITE_HOST="%s"' %
            os.environ['CYLC_SUITE_DEF_PATH'])

        # SSH comms variables. Note:
        # For "poll", contact file will not be installed, and job will not
        # attempt to communicate back.
        # Otherwise, job will attempt to communicate back via HTTP(S).
        comms = self._get_host_item(job_conf, 'task communication method')
        if comms == 'ssh':
            handle.write("\n\n# CYLC MESSAGE ENVIRONMENT:")
            handle.write('\nexport CYLC_TASK_COMMS_METHOD="%s"' % comms)
            handle.write(
                '\nexport CYLC_TASK_SSH_LOGIN_SHELL="%s"' %
                self._get_host_item(job_conf, 'use login shell'))

        handle.write("\n\n# CYLC TASK ENVIRONMENT:")
        task_name, point_string = TaskID.split(job_conf['task_id'])
        handle.write('\nexport CYLC_TASK_ID="%s"' % job_conf['task_id'])
        handle.write('\nexport CYLC_TASK_CYCLE_POINT="%s"' % point_string)
        handle.write('\nexport CYLC_TASK_NAME="%s"' % task_name)
        handle.write(
            '\nexport CYLC_TASK_LOG_ROOT="%s"' % job_conf['job_file_path'])
        handle.write(
            '\nexport CYLC_TASK_NAMESPACE_HIERARCHY="%s"' %
            ' '.join(job_conf['namespace_hierarchy']))
        handle.write(
            '\nexport CYLC_TASK_SUBMIT_NUMBER=%s' % job_conf['submit_num'])
        handle.write('\nexport CYLC_TASK_TRY_NUMBER=%s' % job_conf['try_num'])
        handle.write(
            '\nexport CYLC_TASK_WORK_DIR="${CYLC_SUITE_WORK_DIR}/%s"' %
            job_conf['work_d'])
        handle.write(r'''

# DEPRECATED
export CYLC_SUITE_SHARE_PATH="${CYLC_SUITE_SHARE_DIR}"
export CYLC_SUITE_INITIAL_CYCLE_TIME="${CYLC_SUITE_INITIAL_CYCLE_POINT}"
export CYLC_SUITE_FINAL_CYCLE_TIME="${CYLC_SUITE_FINAL_CYCLE_POINT}"
export CYLC_TASK_CYCLE_TIME="${CYLC_TASK_CYCLE_POINT}"
export CYLC_TASK_WORK_PATH="${CYLC_TASK_WORK_DIR}"''')

    @classmethod
    def _write_env_script(cls, handle, job_conf):
        """Env-script."""
        if job_conf['env-script']:
            handle.write("\n\n# ENV-SCRIPT:\n")
            handle.write(job_conf['env-script'])

    @classmethod
    def _write_suite_bin_access(cls, handle, _):
        """Suite bin/ directory access."""
        handle.write(r'''

# SEND TASK STARTED MESSAGE:
cylc task message '%(message)s' &
CYLC_TASK_MESSAGE_STARTED_PID=$!

# ACCESS TO THE SUITE BIN DIRECTORY:
if [[ -n "${CYLC_SUITE_DEF_PATH:-}" && -d "${CYLC_SUITE_DEF_PATH}/bin" ]]; then
    export PATH="${CYLC_SUITE_DEF_PATH}/bin:${PATH}"
fi''' % {"message": TASK_OUTPUT_STARTED})

    def _write_environment_2(self, handle, job_conf):
        """Run time environment part 2."""
        if not job_conf['environment']:
            return

        # generate variable assignment expressions
        handle.write("\n\n# TASK RUNTIME ENVIRONMENT:")
        for var, val in job_conf['environment'].items():
            handle.write(self._get_var_assign(var, val))

        # export them all now (see note)
        handle.write("\nexport")
        for var in job_conf['environment']:
            handle.write(" " + var)

    @classmethod
    def _write_create_dirs(cls, handle, _):
        """Script to send start message and create work directory."""
        handle.write(r'''

# SHARE DIRECTORY CREATE:
mkdir -p "${CYLC_SUITE_SHARE_DIR}" || true

# WORK DIRECTORY CREATE:
mkdir -p "$(dirname "${CYLC_TASK_WORK_DIR}")" || true
mkdir -p "${CYLC_TASK_WORK_DIR}"
cd "${CYLC_TASK_WORK_DIR}"''')

    @classmethod
    def _write_script(cls, handle, job_conf):
        """Write pre-script, script, and post-script."""
        for prefix in ['pre-', '', 'post-']:
            value = job_conf[prefix + 'script']
            if value:
                handle.write("\n\n# %sSCRIPT:\n%s" % (
                    prefix.upper(), value))

    @classmethod
    def _write_epilogue(cls, handle, job_conf):
        """Write epilogue."""
        handle.write(r"""

# EMPTY WORK DIRECTORY REMOVE:
cd
rmdir "${CYLC_TASK_WORK_DIR}" 2>'/dev/null' || true

# SEND TASK SUCCEEDED MESSAGE:
wait "${CYLC_TASK_MESSAGE_STARTED_PID}" 2>'/dev/null' || true
cylc task message '%(message)s' || true
trap '' EXIT

""" % {"message": TASK_OUTPUT_SUCCEEDED})

        handle.write("%s%s\n" % (
            BATCH_SYS_MANAGER.LINE_PREFIX_EOF, job_conf['job_d']))
