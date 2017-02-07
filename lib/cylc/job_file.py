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
        self._write_environment_1(handle, job_conf)
        self._write_global_init_script(handle, job_conf)
        # suite bin access must be before runtime environment
        # because suite bin commands may be used in variable
        # assignment expressions: FOO=$(command args).
        self._write_environment_2(handle, job_conf)
        self._write_script(handle, job_conf)
        self._write_epilogue(handle, job_conf)
        handle.close()
        # make it executable
        mode = (
            os.stat(local_job_file_path).st_mode |
            stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        os.chmod(local_job_file_path, mode)

    @staticmethod
    def _get_derived_host_item(job_conf, key):
        """Return derived host item from GLOBAL_CFG."""
        return GLOBAL_CFG.get_derived_host_item(
            job_conf['suite_name'], key, job_conf["host"], job_conf["owner"])

    @staticmethod
    def _get_host_item(job_conf, key):
        """Return host item from GLOBAL_CFG."""
        return GLOBAL_CFG.get_host_item(
            key, job_conf["host"], job_conf["owner"])

    @staticmethod
    def _write_header(handle, job_conf):
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

    @staticmethod
    def _write_directives(handle, job_conf):
        """Job directives."""
        lines = BATCH_SYS_MANAGER.format_directives(job_conf)
        if lines:
            handle.write('\n\n# DIRECTIVES:')
            for line in lines:
                handle.write('\n' + line)

    @classmethod
    def _write_prelude(cls, handle, job_conf):
        """Job script prelude."""
        # Environment variables for prelude
        handle.write("\nexport CYLC_DIR='%s'" % (os.environ['CYLC_DIR']))
        if cylc.flags.debug:
            handle.write("\nexport CYLC_DEBUG='true'")
        for key in ['CYLC_VERSION'] + cls._get_host_item(
                job_conf, 'copyable environment variables'):
            if key in os.environ:
                handle.write("\nexport %s='%s'" % (key, os.environ[key]))
        # Variables for traps
        handle.write("\nCYLC_FAIL_SIGNALS='%s'" % " ".join(
            BATCH_SYS_MANAGER.get_fail_signals(job_conf)))
        vacation_signals_str = BATCH_SYS_MANAGER.get_vacation_signal(job_conf)
        if vacation_signals_str:
            handle.write("\nCYLC_VACATION_SIGNALS='%s'" % vacation_signals_str)

    def _write_environment_1(self, handle, job_conf):
        """Suite and task environment."""
        handle.write("\n\ncylc::job::inst::cylc-env() {")
        handle.write("\n    # CYLC SUITE ENVIRONMENT:")
        # write the static suite variables
        for var, val in sorted(self.suite_env.items()):
            if var != 'CYLC_DEBUG':
                handle.write('\n    export %s="%s"' % (var, val))

        if str(self.suite_env.get('CYLC_UTC')) == 'True':
            handle.write('\n    export TZ="UTC"')

        handle.write('\n')
        # override and write task-host-specific suite variables
        run_d = self._get_derived_host_item(job_conf, 'suite run directory')
        work_d = self._get_derived_host_item(job_conf, 'suite work root')
        handle.write('\n    export CYLC_SUITE_RUN_DIR="%s"' % run_d)
        if work_d != run_d:
            handle.write('\n    CYLC_SUITE_WORK_DIR_ROOT="%s"' % work_d)
        if job_conf['remote_suite_d']:
            handle.write(
                '\n    export CYLC_SUITE_DEF_PATH="%s"' %
                job_conf['remote_suite_d'])
        else:
            # replace home dir with '$HOME' for evaluation on the task host
            handle.write(
                '\n    export CYLC_SUITE_DEF_PATH="%s"' %
                os.environ['CYLC_SUITE_DEF_PATH'].replace(
                    os.environ['HOME'], '${HOME}'))
        handle.write(
            '\n    export CYLC_SUITE_DEF_PATH_ON_SUITE_HOST="%s"' %
            os.environ['CYLC_SUITE_DEF_PATH'])

        handle.write("\n\n    # CYLC TASK ENVIRONMENT:")
        handle.write('\n    export CYLC_TASK_JOB="%s"' % job_conf['job_d'])
        handle.write(
            '\n    export CYLC_TASK_NAMESPACE_HIERARCHY="%s"' %
            ' '.join(job_conf['namespace_hierarchy']))
        handle.write(
            '\n    export CYLC_TASK_TRY_NUMBER=%s' % job_conf['try_num'])
        if job_conf['work_d']:
            handle.write(
                "\n    CYLC_TASK_WORK_DIR_BASE='%s'" % job_conf['work_d'])
        handle.write("\n}")

        # SSH comms variables. Note:
        # For "poll", contact file will not be installed, and job will not
        # attempt to communicate back.
        # Otherwise, job will attempt to communicate back via HTTP(S).
        comms = self._get_host_item(job_conf, 'task communication method')
        if comms == 'ssh':
            handle.write("\n\n    # CYLC MESSAGE ENVIRONMENT:")
            handle.write('\n    export CYLC_TASK_COMMS_METHOD="%s"' % comms)
            handle.write(
                '\n    export CYLC_TASK_SSH_LOGIN_SHELL="%s"' %
                self._get_host_item(job_conf, 'use login shell'))

    def _write_environment_2(self, handle, job_conf):
        """Run time environment part 2."""
        if job_conf['environment']:
            handle.write("\n\ncylc::job::inst::user-env() {")
            # Generate variable assignment expressions
            handle.write("\n    # TASK RUNTIME ENVIRONMENT:")
            for var, val in job_conf['environment'].items():
                value = str(val)  # (needed?)
                match = re.match(r"^(~[^/\s]*/)(.*)$", value)
                if match:
                    # ~foo/bar or ~/bar
                    # write as ~foo/"bar" or ~/"bar"
                    head, tail = match.groups()
                    handle.write('\n    %s=%s"%s"' % (var, head, tail))
                elif re.match(r"^~[^\s]*$", value):
                    # plain ~foo or just ~
                    # just leave unquoted as subsequent spaces don't
                    # make sense in this case anyway
                    handle.write('\n    %s=%s' % (var, value))
                else:
                    # Non tilde values - quote the lot.
                    # This gets values like "~one ~two" too, but these
                    # (in variable values) aren't expanded by the shell
                    # anyway so it doesn't matter.
                    handle.write('\n    %s="%s"' % (var, value))

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
            handle.write("\n    export")
            for var in job_conf['environment']:
                handle.write(" " + var)
            handle.write("\n}")

    @classmethod
    def _write_global_init_script(cls, handle, job_conf):
        """Global Init-script."""
        global_init_script = cls._get_host_item(
            job_conf, 'global init-script')
        if global_init_script:
            handle.write("\n\ncylc::job::inst::global-init-script() {")
            handle.write("\n# GLOBAL-INIT-SCRIPT:\n")
            handle.write(global_init_script)
            handle.write("\n}")

    @staticmethod
    def _write_script(handle, job_conf):
        """Write pre-script, script, and post-script."""
        for prefix in ['init-', 'env-', 'pre-', '', 'post-']:
            value = job_conf[prefix + 'script']
            if value:
                handle.write("\n\ncylc::job::inst::%sscript() {" % prefix)
                handle.write("\n# %sSCRIPT:\n%s" % (
                    prefix.upper(), value))
                handle.write("\n}")

    @staticmethod
    def _write_epilogue(handle, job_conf):
        """Write epilogue."""
        handle.write('\n\n. "${CYLC_DIR}/lib/cylc/job.sh"\ncylc::job::main')
        handle.write("\n\n%s%s\n" % (
            BATCH_SYS_MANAGER.LINE_PREFIX_EOF, job_conf['job_d']))
