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

batch_sys.filter_poll_many_output(out) => job_ids
    * Called after the batch system's poll many command. The method should read
      the output and return a list of job IDs that are still in the batch
      system.

batch_sys.filter_submit_output(out, err) => new_out, new_err
    * Filter the standard output and standard error of the job submission
      command. This is useful if the job submission command returns information
      that should just be ignored. See also "batch_sys.SUBMIT_CMD_TMPL" and
      "batch_sys.SUBMIT_CMD_STDIN_TMPL".

batch_sys.format_directives(job_conf) => lines
    * If relevant, this method formats the job directives for a job file, if
      job file directives are relevant for the batch system. The argument
      "job_conf" is a dict containing the job configuration.

batch_sys.get_fail_signals(job_conf) => list of strings
    * Return a list of names of signals to trap for reporting errors. Default
      is ["EXIT", "ERR", "TERM", "XCPU"]. ERR and EXIT are always recommended.
      EXIT is used to report premature stopping of the job script, and its trap
      is unset at the end of the script.

batch_sys.get_poll_many_cmd(job-id-list) => list
    * Return a list containing the shell command to poll the jobs in the
      argument list.

batch_sys.get_vacation_signal(job_conf) => str
    * If relevant, return a string containing the name of the signal that
      indicates the job has been vacated by the batch system.

batch_sys.submit(job_file_path) => ret_code, out, err
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

batch_sys.SUBMIT_CMD_STDIN_IS_JOB_FILE
    * A boolean - iff True, use the contents of the job_file_path as stdin to
      the submit command.
      See also "batch_sys.job_submit", "batch_sys.SUBMIT_CMD", and
      "batch_sys.SUBMIT_CMD_STDIN_TMPL".

