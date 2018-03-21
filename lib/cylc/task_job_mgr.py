#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA
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
"""Manage task jobs.

This module provides logic to:
* Set up the directory structure on remote job hosts.
  * Copy suite service files to remote job hosts for communication clients.
  * Clean up of service files on suite shutdown.
* Prepare task job files.
* Prepare task jobs submission, and manage the callbacks.
* Prepare task jobs poll/kill, and manage the callbacks.
"""

from logging import CRITICAL, INFO, WARNING
import os
from shutil import rmtree
from time import time
import traceback

from parsec.util import pdeepcopy, poverride

from cylc.batch_sys_manager import BatchSysManager
from cylc.cfgspec.glbl_cfg import glbl_cfg
from cylc.envvar import expandvars
import cylc.flags
from cylc.hostuserutil import is_remote_host, is_remote_user
from cylc.job_file import JobFileWriter
from cylc.mkdir_p import mkdir_p
from cylc.mp_pool import SuiteProcPool, SuiteProcContext
from cylc.suite_logging import LOG
from cylc.task_action_timer import TaskActionTimer
from cylc.task_events_mgr import TaskEventsManager
from cylc.task_message import TaskMessage
from cylc.task_outputs import (
    TASK_OUTPUT_SUBMITTED, TASK_OUTPUT_STARTED, TASK_OUTPUT_SUCCEEDED,
    TASK_OUTPUT_FAILED)
from cylc.task_remote_mgr import (
    REMOTE_INIT_FAILED, TaskRemoteMgmtError, TaskRemoteMgr)
from cylc.task_state import (
    TASK_STATUSES_ACTIVE, TASK_STATUS_READY, TASK_STATUS_SUBMITTED,
    TASK_STATUS_RUNNING, TASK_STATUS_SUCCEEDED, TASK_STATUS_FAILED,
    TASK_STATUS_SUBMIT_RETRYING, TASK_STATUS_RETRYING)
from cylc.wallclock import (
    get_current_time_string, get_seconds_as_interval_string)


