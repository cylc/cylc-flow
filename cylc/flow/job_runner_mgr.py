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

"""Manage submission, poll and kill of a job to the job runners.

The job runner interface is documented in
cylc.flow.job_runner_handlers.documentation.

Please update this file as the interface changes.

"""

from contextlib import suppress
import json
import os
from pathlib import Path
import shlex
import stat
import sys
import traceback
from shutil import rmtree
from signal import SIGKILL
from subprocess import DEVNULL  # nosec

from cylc.flow.task_message import (
    CYLC_JOB_PID, CYLC_JOB_INIT_TIME, CYLC_JOB_EXIT_TIME, CYLC_JOB_EXIT,
    CYLC_MESSAGE)
from cylc.flow.cylc_subproc import procopen
from cylc.flow.task_job_logs import (
    JOB_LOG_ERR, JOB_LOG_JOB, JOB_LOG_OUT, JOB_LOG_STATUS)
from cylc.flow.task_outputs import TASK_OUTPUT_SUCCEEDED
from cylc.flow.wallclock import get_current_time_string
from cylc.flow.parsec.OrderedDict import OrderedDict


JOB_FILES_REMOVED_MESSAGE = 'ERR_JOB_FILES_REMOVED'


class JobPollContext():
    """Context object for a job poll."""
    CONTEXT_ATTRIBUTES = (
        'job_log_dir',  # cycle/task/submit_num
        'job_runner_name',
        'job_id',  # job id in job runner
        'job_runner_exit_polled',  # 0 for false, 1 for true
        'run_status',  # 0 for success, 1 for failure
        'run_signal',  # signal received on run failure
        'time_submit_exit',  # submit (exit) time
        'time_run',  # run start time
        'time_run_exit',  # run exit time
        'job_runner_call_no_lines',  # line count in job runner call stdout
    )

    __slots__ = CONTEXT_ATTRIBUTES + (
        'pid',
        'messages'
    )

    def __init__(self, job_log_dir, **attrs):
        self.job_log_dir = job_log_dir
        self.job_runner_name = None
        self.job_id = None
        self.job_runner_exit_polled = None
        self.pid = None
        self.run_status = None
        self.run_signal = None
        self.time_submit_exit = None
        self.time_run = None
        self.time_run_exit = None
        self.job_runner_call_no_lines = None
        self.messages = []

        if attrs:
            for key, value in attrs.items():
                if key not in self.CONTEXT_ATTRIBUTES:
                    raise ValueError('Invalid kwarg "%s"' % key)
                setattr(self, key, value)

    def update(self, other):
        """Update my data from given file context."""
        for i in self.__slots__:
            setattr(self, i, getattr(other, i))

    def get_summary_str(self):
        """Return the poll context as a summary string delimited by "|"."""
        ret = OrderedDict()
        for key in self.CONTEXT_ATTRIBUTES:
            value = getattr(self, key)
            if key == 'job_log_dir' or value is None:
                continue
            ret[key] = value
        return '%s|%s' % (self.job_log_dir, json.dumps(ret))


