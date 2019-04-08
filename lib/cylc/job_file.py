#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
from subprocess import Popen, PIPE

from cylc import __version__ as CYLC_VERSION
from cylc.batch_sys_manager import BatchSysManager
from cylc.cfgspec.glbl_cfg import glbl_cfg
import cylc.flags


class JobFileWriter(object):

    """Write task job files."""

    def __init__(self):
        self.suite_env = {}
        self.batch_sys_mgr = BatchSysManager()

    def set_suite_env(self, suite_env):
        """Configure suite environment for all job files."""
        self.suite_env.clear()
        self.suite_env.update(suite_env)

    def write(self, local_job_file_path, job_conf, check_syntax=True):
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

        tmp_name = local_job_file_path + '.tmp'
        try:
            with open(tmp_name, 'w') as handle:
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
        except IOError as exc:
            # Remove temporary file
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise exc
        # check syntax
        if check_syntax:
            try:
                proc = Popen(
                    ['/bin/bash', '-n', tmp_name],
                    stderr=PIPE, stdin=open(os.devnull))
            except OSError as exc:
                # Popen has a bad habit of not telling you anything if it fails
                # to run the executable.
                if exc.filename is None:
                    exc.filename = '/bin/bash'
                # Remove temporary file
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                raise exc
            else:
                if proc.wait():
                    # This will leave behind the temporary file,
                    # which is useful for debugging syntax errors, etc.
                    raise RuntimeError(proc.communicate()[1].decode())
        # Make job file executable
        mode = (
            os.stat(tmp_name).st_mode |
            stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        os.chmod(tmp_name, mode)
        os.rename(tmp_name, local_job_file_path)

    @staticmethod
    def _check_script_value(value):
        """Return True if script has any executable statements."""
        if value:
            for line in value.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    return True
        return False

    @staticmethod
    def _get_derived_host_item(job_conf, key):
        """Return derived host item from glbl_cfg()."""
        return glbl_cfg().get_derived_host_item(
            job_conf['suite_name'], key, job_conf["host"], job_conf["owner"])

    @staticmethod
    def _get_host_item(job_conf, key):
        """Return host item from glbl_cfg()."""
        return glbl_cfg().get_host_item(
            key, job_conf["host"], job_conf["owner"])

    @staticmethod
    def _write_header(handle, job_conf):
        """Write job script header."""
        handle.write("#!/bin/bash -l\n")
        handle.write("#\n# ++++ THIS IS A CYLC TASK JOB SCRIPT ++++")
        for prefix, value in [
                ("# Suite: ", job_conf['suite_name']),
                ("# Task: ", job_conf['task_id']),
                (BatchSysManager.LINE_PREFIX_JOB_LOG_DIR, job_conf['job_d']),
                (BatchSysManager.LINE_PREFIX_BATCH_SYS_NAME,
                 job_conf['batch_system_name']),
                (BatchSysManager.LINE_PREFIX_BATCH_SUBMIT_CMD_TMPL,
                 job_conf['batch_submit_command_template']),
                (BatchSysManager.LINE_PREFIX_EXECUTION_TIME_LIMIT,
                 job_conf['execution_time_limit'])]:
            if value:
                handle.write("\n%s%s" % (prefix, value))

    def _write_directives(self, handle, job_conf):
        """Job directives."""
        lines = self.batch_sys_mgr.format_directives(job_conf)
        if lines:
            handle.write('\n\n# DIRECTIVES:')
            for line in lines:
                handle.write('\n' + line)

    def _write_prelude(self, handle, job_conf):
        """Job script prelude."""
        # Environment variables for prelude
        handle.write("\nexport CYLC_DIR='%s'" % (os.environ['CYLC_DIR']))
        if cylc.flags.debug:
            handle.write("\nexport CYLC_DEBUG=true")
        handle.write("\nexport CYLC_VERSION='%s'" % CYLC_VERSION)
        for key in self._get_host_item(
                job_conf, 'copyable environment variables'):
            if key in os.environ:
                handle.write("\nexport %s='%s'" % (key, os.environ[key]))
        # Variables for traps
        handle.write("\nCYLC_FAIL_SIGNALS='%s'" % " ".join(
            self.batch_sys_mgr.get_fail_signals(job_conf)))
        vacation_signals_str = self.batch_sys_mgr.get_vacation_signal(job_conf)
        if vacation_signals_str:
            handle.write("\nCYLC_VACATION_SIGNALS='%s'" % vacation_signals_str)

    def _write_environment_1(self, handle, job_conf):
        """Suite and task environment."""
        handle.write("\n\ncylc__job__inst__cylc_env() {")
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
            # Note: not an environment variable, but used by job.sh
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
        handle.write(
            '\n    export CYLC_SUITE_UUID="%s"' % job_conf['uuid_str'])

        handle.write("\n\n    # CYLC TASK ENVIRONMENT:")
        handle.write('\n    export CYLC_TASK_JOB="%s"' % job_conf['job_d'])
        handle.write(
            '\n    export CYLC_TASK_NAMESPACE_HIERARCHY="%s"' %
            ' '.join(job_conf['namespace_hierarchy']))
        handle.write(
            '\n    export CYLC_TASK_DEPENDENCIES="%s"' %
            ' '.join(job_conf['dependencies']))
        handle.write(
            '\n    export CYLC_TASK_TRY_NUMBER=%s' % job_conf['try_num'])
        # Custom parameter environment variables
        for var, tmpl in job_conf['param_env_tmpl'].items():
            handle.write('\n    export %s="%s"' % (
                var, tmpl % job_conf['param_var']))
        # Standard parameter environment variables
        for var, val in job_conf['param_var'].items():
            handle.write('\n    export CYLC_TASK_PARAM_%s="%s"' % (var, val))
        if job_conf['work_d']:
            # Note: not an environment variable, but used by job.sh
            handle.write(
                "\n    CYLC_TASK_WORK_DIR_BASE='%s'" % job_conf['work_d'])
        handle.write("\n}")

    @staticmethod
    def _write_environment_2(handle, job_conf):
        """Run time environment part 2."""
        if job_conf['environment']:
            handle.write("\n\ncylc__job__inst__user_env() {")
            # Generate variable assignment expressions
            handle.write("\n    # TASK RUNTIME ENVIRONMENT:")

            # NOTE: the reason for separate export of user-specified
            # variables is this: inline export does not activate the
            # error trap if sub-expressions fail, e.g. (note typo in
            # 'echo' command name):
            #   export FOO=$( ecko foo )  # error not trapped!
            #   FOO=$( ecko foo )  # error trapped
            # The export is done before variable definition to enable
            # use of already defined variables by command substitutions
            # in later definitions:
            #   FOO='foo'
            #   BAR=$(script_using_FOO)
            handle.write("\n    export")
            for var in job_conf['environment']:
                handle.write(" " + var)
            for var, val in job_conf['environment'].items():
                value = str(val)  # (needed?)
                value = JobFileWriter._get_variable_value_definition(value)
                handle.write('\n    %s=%s' % (var, value))
            handle.write("\n}")

    @staticmethod
    def _get_variable_value_definition(value):
        """Create a quoted command which handles '~'
        Args:
            value: value to assign to a variable
        Returns:
            str: Properly handled '~' value
        """
        match = re.match(r"^(~[^/\s]*/)(.*)$", value)
        if match:
            # ~foo/bar or ~/bar
            # write as ~foo/"bar" or ~/"bar"
            head, tail = match.groups()
            return '%s"%s"' % (head, tail)
        elif re.match(r"^~[^\s]*$", value):
            # plain ~foo or just ~
            # just leave unquoted as subsequent spaces don't
            # make sense in this case anyway
            return value
        else:
            # Non tilde values - quote the lot.
            # This gets values like "~one ~two" too, but these
            # (in variable values) aren't expanded by the shell
            # anyway so it doesn't matter.
            return '"%s"' % value

        # NOTE ON TILDE EXPANSION:
        # The code above handles the following correctly:
        # | ~foo/bar
        # | ~/bar
        # | ~/filename with spaces
        # | ~foo
        # | ~

    @classmethod
    def _write_global_init_script(cls, handle, job_conf):
        """Global Init-script."""
        global_init_script = cls._get_host_item(
            job_conf, 'global init-script')
        if cls._check_script_value(global_init_script):
            handle.write("\n\ncylc__job__inst__global_init_script() {")
            handle.write("\n# GLOBAL-INIT-SCRIPT:\n")
            handle.write(global_init_script)
            handle.write("\n}")

    @classmethod
    def _write_script(cls, handle, job_conf):
        """Write (*-)script in functions.

        init-script, env-script, err-script, pre-script, script, post-script,
        exit-script
        """
        for prefix in ['init-', 'env-', 'err-', 'pre-', '', 'post-', 'exit-']:
            value = job_conf[prefix + 'script']
            if cls._check_script_value(value):
                handle.write("\n\ncylc__job__inst__%sscript() {" % (
                    prefix.replace("-", "_")))
                handle.write("\n# %sSCRIPT:\n%s" % (
                    prefix.upper(), value))
                handle.write("\n}")

    @staticmethod
    def _write_epilogue(handle, job_conf):
        """Write epilogue."""
        handle.write('\n\n. "${CYLC_DIR}/lib/cylc/job.sh"\ncylc__job__main')
        handle.write("\n\n%s%s\n" % (
            BatchSysManager.LINE_PREFIX_EOF, job_conf['job_d']))
