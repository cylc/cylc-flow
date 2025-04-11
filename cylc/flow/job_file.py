# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
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
"""Write job files."""

from contextlib import suppress
import os
import re
import stat
from subprocess import Popen, PIPE, DEVNULL
from textwrap import dedent

from cylc.flow import __version__ as CYLC_VERSION
from cylc.flow.job_runner_mgr import JobRunnerManager
import cylc.flow.flags
from cylc.flow.log_level import verbosity_to_env
from cylc.flow.config import interpolate_template, ParamExpandError


class JobFileWriter:

    """Write job files."""

    def __init__(self):
        self.workflow_env = {}
        self.job_runner_mgr = JobRunnerManager()

    def set_workflow_env(self, workflow_env):
        """Configure workflow environment for all job files."""
        self.workflow_env.clear()
        self.workflow_env.update(workflow_env)

    def write(self, local_job_file_path, job_conf, check_syntax=True):
        """Write each job script section in turn."""

        # ########### !!!!!!!! WARNING !!!!!!!!!!! #####################
        # BE EXTREMELY WARY OF CHANGING THE ORDER OF JOB SCRIPT SECTIONS
        # Users may be relying on the existing order (see for example
        # the comment below on workflow bin path being required before
        # task runtime environment setup).
        # ##############################################################

        # Access to cylc must be configured before user environment so
        # that cylc commands can be used in defining user environment
        # variables: NEXT_CYCLE=$( cylc cycle-point --offset-hours=6 )
        tmp_name = os.path.expandvars(local_job_file_path + '.tmp')
        try:
            with open(tmp_name, 'w') as handle:
                self._write_header(handle, job_conf)
                self._write_directives(handle, job_conf)
                self._write_reinvocation(handle)
                self._write_prelude(handle, job_conf)
                self._write_workflow_environment(handle, job_conf)
                self._write_task_environment(handle, job_conf)
                # workflow bin access must be before runtime environment
                # because workflow bin commands may be used in variable
                # assignment expressions: FOO=$(command args).
                self._write_runtime_environment(handle, job_conf)
                self._write_script(handle, job_conf)
                self._write_global_init_script(handle, job_conf)
                self._write_epilogue(handle, job_conf)
        except IOError as exc:
            # Remove temporary file
            with suppress(OSError):
                os.unlink(tmp_name)
            raise exc
        # check syntax
        if check_syntax:
            try:
                with Popen(  # nosec
                    ['/usr/bin/env', 'bash', '-n', tmp_name],
                    stderr=PIPE,
                    stdin=DEVNULL,
                    text=True
                    # * the purpose of this is to evaluate user defined code
                    #   prior to it being executed
                ) as proc:
                    if proc.wait():
                        # This will leave behind the temporary file,
                        # which is useful for debugging syntax errors, etc.
                        raise RuntimeError(proc.communicate()[1])
            except OSError as exc:
                # Popen has a bad habit of not telling you anything if it fails
                # to run the executable.
                if exc.filename is None:
                    exc.filename = 'bash'
                # Remove temporary file
                with suppress(OSError):
                    os.unlink(tmp_name)
                raise exc
        # Make job file executable
        mode = (
            os.stat(tmp_name).st_mode |
            stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        os.chmod(tmp_name, mode)
        os.rename(tmp_name, os.path.expandvars(local_job_file_path))

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
    def _write_header(handle, job_conf):
        """Write job script header."""
        handle.write("#!/bin/bash -l\n")
        handle.write("#\n# ++++ THIS IS A CYLC JOB SCRIPT ++++")
        for prefix, value in [
                ("# Workflow: ", job_conf['workflow_name']),
                ("# Task: ", job_conf['task_id']),
                (JobRunnerManager.LINE_PREFIX_JOB_LOG_DIR, job_conf['job_d']),
                (JobRunnerManager.LINE_PREFIX_JOB_RUNNER_NAME,
                 job_conf['platform']['job runner']),
                (JobRunnerManager.LINE_PREFIX_JOB_RUNNER_CMD_TMPL,
                 job_conf['platform']['job runner command template']),
                (JobRunnerManager.LINE_PREFIX_EXECUTION_TIME_LIMIT,
                 job_conf['execution_time_limit'])]:
            if value:
                handle.write("\n%s%s" % (prefix, value))

    def _write_directives(self, handle, job_conf):
        """Job directives."""
        lines = self.job_runner_mgr.format_directives(job_conf)
        if lines:
            handle.write('\n\n# DIRECTIVES:')
            for line in lines:
                handle.write('\n' + line)

    def _write_reinvocation(self, handle):
        """Re-invoke using user determined bash interpreter."""
        # NOTE this must be done after the directives are written out
        # due to the way slurm reads directives
        # NOTE we cannot do /usr/bin/env bash because we need to use the -l
        # option and GNU env doesn't support additional arguments (recent
        # versions permit this with the -S option similar to BSD env but we
        # cannot make the jump to this until is it more widely adopted)
        handle.write(dedent('''
            if [[ $1 == 'noreinvoke' ]]; then
                shift
            else
                exec bash -l "$0" noreinvoke "$@"
            fi
        '''))

    def _write_prelude(self, handle, job_conf):
        """Job script prelude."""
        # Variables for traps
        handle.write("\nCYLC_FAIL_SIGNALS='%s'" % " ".join(
            self.job_runner_mgr.get_fail_signals(job_conf)))
        vacation_signals_str = self.job_runner_mgr.get_vacation_signal(
            job_conf)
        if vacation_signals_str:
            handle.write("\nCYLC_VACATION_SIGNALS='%s'" % vacation_signals_str)
        # Path to the `cylc` executable, if defined.
        cylc_path = job_conf['platform']['cylc path']
        if cylc_path:
            handle.write(f"\nexport PATH={cylc_path}:$PATH")
        # Environment variables for prelude
        for key, value in verbosity_to_env(cylc.flow.flags.verbosity).items():
            handle.write(f'\nexport {key}={value}')
        handle.write("\nexport CYLC_VERSION='%s'" % CYLC_VERSION)
        try:
            CYLC_ENV_NAME = os.environ['CYLC_ENV_NAME']
        except KeyError:
            pass
        else:
            handle.write(
                "\nexport CYLC_ENV_NAME='%s'" % CYLC_ENV_NAME)
        handle.write(
            '\nexport CYLC_WORKFLOW_ID='
            f'"{job_conf["workflow_name"]}"'
        )
        env_vars = (
            (job_conf['platform']['copyable environment variables'] or [])
            # pass CYLC_COVERAGE into the job execution environment
            + ['CYLC_COVERAGE']
        )
        for key in env_vars:
            if key in os.environ:
                handle.write("\nexport %s='%s'" % (key, os.environ[key]))

    def _write_workflow_environment(self, handle, job_conf):
        """Workflow and task environment."""
        handle.write("\n\ncylc__job__inst__cylc_env() {")
        handle.write("\n    # CYLC WORKFLOW ENVIRONMENT:")
        # write the static workflow variables
        for var, val in sorted(self.workflow_env.items()):
            if var not in ('CYLC_DEBUG', 'CYLC_VERBOSE', 'CYLC_WORKFLOW_ID'):
                handle.write('\n    export %s="%s"' % (var, val))

        if str(self.workflow_env.get('CYLC_UTC')) == 'True':
            handle.write('\n    export TZ="UTC"')

        handle.write(
            '\n    export CYLC_WORKFLOW_UUID="%s"' % job_conf['uuid_str'])

    def _write_task_environment(self, handle, job_conf):
        comm_meth = job_conf['platform']['communication method']

        handle.write("\n\n    # CYLC TASK ENVIRONMENT:")
        handle.write(f"\n    export CYLC_TASK_COMMS_METHOD={comm_meth}")
        handle.write('\n    export CYLC_TASK_JOB="%s"' % job_conf['job_d'])
        handle.write(
            '\n    export CYLC_TASK_NAMESPACE_HIERARCHY="%s"' %
            ' '.join(job_conf['namespace_hierarchy']))
        handle.write(
            '\n    export CYLC_TASK_TRY_NUMBER=%s' % job_conf['try_num'])
        handle.write(
            "\n    export CYLC_TASK_FLOW_NUMBERS="
            f"{','.join(str(f) for f in job_conf['flow_nums'])}")
        handle.write(
            "\n    export CYLC_PROFILE="
            f"{job_conf['platform']['profile']['activate']}")
        handle.write(
            "\n    export CYLC_CGROUP="
            f"{job_conf['platform']['profile']['cgroups path']}")
        # Standard parameter environment variables
        for var, val in job_conf['param_var'].items():
            handle.write('\n    export CYLC_TASK_PARAM_%s="%s"' % (var, val))
        if job_conf['work_d']:
            # Note: not an environment variable, but used by job.sh
            handle.write(
                "\n    CYLC_TASK_WORK_DIR_BASE='%s'" % job_conf['work_d'])
        handle.write("\n}")

    @staticmethod
    def _write_runtime_environment(handle, job_conf):
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
                handle.write(f' {var}')
            for var, val in job_conf['environment'].items():
                value = JobFileWriter._get_variable_value_definition(
                    str(val), job_conf.get('param_var', {})
                )
                handle.write(f'\n    {var}={value}')
            handle.write("\n}")

    @staticmethod
    def _get_variable_value_definition(value, param_vars):
        """Return a properly-quoted command which handles parameter environment
        templates and the '~' character.

        Args:
            value (str): value to assign to a variable
            param_vars (dict): parameter variables ( job_conf['param_vars'] )
        """
        # Interpolate any parameter environment template variables:
        if param_vars:
            with suppress(ParamExpandError):
                value = interpolate_template(value, param_vars)
                # ParamExpandError: Already logged warnings in
                # cylc.flow.config.WorkflowConfig.check_param_env_tmpls()

        # Handle '~':
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
        global_init_script = job_conf['platform']['global init-script']
        if cls._check_script_value(global_init_script):
            handle.write("\n\n# GLOBAL INIT-SCRIPT:\n")
            handle.write(global_init_script)

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
        handle.write('\n\nCYLC_RUN_DIR="${CYLC_RUN_DIR:-$HOME/cylc-run}"')
        handle.write(
            '\n. '
            '"${CYLC_RUN_DIR}/${CYLC_WORKFLOW_ID}/.service/etc/job.sh"'
            '\ncylc__job__main'
        )
        handle.write("\n\n%s%s\n" % (
            JobRunnerManager.LINE_PREFIX_EOF, job_conf['job_d']))
