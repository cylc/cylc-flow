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

"""Manage submission, poll and kill of a job to the batch systems.

Export the BatchSysManager class.

Batch system handler (a.k.a. job submission method) modules should be placed
under the "cylc.batch_sys_handlers" package. Each module should export the
symbol "BATCH_SYS_HANDLER" for the singleton instance that implements the job
system handler logic.

Each batch system handler class should instantiate with no argument, and may
have the following constants and methods:

batch_sys.filter_poll_many_output(out) => job_ids
    * Called after the batch system's poll many command. The method should read
      the output and return a list of job IDs that are still in the batch
      system.

batch_sys.filter_submit_output(out, err) => new_out, new_err
    * Filter the standard output and standard error of the job submission
      command. This is useful if the job submission command returns information
      that should just be ignored. See also "batch_sys.SUBMIT_CMD_TMPL".

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

batch_sys.manip_job_id(job_id) => job_id
    * Modify the job ID that is returned by the job submit command.

batch_sys.KILL_CMD_TMPL
    *  A Python string template for getting the batch system command to remove
       and terminate a job ID. The command is formed using the logic:
           batch_sys.KILL_CMD_TMPL % {"job_id": job_id}

batch_sys.POLL_CANT_CONNECT_ERR
    * A string containing an error message. If this is defined, when a poll
      command returns a non-zero return code and its STDERR contains this
      string, then the poll result will not be trusted, because it is assumed
      that the batch system is currently unavailable. Jobs submitted to the
      batch system will be assumed OK until we are able to connect to the batch
      system again.

batch_sys.SHOULD_KILL_PROC_GROUP
    * A boolean to indicate whether it is necessary to kill a job by sending
      a signal to its Unix process group. This boolean also indicates that
      a job submitted via this batch system will physically run on the same
      host it is submitted to.

batch_sys.SHOULD_POLL_PROC_GROUP
    * A boolean to indicate whether it is necessary to poll a job by its PID
      as well as the job ID.

batch_sys.REC_ID_FROM_SUBMIT_ERR
batch_sys.REC_ID_FROM_SUBMIT_OUT
    * A regular expression (compiled) to extract the job "id" from the standard
      output or standard error of the job submission command.

batch_sys.SUBMIT_CMD_ENV
    * A Python dict (or an iterable that can be used to update a dict)
      containing extra environment variables for getting the batch system
      command to submit a job file.

batch_sys.SUBMIT_CMD_TMPL
    * A Python string template for getting the batch system command to submit a
      job file. The command is formed using the logic:
          batch_sys.SUBMIT_CMD_TMPL % {"job": job_file_path}
      See also "batch_sys._job_submit_impl".

"""

import json
import os
import shlex
import stat
import sys
import traceback
from shutil import rmtree
from signal import SIGKILL

from cylc.task_message import (
    CYLC_JOB_PID, CYLC_JOB_INIT_TIME, CYLC_JOB_EXIT_TIME, CYLC_JOB_EXIT,
    CYLC_MESSAGE)
from cylc.cylc_subproc import procopen
from cylc.task_job_logs import (JOB_LOG_ERR, JOB_LOG_JOB, JOB_LOG_OUT,
                                JOB_LOG_STATUS)
from cylc.task_outputs import TASK_OUTPUT_SUCCEEDED
from cylc.wallclock import get_current_time_string
from parsec.OrderedDict import OrderedDict


