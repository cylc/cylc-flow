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
"""Manage submit, poll, kill of task jobs."""

from logging import CRITICAL, INFO, WARNING
import os
from pipes import quote
import shlex
from shutil import rmtree
from subprocess import Popen, PIPE
from time import time
import traceback
from uuid import uuid4

from parsec.util import pdeepcopy, poverride

from cylc.batch_sys_manager import BatchSysManager
from cylc.cfgspec.globalcfg import GLOBAL_CFG
import cylc.flags
from cylc.host_select import get_task_host
from cylc.job_file import JobFileWriter
from cylc.mkdir_p import mkdir_p
from cylc.mp_pool import SuiteProcPool, SuiteProcContext
from cylc.network.suite_broadcast_server import BroadcastServer
from cylc.owner import is_remote_user, USER
from cylc.suite_host import is_remote_host
from cylc.suite_logging import ERR, LOG
from cylc.suite_srv_files_mgr import SuiteSrvFilesManager
from cylc.task_events_mgr import TaskEventsManager
from cylc.task_message import TaskMessage
from cylc.task_outputs import (
    TASK_OUTPUT_STARTED, TASK_OUTPUT_SUCCEEDED, TASK_OUTPUT_FAILED)
from cylc.task_action_timer import TaskActionTimer
from cylc.task_state import (
    TASK_STATUSES_ACTIVE, TASK_STATUS_HELD, TASK_STATUS_READY,
    TASK_STATUS_RUNNING, TASK_STATUS_SUBMITTED)
from cylc.wallclock import get_current_time_string


class RemoteJobHostInitError(Exception):
    """Cannot initialise suite run directory of remote job host."""

    MSG_INIT = "%s: initialisation did not complete:\n"  # %s user_at_host
    MSG_TIDY = "%s: clean up did not complete:\n"  # %s user_at_host

    def __str__(self):
        msg, user_at_host, cmd_str, ret_code, out, err = self.args
        ret = (msg + "COMMAND FAILED (%d): %s\n") % (
            user_at_host, ret_code, cmd_str)
        for label, item in ("STDOUT", out), ("STDERR", err):
            if item:
                for line in item.splitlines(True):  # keep newline chars
                    ret += "COMMAND %s: %s" % (label, line)
        return ret