class TaskJobManager(object):
    """Manage task job submit, poll and kill.

    This class provides logic to:
    * Submit task jobs.
    * Poll task jobs.
    * Kill task jobs.
    * Set up the directory structure on job hosts.
    * Install suite communicate client files on job hosts.
    * Remove suite contact files on job hosts.
    """

    JOB_FILE_BASE = BatchSysManager.JOB_FILE_BASE
    JOBS_KILL = 'jobs-kill'
    JOBS_POLL = 'jobs-poll'
    JOBS_SUBMIT = SuiteProcPool.JOBS_SUBMIT
    REMOTE_SELECT_MSG = 'waiting for remote host selection'
    REMOTE_INIT_MSG = 'remote host initialising'
    KEY_EXECUTE_TIME_LIMIT = 'execution_time_limit'

    def __init__(self, suite, proc_pool, suite_db_mgr, suite_srv_files_mgr):
        self.suite = suite
        self.proc_pool = proc_pool
        self.suite_db_mgr = suite_db_mgr
        self.task_events_mgr = TaskEventsManager(
            suite, proc_pool, suite_db_mgr)
        self.job_file_writer = JobFileWriter()
        self.suite_srv_files_mgr = suite_srv_files_mgr
        self.task_remote_mgr = TaskRemoteMgr(
            suite, proc_pool, suite_srv_files_mgr)

    def check_task_jobs(self, suite, task_pool):
        """Check submission and execution timeout and polling timers.

        Poll tasks that have timed out and/or have reached next polling time.
        """
        now = time()
        poll_tasks = set()
        for itask in task_pool.get_tasks():
            if (self._check_timeout(itask, now) or
                    self.task_events_mgr.set_poll_time(itask, now)):
                poll_tasks.add(itask)
        if poll_tasks:
            self.poll_task_jobs(suite, poll_tasks)

    def kill_task_jobs(self, suite, itasks):
        """Kill jobs of active tasks, and hold the tasks.

        If items is specified, kill active tasks matching given IDs.

        """
        active_itasks = []
        for itask in itasks:
            if itask.state.status in TASK_STATUSES_ACTIVE:
                itask.state.set_held()
                active_itasks.append(itask)
            else:
                LOG.warning('skipping %s: task not killable' % itask.identity)
        self._run_job_cmd(
            self.JOBS_KILL, suite, active_itasks,
            self._kill_task_jobs_callback)

    def poll_task_jobs(self, suite, itasks, poll_succ=True, msg=None):
        """Poll jobs of specified tasks.

        Any job that is or was submitted or running can be polled, except for
        retrying tasks - which would poll (correctly) as failed. And don't poll
        succeeded tasks by default.

        This method uses _poll_task_jobs_callback() and
        _manip_task_jobs_callback() as help/callback methods.

        _poll_task_job_callback() executes one specific job.
        """
        poll_me = []
        pollable = [TASK_STATUS_SUBMITTED, TASK_STATUS_RUNNING,
                    TASK_STATUS_FAILED]
        for itask in itasks:
            if itask.state.status in pollable or (
                    itask.state.status == TASK_STATUS_SUCCEEDED and poll_succ):
                poll_me.append(itask)
            else:
                LOG.debug("skipping %s: not pollable, "
                          "or skipping 'succeeded' tasks" % itask.identity)
        if poll_me:
            if msg is not None:
                LOG.info(msg)
            self._run_job_cmd(
                self.JOBS_POLL, suite, poll_me, self._poll_task_jobs_callback)

    def prep_submit_task_jobs(self, suite, itasks, dry_run=False,
                              check_syntax=True):
        """Prepare task jobs for submit.

        Prepare tasks where possible. Ignore tasks that are waiting for host
        select command to complete. Bad host select command or error writing to
        a job file will cause a bad task - leading to submission failure.

        Return [list, list]: list of good tasks, list of bad tasks
        """
        prepared_tasks = []
        bad_tasks = []
        for itask in itasks:
            prep_task = self._prep_submit_task_job(suite, itask, dry_run,
                                                   check_syntax=check_syntax)
            if prep_task:
                prepared_tasks.append(itask)
            elif prep_task is False:
                bad_tasks.append(itask)
        return [prepared_tasks, bad_tasks]

    def submit_task_jobs(self, suite, itasks, is_simulation=False):
        """Prepare and submit task jobs.

        Submit tasks where possible. Ignore tasks that are waiting for host
        select command to complete, or tasks that are waiting for remote
        initialisation. Bad host select command, error writing to a job file or
        bad remote initialisation will cause a bad task - leading to submission
        failure.

        This method uses prep_submit_task_job() as helper.

        Return (list): list of tasks that attempted submission
        """
        if is_simulation:
            return self._simulation_submit_task_jobs(itasks)

        # Prepare tasks for job submission
        prepared_tasks, bad_tasks = self.prep_submit_task_jobs(suite, itasks)

        # Reset consumed host selection results
        self.task_remote_mgr.remote_host_select_reset()

        if not prepared_tasks:
            return bad_tasks

        # Group task jobs by (host, owner)
        auth_itasks = {}  # {(host, owner): [itask, ...], ...}
        for itask in prepared_tasks:
            auth_itasks.setdefault((itask.task_host, itask.task_owner), [])
            auth_itasks[(itask.task_host, itask.task_owner)].append(itask)
        # Submit task jobs for each (host, owner) group
        done_tasks = bad_tasks
        for (host, owner), itasks in sorted(auth_itasks.items()):
            is_init = self.task_remote_mgr.remote_init(host, owner)
            if is_init is None:
                # Remote is waiting to be initialised
                for itask in itasks:
                    itask.summary['latest_message'] = self.REMOTE_INIT_MSG
                continue
            # Persist
            if owner:
                owner_at_host = owner + '@' + host
            else:
                owner_at_host = host
            now_str = get_current_time_string()
            done_tasks.extend(itasks)
            for itask in itasks:
                # Log and perist
                LOG.info(
                    'submit-num=%d, owner@host=%s' % (
                        itask.submit_num, owner_at_host),
                    itask=itask)
                self.suite_db_mgr.put_insert_task_jobs(itask, {
                    'is_manual_submit': itask.is_manual_submit,
                    'try_num': itask.get_try_num(),
                    'time_submit': now_str,
                    'user_at_host': owner_at_host,
                    'batch_sys_name': itask.summary['batch_sys_name'],
                })
                itask.is_manual_submit = False
            if is_init == REMOTE_INIT_FAILED:
                # Remote has failed to initialise
                # Set submit-failed for all affected tasks
                for itask in itasks:
                    itask.local_job_file_path = None  # reset for retry
                    self.task_events_mgr.log_task_job_activity(
                        SuiteProcContext(
                            self.JOBS_SUBMIT,
                            '(init %s)' % owner_at_host,
                            err=REMOTE_INIT_FAILED,
                            ret_code=1),
                        suite, itask.point, itask.tdef.name)
                    self.task_events_mgr.process_message(
                        itask, CRITICAL,
                        self.task_events_mgr.EVENT_SUBMIT_FAILED,
                        self.poll_task_jobs)
                continue
            # Build the "cylc jobs-submit" command
            cmd = ['cylc', self.JOBS_SUBMIT]
            if cylc.flags.debug:
                cmd.append('--debug')
            remote_mode = False
            kwargs = {}
            for key, value, test_func in [
                    ('host', host, is_remote_host),
                    ('user', owner, is_remote_user)]:
                if test_func(value):
                    cmd.append('--%s=%s' % (key, value))
                    remote_mode = True
                    kwargs[key] = value
            if remote_mode:
                cmd.append('--remote-mode')
            cmd.append('--')
            cmd.append(glbl_cfg().get_derived_host_item(
                suite, 'suite job log directory', host, owner))
            stdin_file_paths = []
            job_log_dirs = []
            for itask in sorted(itasks, key=lambda itask: itask.identity):
                if remote_mode:
                    stdin_file_paths.append(
                        self.task_events_mgr.get_task_job_log(
                            suite, itask.point, itask.tdef.name,
                            itask.submit_num, self.JOB_FILE_BASE))
                job_log_dirs.append(self.task_events_mgr.get_task_job_id(
                    itask.point, itask.tdef.name, itask.submit_num))
                # The job file is now (about to be) used: reset the file write
                # flag so that subsequent manual retrigger will generate a new
                # job file.
                itask.local_job_file_path = None
                itask.state.reset_state(TASK_STATUS_READY)
                if itask.state.outputs.has_custom_triggers():
                    self.suite_db_mgr.put_update_task_outputs(itask)
            cmd += job_log_dirs
            self.proc_pool.put_command(
                SuiteProcContext(
                    self.JOBS_SUBMIT,
                    cmd,
                    stdin_file_paths=stdin_file_paths,
                    job_log_dirs=job_log_dirs,
                    **kwargs
                ),
                self._submit_task_jobs_callback, [suite, itasks])
        return done_tasks

    def _check_timeout(self, itask, now):
        """Check/handle submission/execution timeouts."""
        if itask.state.status == TASK_STATUS_RUNNING:
            timer = itask.poll_timers.get(self.KEY_EXECUTE_TIME_LIMIT)
            if timer is not None:
                if not timer.is_timeout_set():
                    timer.next()
                if not timer.is_delay_done():
                    # Don't poll
                    return False
                if timer.next() is not None:
                    # Poll now, and more retries lined up
                    return True
                # No more retry lined up, can issue execution timeout event
        if itask.state.status in itask.timeout_timers:
            timeout = itask.timeout_timers[itask.state.status]
            if timeout is None or now <= timeout:
                return False
            itask.timeout_timers[itask.state.status] = None
            if (itask.state.status == TASK_STATUS_RUNNING and
                    itask.summary['started_time'] is not None):
                msg = 'job started %s ago, but has not finished' % (
                    get_seconds_as_interval_string(
                        timeout - itask.summary['started_time']))
                event = 'execution timeout'
            elif (itask.state.status == TASK_STATUS_SUBMITTED and
                    itask.summary['submitted_time'] is not None):
                msg = 'job submitted %s ago, but has not started' % (
                    get_seconds_as_interval_string(
                        timeout - itask.summary['submitted_time']))
                event = 'submission timeout'
            else:
                return False
            LOG.warning(msg, itask=itask)
            self.task_events_mgr.setup_event_handlers(itask, event, msg)
            return True

    def _create_job_log_path(self, suite, itask):
        """Create job log directory for a task job, etc.

        Create local job directory, and NN symbolic link.
        If NN => 01, remove numbered directories with submit numbers greater
        than 01.
        Return a string in the form "POINT/NAME/SUBMIT_NUM".

        """
        job_file_dir = self.task_events_mgr.get_task_job_log(
            suite, itask.point, itask.tdef.name, itask.submit_num)
        task_log_dir = os.path.dirname(job_file_dir)
        if itask.submit_num == 1:
            try:
                names = os.listdir(task_log_dir)
            except OSError:
                pass
            else:
                for name in names:
                    if name not in ["01", self.task_events_mgr.NN]:
                        rmtree(
                            os.path.join(task_log_dir, name),
                            ignore_errors=True)
        else:
            rmtree(job_file_dir, ignore_errors=True)

        mkdir_p(job_file_dir)
        target = os.path.join(task_log_dir, self.task_events_mgr.NN)
        source = os.path.basename(job_file_dir)
        try:
            prev_source = os.readlink(target)
        except OSError:
            prev_source = None
        if prev_source == source:
            return
        try:
            if prev_source:
                os.unlink(target)
            os.symlink(source, target)
        except OSError as exc:
            if not exc.filename:
                exc.filename = target
            raise exc

    @staticmethod
    def _get_job_scripts(itask, rtconfig):
        """Return pre-script, script, post-script for a job."""
        script = rtconfig['script']
        pre_script = rtconfig['pre-script']
        post_script = rtconfig['post-script']
        if itask.tdef.suite_polling_cfg:
            # Automatic suite state polling script
            comstr = "cylc suite-state " + \
                     " --task=" + itask.tdef.suite_polling_cfg['task'] + \
                     " --point=" + str(itask.point) + \
                     " --status=" + itask.tdef.suite_polling_cfg['status']
            if cylc.flags.debug:
                comstr += ' --debug'
            for key, fmt in [
                    ('user', ' --%s=%s'),
                    ('host', ' --%s=%s'),
                    ('interval', ' --%s=%d'),
                    ('max-polls', ' --%s=%s'),
                    ('run-dir', ' --%s=%s'),
                    ('template', ' --%s=%s')]:
                if rtconfig['suite state polling'][key]:
                    comstr += fmt % (key, rtconfig['suite state polling'][key])
            comstr += " " + itask.tdef.suite_polling_cfg['suite']
            script = "echo " + comstr + "\n" + comstr
        return pre_script, script, post_script

    def _job_cmd_out_callback(self, suite, itask, cmd_ctx, line):
        """Callback on job command STDOUT/STDERR."""
        if cmd_ctx.cmd_kwargs.get("host") and cmd_ctx.cmd_kwargs.get("user"):
            owner_at_host = "(%(user)s@%(host)s) " % cmd_ctx.cmd_kwargs
        elif cmd_ctx.cmd_kwargs.get("host"):
            owner_at_host = "(%(host)s) " % cmd_ctx.cmd_kwargs
        elif cmd_ctx.cmd_kwargs.get("user"):
            owner_at_host = "(%(user)s@localhost) " % cmd_ctx.cmd_kwargs
        else:
            owner_at_host = ""
        try:
            timestamp, _, content = line.split("|")
        except ValueError:
            pass
        else:
            line = "%s %s" % (timestamp, content)
        job_activity_log = self.task_events_mgr.get_task_job_activity_log(
            suite, itask.point, itask.tdef.name)
        try:
            with open(job_activity_log, "ab") as handle:
                if not line.endswith("\n"):
                    line += "\n"
                handle.write(owner_at_host + line)
        except IOError as exc:
            LOG.warning("%s: write failed\n%s" % (job_activity_log, exc))
            LOG.warning(owner_at_host + line, itask=itask)

    def _kill_task_jobs_callback(self, ctx, suite, itasks):
        """Callback when kill tasks command exits."""
        self._manip_task_jobs_callback(
            ctx,
            suite,
            itasks,
            self._kill_task_job_callback,
            {BatchSysManager.OUT_PREFIX_COMMAND: self._job_cmd_out_callback})

    def _kill_task_job_callback(self, suite, itask, cmd_ctx, line):
        """Helper for _kill_task_jobs_callback, on one task job."""
        ctx = SuiteProcContext(self.JOBS_KILL, None)
        ctx.out = line
        try:
            ctx.timestamp, _, ctx.ret_code = line.split("|", 2)
        except ValueError:
            ctx.ret_code = 1
            ctx.cmd = cmd_ctx.cmd  # print original command on failure
        else:
            ctx.ret_code = int(ctx.ret_code)
            if ctx.ret_code:
                ctx.cmd = cmd_ctx.cmd  # print original command on failure
        self.task_events_mgr.log_task_job_activity(
            ctx, suite, itask.point, itask.tdef.name)
        log_lvl = INFO
        log_msg = 'killed'
        if ctx.ret_code:  # non-zero exit status
            log_lvl = WARNING
            log_msg = 'kill failed'
            itask.state.kill_failed = True
        elif itask.state.status == TASK_STATUS_SUBMITTED:
            self.task_events_mgr.process_message(
                itask, CRITICAL, "%s at %s" % (
                    self.task_events_mgr.EVENT_SUBMIT_FAILED, ctx.timestamp),
                self.poll_task_jobs)
            cylc.flags.iflag = True
        elif itask.state.status == TASK_STATUS_RUNNING:
            self.task_events_mgr.process_message(
                itask, CRITICAL, TASK_OUTPUT_FAILED, self.poll_task_jobs)
            cylc.flags.iflag = True
        else:
            log_lvl = WARNING
            log_msg = (
                'ignoring job kill result, unexpected task state: %s' %
                itask.state.status)
        itask.summary['latest_message'] = log_msg
        LOG.log(log_lvl, "[%s] -job(%02d) %s" % (
            itask.identity, itask.submit_num, log_msg))

    @staticmethod
    def _manip_task_jobs_callback(
            ctx, suite, itasks, summary_callback, more_callbacks=None):
        """Callback when submit/poll/kill tasks command exits."""
        if ctx.ret_code:
            LOG.error(ctx)
        else:
            LOG.debug(ctx)
        tasks = {}
        # Note for "kill": It is possible for a job to trigger its trap and
        # report back to the suite back this logic is called. If so, the task
        # will no longer be TASK_STATUS_SUBMITTED or TASK_STATUS_RUNNING, and
        # its output line will be ignored here.
        for itask in itasks:
            if itask.point is not None and itask.submit_num:
                submit_num = "%02d" % (itask.submit_num)
                tasks[(str(itask.point), itask.tdef.name, submit_num)] = itask
        handlers = [(BatchSysManager.OUT_PREFIX_SUMMARY, summary_callback)]
        if more_callbacks:
            for prefix, callback in more_callbacks.items():
                handlers.append((prefix, callback))
        out = ctx.out
        if not out:
            out = ""
            # Something is very wrong here
            # Fallback to use "job_log_dirs" list to report the problem
            job_log_dirs = ctx.cmd_kwargs.get("job_log_dirs", [])
            for job_log_dir in job_log_dirs:
                point, name, submit_num = job_log_dir.split(os.sep, 2)
                itask = tasks[(point, name, submit_num)]
                out += (BatchSysManager.OUT_PREFIX_SUMMARY +
                        "|".join([ctx.timestamp, job_log_dir, "1"]) + "\n")
        for line in out.splitlines(True):
            for prefix, callback in handlers:
                if line.startswith(prefix):
                    line = line[len(prefix):].strip()
                    try:
                        path = line.split("|", 2)[1]  # timestamp, path, status
                        point, name, submit_num = path.split(os.sep, 2)
                        itask = tasks[(point, name, submit_num)]
                        callback(suite, itask, ctx, line)
                    except (KeyError, ValueError):
                        if cylc.flags.debug:
                            LOG.warning('Unhandled %s output: %s' % (
                                ctx.cmd_key, line))
                            LOG.warning(traceback.format_exc())

    def _poll_task_jobs_callback(self, ctx, suite, itasks):
        """Callback when poll tasks command exits."""
        self._manip_task_jobs_callback(
            ctx,
            suite,
            itasks,
            self._poll_task_job_callback,
            {BatchSysManager.OUT_PREFIX_MESSAGE:
             self._poll_task_job_message_callback})

    def _poll_task_job_callback(self, suite, itask, cmd_ctx, line):
        """Helper for _poll_task_jobs_callback, on one task job."""
        ctx = SuiteProcContext(self.JOBS_POLL, None)
        ctx.out = line
        ctx.ret_code = 0

        items = line.split("|")
        # See cylc.batch_sys_manager.JobPollContext
        try:
            (
                batch_sys_exit_polled, run_status, run_signal,
                time_submit_exit, time_run, time_run_exit
            ) = items[4:10]
        except IndexError:
            itask.summary['latest_message'] = 'poll failed'
            cylc.flags.iflag = True
            ctx.cmd = cmd_ctx.cmd  # print original command on failure
            return
        finally:
            self.task_events_mgr.log_task_job_activity(
                ctx, suite, itask.point, itask.tdef.name)
        if run_status == "1" and run_signal in ["ERR", "EXIT"]:
            # Failed normally
            self.task_events_mgr.process_message(
                itask, INFO, TASK_OUTPUT_FAILED, self.poll_task_jobs,
                time_run_exit)
        elif run_status == "1" and batch_sys_exit_polled == "1":
            # Failed by a signal, and no longer in batch system
            self.task_events_mgr.process_message(
                itask, INFO, TASK_OUTPUT_FAILED, self.poll_task_jobs,
                time_run_exit)
            self.task_events_mgr.process_message(
                itask, INFO, TaskMessage.FAIL_MESSAGE_PREFIX + run_signal,
                self.poll_task_jobs, time_run_exit)
        elif run_status == "1":
            # The job has terminated, but is still managed by batch system.
            # Some batch system may restart a job in this state, so don't
            # mark as failed yet.
            self.task_events_mgr.process_message(
                itask, INFO, TASK_OUTPUT_STARTED, self.poll_task_jobs,
                time_run)
        elif run_status == "0":
            # The job succeeded
            self.task_events_mgr.process_message(
                itask, INFO, TASK_OUTPUT_SUCCEEDED, self.poll_task_jobs,
                time_run_exit)
        elif time_run and batch_sys_exit_polled == "1":
            # The job has terminated without executing the error trap
            self.task_events_mgr.process_message(
                itask, INFO, TASK_OUTPUT_FAILED, self.poll_task_jobs, "")
        elif time_run:
            # The job has started, and is still managed by batch system
            self.task_events_mgr.process_message(
                itask, INFO, TASK_OUTPUT_STARTED, self.poll_task_jobs,
                time_run)
        elif batch_sys_exit_polled == "1":
            # The job never ran, and no longer in batch system
            self.task_events_mgr.process_message(
                itask, INFO, self.task_events_mgr.EVENT_SUBMIT_FAILED,
                self.poll_task_jobs, time_submit_exit)
        else:
            # The job never ran, and is in batch system
            self.task_events_mgr.process_message(
                itask, INFO, TASK_STATUS_SUBMITTED, self.poll_task_jobs,
                time_submit_exit)

    def _poll_task_job_message_callback(self, suite, itask, cmd_ctx, line):
        """Helper for _poll_task_jobs_callback, on message of one task job."""
        ctx = SuiteProcContext(self.JOBS_POLL, None)
        ctx.out = line
        try:
            event_time, severity, message = line.split("|")[2:5]
        except ValueError:
            ctx.ret_code = 1
            ctx.cmd = cmd_ctx.cmd  # print original command on failure
        else:
            ctx.ret_code = 0
            self.task_events_mgr.process_message(
                itask, severity, message, self.poll_task_jobs, event_time)
        self.task_events_mgr.log_task_job_activity(
            ctx, suite, itask.point, itask.tdef.name)

    def _run_job_cmd(self, cmd_key, suite, itasks, callback):
        """Run job commands, e.g. poll, kill, etc.

        Group itasks with their user@host.
        Put a job command for each user@host to the multiprocess pool.

        """
        if not itasks:
            return
        auth_itasks = {}
        for itask in itasks:
            if (itask.task_host, itask.task_owner) not in auth_itasks:
                auth_itasks[(itask.task_host, itask.task_owner)] = []
            auth_itasks[(itask.task_host, itask.task_owner)].append(itask)
        for (host, owner), itasks in sorted(auth_itasks.items()):
            cmd = ["cylc", cmd_key]
            if cylc.flags.debug:
                cmd.append("--debug")
            if is_remote_host(host):
                cmd.append("--host=%s" % (host))
            if is_remote_user(owner):
                cmd.append("--user=%s" % (owner))
            cmd.append("--")
            cmd.append(glbl_cfg().get_derived_host_item(
                suite, "suite job log directory", host, owner))
            job_log_dirs = []
            for itask in sorted(itasks, key=lambda itask: itask.identity):
                job_log_dirs.append(self.task_events_mgr.get_task_job_id(
                    itask.point, itask.tdef.name, itask.submit_num))
            cmd += job_log_dirs
            self.proc_pool.put_command(
                SuiteProcContext(cmd_key, cmd), callback, [suite, itasks])

    @staticmethod
    def _set_retry_timers(itask, rtconfig=None):
        """Set try number and retry delays."""
        if rtconfig is None:
            rtconfig = itask.tdef.rtconfig
        try:
            no_retry = (
                rtconfig[itask.tdef.run_mode + ' mode']['disable retries'])
        except KeyError:
            no_retry = False
        if not no_retry:
            for key, cfg_key in [
                    (TASK_STATUS_SUBMIT_RETRYING, 'submission retry delays'),
                    (TASK_STATUS_RETRYING, 'execution retry delays')]:
                delays = rtconfig['job'][cfg_key]
                try:
                    itask.try_timers[key].set_delays(delays)
                except KeyError:
                    itask.try_timers[key] = TaskActionTimer(delays=delays)

    def _simulation_submit_task_jobs(self, itasks):
        """Simulation mode task jobs submission."""
        for itask in itasks:
            self._set_retry_timers(itask)
            itask.task_host = 'SIMULATION'
            itask.task_owner = 'SIMULATION'
            itask.summary['batch_sys_name'] = 'SIMULATION'
            itask.summary[self.KEY_EXECUTE_TIME_LIMIT] = (
                itask.tdef.rtconfig['job']['simulated run length'])
            self.task_events_mgr.process_message(
                itask, INFO, TASK_OUTPUT_SUBMITTED, self.poll_task_jobs)
        return itasks

    def _submit_task_jobs_callback(self, ctx, suite, itasks):
        """Callback when submit task jobs command exits."""
        self._manip_task_jobs_callback(
            ctx,
            suite,
            itasks,
            self._submit_task_job_callback,
            {BatchSysManager.OUT_PREFIX_COMMAND: self._job_cmd_out_callback})

    def _submit_task_job_callback(self, suite, itask, cmd_ctx, line):
        """Helper for _submit_task_jobs_callback, on one task job."""
        ctx = SuiteProcContext(self.JOBS_SUBMIT, None)
        ctx.out = line
        items = line.split("|")
        try:
            ctx.timestamp, _, ctx.ret_code = items[0:3]
        except ValueError:
            ctx.ret_code = 1
            ctx.cmd = cmd_ctx.cmd  # print original command on failure
        else:
            ctx.ret_code = int(ctx.ret_code)
            if ctx.ret_code:
                ctx.cmd = cmd_ctx.cmd  # print original command on failure
        self.task_events_mgr.log_task_job_activity(
            ctx, suite, itask.point, itask.tdef.name)

        if ctx.ret_code == SuiteProcPool.RET_CODE_SUITE_STOPPING:
            return

        try:
            itask.summary['submit_method_id'] = items[3]
        except IndexError:
            itask.summary['submit_method_id'] = None
        if itask.summary['submit_method_id'] == "None":
            itask.summary['submit_method_id'] = None
        if itask.summary['submit_method_id'] and ctx.ret_code == 0:
            self.task_events_mgr.process_message(
                itask, INFO, '%s at %s' % (
                    TASK_OUTPUT_SUBMITTED, ctx.timestamp),
                self.poll_task_jobs)
        else:
            self.task_events_mgr.process_message(
                itask, CRITICAL, '%s at %s' % (
                    self.task_events_mgr.EVENT_SUBMIT_FAILED, ctx.timestamp),
                self.poll_task_jobs)

    def _prep_submit_task_job(self, suite, itask, dry_run, check_syntax=True):
        """Prepare a task job submission.

        Return itask on a good preparation.

        """
        if itask.local_job_file_path and not dry_run:
            return itask

        # Handle broadcasts
        overrides = self.task_events_mgr.broadcast_mgr.get_broadcast(
            itask.identity)
        if overrides:
            rtconfig = pdeepcopy(itask.tdef.rtconfig)
            poverride(rtconfig, overrides, prepend=True)
        else:
            rtconfig = itask.tdef.rtconfig

        # Determine task host settings now, just before job submission,
        # because dynamic host selection may be used.
        try:
            task_host = self.task_remote_mgr.remote_host_select(
                rtconfig['remote']['host'])
        except TaskRemoteMgmtError as exc:
            # Submit number not yet incremented
            itask.submit_num += 1
            itask.summary['submit_num'] = itask.submit_num
            # Retry delays, needed for the try_num
            self._set_retry_timers(itask, rtconfig)
            self._prep_submit_task_job_error(
                suite, itask, dry_run, '(remote host select)', exc)
            return False
        else:
            if task_host is None:  # host select not ready
                itask.summary['latest_message'] = self.REMOTE_SELECT_MSG
                return
            itask.task_host = task_host
            # Submit number not yet incremented
            itask.submit_num += 1
            itask.summary['submit_num'] = itask.submit_num
            # Retry delays, needed for the try_num
            self._set_retry_timers(itask, rtconfig)

        try:
            job_conf = self._prep_submit_task_job_impl(suite, itask, rtconfig)
            local_job_file_path = self.task_events_mgr.get_task_job_log(
                suite, itask.point, itask.tdef.name, itask.submit_num,
                self.JOB_FILE_BASE)
            self.job_file_writer.write(local_job_file_path, job_conf,
                                       check_syntax=check_syntax)
        except StandardError as exc:
            # Could be a bad command template, IOError, etc
            self._prep_submit_task_job_error(
                suite, itask, dry_run, '(prepare job file)', exc)
            return False
        itask.local_job_file_path = local_job_file_path

        if dry_run:
            # This will be shown next to submit num in gcylc:
            itask.summary['latest_message'] = 'job file written (edit/dry-run)'
            LOG.debug(itask.summary['latest_message'], itask=itask)

        # Return value used by "cylc submit" and "cylc jobscript":
        return itask

    def _prep_submit_task_job_error(self, suite, itask, dry_run, action, exc):
        """Helper for self._prep_submit_task_job. On error."""
        LOG.debug("submit_num %s" % itask.submit_num)
        LOG.debug(traceback.format_exc())
        LOG.error(exc)
        self.task_events_mgr.log_task_job_activity(
            SuiteProcContext(self.JOBS_SUBMIT, action, err=exc, ret_code=1),
            suite, itask.point, itask.tdef.name, submit_num=itask.submit_num)
        if not dry_run:
            # Perist
            self.suite_db_mgr.put_insert_task_jobs(itask, {
                'is_manual_submit': itask.is_manual_submit,
                'try_num': itask.get_try_num(),
                'time_submit': get_current_time_string(),
                'batch_sys_name': itask.summary.get('batch_sys_name'),
            })
            itask.is_manual_submit = False
            self.task_events_mgr.process_message(
                itask, CRITICAL, self.task_events_mgr.EVENT_SUBMIT_FAILED,
                self.poll_task_jobs)

    def _prep_submit_task_job_impl(self, suite, itask, rtconfig):
        """Helper for self._prep_submit_task_job."""
        itask.task_owner = rtconfig['remote']['owner']
        if itask.task_owner:
            owner_at_host = itask.task_owner + "@" + itask.task_host
        else:
            owner_at_host = itask.task_host
        itask.summary['host'] = owner_at_host
        itask.summary['job_hosts'][itask.submit_num] = owner_at_host

        itask.summary['batch_sys_name'] = rtconfig['job']['batch system']
        for name in rtconfig['extra log files']:
            itask.summary['logfiles'].append(expandvars(name))
        try:
            batch_sys_conf = self.task_events_mgr.get_host_conf(
                itask, 'batch systems')[rtconfig['job']['batch system']]
        except (TypeError, KeyError):
            batch_sys_conf = {}
        try:
            itask.summary[self.KEY_EXECUTE_TIME_LIMIT] = float(
                rtconfig['job']['execution time limit'])
        except TypeError:
            pass
        if itask.summary[self.KEY_EXECUTE_TIME_LIMIT]:
            # Default = 1, 2 and 7 minutes intervals, roughly 1, 3 and 10
            # minutes after time limit exceeded
            itask.poll_timers[self.KEY_EXECUTE_TIME_LIMIT] = (
                TaskActionTimer(delays=batch_sys_conf.get(
                    'execution time limit polling intervals', [60, 120, 420])))
        for label, key in [
                ('submission polling intervals', TASK_STATUS_SUBMITTED),
                ('execution polling intervals', TASK_STATUS_RUNNING)]:
            if key in itask.poll_timers:
                itask.poll_timers[key].reset()
            else:
                values = self.task_events_mgr.get_host_conf(
                    itask, label, skey='job')
                if values:
                    itask.poll_timers[key] = TaskActionTimer(delays=values)

        scripts = self._get_job_scripts(itask, rtconfig)

        # Location of job file, etc
        self._create_job_log_path(suite, itask)
        job_d = self.task_events_mgr.get_task_job_id(
            itask.point, itask.tdef.name, itask.submit_num)
        job_file_path = os.path.join(
            glbl_cfg().get_derived_host_item(
                suite, "suite job log directory",
                itask.task_host, itask.task_owner),
            job_d, self.JOB_FILE_BASE)
        return {
            'batch_system_name': rtconfig['job']['batch system'],
            'batch_submit_command_template': (
                rtconfig['job']['batch submit command template']),
            'batch_system_conf': batch_sys_conf,
            'directives': rtconfig['directives'],
            'environment': rtconfig['environment'],
            'execution_time_limit': itask.summary[self.KEY_EXECUTE_TIME_LIMIT],
            'env-script': rtconfig['env-script'],
            'err-script': rtconfig['err-script'],
            'host': itask.task_host,
            'init-script': rtconfig['init-script'],
            'job_file_path': job_file_path,
            'job_d': job_d,
            'namespace_hierarchy': itask.tdef.namespace_hierarchy,
            'owner': itask.task_owner,
            'param_env_tmpl': rtconfig['parameter environment templates'],
            'param_var': itask.tdef.param_var,
            'post-script': scripts[2],
            'pre-script': scripts[0],
            'remote_suite_d': rtconfig['remote']['suite definition directory'],
            'script': scripts[1],
            'shell': rtconfig['job']['shell'],
            'submit_num': itask.submit_num,
            'suite_name': suite,
            'task_id': itask.identity,
            'try_num': itask.get_try_num(),
            'work_d': rtconfig['work sub-directory'],
        }