class JobRunnerManager():
    """Job submission, poll and kill.

    Manage the importing of job submission method modules.

    """

    CYLC_JOB_RUNNER_NAME = "CYLC_JOB_RUNNER_NAME"
    CYLC_JOB_ID = "CYLC_JOB_ID"
    CYLC_JOB_RUNNER_SUBMIT_TIME = "CYLC_JOB_RUNNER_SUBMIT_TIME"
    CYLC_JOB_RUNNER_EXIT_POLLED = "CYLC_JOB_RUNNER_EXIT_POLLED"
    FAIL_SIGNALS = ("EXIT", "ERR", "TERM", "XCPU")
    LINE_PREFIX_JOB_RUNNER_NAME = "# Job runner: "
    LINE_PREFIX_JOB_RUNNER_CMD_TMPL = "# Job runner command template: "
    LINE_PREFIX_EXECUTION_TIME_LIMIT = "# Execution time limit: "
    LINE_PREFIX_EOF = "#EOF: "
    LINE_PREFIX_JOB_LOG_DIR = "# Job log directory: "
    OUT_PREFIX_COMMAND = "[TASK JOB COMMAND]"
    OUT_PREFIX_MESSAGE = "[TASK JOB MESSAGE]"
    OUT_PREFIX_SUMMARY = "[TASK JOB SUMMARY]"
    OUT_PREFIX_CMD_ERR = "[TASK JOB ERROR]"
    _INSTANCES: dict = {}

    @classmethod
    def configure_workflow_run_dir(cls, workflow_run_dir):
        """Add local python module paths if not already done."""
        for sub_dir in ["python", os.path.join("lib", "python")]:
            # TODO - eventually drop the deprecated "python" sub-dir.
            workflow_py = os.path.join(workflow_run_dir, sub_dir)
            if os.path.isdir(workflow_py) and workflow_py not in sys.path:
                sys.path.append(workflow_py)

    def __init__(self, clean_env=False, env=None, path=None):
        """Initialise JobRunnerManager."""
        # Job submission environment.
        self.clean_env = clean_env
        self.path = path
        self.env = env

    def _get_sys(self, job_runner_name):
        """Return an instance of the class for "job_runner_name"."""
        if job_runner_name in self._INSTANCES:
            return self._INSTANCES[job_runner_name]
        for key in [f"cylc.flow.job_runner_handlers.{job_runner_name}",
                    job_runner_name]:

            try:
                mod_of_name = __import__(key, fromlist=[key])
                self._INSTANCES[job_runner_name] = getattr(
                    mod_of_name, "JOB_RUNNER_HANDLER", None)
                return self._INSTANCES[job_runner_name]
            except ImportError:
                if key == job_runner_name:
                    raise

    def format_directives(self, job_conf):
        """Format the job directives for a job file, if relevant."""
        job_runner = self._get_sys(job_conf['platform']['job runner'])
        if hasattr(job_runner, "format_directives"):
            job_conf = {
                # strip $HOME from the job file path
                # paths in directives should be interpreted relative to $HOME
                # https://github.com/cylc/cylc-flow/issues/4247
                **job_conf,
                'job_file_path': (
                    job_conf["job_file_path"].replace(r"$HOME/", "")
                )
            }
            return job_runner.format_directives(job_conf)

    def get_fail_signals(self, job_conf):
        """Return a list of failure signal names to trap in the job file."""
        job_runner = self._get_sys(job_conf['platform']['job runner'])
        return getattr(job_runner, "FAIL_SIGNALS", self.FAIL_SIGNALS)

    def get_vacation_signal(self, job_conf):
        """Return the vacation signal name for a job file."""
        job_runner = self._get_sys(job_conf['platform']['job runner'])
        if hasattr(job_runner, "get_vacation_signal"):
            return job_runner.get_vacation_signal(job_conf)

    def is_job_local_to_host(self, job_runner_name):
        """Return True if job runner runs jobs local to the submit host."""
        return getattr(
            self._get_sys(job_runner_name), "SHOULD_KILL_PROC_GROUP", False)

    def jobs_kill(self, job_log_root, job_log_dirs):
        """Kill multiple jobs.

        job_log_root -- The log/job/ sub-directory of the workflow.
        job_log_dirs -- A list containing point/name/submit_num for jobs.

        """
        # Note: The more efficient way to do this is to group the jobs by their
        # job runners, and call the kill command for each job runner once.
        # However, this will make it more difficult to determine if the kill
        # command for a particular job is successful or not.
        if "$" in job_log_root:
            job_log_root = os.path.expandvars(job_log_root)
        self.configure_workflow_run_dir(job_log_root.rsplit(os.sep, 2)[0])
        now = get_current_time_string()
        for job_log_dir in job_log_dirs:
            ret_code, err = self.job_kill(
                os.path.join(job_log_root, job_log_dir, JOB_LOG_STATUS))
            sys.stdout.write("%s%s|%s|%d\n" % (
                self.OUT_PREFIX_SUMMARY, now, job_log_dir, ret_code))
            # Note: Print STDERR to STDOUT may look a bit strange, but it
            # requires less logic for the workflow to parse the output.
            for line in err.strip().splitlines():
                sys.stdout.write(
                    f"{self.OUT_PREFIX_CMD_ERR}{now}|{job_log_dir}|{line}\n"
                )

    def jobs_poll(self, job_log_root, job_log_dirs):
        """Poll multiple jobs.

        job_log_root -- The log/job/ sub-directory of the workflow.
        job_log_dirs -- A list containing point/name/submit_num for jobs.

        """
        if "$" in job_log_root:
            job_log_root = os.path.expandvars(job_log_root)
        self.configure_workflow_run_dir(job_log_root.rsplit(os.sep, 2)[0])

        ctx_list = []  # Contexts for all relevant jobs
        ctx_list_by_job_runner = {}  # {job_runner_name1: [ctx1, ...], ...}

        for job_log_dir in job_log_dirs:
            ctx = self._jobs_poll_status_files(job_log_root, job_log_dir)
            if ctx is None:
                continue
            ctx_list.append(ctx)

            if not ctx.job_runner_name or not ctx.job_id:
                # Lost job runner information for some reason.
                # Mark the job as if it is no longer in the job runner.
                ctx.job_runner_exit_polled = 1
                sys.stderr.write(
                    "%s/%s: incomplete job runner info\n" % (
                        ctx.job_log_dir, JOB_LOG_STATUS))

            # We can trust:
            # * Jobs previously polled to have exited the job runner.
            # * Jobs succeeded or failed with ERR/EXIT.
            if (ctx.job_runner_exit_polled or ctx.run_status == 0 or
                    ctx.run_signal in ["ERR", "EXIT"]):
                continue

            if ctx.job_runner_name not in ctx_list_by_job_runner:
                ctx_list_by_job_runner[ctx.job_runner_name] = []
            ctx_list_by_job_runner[ctx.job_runner_name].append(ctx)

        for job_runner_name, my_ctx_list in ctx_list_by_job_runner.items():
            self._jobs_poll_runner(
                job_log_root, job_runner_name, my_ctx_list)

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

        job_log_root -- The log/job/ sub-directory of the workflow.
        job_log_dirs -- A list containing point/name/submit_num for jobs.
        remote_mode -- am I running on the remote job host?
        utc_mode -- is the workflow running in UTC mode?

        """
        if "$" in job_log_root:
            job_log_root = os.path.expandvars(job_log_root)
        self.configure_workflow_run_dir(job_log_root.rsplit(os.sep, 2)[0])
        if remote_mode:
            items = self._jobs_submit_prep_by_stdin(job_log_root, job_log_dirs)
        else:
            items = self._jobs_submit_prep_by_args(job_log_root, job_log_dirs)
        now = get_current_time_string(override_use_utc=utc_mode)
        for job_log_dir, job_runner_name, submit_opts in items:
            job_file_path = os.path.join(
                job_log_root, job_log_dir, JOB_LOG_JOB)
            if not job_runner_name:
                sys.stdout.write("%s%s|%s|1|\n" % (
                    self.OUT_PREFIX_SUMMARY, now, job_log_dir))
                continue
            ret_code, out, err, job_id = self._job_submit_impl(
                job_file_path, job_runner_name, submit_opts)
            sys.stdout.write("%s%s|%s|%d|%s\n" % (
                self.OUT_PREFIX_SUMMARY, now, job_log_dir, ret_code, job_id))
            for key, value in [("STDERR", err), ("STDOUT", out)]:
                if value is None:
                    continue
                for line in value.strip().splitlines():
                    sys.stdout.write(
                        f"{self.OUT_PREFIX_COMMAND}{now}"
                        f"|{job_log_dir}|[{key}] {line}\n"
                    )

    def job_kill(self, st_file_path):
        """Ask job runner to terminate the job specified in "st_file_path".

        Return 0 on success, non-zero integer on failure.

        """
        # WORKFLOW_RUN_DIR/log/job/CYCLE/TASK/SUBMIT/job.status
        self.configure_workflow_run_dir(st_file_path.rsplit(os.sep, 6)[0])
        try:
            with open(st_file_path) as st_file:
                for line in st_file:
                    if line.startswith(f"{self.CYLC_JOB_RUNNER_NAME}="):
                        job_runner = self._get_sys(
                            line.strip().split("=", 1)[1]
                        )
                        break
                else:
                    return (
                        1,
                        "Cannot determine job runner from "
                        f"{JOB_LOG_STATUS} file"
                    )
                st_file.seek(0, 0)  # rewind
                if getattr(job_runner, "SHOULD_KILL_PROC_GROUP", False):
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
                if hasattr(job_runner, "KILL_CMD_TMPL"):
                    for line in st_file:
                        if not line.startswith(f"{self.CYLC_JOB_ID}="):
                            continue
                        job_id = line.strip().split("=", 1)[1]
                        command = shlex.split(
                            job_runner.KILL_CMD_TMPL % {"job_id": job_id})
                        try:
                            proc = procopen(command, stdindevnull=True,
                                            stderrpipe=True)
                        except OSError as exc:
                            # subprocess.Popen has a bad habit of not setting
                            # the filename of the executable when it raises an
                            # OSError.
                            if not exc.filename:
                                exc.filename = command[0]
                            traceback.print_exc()
                            return (1, str(exc))
                        else:
                            return (
                                proc.wait(),
                                proc.communicate()[1].decode()
                            )
            return (1, f"Cannot determine job ID from {JOB_LOG_STATUS} file")
        except IOError as exc:
            return (1, str(exc))

    @classmethod
    def _create_nn(cls, job_file_path):
        """Create NN symbolic link if necessary, and remove any old job logs.

        If NN => 01, remove numbered dirs with submit numbers greater than 01.

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

        # Delete old job logs if necessary
        for name in JOB_LOG_ERR, JOB_LOG_OUT:
            with suppress(FileNotFoundError):
                os.unlink(os.path.join(job_file_dir, name))

    @classmethod
    def _filter_submit_output(cls, st_file_path, job_runner, out, err):
        """Filter submit command output, if relevant."""
        job_id = None
        if hasattr(job_runner, "REC_ID_FROM_SUBMIT_ERR"):
            text = err
            rec_id = job_runner.REC_ID_FROM_SUBMIT_ERR
        elif hasattr(job_runner, "REC_ID_FROM_SUBMIT_OUT"):
            text = out
            rec_id = job_runner.REC_ID_FROM_SUBMIT_OUT
        if rec_id:
            for line in str(text).splitlines():
                match = rec_id.match(line)
                if match:
                    job_id = match.group("id")
                    if hasattr(job_runner, "manip_job_id"):
                        job_id = job_runner.manip_job_id(job_id)
                    with open(st_file_path, "a") as job_status_file:
                        job_status_file.write("{0}={1}\n".format(
                            cls.CYLC_JOB_ID, job_id))
                        job_status_file.write("{0}={1}\n".format(
                            cls.CYLC_JOB_RUNNER_SUBMIT_TIME,
                            get_current_time_string()))
                    break
        if hasattr(job_runner, "filter_submit_output"):
            out, err = job_runner.filter_submit_output(out, err)
        return out, err, job_id

    def _jobs_poll_status_files(self, job_log_root, job_log_dir):
        """Helper 1 for self.jobs_poll(job_log_root, job_log_dirs)."""
        ctx = JobPollContext(job_log_dir)
        # If the log directory has been deleted prematurely, return a task
        # failure and an explanation:
        if not os.path.exists(os.path.join(job_log_root, ctx.job_log_dir)):
            ctx.run_status = 1
            ctx.run_signal = JOB_FILES_REMOVED_MESSAGE
            return ctx
        try:
            with open(
                os.path.join(job_log_root, ctx.job_log_dir, JOB_LOG_STATUS)
            ) as handle:
                for line in handle:
                    if "=" not in line:
                        continue
                    key, value = line.strip().split("=", 1)
                    if key == self.CYLC_JOB_RUNNER_NAME:
                        ctx.job_runner_name = value
                    elif key == self.CYLC_JOB_ID:
                        ctx.job_id = value
                    elif key == self.CYLC_JOB_RUNNER_EXIT_POLLED:
                        ctx.job_runner_exit_polled = 1
                    elif key == CYLC_JOB_PID:
                        ctx.pid = value
                    elif key == self.CYLC_JOB_RUNNER_SUBMIT_TIME:
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
        except IOError as exc:
            sys.stderr.write(f"{exc}\n")
            return

        return ctx

    def _jobs_poll_runner(self, job_log_root, job_runner_name, my_ctx_list):
        """Helper 2 for self.jobs_poll(job_log_root, job_log_dirs)."""
        exp_job_ids = [ctx.job_id for ctx in my_ctx_list]
        bad_job_ids = list(exp_job_ids)
        exp_pids = []
        bad_pids = []
        items = [[self._get_sys(job_runner_name), exp_job_ids, bad_job_ids]]
        if getattr(items[0][0], "SHOULD_POLL_PROC_GROUP", False):
            exp_pids = [ctx.pid for ctx in my_ctx_list if ctx.pid is not None]
            bad_pids.extend(exp_pids)
            items.append([self._get_sys("background"), exp_pids, bad_pids])
        debug_messages = []
        for job_runner, exp_ids, bad_ids in items:
            if hasattr(job_runner, "get_poll_many_cmd"):
                # Some poll commands may not be as simple
                cmd = job_runner.get_poll_many_cmd(exp_ids)
            else:  # if hasattr(job_runner, "POLL_CMD"):
                # Simple poll command that takes a list of job IDs
                cmd = [job_runner.POLL_CMD, *exp_ids]
            try:
                proc = procopen(cmd, stdindevnull=True,
                                stderrpipe=True, stdoutpipe=True)
            except OSError as exc:
                # subprocess.Popen has a bad habit of not setting the
                # filename of the executable when it raises an OSError.
                if not exc.filename:
                    exc.filename = cmd[0]
                sys.stderr.write(f"{exc}\n")
                return
            ret_code = proc.wait()
            out, err = (f.decode() for f in proc.communicate())
            debug_messages.append('{0} - {1}'.format(
                job_runner, len(out.split('\n')))
            )
            sys.stderr.write(err)
            if (ret_code and hasattr(job_runner, "POLL_CANT_CONNECT_ERR") and
                    job_runner.POLL_CANT_CONNECT_ERR in err):
                # Poll command failed because it cannot connect to job runner
                # Assume jobs are still healthy until the job runner is back.
                bad_ids[:] = []
            elif hasattr(job_runner, "filter_poll_many_output"):
                # Allow custom filter
                for id_ in job_runner.filter_poll_many_output(out):
                    with suppress(ValueError):
                        bad_ids.remove(id_)
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
                        with suppress(ValueError):
                            bad_ids.remove(head)

        debug_flag = False
        for ctx in my_ctx_list:
            ctx.job_runner_exit_polled = int(
                ctx.job_id in bad_job_ids)
            # Exited job runner, but process still running
            # This can happen to jobs in some "at" implementation
            if ctx.job_runner_exit_polled and ctx.pid in exp_pids:
                if ctx.pid not in bad_pids:
                    ctx.job_runner_exit_polled = 0
                else:
                    debug_flag = True
            # Add information to "job.status"
            if ctx.job_runner_exit_polled:
                try:
                    with open(os.path.join(
                        job_log_root, ctx.job_log_dir, JOB_LOG_STATUS), "a"
                    ) as handle:
                        handle.write("{0}={1}\n".format(
                            self.CYLC_JOB_RUNNER_EXIT_POLLED,
                            get_current_time_string())
                        )
                except IOError as exc:
                    sys.stderr.write(f"{exc}\n")

                # Re-read the status file in case the job started and exited
                # between the file and batch system checks, which would be
                # interpreted as submit-failed (job exited without starting).
                # Possible if polling many jobs and/or system heavily loaded.
                file_ctx = self._jobs_poll_status_files(
                    job_log_root, ctx.job_log_dir)
                ctx.update(file_ctx)

        if debug_flag:
            ctx.job_runner_call_no_lines = ', '.join(debug_messages)

    def _job_submit_impl(
            self, job_file_path, job_runner_name, submit_opts):
        """Helper for self.jobs_submit() and self.job_submit()."""

        # Create NN symbolic link, if necessary
        self._create_nn(job_file_path)

        # Start new status file
        with open(f"{job_file_path}.status", "w") as job_status_file:
            job_status_file.write(
                "{0}={1}\n".format(
                    self.CYLC_JOB_RUNNER_NAME,
                    job_runner_name
                )
            )

        # Submit job
        job_runner = self._get_sys(job_runner_name)
        if not self.clean_env:
            # Pass the whole environment to the job submit subprocess.
            # (Note this runs on the job host).
            env = os.environ
        else:
            # $HOME is required by job.sh on the job host.
            env = {'HOME': os.environ.get('HOME', '')}
        # Pass selected extra variables to the job submit subprocess.
        for var in self.env:
            env[var] = os.environ.get(var, '')
        if self.path is not None:
            # Append to avoid overriding an inherited PATH (e.g. in a venv)
            env['PATH'] = env.get('PATH', '') + ':' + ':'.join(self.path)
        if hasattr(job_runner, "submit"):
            submit_opts['env'] = env
            # job_runner.submit should handle OSError, if relevant.
            ret_code, out, err = job_runner.submit(job_file_path, submit_opts)
        else:
            proc_stdin_arg = None
            # Set command STDIN to DEVNULL by default to prevent leakage of
            # STDIN from current environment.
            proc_stdin_value = DEVNULL  # nosec
            if hasattr(job_runner, "get_submit_stdin"):
                proc_stdin_arg, proc_stdin_value = job_runner.get_submit_stdin(
                    job_file_path, submit_opts)
                if isinstance(proc_stdin_value, str):
                    proc_stdin_value = proc_stdin_value.encode()
            if hasattr(job_runner, "SUBMIT_CMD_ENV"):
                env.update(job_runner.SUBMIT_CMD_ENV)
            job_runner_cmd_tmpl = submit_opts.get("job_runner_cmd_tmpl")
            if job_runner_cmd_tmpl:
                # No need to catch OSError when using shell. It is unlikely
                # that we do not have a shell, and still manage to get as far
                # as here.
                job_runner_cmd = job_runner_cmd_tmpl % {"job": job_file_path}
                proc = procopen(job_runner_cmd, stdin=proc_stdin_arg,
                                stdoutpipe=True, stderrpipe=True, usesh=True,
                                env=env)
                # calls to open a shell are aggregated in
                # cylc_subproc.procopen()
            else:
                command = shlex.split(
                    job_runner.SUBMIT_CMD_TMPL % {"job": job_file_path})
                try:
                    proc = procopen(
                        command,
                        stdin=proc_stdin_arg,
                        stdoutpipe=True,
                        stderrpipe=True,
                        env=env,
                        # paths in directives should be interpreted relative to
                        # $HOME
                        # https://github.com/cylc/cylc-flow/issues/4247
                        cwd=Path('~').expanduser()
                    )
                except OSError as exc:
                    # subprocess.Popen has a bad habit of not setting the
                    # filename of the executable when it raises an OSError.
                    if not exc.filename:
                        exc.filename = command[0]
                    return 1, "", str(exc), ""
            out, err = (f.decode() for f in proc.communicate(proc_stdin_value))
            ret_code = proc.wait()
            with suppress(AttributeError, IOError):
                proc_stdin_arg.close()

        # Filter submit command output, if relevant
        # Get job ID, if possible
        job_id = None
        if out or err:
            try:
                out, err, job_id = self._filter_submit_output(
                    f"{job_file_path}.status", job_runner, out, err)
            except OSError:
                ret_code = 1
                self.job_kill(f"{job_file_path}.status")

        return ret_code, out, err, job_id

    def _jobs_submit_prep_by_args(self, job_log_root, job_log_dirs):
        """Prepare job files for submit by reading files in arguments.

        Job files are specified in the arguments in local mode. Extract job
        submission methods and job submission command templates from each job
        file.

        Return a list, where each element contains something like:
        (job_log_dir, job_runner_name, submit_opts)

        """
        items = []
        for job_log_dir in job_log_dirs:
            job_file_path = os.path.join(job_log_root, job_log_dir, "job")
            job_runner_name = None
            submit_opts = {}
            with open(job_file_path, 'r') as job_file:
                for line in job_file:
                    if line.startswith(self.LINE_PREFIX_JOB_RUNNER_NAME):
                        job_runner_name = line.replace(
                            self.LINE_PREFIX_JOB_RUNNER_NAME, "").strip()
                    elif line.startswith(self.LINE_PREFIX_JOB_RUNNER_CMD_TMPL):
                        submit_opts["job_runner_cmd_tmpl"] = line.replace(
                            self.LINE_PREFIX_JOB_RUNNER_CMD_TMPL, "").strip()
                    elif line.startswith(
                        self.LINE_PREFIX_EXECUTION_TIME_LIMIT
                    ):
                        submit_opts["execution_time_limit"] = float(
                            line.replace(
                                self.LINE_PREFIX_EXECUTION_TIME_LIMIT, ""
                            ).strip()
                        )
            items.append((job_log_dir, job_runner_name, submit_opts))
        return items

    def _jobs_submit_prep_by_stdin(self, job_log_root, job_log_dirs):
        """Prepare job files for submit by reading from STDIN.

        Job files are uploaded via STDIN in remote mode. Extract job submission
        methods and job submission command templates from each job file.

        Return a list, where each element contains something like:
        (job_log_dir, job_runner_name, submit_opts)

        """
        items = [[job_log_dir, None, {}] for job_log_dir in job_log_dirs]
        items_map = {}
        for item in items:
            items_map[item[0]] = item
        handle = None
        job_runner_name = None
        submit_opts = {}
        job_log_dir = None
        lines = []
        # Get job files from STDIN.
        # Get job runner name and job runner command template from each job
        # file.
        # Write job file in correct location.
        while True:  # Note: "for cur_line in sys.stdin:" may hang
            cur_line = sys.stdin.readline()
            if not cur_line:
                if handle is not None:
                    handle.close()
                break
            if cur_line.startswith(self.LINE_PREFIX_JOB_RUNNER_NAME):
                job_runner_name = cur_line.replace(
                    self.LINE_PREFIX_JOB_RUNNER_NAME, "").strip()
            elif cur_line.startswith(self.LINE_PREFIX_JOB_RUNNER_CMD_TMPL):
                submit_opts["job_runner_cmd_tmpl"] = cur_line.replace(
                    self.LINE_PREFIX_JOB_RUNNER_CMD_TMPL, "").strip()
            elif cur_line.startswith(self.LINE_PREFIX_EXECUTION_TIME_LIMIT):
                submit_opts["execution_time_limit"] = float(cur_line.replace(
                    self.LINE_PREFIX_EXECUTION_TIME_LIMIT, "").strip())
            elif cur_line.startswith(self.LINE_PREFIX_JOB_LOG_DIR):
                job_log_dir = cur_line.replace(
                    self.LINE_PREFIX_JOB_LOG_DIR, "").strip()
                os.makedirs(
                    os.path.join(job_log_root, job_log_dir),
                    exist_ok=True)
                if handle is not None:
                    handle.close()
                handle = open(  # noqa: SIM115 (can't convert to with open)
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
                        items_map[job_log_dir][1] = job_runner_name
                        items_map[job_log_dir][2] = submit_opts
                    except KeyError:
                        pass
                    handle = None
                    job_log_dir = None
                    job_runner_name = None
                    submit_opts = {}
        return items