class JobPollContext(object):
    """Context object for a job poll."""
    CONTEXT_ATTRIBUTES = (
        'job_log_dir',  # cycle/task/submit_num
        'batch_sys_name',  # batch system name
        'batch_sys_job_id',  # job id in batch system
        'batch_sys_exit_polled',  # 0 for false, 1 for true
        'run_status',  # 0 for success, 1 for failure
        'run_signal',  # signal received on run failure
        'time_submit_exit',  # submit (exit) time
        'time_run',  # run start time
        'time_run_exit',  # run exit time
        'batch_sys_call_no_lines',  # number of lines in batch sys call stdout
    )

    __slots__ = CONTEXT_ATTRIBUTES + (
        'pid',
        'messages'
    )

    def __init__(self, job_log_dir, **attrs):
        self.job_log_dir = job_log_dir
        self.batch_sys_name = None
        self.batch_sys_job_id = None
        self.batch_sys_exit_polled = None
        self.pid = None
        self.run_status = None
        self.run_signal = None
        self.time_submit_exit = None
        self.time_run = None
        self.time_run_exit = None
        self.batch_sys_call_no_lines = None
        self.messages = []

        if attrs:
            for key, value in attrs.items():
                if key in self.CONTEXT_ATTRIBUTES:
                    setattr(self, key, value)
                else:
                    raise ValueError('Invalid kwarg "%s"' % key)

    def get_summary_str(self):
        """Return the poll context as a summary string delimited by "|"."""
        ret = OrderedDict()
        for key in self.CONTEXT_ATTRIBUTES:
            value = getattr(self, key)
            if key == 'job_log_dir' or value is None:
                continue
            ret[key] = value
        return '%s|%s' % (self.job_log_dir, json.dumps(ret))


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
    LINE_PREFIX_EXECUTION_TIME_LIMIT = "# Execution time limit: "
    LINE_PREFIX_EOF = "#EOF: "
    LINE_PREFIX_JOB_LOG_DIR = "# Job log directory: "
    LINE_UPDATE_CYLC_DIR = (
        "# N.B. CYLC_DIR has been updated on the remote host\n")
    OUT_PREFIX_COMMAND = "[TASK JOB COMMAND]"
    OUT_PREFIX_MESSAGE = "[TASK JOB MESSAGE]"
    OUT_PREFIX_SUMMARY = "[TASK JOB SUMMARY]"
    OUT_PREFIX_CMD_ERR = "[TASK JOB ERROR]"
    _INSTANCES = {}

    @classmethod
    def configure_suite_run_dir(cls, suite_run_dir):
        """Add local python module paths if not already done."""
        for sub_dir in ["python", os.path.join("lib", "python")]:
            # TODO - eventually drop the deprecated "python" sub-dir.
            suite_py = os.path.join(suite_run_dir, sub_dir)
            if os.path.isdir(suite_py) and suite_py not in sys.path:
                sys.path.append(suite_py)

    def _get_sys(self, batch_sys_name):
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
        batch_sys = self._get_sys(job_conf['batch_system_name'])
        if hasattr(batch_sys, "format_directives"):
            return batch_sys.format_directives(job_conf)

    def get_fail_signals(self, job_conf):
        """Return a list of failure signal names to trap in the job file."""
        batch_sys = self._get_sys(job_conf['batch_system_name'])
        if hasattr(batch_sys, "get_fail_signals"):
            return batch_sys.get_fail_signals(job_conf)
        return ["EXIT", "ERR", "TERM", "XCPU"]

    def get_vacation_signal(self, job_conf):
        """Return the vacation signal name for a job file."""
        batch_sys = self._get_sys(job_conf['batch_system_name'])
        if hasattr(batch_sys, "get_vacation_signal"):
            return batch_sys.get_vacation_signal(job_conf)

    def is_job_local_to_host(self, batch_sys_name):
        """Return True if batch system runs jobs local to the submit host."""
        return getattr(
            self._get_sys(batch_sys_name), "SHOULD_KILL_PROC_GROUP", False)

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
                os.path.join(job_log_root, job_log_dir, JOB_LOG_STATUS))
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
                # Lost batch system information for some reason.
                # Mark the job as if it is no longer in the batch system.
                ctx.batch_sys_exit_polled = 1
                sys.stderr.write(
                    "%s/%s: incomplete batch system info\n" % (
                        ctx.job_log_dir, JOB_LOG_STATUS))

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

    def jobs_submit(self, job_log_root, job_log_dirs, remote_mode=False,
                    utc_mode=False):
        """Submit multiple jobs.

        job_log_root -- The log/job/ sub-directory of the suite.
        job_log_dirs -- A list containing point/name/submit_num for task jobs.
        remote_mode -- am I running on the remote job host?
        utc_mode -- is the suite running in UTC mode?

        """
        if "$" in job_log_root:
            job_log_root = os.path.expandvars(job_log_root)
        self.configure_suite_run_dir(job_log_root.rsplit(os.sep, 2)[0])

        if remote_mode:
            items = self._jobs_submit_prep_by_stdin(job_log_root, job_log_dirs)
        else:
            items = self._jobs_submit_prep_by_args(job_log_root, job_log_dirs)
        now = get_current_time_string(override_use_utc=utc_mode)
        for job_log_dir, batch_sys_name, submit_opts in items:
            job_file_path = os.path.join(
                job_log_root, job_log_dir, JOB_LOG_JOB)
            if not batch_sys_name:
                sys.stdout.write("%s%s|%s|1|\n" % (
                    self.OUT_PREFIX_SUMMARY, now, job_log_dir))
                continue
            ret_code, out, err, job_id = self._job_submit_impl(
                job_file_path, batch_sys_name, submit_opts)
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
        try:
            st_file = open(st_file_path)
            for line in st_file:
                if line.startswith(self.CYLC_BATCH_SYS_NAME + "="):
                    batch_sys = self._get_sys(line.strip().split("=", 1)[1])
                    break
            else:
                return (1,
                        "Cannot determine batch system from %s file" % (
                            JOB_LOG_STATUS))
            st_file.seek(0, 0)  # rewind
            if getattr(batch_sys, "SHOULD_KILL_PROC_GROUP", False):
                for line in st_file:
                    if line.startswith(CYLC_JOB_PID + "="):
                        pid = line.strip().split("=", 1)[1]
                        try:
                            os.killpg(os.getpgid(int(pid)), SIGKILL)
                        except (OSError, ValueError) as exc:
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
                        proc = procopen(command, stdin=open(os.devnull),
                                        stderrpipe=True)
                    except OSError as exc:
                        # subprocess.Popen has a bad habit of not setting the
                        # filename of the executable when it raises an OSError.
                        if not exc.filename:
                            exc.filename = command[0]
                        traceback.print_exc()
                        return (1, str(exc))
                    else:
                        return (proc.wait(), proc.communicate()[1].decode())
            return (1, "Cannot determine batch job ID from %s file" % (
                       JOB_LOG_STATUS))
        except IOError as exc:
            return (1, str(exc))

    @classmethod
    def _create_nn(cls, job_file_path):
        """Create NN symbolic link, if necessary.

        If NN => 01, remove numbered directories with submit numbers greater
        than 01.
        Helper for "self._job_submit_impl".

        """
        job_file_dir = os.path.dirname(job_file_path)
        source = os.path.basename(job_file_dir)
        task_log_dir = os.path.dirname(job_file_dir)
        nn_path = os.path.join(task_log_dir, "NN")
        try:
            old_source = os.readlink(nn_path)
        except OSError:
            old_source = None
        if old_source is not None and old_source != source:
            os.unlink(nn_path)
            old_source = None
        if old_source is None:
            os.symlink(source, nn_path)
        # On submit 1, remove any left over digit directories from prev runs
        if source == "01":
            for name in os.listdir(task_log_dir):
                if name != source and name.isdigit():
                    # Ignore errors, not disastrous if rmtree fails
                    rmtree(
                        os.path.join(task_log_dir, name), ignore_errors=True)

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
                    if hasattr(batch_sys, "manip_job_id"):
                        job_id = batch_sys.manip_job_id(job_id)
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
                job_log_root, ctx.job_log_dir, JOB_LOG_STATUS))
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
            elif key == CYLC_JOB_PID:
                ctx.pid = value
            elif key == self.CYLC_BATCH_SYS_JOB_SUBMIT_TIME:
                ctx.time_submit_exit = value
            elif key == CYLC_JOB_INIT_TIME:
                ctx.time_run = value
            elif key == CYLC_JOB_EXIT_TIME:
                ctx.time_run_exit = value
            elif key == CYLC_JOB_EXIT:
                if value == TASK_OUTPUT_SUCCEEDED.upper():
                    ctx.run_status = 0
                else:
                    ctx.run_status = 1
                    ctx.run_signal = value
            elif key == CYLC_MESSAGE:
                ctx.messages.append(value)
        handle.close()

        return ctx

    def _jobs_poll_batch_sys(self, job_log_root, batch_sys_name, my_ctx_list):
        """Helper 2 for self.jobs_poll(job_log_root, job_log_dirs)."""
        exp_job_ids = [ctx.batch_sys_job_id for ctx in my_ctx_list]
        bad_job_ids = list(exp_job_ids)
        exp_pids = []
        bad_pids = []
        items = [[self._get_sys(batch_sys_name), exp_job_ids, bad_job_ids]]
        if getattr(items[0][0], "SHOULD_POLL_PROC_GROUP", False):
            exp_pids = [ctx.pid for ctx in my_ctx_list if ctx.pid is not None]
            bad_pids.extend(exp_pids)
            items.append([self._get_sys("background"), exp_pids, bad_pids])
        debug_messages = []
        for batch_sys, exp_ids, bad_ids in items:
            if hasattr(batch_sys, "get_poll_many_cmd"):
                # Some poll commands may not be as simple
                cmd = batch_sys.get_poll_many_cmd(exp_ids)
            else:  # if hasattr(batch_sys, "POLL_CMD"):
                # Simple poll command that takes a list of job IDs
                cmd = [batch_sys.POLL_CMD] + exp_ids
            try:
                proc = procopen(cmd, stdin=open(os.devnull),
                                stderrpipe=True, stdoutpipe=True)
            except OSError as exc:
                # subprocess.Popen has a bad habit of not setting the
                # filename of the executable when it raises an OSError.
                if not exc.filename:
                    exc.filename = cmd[0]
                sys.stderr.write(str(exc) + "\n")
                return
            ret_code = proc.wait()
            out, err = (f.decode() for f in proc.communicate())
            debug_messages.append('%s - %s' % (
                batch_sys, len(out.split('\n'))))
            sys.stderr.write(err)
            if (ret_code and hasattr(batch_sys, "POLL_CANT_CONNECT_ERR") and
                    batch_sys.POLL_CANT_CONNECT_ERR in err):
                # Poll command failed because it cannot connect to batch system
                # Assume jobs are still healthy until the batch system is back.
                bad_ids[:] = []
            elif hasattr(batch_sys, "filter_poll_many_output"):
                # Allow custom filter
                for id_ in batch_sys.filter_poll_many_output(out):
                    try:
                        bad_ids.remove(id_)
                    except ValueError:
                        pass
            else:
                # Just about all poll commands return a table, with column 1
                # being the job ID. The logic here should be sufficient to
                # ensure that any table header is ignored.
                for line in out.splitlines():
                    try:
                        head = line.split(None, 1)[0]
                    except IndexError:
                        continue
                    if head in exp_ids:
                        try:
                            bad_ids.remove(head)
                        except ValueError:
                            pass

        debug_flag = False
        for ctx in my_ctx_list:
            ctx.batch_sys_exit_polled = int(
                ctx.batch_sys_job_id in bad_job_ids)
            # Exited batch system, but process still running
            # This can happen to jobs in some "at" implementation
            if ctx.batch_sys_exit_polled and ctx.pid in exp_pids:
                if ctx.pid not in bad_pids:
                    ctx.batch_sys_exit_polled = 0
                else:
                    debug_flag = True
            # Add information to "job.status"
            if ctx.batch_sys_exit_polled:
                try:
                    handle = open(os.path.join(
                        job_log_root, ctx.job_log_dir, JOB_LOG_STATUS), "a")
                    handle.write("%s=%s\n" % (
                        self.CYLC_BATCH_SYS_EXIT_POLLED,
                        get_current_time_string()))
                    handle.close()
                except IOError as exc:
                    sys.stderr.write(str(exc) + "\n")

        if debug_flag:
            ctx.batch_sys_call_no_lines = ', '.join(debug_messages)

    def _job_submit_impl(
            self, job_file_path, batch_sys_name, submit_opts):
        """Helper for self.jobs_submit() and self.job_submit()."""

        # Create NN symbolic link, if necessary
        self._create_nn(job_file_path)
        for name in JOB_LOG_ERR, JOB_LOG_OUT:
            try:
                os.unlink(os.path.join(job_file_path, name))
            except OSError:
                pass

        # Start new status file
        job_status_file = open(job_file_path + ".status", "w")
        job_status_file.write(
            "%s=%s\n" % (self.CYLC_BATCH_SYS_NAME, batch_sys_name))
        job_status_file.close()

        # Submit job
        batch_sys = self._get_sys(batch_sys_name)
        proc_stdin_arg = None
        proc_stdin_value = open(os.devnull)
        if hasattr(batch_sys, "get_submit_stdin"):
            proc_stdin_arg, proc_stdin_value = batch_sys.get_submit_stdin(
                job_file_path, submit_opts)
            if isinstance(proc_stdin_arg, str):
                proc_stdin_arg = proc_stdin_arg.encode()
            if isinstance(proc_stdin_value, str):
                proc_stdin_value = proc_stdin_value.encode()
        if hasattr(batch_sys, "submit"):
            # batch_sys.submit should handle OSError, if relevant.
            ret_code, out, err = batch_sys.submit(job_file_path, submit_opts)
        else:
            env = None
            if hasattr(batch_sys, "SUBMIT_CMD_ENV"):
                env = dict(os.environ)
                env.update(batch_sys.SUBMIT_CMD_ENV)
            batch_submit_cmd_tmpl = submit_opts.get("batch_submit_cmd_tmpl")
            if batch_submit_cmd_tmpl:
                # No need to catch OSError when using shell. It is unlikely
                # that we do not have a shell, and still manage to get as far
                # as here.
                batch_sys_cmd = batch_submit_cmd_tmpl % {"job": job_file_path}
                proc = procopen(batch_sys_cmd, stdin=proc_stdin_arg,
                                stdoutpipe=True, stderrpipe=True, usesh=True,
                                env=env)
                # calls to open a shell are aggregated in
                # cylc_subproc.procopen()
            else:
                command = shlex.split(
                    batch_sys.SUBMIT_CMD_TMPL % {"job": job_file_path})
                try:
                    proc = procopen(command, stdin=proc_stdin_arg,
                                    stdoutpipe=True, stderrpipe=True, env=env)
                except OSError as exc:
                    # subprocess.Popen has a bad habit of not setting the
                    # filename of the executable when it raises an OSError.
                    if not exc.filename:
                        exc.filename = command[0]
                    return 1, "", str(exc), ""
            out, err = (f.decode() for f in proc.communicate(proc_stdin_value))
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
        (job_log_dir, batch_sys_name, submit_opts)

        """
        items = []
        for job_log_dir in job_log_dirs:
            job_file_path = os.path.join(job_log_root, job_log_dir, "job")
            batch_sys_name = None
            submit_opts = {}
            for line in open(job_file_path):
                if line.startswith(self.LINE_PREFIX_BATCH_SYS_NAME):
                    batch_sys_name = line.replace(
                        self.LINE_PREFIX_BATCH_SYS_NAME, "").strip()
                elif line.startswith(self.LINE_PREFIX_BATCH_SUBMIT_CMD_TMPL):
                    submit_opts["batch_submit_cmd_tmpl"] = line.replace(
                        self.LINE_PREFIX_BATCH_SUBMIT_CMD_TMPL, "").strip()
                elif line.startswith(self.LINE_PREFIX_EXECUTION_TIME_LIMIT):
                    submit_opts["execution_time_limit"] = float(line.replace(
                        self.LINE_PREFIX_EXECUTION_TIME_LIMIT, "").strip())
            items.append((job_log_dir, batch_sys_name, submit_opts))
        return items

    def _jobs_submit_prep_by_stdin(self, job_log_root, job_log_dirs):
        """Prepare job files for submit by reading from STDIN.

        Job files are uploaded via STDIN in remote mode. Modify job
        files' CYLC_DIR for this host. Extract job submission methods
        and job submission command templates from each job file.

        Return a list, where each element contains something like:
        (job_log_dir, batch_sys_name, submit_opts)

        """
        items = [[job_log_dir, None, {}] for job_log_dir in job_log_dirs]
        items_map = {}
        for item in items:
            items_map[item[0]] = item
        handle = None
        batch_sys_name = None
        submit_opts = {}
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
                cur_line = "%s'%s'\n" % (
                    self.LINE_PREFIX_CYLC_DIR, os.environ["CYLC_DIR"])
                if old_line != cur_line:
                    lines.append(self.LINE_UPDATE_CYLC_DIR)
            elif cur_line.startswith(self.LINE_PREFIX_BATCH_SYS_NAME):
                batch_sys_name = cur_line.replace(
                    self.LINE_PREFIX_BATCH_SYS_NAME, "").strip()
            elif cur_line.startswith(self.LINE_PREFIX_BATCH_SUBMIT_CMD_TMPL):
                submit_opts["batch_submit_cmd_tmpl"] = cur_line.replace(
                    self.LINE_PREFIX_BATCH_SUBMIT_CMD_TMPL, "").strip()
            elif cur_line.startswith(self.LINE_PREFIX_EXECUTION_TIME_LIMIT):
                submit_opts["execution_time_limit"] = float(cur_line.replace(
                    self.LINE_PREFIX_EXECUTION_TIME_LIMIT, "").strip())
            elif cur_line.startswith(self.LINE_PREFIX_JOB_LOG_DIR):
                job_log_dir = cur_line.replace(
                    self.LINE_PREFIX_JOB_LOG_DIR, "").strip()
                os.makedirs(
                    os.path.join(job_log_root, job_log_dir),
                    exist_ok=True)
                handle = open(
                    os.path.join(job_log_root, job_log_dir, "job.tmp"), "wb")

            if handle is None:
                lines.append(cur_line)
            else:
                for line in lines + [cur_line]:
                    handle.write(line.encode())
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
                        items_map[job_log_dir][2] = submit_opts
                    except KeyError:
                        pass
                    handle = None
                    job_log_dir = None
                    batch_sys_name = None
                    submit_opts = {}
        return items
