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

"""
Job submission base class.

Writes a temporary "job file" that encapsulates the task runtime settings
(execution environment, command scripting, etc.) then submits it by the
chosen method on the chosen host (using passwordless ssh if not local).

Derived classes define the particular job submission method.
"""

import os
from signal import SIGKILL
import socket
import stat
from subprocess import check_call, Popen, PIPE
import sys

from cylc.job_submission.jobfile import JobFile
from cylc.cfgspec.globalcfg import GLOBAL_CFG
from cylc.owner import is_remote_user
from cylc.suite_host import is_remote_host
from cylc.envvar import expandvars


class JobSubmit(object):
    """Base class for method-specific job script and submission command."""

    COMMAND = None
    EXEC_KILL = None
    EXEC_SUBMIT = None
    REC_ID_FROM_ERR = None
    REC_ID_FROM_OUT = None

    @classmethod
    def get_class(cls, name, suite_run_dir=None):
        """Return the class for the job submission method "name"."""
        if suite_run_dir:
            suite_py = os.path.join(suite_run_dir, "python")
            if os.path.isdir(suite_py) and suite_py not in sys.path:
                sys.path.append(suite_py)
        for key in ["cylc.job_submission." + name, name]:
            try:
                return getattr(__import__(key, fromlist=[key]), name)
            except ImportError:
                if key == name:
                    raise

    def __init__(self, task_id, suite, jobconfig):

        self.jobconfig = jobconfig

        self.task_id = task_id
        self.suite = suite
        self.logfiles = jobconfig.get('log files')

        self.command = None
        self.job_submit_command_template = jobconfig.get('command template')

        common_job_log_path = jobconfig.get('common job log path')
        self.local_jobfile_path = jobconfig.get('local job file path')
        self.logfiles.add_path(self.local_jobfile_path)

        task_host = jobconfig.get('task host')
        task_owner = jobconfig.get('task owner')

        if is_remote_host(task_host) or is_remote_user(task_owner):
            self.local = False
            if task_owner:
                self.task_owner = task_owner
            else:
                self.task_owner = None

            if task_host:
                self.task_host = task_host
            else:
                self.task_host = socket.gethostname()

            remote_job_log_dir = GLOBAL_CFG.get_derived_host_item(
                self.suite,
                'suite job log directory',
                self.task_host,
                self.task_owner)

            remote_jobfile_path = os.path.join(
                remote_job_log_dir, common_job_log_path)

            # Remote log files
            self.stdout_file = remote_jobfile_path + ".out"
            self.stderr_file = remote_jobfile_path + ".err"

            # Used in command construction:
            self.jobfile_path = remote_jobfile_path

            # Record paths of remote log files for access by gui
            if True:
                # by ssh URL
                url_prefix = self.task_host
                if self.task_owner:
                    url_prefix = self.task_owner + "@" + url_prefix
                self.logfiles.add_path(url_prefix + ':' + self.stdout_file)
                self.logfiles.add_path(url_prefix + ':' + self.stderr_file)
            else:
                # CURRENTLY DISABLED:
                # If the remote and suite hosts see a common filesystem, or
                # if the remote task is really just a local task with a
                # different owner, we could just use local filesystem access.
                # But to use this: (a) special namespace config would be
                # required to indicate we have a common filesystem, and
                # (b) we'd need to consider how the log directory can be
                # specified (for example use of '$HOME' as for remote
                # task use would not work here as log file access is by
                # gui under the suite owner account.
                self.logfiles.add_path(self.stdout_file)
                self.logfiles.add_path(self.stderr_file)
        else:
            # LOCAL TASKS
            self.local = True
            self.task_owner = None
            # Used in command construction:
            self.jobfile_path = self.local_jobfile_path

            # Local stdout and stderr log file paths:
            self.stdout_file = self.local_jobfile_path + ".out"
            self.stderr_file = self.local_jobfile_path + ".err"

            # interpolate environment variables in extra logs
            for idx in range(0, len(self.logfiles.paths)):
                self.logfiles.paths[idx] = expandvars(self.logfiles.paths[idx])

            # Record paths of local log files for access by gui
            self.logfiles.add_path(self.stdout_file)
            self.logfiles.add_path(self.stderr_file)

        # set some defaults that can be overridden by derived classes
        self.jobconfig['directive prefix'] = None
        self.jobconfig['directive final'] = "# FINAL DIRECTIVE"
        self.jobconfig['directive connector'] = " "
        self.jobconfig['job vacation signal'] = None

        # overrideable methods
        self.set_directives()
        self.set_job_vacation_signal()
        self.set_scripting()
        self.set_environment()

    def set_directives(self):
        """OVERRIDE IN DERIVED JOB SUBMISSION CLASSES THAT USE DIRECTIVES

        (directives will be ignored if the prefix below is not overridden)

        Defaults set in task.py:
        self.jobconfig = {
         PREFIX: e.g. '#QSUB' (qsub), or '# @' (loadleveler)
             'directive prefix' : None,
         FINAL directive, WITH PREFIX, e.g. '# @ queue' for loadleveler
             'directive final' : '# FINAL_DIRECTIVE '
         CONNECTOR, e.g. ' = ' for loadleveler, ' ' for qsub
             'directive connector' :  " DIRECTIVE_CONNECTOR "
        }
        """
        pass

    def set_scripting(self):
        """Derived class can use this to modify pre/post-command scripting"""
        return

    def set_environment(self):
        """Derived classes can use this to modify task execution environment"""
        return

    def set_job_vacation_signal(self):
        """Derived class can set self.jobconfig['job vacation signal']."""
        return

    def filter_output(self, out, err):
        """Filter the stdout/stderr from a job submission command.

        Derived classes should override this method.
        Used to prevent routine logging of irrelevant information.

        """
        return out, err

    def get_id(self, out, err):
        """Get the job submit ID from a job submission command output."""
        if self.REC_ID_FROM_ERR:
            text = err
            rec_id = self.REC_ID_FROM_ERR
        elif self.REC_ID_FROM_OUT:
            text = out
            rec_id = self.REC_ID_FROM_OUT
        else:
            raise NotImplementedError()
        for line in str(text).splitlines():
            match = rec_id.match(line)
            if match:
                return match.group("id")

    def kill(self, st_file):
        """Kill a job."""
        if not self.EXEC_KILL:
            raise NotImplementedError()
        for line in open(st_file):
            if line.startswith("CYLC_JOB_SUBMIT_METHOD_ID="):
                job_sys_id = line.strip().split("=", 1)[1]
                return check_call([self.EXEC_KILL, job_sys_id])

    @classmethod
    def kill_proc_group(cls, st_file):
        """Kill the job process group, for e.g. "background" and "at" jobs."""
        for line in open(st_file):
            if line.startswith("CYLC_JOB_PID="):
                pid = line.strip().split("=", 1)[1]
                os.killpg(int(pid), SIGKILL)
                return 0
        return 1

    def submit(self, job_file_path, command_template=None):
        """Submit the job.

        Derived classes should override this method.

        """
        if command_template:
            command = command_template % {"job": job_file_path}
            proc = Popen(command, stdout=PIPE, stderr=PIPE, shell=True)
        else:
            if not self.EXEC_SUBMIT:
                raise NotImplementedError()
            proc = Popen(
                [self.EXEC_SUBMIT, job_file_path], stdout=PIPE, stderr=PIPE)
        out, err = proc.communicate()
        return (proc.wait(), out, err)

    def write_jobscript(self):
        """ submit the task and return the process ID of the job
        submission sub-process, or None if a failure occurs."""

        job_file = JobFile(
            self.suite,
            self.jobfile_path,
            self.__class__.__name__,
            self.task_id,
            self.jobconfig)

        job_file.write(self.local_jobfile_path)
        # make it executable
        mode = (os.stat(self.local_jobfile_path).st_mode |
                stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        os.chmod(self.local_jobfile_path, mode)