"""

import os
import shlex
from signal import SIGKILL
import stat
from subprocess import call, Popen, PIPE
import sys
import traceback
from cylc.mkdir_p import mkdir_p
from cylc.task_id import TaskID
from cylc.task_message import TaskMessage
from cylc.wallclock import get_current_time_string


class JobPollContext(object):
    """Context object for a job poll.

    0 ctx.job_log_dir -- cycle/task/submit_num
    1 ctx.batch_sys_name -- batch system name
    2 ctx.batch_sys_job_id -- job ID in batch system
    3 ctx.batch_sys_exit_polled -- 0 for false, 1 for true
    4 ctx.run_status -- 0 for success, 1 for failure
    5 ctx.run_signal -- signal received on run failure
    6 ctx.time_submit_exit -- submit (exit) time
    7 ctx.time_run -- run start time
    8 ctx.time_run_exit -- run exit time

    """

    def __init__(self, job_log_dir):
        self.job_log_dir = job_log_dir
        self.batch_sys_name = None
        self.batch_sys_job_id = None
        self.batch_sys_exit_polled = None
        self.run_status = None
        self.run_signal = None
        self.time_submit_exit = None
        self.time_run = None
        self.time_run_exit = None
        self.messages = []

    def get_summary_str(self):
        """Return the poll context as a summary string delimited by "|"."""
        items = []
        for item in [
                self.job_log_dir,
                self.batch_sys_name,
                self.batch_sys_job_id,
                self.batch_sys_exit_polled,
                self.run_status,
                self.run_signal,
                self.time_submit_exit,
                self.time_run,
                self.time_run_exit]:
            if item is None:
                items.append("")
            else:
                items.append(str(item))
        return "|".join(items)


class BatchSysManager(object):
    """Job submission, poll and kill.

    Manage the importing of job submission method modules.

    """

    CYLC_BATCH_SYS_NAME = "CYLC_BATCH_SYS_NAME"
    CYLC_BATCH_SYS_JOB_ID = "CYLC_BATCH_SYS_JOB_ID"
    CYLC_BATCH_SYS_JOB_SUBMIT_TIME = "CYLC_BATCH_SYS_JOB_SUBMIT_TIME"
    CYLC_BATCH_SYS_EXIT_POLLED = "CYLC_BATCH_SYS_EXIT_POLLED"
    LINE_PREFIX_CYLC_DIR = "export CYLC_DIR="
    LINE_PREFIX_BATCH_SYS_NAME = "# Job submit method: "
    LINE_PREFIX_BATCH_SUBMIT_CMD_TMPL = "# Job submit command template: "
    LINE_PREFIX_EOF = "#EOF: "
    LINE_PREFIX_JOB_LOG_DIR = "# Job log directory: "
    LINE_UPDATE_CYLC_DIR = (
        "# N.B. CYLC_DIR has been updated on the remote host\n")
    OUT_PREFIX_COMMAND = "[TASK JOB COMMAND]"
    OUT_PREFIX_MESSAGE = "[TASK JOB MESSAGE]"
    OUT_PREFIX_SUMMARY = "[TASK JOB SUMMARY]"
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

    def jobs_kill(self, job_log_root, job_log_dirs):
        """Kill multiple jobs.

        job_log_root -- The log/job/ sub-directory of the suite.
        job_log_dirs -- A list containing point/name/submit_num for task jobs.

        """
        # Note: The more efficient way to do this is to group the jobs by their
        # batch systems, and call the kill command for each batch system once.
        # However, this will make it more difficult to determine if the kill
        # command for a particular job is successful or not.
        if "$" in job_log_root:
            job_log_root = os.path.expandvars(job_log_root)
        self.configure_suite_run_dir(job_log_root.rsplit(os.sep, 2)[0])
        now = get_current_time_string()
        for job_log_dir in job_log_dirs:
            ret_code, err = self.job_kill(
                os.path.join(job_log_root, job_log_dir, "job.status"))
            sys.stdout.write("%s%s|%s|%d\n" % (
                self.OUT_PREFIX_SUMMARY, now, job_log_dir, ret_code))
            # Note: Print STDERR to STDOUT may look a bit strange, but it
            # requires less logic for the suite to parse the output.
            if err.strip():
                for line in err.splitlines(True):
                    if not line.endswith("\n"):
                        line += "\n"
                    sys.stdout.write("%s%s|%s|%s" % (
                        self.OUT_PREFIX_CMD_ERR, now, job_log_dir, line))

    def jobs_poll(self, job_log_root, job_log_dirs):
        """Poll multiple jobs.

        job_log_root -- The log/job/ sub-directory of the suite.
        job_log_dirs -- A list containing point/name/submit_num for task jobs.

        """
        if "$" in job_log_root:
            job_log_root = os.path.expandvars(job_log_root)
        self.configure_suite_run_dir(job_log_root.rsplit(os.sep, 2)[0])

        ctx_list = []  # Contexts for all relevant jobs
        ctx_list_by_batch_sys = {}  # {batch_sys_name1: [ctx1, ...], ...}

        for job_log_dir in job_log_dirs:
            ctx = self._jobs_poll_status_files(job_log_root, job_log_dir)
            if ctx is None:
                continue
            ctx_list.append(ctx)

            if not ctx.batch_sys_name or not ctx.batch_sys_job_id:
                sys.stderr.write(
                    "%s/job.status: incomplete batch system info\n" % (
                        ctx.job_log_dir))
                continue

            # We can trust:
            # * Jobs previously polled to have exited the batch system.
            # * Jobs succeeded or failed with ERR/EXIT.
            if (ctx.batch_sys_exit_polled or ctx.run_status == 0 or
                    ctx.run_signal in ["ERR", "EXIT"]):
                continue

            if ctx.batch_sys_name not in ctx_list_by_batch_sys:
                ctx_list_by_batch_sys[ctx.batch_sys_name] = []
            ctx_list_by_batch_sys[ctx.batch_sys_name].append(ctx)

        for batch_sys_name, my_ctx_list in ctx_list_by_batch_sys.items():
            self._jobs_poll_batch_sys(
                job_log_root, batch_sys_name, my_ctx_list)

        cur_time_str = get_current_time_string()
        for ctx in ctx_list:
            for message in ctx.messages:
                sys.stdout.write("%s%s|%s|%s\n" % (
                    self.OUT_PREFIX_MESSAGE,
                    cur_time_str,
                    ctx.job_log_dir,
                    message))
            sys.stdout.write("%s%s|%s\n" % (
                self.OUT_PREFIX_SUMMARY,
                cur_time_str,
                ctx.get_summary_str()))

    def jobs_submit(self, job_log_root, job_log_dirs, remote_mode=False):
        """Submit multiple jobs.

        job_log_root -- The log/job/ sub-directory of the suite.
        job_log_dirs -- A list containing point/name/submit_num for task jobs.

        """
        if "$" in job_log_root:
            job_log_root = os.path.expandvars(job_log_root)
        self.configure_suite_run_dir(job_log_root.rsplit(os.sep, 2)[0])

        if remote_mode:
            items = self._jobs_submit_prep_by_stdin(job_log_root, job_log_dirs)
        else:
            items = self._jobs_submit_prep_by_args(job_log_root, job_log_dirs)
        now = get_current_time_string()
        for job_log_dir, batch_sys_name, batch_submit_cmd_tmpl in items:
            job_file_path = os.path.join(job_log_root, job_log_dir, "job")
            if not batch_sys_name:
                sys.stdout.write("%s%s|%s|1|\n" % (
                    self.OUT_PREFIX_SUMMARY, now, job_log_dir))
                continue
            ret_code, out, err, job_id = self._job_submit_impl(
                job_file_path, batch_sys_name, batch_submit_cmd_tmpl)
            sys.stdout.write("%s%s|%s|%d|%s\n" % (
                self.OUT_PREFIX_SUMMARY, now, job_log_dir, ret_code, job_id))
            for key, value in [("STDERR", err), ("STDOUT", out)]:
                if value is None or not value.strip():
                    continue
                for line in value.splitlines(True):
                    if not value.endswith("\n"):
                        value += "\n"
                    sys.stdout.write("%s%s|%s|[%s] %s" % (
                        self.OUT_PREFIX_COMMAND, now, job_log_dir, key, line))

    def job_kill(self, st_file_path):
        """Ask batch system to terminate the job specified in "st_file_path".

        Return 0 on success, non-zero integer on failure.

        """
        # SUITE_RUN_DIR/log/job/CYCLE/TASK/SUBMIT/job.status
        self.configure_suite_run_dir(st_file_path.rsplit(os.sep, 6)[0])
        st_file = open(st_file_path)
        for line in st_file:
            if line.startswith(self.CYLC_BATCH_SYS_NAME + "="):
                batch_sys = self.get_inst(line.strip().split("=", 1)[1])
                break
        else:
            return (1, "Cannot determine batch system from 'job.status' file")
        st_file.seek(0, 0)  # rewind
        if getattr(batch_sys, "CAN_KILL_PROC_GROUP", False):
            for line in st_file:
                if line.startswith("CYLC_JOB_PID="):
                    pid = line.strip().split("=", 1)[1]
                    try:
                        os.killpg(int(pid), SIGKILL)
                    except OSError as exc:
                        traceback.print_exc()
                        return (1, str(exc))
                    else:
                        return (0, "")
        st_file.seek(0, 0)  # rewind
        if hasattr(batch_sys, "KILL_CMD_TMPL"):
            for line in st_file:
                if not line.startswith(self.CYLC_BATCH_SYS_JOB_ID + "="):
                    continue
                job_id = line.strip().split("=", 1)[1]
                command = shlex.split(
                    batch_sys.KILL_CMD_TMPL % {"job_id": job_id})
                try:
                    proc = Popen(command, stderr=PIPE)
                except OSError as exc:
                    # subprocess.Popen has a bad habit of not setting the
                    # filename of the executable when it raises an OSError.
                    if not exc.filename:
                        exc.filename = command[0]
                    traceback.print_exc()
                    return (1, str(exc))
                else:
                    return (proc.wait(), proc.communicate()[1])
        return (1, "Cannot determine batch job ID from 'job.status' file")

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
        command = shlex.split(batch_sys.POLL_CMD_TMPL % {"job_id": job_id})
        try:
            proc = Popen(command, stdout=PIPE)
        except OSError as exc:
            # subprocess.Popen has a bad habit of not setting the filename of
            # the executable when it raises an OSError.
            if not exc.filename:
                exc.filename = command[0]
            raise
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
        if "$" in job_file_path:
            job_file_path = os.path.expandvars(job_file_path)
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

        return self._job_submit_impl(
            job_file_path, batch_sys_name, batch_submit_cmd_tmpl)

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

    def _filter_submit_output(self, st_file_path, batch_sys, out, err):
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
                    job_status_file = open(st_file_path, "a")
                    job_status_file.write("%s=%s\n" % (
                        self.CYLC_BATCH_SYS_JOB_ID, job_id))
                    job_status_file.write("%s=%s\n" % (
                        self.CYLC_BATCH_SYS_JOB_SUBMIT_TIME,
                        get_current_time_string()))
                    job_status_file.close()
                    break
        if hasattr(batch_sys, "filter_submit_output"):
            out, err = batch_sys.filter_submit_output(out, err)
        return out, err, job_id

    def _jobs_poll_status_files(self, job_log_root, job_log_dir):
        """Helper 1 for self.jobs_poll(job_log_root, job_log_dirs)."""
        ctx = JobPollContext(job_log_dir)
        try:
            handle = open(os.path.join(
                job_log_root, ctx.job_log_dir, "job.status"))
        except IOError as exc:
            sys.stderr.write(str(exc) + "\n")
            return
        for line in handle:
            if "=" not in line:
                continue
            key, value = line.strip().split("=", 1)
            if key == self.CYLC_BATCH_SYS_NAME:
                ctx.batch_sys_name = value
            elif key == self.CYLC_BATCH_SYS_JOB_ID:
                ctx.batch_sys_job_id = value
            elif key == self.CYLC_BATCH_SYS_EXIT_POLLED:
                ctx.batch_sys_exit_polled = 1
            elif key == self.CYLC_BATCH_SYS_JOB_SUBMIT_TIME:
                ctx.time_submit_exit = value
            elif key == TaskMessage.CYLC_JOB_INIT_TIME:
                ctx.time_run = value
            elif key == TaskMessage.CYLC_JOB_EXIT_TIME:
                ctx.time_run_exit = value
            elif key == TaskMessage.CYLC_JOB_EXIT:
                if value == TaskMessage.SUCCEEDED.upper():
                    ctx.run_status = 0
                else:
                    ctx.run_status = 1
                    ctx.run_signal = value
            elif key == TaskMessage.CYLC_MESSAGE:
                ctx.messages.append(value)
        handle.close()

        return ctx

    def _jobs_poll_batch_sys(self, job_log_root, batch_sys_name, my_ctx_list):
        """Helper 2 for self.jobs_poll(job_log_root, job_log_dirs)."""
        batch_sys = self.get_inst(batch_sys_name)
        all_job_ids = [ctx.batch_sys_job_id for ctx in my_ctx_list]
        if hasattr(batch_sys, "get_poll_many_cmd"):
            # Some poll commands may not be as simple
            cmd = batch_sys.get_poll_many_cmd(all_job_ids)
        else:  # if hasattr(batch_sys, "POLL_CMD"):
            # Simple poll command that takes a list of job IDs
            cmd = [batch_sys.POLL_CMD] + all_job_ids
        try:
            proc = Popen(cmd, stderr=PIPE, stdout=PIPE)
        except OSError as exc:
            # subprocess.Popen has a bad habit of not setting the
            # filename of the executable when it raises an OSError.
            if not exc.filename:
                exc.filename = cmd[0]
            sys.stderr.write(str(exc) + "\n")
            return
        proc.wait()
        out, err = proc.communicate()
        sys.stderr.write(err)
        if hasattr(batch_sys, "filter_poll_many_output"):
            # Allow custom filter
            job_ids = batch_sys.filter_poll_many_output(out)
        else:
            # Just about all poll commands return a table, with column 1
            # being the job ID. The logic here should be sufficient to
            # ensure that any table header is ignored.
            job_ids = []
            for line in out.splitlines():
                head = line.split(None, 1)[0]
                if head in all_job_ids:
                    job_ids.append(head)
        for ctx in my_ctx_list:
            ctx.batch_sys_exit_polled = int(
                ctx.batch_sys_job_id not in job_ids)
            # Add information to "job.status"
            if ctx.batch_sys_exit_polled:
                try:
                    handle = open(os.path.join(
                        job_log_root, ctx.job_log_dir, "job.status"), "a")
                    handle.write("%s=%s\n" % (
                        self.CYLC_BATCH_SYS_EXIT_POLLED,
                        get_current_time_string()))
                    handle.close()
                except IOError as exc:
                    sys.stderr.write(str(exc) + "\n")

    def _job_submit_impl(
            self, job_file_path, batch_sys_name, batch_submit_cmd_tmpl):
        """Helper for self.jobs_submit() and self.job_submit()."""

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
        if getattr(batch_sys, "SUBMIT_CMD_STDIN_IS_JOB_FILE", False):
            proc_stdin_arg = open(job_file_path)
        elif hasattr(batch_sys, "SUBMIT_CMD_STDIN_TMPL"):
            proc_stdin_value = batch_sys.SUBMIT_CMD_STDIN_TMPL % {
                "job": job_file_path}
            proc_stdin_arg = PIPE
        if hasattr(batch_sys, "submit"):
            # batch_sys.submit should handle OSError, if relevant.
            ret_code, out, err = batch_sys.submit(job_file_path)
        else:
            if batch_submit_cmd_tmpl:
                # No need to catch OSError when using shell. It is unlikely
                # that we do not have a shell, and still manage to get as far
                # as here.
                batch_sys_cmd = batch_submit_cmd_tmpl % {"job": job_file_path}
                proc = Popen(
                    batch_sys_cmd,
                    stdin=proc_stdin_arg, stdout=PIPE, stderr=PIPE, shell=True)
            else:
                command = shlex.split(
                    batch_sys.SUBMIT_CMD_TMPL % {"job": job_file_path})
                try:
                    proc = Popen(
                        command, stdin=proc_stdin_arg, stdout=PIPE, stderr=PIPE)
                except OSError as exc:
                    # subprocess.Popen has a bad habit of not setting the
                    # filename of the executable when it raises an OSError.
                    if not exc.filename:
                        exc.filename = command[0]
                    return 1, "", str(exc), ""
            out, err = proc.communicate(proc_stdin_value)
            ret_code = proc.wait()

        # Filter submit command output, if relevant
        # Get job ID, if possible
        job_id = None
        if out or err:
            try:
                out, err, job_id = self._filter_submit_output(
                    job_file_path + ".status", batch_sys, out, err)
            except OSError:
                ret_code = 1
                self.job_kill(job_file_path + ".status")

        return ret_code, out, err, job_id

    def _jobs_submit_prep_by_args(self, job_log_root, job_log_dirs):
        """Prepare job files for submit by reading files in arguments.

        Job files are specified in the arguments in local mode. Extract job
        submission methods and job submission command templates from each job
        file.

        Return a list, where each element contains something like:
        (job_log_dir, batch_sys_name, batch_submit_cmd_tmpl)

        """
        items = []
        for job_log_dir in job_log_dirs:
            job_file_path = os.path.join(job_log_root, job_log_dir, "job")
            batch_sys_name = None
            batch_submit_cmd_tmpl = None
            for line in open(job_file_path):
                if line.startswith(self.LINE_PREFIX_BATCH_SYS_NAME):
                    batch_sys_name = line.replace(
                        self.LINE_PREFIX_BATCH_SYS_NAME, "").strip()
                elif line.startswith(self.LINE_PREFIX_BATCH_SUBMIT_CMD_TMPL):
                    batch_submit_cmd_tmpl = line.replace(
                        self.LINE_PREFIX_BATCH_SUBMIT_CMD_TMPL, "").strip()
            items.append((job_log_dir, batch_sys_name, batch_submit_cmd_tmpl))
        return items

    def _jobs_submit_prep_by_stdin(self, job_log_root, job_log_dirs):
        """Prepare job files for submit by reading from STDIN.

        Job files are uploaded via STDIN in remote mode. Modify job
        files' CYLC_DIR for this host. Extract job submission methods
        and job submission command templates from each job file.

        Return a list, where each element contains something like:
        (job_log_dir, batch_sys_name, batch_submit_cmd_tmpl)

        """
        items = [[job_log_dir, None, None] for job_log_dir in job_log_dirs]
        items_map = {}
        for item in items:
            items_map[item[0]] = item
        handle = None
        batch_sys_name = None
        batch_submit_cmd_tmpl = None
        job_log_dir = None
        lines = []
        # Get job files from STDIN.
        # Modify CYLC_DIR in job file, if necessary.
        # Get batch system name and batch submit command template from each job
        # file.
        # Write job file in correct location.
        while True:  # Note: "for cur_line in sys.stdin:" may hang
            cur_line = sys.stdin.readline()
            if not cur_line:
                if handle is not None:
                    handle.close()
                break

            if cur_line.startswith(self.LINE_PREFIX_CYLC_DIR):
                old_line = cur_line
                cur_line = (
                    cur_line[0:cur_line.find(self.LINE_PREFIX_CYLC_DIR)] +
                    self.LINE_PREFIX_CYLC_DIR +
                    "'%s'\n" % os.environ["CYLC_DIR"])
                if old_line != cur_line:
                    lines.append(self.LINE_UPDATE_CYLC_DIR)
            elif cur_line.startswith(self.LINE_PREFIX_BATCH_SYS_NAME):
                batch_sys_name = cur_line.replace(
                    self.LINE_PREFIX_BATCH_SYS_NAME, "").strip()
            elif cur_line.startswith(self.LINE_PREFIX_BATCH_SUBMIT_CMD_TMPL):
                batch_submit_cmd_tmpl = cur_line.replace(
                    self.LINE_PREFIX_BATCH_SUBMIT_CMD_TMPL, "").strip()
            elif cur_line.startswith(self.LINE_PREFIX_JOB_LOG_DIR):
                job_log_dir = cur_line.replace(
                    self.LINE_PREFIX_JOB_LOG_DIR, "").strip()
                mkdir_p(os.path.join(job_log_root, job_log_dir))
                handle = open(
                    os.path.join(job_log_root, job_log_dir, "job.tmp"), "wb")

            if handle is None:
                lines.append(cur_line)
            else:
                for line in lines + [cur_line]:
                    handle.write(line)
                lines = []
                if cur_line.startswith(self.LINE_PREFIX_EOF + job_log_dir):
                    handle.close()
                    # Make it executable
                    os.chmod(handle.name, (
                        os.stat(handle.name).st_mode |
                        stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))
                    # Rename from "*/job.tmp" to "*/job"
                    os.rename(handle.name, handle.name[:-4])
                    try:
                        items_map[job_log_dir][1] = batch_sys_name
                        items_map[job_log_dir][2] = batch_submit_cmd_tmpl
                    except KeyError:
                        pass
                    handle = None
                    job_log_dir = None
                    batch_sys_name = None
                    batch_submit_cmd_tmpl = None
        return items

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
