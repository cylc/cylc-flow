#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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

"""Manage submission, poll and kill of a job to the batch systems.

Export the symbol BATCH_SYS_MANAGER, which is the singleton object for the
BatchSysManager class.

Batch system handler (a.k.a. job submission method) modules should be placed
under the "cylc.batch_sys_handlers" package. Each module should export the
symbol "BATCH_SYS_HANDLER" for the singleton instance that implements the job
system handler logic.

Each batch system handler class should instantiate with no argument, and may
have the following constants and methods:

batch_sys.filter_poll_output(out, job_id) => boolean
    * If this method is available, it will be called after the batch system's
      poll command is called and returns zero. The method should read the
      output to see if job_id is still alive in the batch system, and return
      True if so. See also "batch_sys.POLL_CMD_TMPL".

batch_sys.filter_submit_output(out, err) => new_out, new_err
    * Filter the standard output and standard error of the job submission
      command. This is useful if the job submission command returns information
      that should just be ignored. See also "batch_sys.SUBMIT_CMD_TMPL" and
      "batch_sys.SUBMIT_CMD_STDIN_TMPL".

batch_sys.get_fail_signals(job_conf) => list of strings
    * Return a list of names of signals to trap for reporting errors. Default
      is ["EXIT", "ERR", "TERM", "XCPU"]. ERR and EXIT are always recommended.
      EXIT is used to report premature stopping of the job script, and its trap
      is unset at the end of the script.

batch_sys.get_vacation_signal(job_conf) => str
    * If relevant, return a string containing the name of the signal that
      indicates the job has been vacated by the batch system.

batch_sys.format_directives(job_conf) => lines
    * If relevant, this method formats the job directives for a job file, if
      job file directives are relevant for the batch system. The argument
      "job_conf" is a dict containing the job configuration.

batch_sys.submit(job_file_path) => proc
    * Submit a job and return an instance of the Popen object for the
      submission. This method is useful if the job submission requires logic
      beyond just running a system or shell command. See also
      "batch_sys.SUBMIT_CMD".

batch_sys.CAN_KILL_PROC_GROUP
    * A boolean to indicate whether it is possible to kill the job by sending
      a signal to its Unix process group.

batch_sys.KILL_CMD_TMPL
    *  A Python string template for getting the batch system command to remove
       and terminate a job ID. The command is formed using the logic:
           batch_sys.KILL_CMD_TMPL % {"job_id": job_id}

batch_sys.POLL_CMD_TMPL
    * A Python string template for getting the batch system command to
      determine whether a job is alive, or to list jobs. The command is formed
      using the logic:
           batch_sys.POLL_CMD_TMPL % {"job_id": job_id}
      See also "batch_sys.filter_poll_output".

batch_sys.REC_ID_FROM_SUBMIT_ERR
batch_sys.REC_ID_FROM_SUBMIT_OUT
    * A regular expression (compiled) to extract the job "id" from the standard
      output or standard error of the job submission command.

batch_sys.SUBMIT_CMD_TMPL
    * A Python string template for getting the batch system command to submit a
      job file. The command is formed using the logic:
          batch_sys.SUBMIT_CMD_TMPL % {"job": job_file_path}
      See also "batch_sys.job_submit" and "batch_sys.SUBMIT_CMD_STDIN_TMPL".

batch_sys.SUBMIT_CMD_STDIN_TMPL
    * The template string for getting the STDIN for the batch system command to
      submit a job file. The value to write to STDIN is formed using the logic:
          batch_sys.SUBMIT_CMD_STDIN_TMPL % {"job": job_file_path}
      See also "batch_sys.job_submit" and "batch_sys.SUBMIT_CMD".

"""

from datetime import datetime
import os
import shlex
from signal import SIGKILL
import stat
from subprocess import call, Popen, PIPE
import sys
from cylc.mkdir_p import mkdir_p
from cylc.task_id import TaskID