class TaskJobManager(object):
    """Manage task job submit, poll and kill."""

    JOB_FILE_BASE = BatchSysManager.JOB_FILE_BASE
    JOBS_KILL = "jobs-kill"
    JOBS_POLL = "jobs-poll"
    JOBS_SUBMIT = SuiteProcPool.JOBS_SUBMIT

    def __init__(self, proc_pool, task_events_mgr=None):
        self.proc_pool = proc_pool
        if task_events_mgr is None:
            task_events_mgr = TaskEventsManager(proc_pool)
        self.task_events_mgr = task_events_mgr
        self.job_file_writer = JobFileWriter()
        self.suite_srv_files_mgr = SuiteSrvFilesManager()
        self.init_host_map = {}  # {(user, host): should_unlink, ...}
        self.single_task_mode = False

    def init_host(self, reg, host, owner):
        """Initialise suite run dir on a user@host.

        Create SUITE_RUN_DIR/log/job/ if necessary.
        Install suite contact environment file.
        Install suite python modules.

        Raise RemoteJobHostInitError if initialisation cannot complete.

        """
        if host is None:
            host = 'localhost'
        if ((host, owner) in [('localhost', None), ('localhost', USER)] or
                (host, owner) in self.init_host_map or self.single_task_mode):
            return
        user_at_host = host
        if owner:
            user_at_host = owner + '@' + host

        r_suite_run_dir = GLOBAL_CFG.get_derived_host_item(
            reg, 'suite run directory', host, owner)
        r_log_job_dir = GLOBAL_CFG.get_derived_host_item(
            reg, 'suite job log directory', host, owner)
        r_suite_srv_dir = os.path.join(
            r_suite_run_dir, self.suite_srv_files_mgr.DIR_BASE_SRV)

        # Create a UUID file in the service directory.
        # If remote host has the file in its service directory, we can assume
        # that the remote host has a shared file system with the suite host.
        ssh_tmpl = GLOBAL_CFG.get_host_item('ssh command', host, owner)
        uuid_str = str(uuid4())
        uuid_fname = os.path.join(
            self.suite_srv_files_mgr.get_suite_srv_dir(reg), uuid_str)
        try:
            open(uuid_fname, 'wb').close()
            proc = Popen(
                shlex.split(ssh_tmpl) + [
                    '-n', user_at_host,
                    'test', '-e', os.path.join(r_suite_srv_dir, uuid_str)],
                stdout=PIPE, stderr=PIPE)
            if proc.wait() == 0:
                # Initialised, but no need to tidy up
                self.init_host_map[(host, owner)] = False
                return
        finally:
            try:
                os.unlink(uuid_fname)
            except OSError:
                pass

        cmds = []
        # Command to create suite directory structure on remote host.
        cmds.append(shlex.split(ssh_tmpl) + [
            '-n', user_at_host,
            'mkdir', '-p',
            r_suite_run_dir, r_log_job_dir, r_suite_srv_dir])
        # Command to copy contact and authentication files to remote host.
        # Note: no need to do this if task communication method is "poll".
        should_unlink = GLOBAL_CFG.get_host_item(
            'task communication method', host, owner) != "poll"
        if should_unlink:
            scp_tmpl = GLOBAL_CFG.get_host_item('scp command', host, owner)
            cmds.append(shlex.split(scp_tmpl) + [
                '-p',
                self.suite_srv_files_mgr.get_contact_file(reg),
                self.suite_srv_files_mgr.get_auth_item(
                    self.suite_srv_files_mgr.FILE_BASE_PASSPHRASE, reg),
                self.suite_srv_files_mgr.get_auth_item(
                    self.suite_srv_files_mgr.FILE_BASE_SSL_CERT, reg),
                user_at_host + ':' + r_suite_srv_dir + '/'])
        # Command to copy python library to remote host.
        suite_run_py = os.path.join(
            GLOBAL_CFG.get_derived_host_item(reg, 'suite run directory'),
            'python')
        if os.path.isdir(suite_run_py):
            cmds.append(shlex.split(scp_tmpl) + [
                '-pr',
                suite_run_py, user_at_host + ':' + r_suite_run_dir + '/'])
        # Run commands in sequence.
        for cmd in cmds:
            proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
            out, err = proc.communicate()
            if proc.wait():
                raise RemoteJobHostInitError(
                    RemoteJobHostInitError.MSG_INIT,
                    user_at_host, ' '.join([quote(item) for item in cmd]),
                    proc.returncode, out, err)
        self.init_host_map[(host, owner)] = should_unlink
        LOG.info('Initialised %s:%s' % (user_at_host, r_suite_run_dir))

    def kill_task_jobs(self, suite, itasks, warn_skips=False):
        """Kill jobs of active tasks, and hold the tasks.

        If items is specified, kill active tasks matching given IDs.

        """
        active_itasks = []
        for itask in itasks:
            if itask.state.status in TASK_STATUSES_ACTIVE:
                itask.state.reset_state(TASK_STATUS_HELD)
                active_itasks.append(itask)
            elif warn_skips:  # and not active
                LOG.warning(
                    '%s: skip kill, task not killable' % itask.identity)
        self._run_job_cmd(
            self.JOBS_KILL, suite, active_itasks,
            self._kill_task_jobs_callback)

    def poll_task_jobs(self, suite, itasks, warn_skips=False):
        """Poll jobs of specified tasks."""
        active_itasks = []
        for itask in itasks:
            if itask.state.status in TASK_STATUSES_ACTIVE:
                active_itasks.append(itask)
            elif warn_skips:  # and not active
                LOG.warning(
                    '%s: skip poll, task not pollable' % itask.identity)
        self._run_job_cmd(
            self.JOBS_POLL, suite, active_itasks,
            self._poll_task_jobs_callback)

    def prep_submit_task_jobs(self, suite, itasks, dry_run=False):
        """Prepare task jobs for submit."""
        if not itasks:
            return
        prepared_tasks = []
        for itask in itasks:
            if self._prep_submit_task_job(suite, itask, dry_run) is not None:
                prepared_tasks.append(itask)
        return prepared_tasks

    def submit_task_jobs(self, suite, itasks):
        """Prepare and submit task jobs."""
        # Prepare tasks for job submission
        prepared_tasks = self.prep_submit_task_jobs(suite, itasks)
        if not prepared_tasks:
            return

        # Submit task jobs
        auth_itasks = {}
        for itask in prepared_tasks:
            # The job file is now (about to be) used: reset the file write flag
            # so that subsequent manual retrigger will generate a new job file.
            itask.local_job_file_path = None
            itask.state.set_state(TASK_STATUS_READY)
            if (itask.task_host, itask.task_owner) not in auth_itasks:
                auth_itasks[(itask.task_host, itask.task_owner)] = []
            auth_itasks[(itask.task_host, itask.task_owner)].append(itask)
        for auth, itasks in sorted(auth_itasks.items()):
            cmd = ["cylc", self.JOBS_SUBMIT]
            if cylc.flags.debug:
                cmd.append("--debug")
            host, owner = auth
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
            cmd.append("--")
            cmd.append(GLOBAL_CFG.get_derived_host_item(
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

    def unlink_hosts_contacts(self, reg):
        """Remove suite contact files from initialised hosts.

        This is called on shutdown, so we don't want anything to hang.
        Terminate any incomplete SSH commands after 10 seconds.
        """
        # Issue all SSH commands in parallel
        procs = {}
        for (host, owner), should_unlink in self.init_host_map.items():
            if not should_unlink:
                continue
            user_at_host = host
            if owner:
                user_at_host = owner + '@' + host
            ssh_tmpl = GLOBAL_CFG.get_host_item('ssh command', host, owner)
            r_suite_contact_file = os.path.join(
                GLOBAL_CFG.get_derived_host_item(
                    reg, 'suite run directory', host, owner),
                SuiteSrvFilesManager.DIR_BASE_SRV,
                SuiteSrvFilesManager.FILE_BASE_CONTACT)
            cmd = shlex.split(ssh_tmpl) + [
                '-n', user_at_host, 'rm', '-f', r_suite_contact_file]
            procs[user_at_host] = (cmd, Popen(cmd, stdout=PIPE, stderr=PIPE))
        # Wait for commands to complete for a max of 10 seconds
        timeout = time() + 10.0
        while procs and time() < timeout:
            for user_at_host, (cmd, proc) in procs.copy().items():
                if proc.poll() is None:
                    continue
                del procs[user_at_host]
                out, err = proc.communicate()
                if proc.wait():
                    ERR.warning(RemoteJobHostInitError(
                        RemoteJobHostInitError.MSG_TIDY,
                        user_at_host, ' '.join([quote(item) for item in cmd]),
                        proc.returncode, out, err))
        # Terminate any remaining commands
        for user_at_host, (cmd, proc) in procs.items():
            try:
                proc.terminate()
            except OSError:
                pass
            out, err = proc.communicate()
            if proc.wait():
                ERR.warning(RemoteJobHostInitError(
                    RemoteJobHostInitError.MSG_TIDY,
                    user_at_host, ' '.join([quote(item) for item in cmd]),
                    proc.returncode, out, err))

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
                    if name not in ["01", itask.NN]:
                        rmtree(
                            os.path.join(task_log_dir, name),
                            ignore_errors=True)
        else:
            rmtree(job_file_dir, ignore_errors=True)

        mkdir_p(job_file_dir)
        target = os.path.join(task_log_dir, itask.NN)
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
        if itask.tdef.run_mode == 'dummy':
            # Use dummy script items in dummy mode.
            script = rtconfig['dummy mode']['script']
            if rtconfig['dummy mode']['disable pre-script']:
                pre_script = None
            if rtconfig['dummy mode']['disable post-script']:
                post_script = None
        elif itask.tdef.suite_polling_cfg:
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
            user_at_host = "(%(user)s@%(host)s) " % cmd_ctx.cmd_kwargs
        elif cmd_ctx.cmd_kwargs.get("host"):
            user_at_host = "(%(host)s) " % cmd_ctx.cmd_kwargs
        elif cmd_ctx.cmd_kwargs.get("user"):
            user_at_host = "(%(user)s@localhost) " % cmd_ctx.cmd_kwargs
        else:
            user_at_host = ""
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
                handle.write(user_at_host + line)
        except IOError as exc:
            LOG.warning("%s: write failed\n%s" % (job_activity_log, exc))

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
                itask, CRITICAL, 'submission failed', ctx.timestamp)
            cylc.flags.iflag = True
        elif itask.state.status == TASK_STATUS_RUNNING:
            self.task_events_mgr.process_message(itask, CRITICAL, 'failed')
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
                itask, INFO, TASK_OUTPUT_FAILED, time_run_exit)
        elif run_status == "1" and batch_sys_exit_polled == "1":
            # Failed by a signal, and no longer in batch system
            self.task_events_mgr.process_message(
                itask, INFO, TASK_OUTPUT_FAILED, time_run_exit)
            self.task_events_mgr.process_message(
                itask, INFO, TaskMessage.FAIL_MESSAGE_PREFIX + run_signal,
                time_run_exit)
        elif run_status == "1":
            # The job has terminated, but is still managed by batch system.
            # Some batch system may restart a job in this state, so don't
            # mark as failed yet.
            self.task_events_mgr.process_message(
                itask, INFO, TASK_OUTPUT_STARTED, time_run)
        elif run_status == "0":
            # The job succeeded
            self.task_events_mgr.process_message(
                itask, INFO, TASK_OUTPUT_SUCCEEDED, time_run_exit)
        elif time_run and batch_sys_exit_polled == "1":
            # The job has terminated without executing the error trap
            self.task_events_mgr.process_message(
                itask, INFO, TASK_OUTPUT_FAILED, "")
        elif time_run:
            # The job has started, and is still managed by batch system
            self.task_events_mgr.process_message(
                itask, INFO, TASK_OUTPUT_STARTED, time_run)
        elif batch_sys_exit_polled == "1":
            # The job never ran, and no longer in batch system
            self.task_events_mgr.process_message(
                itask, INFO, "submission failed", time_submit_exit)
        else:
            # The job never ran, and is in batch system
            self.task_events_mgr.process_message(
                itask, INFO, TASK_STATUS_SUBMITTED, time_submit_exit)

    def _poll_task_job_message_callback(self, suite, itask, cmd_ctx, line):
        """Helper for _poll_task_jobs_callback, on message of one task job."""
        ctx = SuiteProcContext(self.JOBS_POLL, None)
        ctx.out = line
        try:
            event_time, priority, message = line.split("|")[2:5]
        except ValueError:
            ctx.ret_code = 1
            ctx.cmd = cmd_ctx.cmd  # print original command on failure
        else:
            ctx.ret_code = 0
            self.task_events_mgr.process_message(
                itask, priority, message, event_time)
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
            try:
                if is_remote_host(host):
                    cmd.append("--host=%s" % (host))
            except IOError:
                # Bad host, run the command any way, command will fail and
                # callback will deal with it
                cmd.append("--host=%s" % (host))
            if is_remote_user(owner):
                cmd.append("--user=%s" % (owner))
            cmd.append("--")
            cmd.append(GLOBAL_CFG.get_derived_host_item(
                suite, "suite job log directory", host, owner))
            job_log_dirs = []
            for itask in sorted(itasks, key=lambda itask: itask.identity):
                job_log_dirs.append(self.task_events_mgr.get_task_job_id(
                    itask.point, itask.tdef.name, itask.submit_num))
            cmd += job_log_dirs
            self.proc_pool.put_command(
                SuiteProcContext(cmd_key, cmd), callback, [suite, itasks])

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

        if ctx.ret_code == SuiteProcPool.JOB_SKIPPED_FLAG:
            return

        try:
            itask.summary['submit_method_id'] = items[3]
        except IndexError:
            itask.summary['submit_method_id'] = None
        if itask.summary['submit_method_id'] == "None":
            itask.summary['submit_method_id'] = None
        if itask.summary['submit_method_id'] and ctx.ret_code == 0:
            self.task_events_mgr.process_message(
                itask, INFO, 'submission succeeded at %s' % ctx.timestamp)
        else:
            self.task_events_mgr.process_message(
                itask, CRITICAL, 'submission failed at %s' % ctx.timestamp)

    def _prep_submit_task_job(self, suite, itask, dry_run):
        """Prepare a task job submission.

        Return itask on a good preparation.

        """
        if itask.local_job_file_path and not dry_run:
            return itask

        try:
            job_conf = self._prep_submit_task_job_impl(suite, itask)
            local_job_file_path = self.task_events_mgr.get_task_job_log(
                suite, itask.point, itask.tdef.name, itask.submit_num,
                self.JOB_FILE_BASE)
            self.job_file_writer.write(local_job_file_path, job_conf)
        except Exception, exc:
            # Could be a bad command template.
            ERR.error(traceback.format_exc())
            LOG.error(traceback.format_exc())
            self.task_events_mgr.log_task_job_activity(
                SuiteProcContext(
                    self.JOBS_SUBMIT,
                    '(prepare job file)', err=exc, ret_code=1),
                suite, itask.point, itask.tdef.name)
            if not dry_run:
                self.task_events_mgr.process_message(
                    itask, CRITICAL, 'submission failed')
            return
        itask.local_job_file_path = local_job_file_path

        if dry_run:
            # This will be shown next to submit num in gcylc:
            itask.summary['latest_message'] = 'job file written (edit/dry-run)'
            LOG.debug("[%s] -%s" % (
                itask.identity, itask.summary['latest_message']))

        # Return value used by "cylc submit" and "cylc jobscript":
        return itask

    def _prep_submit_task_job_impl(self, suite, itask):
        """Helper for self._prep_submit_task_job."""
        overrides = BroadcastServer.get_inst().get(itask.identity)
        if overrides:
            rtconfig = pdeepcopy(itask.tdef.rtconfig)
            poverride(rtconfig, overrides)
        else:
            rtconfig = itask.tdef.rtconfig
        LOG.debug("[%s] -incrementing submit number" % (itask.identity,))
        itask.submit_num += 1
        itask.summary['submit_num'] = itask.submit_num
        itask.local_job_file_path = None
        itask.db_events_insert(event="incrementing submit number")
        itask.db_inserts_map[itask.TABLE_TASK_JOBS].append({
            "is_manual_submit": itask.is_manual_submit,
            "try_num": itask.try_timers[itask.KEY_EXECUTE].num + 1,
            "time_submit": get_current_time_string(),
        })

        itask.events_conf = rtconfig['events']

        # construct the job_sub_method here so that a new one is used if
        # the task is re-triggered by the suite operator - so it will
        # get new stdout/stderr logfiles and not overwrite the old ones.

        # dynamic instantiation - don't know job sub method till run time.
        itask.summary['batch_sys_name'] = rtconfig['job']['batch system']
        itask.summary['execution_time_limit'] = (
            rtconfig['job']['execution time limit'])

        # Determine task host settings now, just before job submission,
        # because dynamic host selection may be used.

        # host may be None (= run task on suite host)
        itask.task_host = get_task_host(rtconfig['remote']['host'])
        if not itask.task_host:
            itask.task_host = 'localhost'
        elif itask.task_host != "localhost":
            LOG.info("[%s] -Task host: %s" % (
                itask.identity, itask.task_host))

        itask.task_owner = rtconfig['remote']['owner']

        if itask.task_owner:
            user_at_host = itask.task_owner + "@" + itask.task_host
        else:
            user_at_host = itask.task_host
        itask.summary['host'] = user_at_host
        itask.summary['job_hosts'][itask.submit_num] = user_at_host
        try:
            batch_sys_conf = itask.get_host_conf('batch systems')[
                rtconfig['job']['batch system']]
        except (TypeError, KeyError):
            batch_sys_conf = {}
        if itask.summary['execution_time_limit']:
            # Default = 1, 2 and 7 minutes intervals, roughly 1, 3 and 10
            # minutes after time limit exceeded
            itask.poll_timers[itask.KEY_EXECUTE_TIME_LIMIT] = (
                TaskActionTimer(delays=batch_sys_conf.get(
                    'execution time limit polling intervals', [60, 120, 420])))
        for key in itask.KEY_SUBMIT, itask.KEY_EXECUTE:
            try:
                itask.poll_timers[key].reset()
            except (AttributeError, KeyError):
                pass

        self.init_host(suite, itask.task_host, itask.task_owner)
        itask.db_updates_map[itask.TABLE_TASK_JOBS].append({
            "user_at_host": user_at_host,
            "batch_sys_name": itask.summary['batch_sys_name'],
        })
        itask.is_manual_submit = False

        scripts = self._get_job_scripts(itask, rtconfig)
        execution_time_limit = rtconfig['job']['execution time limit']
        if execution_time_limit:
            execution_time_limit = float(execution_time_limit)

        # Location of job file, etc
        self._create_job_log_path(suite, itask)
        job_d = self.task_events_mgr.get_task_job_id(
            itask.point, itask.tdef.name, itask.submit_num)
        job_file_path = os.path.join(
            GLOBAL_CFG.get_derived_host_item(
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
            'execution_time_limit': execution_time_limit,
            'env-script': rtconfig['env-script'],
            'err-script': rtconfig['err-script'],
            'host': itask.task_host,
            'init-script': rtconfig['init-script'],
            'job_file_path': job_file_path,
            'job_d': job_d,
            'namespace_hierarchy': itask.tdef.namespace_hierarchy,
            'owner': itask.task_owner,
            'post-script': scripts[2],
            'pre-script': scripts[0],
            'remote_suite_d': rtconfig['remote']['suite definition directory'],
            'script': scripts[1],
            'shell': rtconfig['job']['shell'],
            'submit_num': itask.submit_num,
            'suite_name': suite,
            'task_id': itask.identity,
            'try_num': itask.try_timers[itask.KEY_EXECUTE].num + 1,
            'work_d': rtconfig['work sub-directory'],
        }