class BatchSysManager(object):
    """Job submission, poll and kill.

    Manage the importing of job submission method modules.

    """

    CYLC_JOB_SUBMIT_TIME = "CYLC_JOB_SUBMIT_TIME"
    CYLC_BATCH_SYS_NAME = "CYLC_BATCH_SYS_NAME"
    CYLC_BATCH_SYS_JOB_ID = "CYLC_BATCH_SYS_JOB_ID"
    LINE_PREFIX_CYLC_DIR = "export CYLC_DIR="
    LINE_PREFIX_BATCH_SYS_NAME = "# Job submit method: "
    LINE_PREFIX_BATCH_SUBMIT_CMD_TMPL = "# Job submit command template: "
    LINE_UPDATE_CYLC_DIR = (
        "# N.B. CYLC_DIR has been updated on the remote host\n")
    _INSTANCES = {}

    @classmethod
    def configure_suite_run_dir(cls, suite_run_dir):
        """Add "suite_run_dir"/python to sys.path if not already done."""
        suite_py = os.path.join(suite_run_dir, "python")
        if os.path.isdir(suite_py) and suite_py not in sys.path:
            sys.path.append(suite_py)

    def get_inst(self, batch_sys_name):
        """Return an instance of the class for "batch_sys_name"."""
        if batch_sys_name in self._INSTANCES:
            return self._INSTANCES[batch_sys_name]
        for key in [
                "cylc.batch_sys_handlers." + batch_sys_name,
                batch_sys_name]:
            try:
                mod_of_name = __import__(key, fromlist=[key])
                self._INSTANCES[batch_sys_name] = getattr(
                    mod_of_name, "BATCH_SYS_HANDLER")
                return self._INSTANCES[batch_sys_name]
            except ImportError:
                if key == batch_sys_name:
                    raise

    def format_directives(self, job_conf):
        """Format the job directives for a job file, if relevant."""
        batch_sys = self.get_inst(job_conf['batch system name'])
        if hasattr(batch_sys, "format_directives"):
            return batch_sys.format_directives(job_conf)

    def get_fail_signals(self, job_conf):
        """Return a list of failure signal names to trap in the job file."""
        batch_sys = self.get_inst(job_conf['batch system name'])
        if hasattr(batch_sys, "get_fail_signals"):
            return batch_sys.get_fail_signals(job_conf)
        return ["EXIT", "ERR", "TERM", "XCPU"]

    def get_vacation_signal(self, job_conf):
        """Return the vacation signal name for a job file."""
        batch_sys = self.get_inst(job_conf['batch system name'])
        if hasattr(batch_sys, "get_vacation_signal"):
            return batch_sys.get_vacation_signal(job_conf)

    def is_bg_submit(self, batch_sys_name):
        """Return True if batch_sys_name behaves like background submit."""
        return getattr(self.get_inst(batch_sys_name), "IS_BG_SUBMIT", False)

    def job_kill(self, st_file_path):
        """Ask batch system to terminate the job specified in "st_file_path".

        Return zero on success, non-zero on failure.

        """
        # SUITE_RUN_DIR/log/job/CYCLE/TASK/SUBMIT/job.status
        self.configure_suite_run_dir(st_file_path.rsplit(os.sep, 6)[0])
        st_file = open(st_file_path)
        for line in st_file:
            if line.startswith(self.CYLC_BATCH_SYS_NAME + "="):
                batch_sys = self.get_inst(line.strip().split("=", 1)[1])
                break
        else:
            return 1
        st_file.seek(0, 0)
        if getattr(batch_sys, "CAN_KILL_PROC_GROUP", False):
            for line in st_file:
                if line.startswith("CYLC_JOB_PID="):
                    pid = line.strip().split("=", 1)[1]
                    os.killpg(int(pid), SIGKILL)
                    return 0
        if hasattr(batch_sys, "KILL_CMD_TMPL"):
            for line in st_file:
                if line.startswith(self.CYLC_BATCH_SYS_JOB_ID + "="):
                    job_id = line.strip().split("=", 1)[1]
                    return call(shlex.split(
                        batch_sys.KILL_CMD_TMPL % {"job_id": job_id}))
        return 1

    def job_poll(self, st_file_path):
        """Poll status of the job specified in the "st_file_path".

        Return a status string that can be recognised by the suite.

        """
        # SUITE_RUN_DIR/log/job/CYCLE/TASK/SUBMIT/job.status
        st_file_path_strs = st_file_path.rsplit(os.sep, 6)
        task_id = TaskID.get(st_file_path_strs[4], st_file_path_strs[3])
        self.configure_suite_run_dir(st_file_path_strs[0])

        statuses = {}
        try:
            for line in open(st_file_path):
                key, value = line.strip().split("=", 1)
                statuses[key] = value
        except IOError:
            return "polled %s submission failed\n" % (task_id)

        if (statuses.get("CYLC_JOB_EXIT_TIME") and
                statuses.get("CYLC_JOB_EXIT") == "SUCCEEDED"):
            return "polled %s succeeded at %s\n" % (
                task_id, statuses["CYLC_JOB_EXIT_TIME"])

        if (statuses.get("CYLC_JOB_EXIT_TIME") and
                statuses.get("CYLC_JOB_EXIT")):
            return "polled %s failed at %s\n" % (
                task_id, statuses["CYLC_JOB_EXIT_TIME"])

        if (self.CYLC_BATCH_SYS_NAME not in statuses or
                self.CYLC_BATCH_SYS_JOB_ID not in statuses):
            return "polled %s submission failed\n" % (task_id)

        # Ask batch system if job is still alive or not
        batch_sys = self.get_inst(statuses[self.CYLC_BATCH_SYS_NAME])
        job_id = statuses[self.CYLC_BATCH_SYS_JOB_ID]
        proc = Popen(
            shlex.split(batch_sys.POLL_CMD_TMPL % {"job_id": job_id}),
            stdout=PIPE)
        is_in_batch_sys = (proc.wait() == 0)
        if is_in_batch_sys and hasattr(batch_sys, "filter_poll_output"):
            is_in_batch_sys = batch_sys.filter_poll_output(
                proc.communicate()[0], job_id)

        if is_in_batch_sys and "CYLC_JOB_INIT_TIME" in statuses:
            return "polled %s started at %s\n" % (
                task_id, statuses["CYLC_JOB_INIT_TIME"])

        if is_in_batch_sys:
            return "polled %s submitted\n" % (task_id)

        if "CYLC_JOB_INIT_TIME" in statuses:
            return "polled %s failed at unknown-time\n" % (task_id)

        # Submitted but disappeared
        return "polled %s submission failed\n" % (task_id)

    def job_submit(self, job_file_path, remote_mode):
        """Submit a job file.

        "job_file_path" is a string containing the path to the job file.
        "remote_mode" is a boolean to indicate if submit is being initiated on
        a remote job host.

        Return a 4-element tuple (ret_code, out, err, job_id) where:
        "ret_code" is the integer return code of the job submit command.
        "out" is a string containing the standard output of the job submit
        command.
        "err" is a string containing the standard error output of the job
        submit command.
        "job_id" is a string containing the ID of the job submitted.

        """
        # SUITE_RUN_DIR/log/job/CYCLE/TASK/SUBMIT/job
        self.configure_suite_run_dir(job_file_path.rsplit(os.sep, 6)[0])

        batch_sys_name = None
        batch_submit_cmd_tmpl = None
        if remote_mode:
            batch_sys_name, batch_submit_cmd_tmpl = (
                self._job_submit_prepare_remote(job_file_path))
        else:  # local mode
            for line in open(job_file_path):
                if line.startswith(self.LINE_PREFIX_BATCH_SYS_NAME):
                    batch_sys_name = line.replace(
                        self.LINE_PREFIX_BATCH_SYS_NAME, "").strip()
                elif line.startswith(self.LINE_PREFIX_BATCH_SUBMIT_CMD_TMPL):
                    batch_submit_cmd_tmpl = line.replace(
                        self.LINE_PREFIX_BATCH_SUBMIT_CMD_TMPL, "").strip()

        # Create NN symbolic link, if necessary
        self._create_nn(job_file_path)

        # Start new status file
        job_status_file = open(job_file_path + ".status", "w")
        job_status_file.write(
            "%s=%s\n" % (self.CYLC_BATCH_SYS_NAME, batch_sys_name))
        job_status_file.close()

        # Submit job
        batch_sys = self.get_inst(batch_sys_name)
        proc_stdin_arg = None
        proc_stdin_value = None
        if hasattr(batch_sys, "SUBMIT_CMD_STDIN_TMPL"):
            proc_stdin_value = batch_sys.SUBMIT_CMD_STDIN_TMPL % {
                "job": job_file_path}
            proc_stdin_arg = PIPE
        if batch_submit_cmd_tmpl:
            batch_sys_cmd = batch_submit_cmd_tmpl % {"job": job_file_path}
            proc = Popen(
                batch_sys_cmd,
                stdin=proc_stdin_arg, stdout=PIPE, stderr=PIPE, shell=True)
        elif hasattr(batch_sys, "submit"):
            proc = batch_sys.submit(job_file_path)
        else:
            proc = Popen(
                shlex.split(
                    batch_sys.SUBMIT_CMD_TMPL % {"job": job_file_path}),
                stdin=proc_stdin_arg, stdout=PIPE, stderr=PIPE)
        out, err = proc.communicate(proc_stdin_value)

        # Filter submit command output, if relevant
        # Get job ID, if possible
        job_id = None
        if out or err:
            out, err, job_id = self._filter_submit_output(
                job_file_path, batch_sys, out, err)

        return proc.wait(), out, err, job_id

    @classmethod
    def _create_nn(cls, job_file_path):
        """Create NN symbolic link, if necessary.

        Helper for "self.submit".

        """
        job_file_dir = os.path.dirname(job_file_path)
        nn_path = os.path.join(os.path.dirname(job_file_dir), "NN")
        try:
            os.unlink(nn_path)
        except OSError:
            pass
        os.symlink(os.path.basename(job_file_dir), nn_path)

    def _filter_submit_output(self, job_file_path, batch_sys, out, err):
        """Filter submit command output, if relevant."""
        job_id = None
        if hasattr(batch_sys, "REC_ID_FROM_SUBMIT_ERR"):
            text = err
            rec_id = batch_sys.REC_ID_FROM_SUBMIT_ERR
        elif hasattr(batch_sys, "REC_ID_FROM_SUBMIT_OUT"):
            text = out
            rec_id = batch_sys.REC_ID_FROM_SUBMIT_OUT
        if rec_id:
            for line in str(text).splitlines():
                match = rec_id.match(line)
                if match:
                    job_id = match.group("id")
                    job_status_file = open(job_file_path + ".status", "a")
                    job_status_file.write("%s=%s\n" % (
                        self.CYLC_BATCH_SYS_JOB_ID, job_id))
                    job_status_file.write("%s=%s\n" % (
                        self.CYLC_JOB_SUBMIT_TIME,
                        datetime.utcnow().strftime("%FT%H:%M:%SZ")))
                    job_status_file.close()
                    break
        if hasattr(batch_sys, "filter_submit_output"):
            out, err = batch_sys.filter_submit_output(out, err)
        return out, err, job_id

    def _job_submit_prepare_remote(self, job_file_path):
        """Prepare a remote job file.

        On remote mode, write job file, content from STDIN Modify job
        script's CYLC_DIR for this host. Extract job submission method
        and job submission command template.

        Return (batch_sys_name, batch_sys_submit)

        """
        batch_sys_name = None
        batch_submit_cmd_tmpl = None
        mkdir_p(os.path.dirname(job_file_path))
        job_file = open(job_file_path + ".tmp", "w")
        while True:  # Note: "for line in sys.stdin:" may hang
            line = sys.stdin.readline()
            if not line:
                sys.stdin.close()
                break
            if line.strip().startswith(self.LINE_PREFIX_CYLC_DIR):
                old_line = line
                line = (
                    line[0:line.find(self.LINE_PREFIX_CYLC_DIR)] +
                    self.LINE_PREFIX_CYLC_DIR + "'%s'\n" %
                    os.environ["CYLC_DIR"])
                if old_line != line:
                    job_file.write(self.LINE_UPDATE_CYLC_DIR)
            elif line.startswith(self.LINE_PREFIX_BATCH_SYS_NAME):
                batch_sys_name = line.replace(
                    self.LINE_PREFIX_BATCH_SYS_NAME, "").strip()
            elif line.startswith(self.LINE_PREFIX_BATCH_SUBMIT_CMD_TMPL):
                batch_submit_cmd_tmpl = line.replace(
                    self.LINE_PREFIX_BATCH_SUBMIT_CMD_TMPL, "").strip()
            job_file.write(line)
        job_file.close()
        os.rename(job_file_path + ".tmp", job_file_path)
        os.chmod(job_file_path, (
            os.stat(job_file_path).st_mode |
            stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))
        return batch_sys_name, batch_submit_cmd_tmpl


BATCH_SYS_MANAGER = BatchSysManager()
