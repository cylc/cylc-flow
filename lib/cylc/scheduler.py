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
"""Cylc scheduler server."""

from collections import deque
import logging
import os
from shlex import quote
from queue import Empty, Queue
from shutil import copytree, rmtree
from subprocess import Popen, PIPE
import sys
from time import sleep, time
import traceback
from uuid import uuid4

from isodatetime.parsers import TimePointParser
from parsec.util import printcfg

from cylc import LOG
from cylc.broadcast_mgr import BroadcastMgr
from cylc.cfgspec.glbl_cfg import glbl_cfg
from cylc.config import SuiteConfig
from cylc.cycling.loader import get_point, standardise_point_string
from cylc.daemonize import daemonize
from cylc.exceptions import (
    CylcError, PointParsingError, TaskProxySequenceBoundsError)
import cylc.flags
from cylc.host_appointer import HostAppointer, EmptyHostList
from cylc.hostuserutil import get_host, get_user, get_fqdn_by_host
from cylc.loggingutil import TimestampRotatingFileHandler,\
    ReferenceLogFileHandler
from cylc.log_diagnosis import LogSpec
from cylc.network.server import SuiteRuntimeServer
from cylc.profiler import Profiler
from cylc.state_summary_mgr import StateSummaryMgr
from cylc.subprocpool import SubProcPool
from cylc.suite_db_mgr import SuiteDatabaseManager
from cylc.suite_events import (
    SuiteEventContext, SuiteEventError, SuiteEventHandler)
from cylc.suite_srv_files_mgr import (
    SuiteSrvFilesManager, SuiteServiceFileError)
from cylc.taskdef import TaskDef
from cylc.task_events_mgr import TaskEventsManager
from cylc.task_id import TaskID
from cylc.task_job_logs import JOB_LOG_JOB, get_task_job_log
from cylc.task_job_mgr import TaskJobManager
from cylc.task_pool import TaskPool
from cylc.task_proxy import TaskProxy
from cylc.task_state import (
    TASK_STATUSES_ACTIVE, TASK_STATUSES_NEVER_ACTIVE, TASK_STATUS_FAILED)
from cylc.templatevars import load_template_vars
from cylc import __version__ as CYLC_VERSION
from cylc.wallclock import (
    get_current_time_string, get_seconds_as_interval_string,
    get_time_string_from_unix_time as time2str, get_utc_mode)
from cylc.xtrigger_mgr import XtriggerManager


class SchedulerError(CylcError):
    """Scheduler error."""
    pass


class SchedulerStop(CylcError):
    """Scheduler has stopped."""
    pass


class SchedulerUUID(object):
    """Scheduler identifier - which persists on restart."""
    __slots__ = ('value')

    def __init__(self):
        self.value = str(uuid4())

    def __str__(self):
        return self.value


class Scheduler(object):
    """Cylc scheduler server."""

    EVENT_STARTUP = SuiteEventHandler.EVENT_STARTUP
    EVENT_SHUTDOWN = SuiteEventHandler.EVENT_SHUTDOWN
    EVENT_TIMEOUT = SuiteEventHandler.EVENT_TIMEOUT
    EVENT_INACTIVITY_TIMEOUT = SuiteEventHandler.EVENT_INACTIVITY_TIMEOUT
    EVENT_STALLED = SuiteEventHandler.EVENT_STALLED

    # Intervals in seconds
    INTERVAL_MAIN_LOOP = 1.0
    INTERVAL_MAIN_LOOP_QUICK = 0.5
    INTERVAL_STOP_KILL = 10.0
    INTERVAL_STOP_PROCESS_POOL_EMPTY = 0.5
    INTERVAL_AUTO_RESTART_ERROR = 5

    START_MESSAGE_PREFIX = 'Suite server: '
    START_MESSAGE_TMPL = (
        START_MESSAGE_PREFIX +
        'url=%(comms_method)s://%(host)s:%(port)s/ pid=%(pid)s')

    AUTO_STOP_RESTART_NORMAL = 'stop and restart'
    AUTO_STOP_RESTART_FORCE = 'stop'

    # Dependency negotiation etc. will run after these commands
    PROC_CMDS = (
        'release_suite',
        'release_tasks',
        'kill_tasks',
        'reset_task_states',
        'spawn_tasks',
        'trigger_tasks',
        'nudge',
        'insert_tasks',
        'reload_suite'
    )

    def __init__(self, is_restart, options, args):
        self.options = options
        self.profiler = Profiler(self.options.profile_mode)
        self.suite_srv_files_mgr = SuiteSrvFilesManager()
        self.suite = args[0]
        self.uuid_str = SchedulerUUID()
        self.suite_dir = self.suite_srv_files_mgr.get_suite_source_dir(
            self.suite)
        self.suiterc = self.suite_srv_files_mgr.get_suite_rc(self.suite)
        self.suiterc_update_time = None
        # For user-defined batch system handlers
        sys.path.append(os.path.join(self.suite_dir, 'python'))
        sys.path.append(os.path.join(self.suite_dir, 'lib', 'python'))
        self.suite_run_dir = glbl_cfg().get_derived_host_item(
            self.suite, 'suite run directory')
        self.suite_work_dir = glbl_cfg().get_derived_host_item(
            self.suite, 'suite work directory')
        self.suite_share_dir = glbl_cfg().get_derived_host_item(
            self.suite, 'suite share directory')
        self.suite_log_dir = glbl_cfg().get_derived_host_item(
            self.suite, 'suite log directory')

        self.config = None

        self.is_restart = is_restart
        self.cli_initial_point_string = None
        self.cli_start_point_string = None
        start_point_str = None
        if len(args) > 1:
            start_point_str = args[1]
        if getattr(self.options, 'warm', None):
            self.cli_start_point_string = start_point_str
        else:
            self.cli_initial_point_string = start_point_str
        self.template_vars = load_template_vars(
            self.options.templatevars, self.options.templatevars_file)

        self.run_mode = self.options.run_mode

        self.owner = get_user()
        self.host = get_host()

        self.is_updated = False
        self.is_stalled = False

        self.contact_data = None

        # initialize some items in case of early shutdown
        # (required in the shutdown() method)
        self.state_summary_mgr = None
        self.pool = None
        self.proc_pool = None
        self.task_job_mgr = None
        self.task_events_mgr = None
        self.suite_event_handler = None
        self.server = None
        self.port = None
        self.command_queue = None
        self.message_queue = None
        self.ext_trigger_queue = None

        self._profile_amounts = {}
        self._profile_update_times = {}

        self.stop_mode = None

        # TODO - stop task should be held by the task pool.
        self.stop_task = None
        self.stop_point = None
        self.stop_clock_time = None  # When not None, in Unix time
        self.stop_clock_time_string = None  # Human-readable format.

        self.initial_point = None
        self.start_point = None
        self.final_point = None
        self.pool_hold_point = None
        self.suite_timer_timeout = 0.0
        self.suite_timer_active = False
        self.suite_inactivity_timeout = 0.0
        self.already_inactive = False

        self.time_next_kill = None
        self.already_timed_out = False

        self.suite_db_mgr = SuiteDatabaseManager(
            self.suite_srv_files_mgr.get_suite_srv_dir(self.suite),  # pri_d
            os.path.join(self.suite_run_dir, 'log'))                 # pub_d
        self.broadcast_mgr = BroadcastMgr(self.suite_db_mgr)
        self.xtrigger_mgr = XtriggerManager(
            self.suite, self.owner, self.broadcast_mgr, self.suite_run_dir,
            self.suite_share_dir, self.suite_work_dir, self.suite_dir)
        self.ref_test_allowed_failures = []
        # Last 10 durations (in seconds) of the main loop
        self.main_loop_intervals = deque(maxlen=10)

        self.can_auto_stop = True
        self.previous_profile_point = 0
        self.count = 0

        # health check settings
        self.time_next_health_check = None
        self.auto_restart_mode = None
        self.auto_restart_time = None

    def start(self):
        """Start the server."""
        self._start_print_blurb()

        glbl_cfg().create_cylc_run_tree(self.suite)

        if self.is_restart:
            self.suite_db_mgr.restart_upgrade()

        try:
            if not self.options.no_detach:
                daemonize(self)
            self._setup_suite_logger()
            self.server = SuiteRuntimeServer(self)
            port_range = glbl_cfg().get(['suite servers', 'run ports'])
            self.server.start(port_range[0], port_range[-1])
            self.port = self.server.port
            self.configure()
            self.profiler.start()
            self.run()
        except SchedulerStop as exc:
            # deliberate stop
            self.shutdown(exc)
            if self.auto_restart_mode == self.AUTO_STOP_RESTART_NORMAL:
                self.suite_auto_restart()
            self.close_logs()

        except SchedulerError as exc:
            self.shutdown(exc)
            self.close_logs()
            sys.exit(1)

        except KeyboardInterrupt as exc:
            try:
                self.shutdown(str(exc))
            except Exception as exc2:
                # In case of exceptions in the shutdown method itself.
                LOG.exception(exc2)
                sys.exit(1)
            self.close_logs()

        except Exception as exc:
            LOG.exception(exc)
            LOG.error("error caught: cleaning up before exit")
            try:
                self.shutdown('ERROR: ' + str(exc))
            except Exception as exc2:
                # In case of exceptions in the shutdown method itself
                LOG.exception(exc2)
            self.close_logs()
            raise exc

        else:
            # main loop ends (not used?)
            self.shutdown()
            self.close_logs()

    def close_logs(self):
        """Close the Cylc logger."""
        LOG.info("DONE")  # main thread exit
        self.profiler.stop()
        for handler in LOG.handlers:
            try:
                handler.close()
            except IOError:
                # suppress traceback which `logging` might try to write to the
                # log we are trying to close
                pass

    @staticmethod
    def _start_print_blurb():
        """Print copyright and license information."""
        logo = (
            "            ._.       \n"
            "            | |       \n"
            "._____._. ._| |_____. \n"
            "| .___| | | | | .___| \n"
            "| !___| !_! | | !___. \n"
            "!_____!___. |_!_____! \n"
            "      .___! |         \n"
            "      !_____!         \n"
        )
        cylc_license = """
The Cylc Suite Engine [%s]
Copyright (C) 2008-2019 NIWA
& British Crown (Met Office) & Contributors.
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
This program comes with ABSOLUTELY NO WARRANTY.
It is free software, you are welcome to
redistribute it under certain conditions;
see `COPYING' in the Cylc source distribution.

  """ % CYLC_VERSION

        logo_lines = logo.splitlines()
        license_lines = cylc_license.splitlines()
        lmax = max(len(line) for line in license_lines)
        print(('\n'.join((
            ('{0} {1: ^%s}' % lmax).format(*x)
            for x in zip(logo_lines, license_lines)))))

    def _setup_suite_logger(self):
        """Set up logger for suite."""
        # Remove stream handlers in detach mode
        if not self.options.no_detach:
            while LOG.handlers:
                LOG.handlers[0].close()
                LOG.removeHandler(LOG.handlers[0])
        LOG.addHandler(
            TimestampRotatingFileHandler(self.suite, self.options.no_detach))

    def configure(self):
        """Configure suite server program."""
        self.profiler.log_memory("scheduler.py: start configure")

        # Start up essential services
        self.proc_pool = SubProcPool()
        self.state_summary_mgr = StateSummaryMgr()
        self.command_queue = Queue()
        self.message_queue = Queue()
        self.ext_trigger_queue = Queue()
        self.suite_event_handler = SuiteEventHandler(self.proc_pool)
        self.task_events_mgr = TaskEventsManager(
            self.suite, self.proc_pool, self.suite_db_mgr, self.broadcast_mgr)
        self.task_events_mgr.uuid_str = self.uuid_str
        self.task_job_mgr = TaskJobManager(
            self.suite, self.proc_pool, self.suite_db_mgr,
            self.suite_srv_files_mgr, self.task_events_mgr)
        self.task_job_mgr.task_remote_mgr.uuid_str = self.uuid_str

        if self.is_restart:
            # This logic handles the lack of initial cycle point in "suite.rc".
            # Things that can't change on suite reload.
            pri_dao = self.suite_db_mgr.get_pri_dao()
            pri_dao.select_suite_params(self._load_suite_params_1)
            # Configure contact data only after loading UUID string
            self.configure_contact()
            pri_dao.select_suite_template_vars(self._load_template_vars)
            # Take checkpoint and commit immediately so that checkpoint can be
            # copied to the public database.
            pri_dao.take_checkpoints("restart")
            pri_dao.execute_queued_items()
            n_restart = pri_dao.select_checkpoint_id_restart_count()
        else:
            self.configure_contact()
            n_restart = 0

        # Copy local python modules from source to run directory
        for sub_dir in ["python", os.path.join("lib", "python")]:
            # TODO - eventually drop the deprecated "python" sub-dir.
            suite_py = os.path.join(self.suite_dir, sub_dir)
            if (os.path.realpath(self.suite_dir) !=
                    os.path.realpath(self.suite_run_dir) and
                    os.path.isdir(suite_py)):
                suite_run_py = os.path.join(self.suite_run_dir, sub_dir)
                try:
                    rmtree(suite_run_py)
                except OSError:
                    pass
                copytree(suite_py, suite_run_py)

        self.profiler.log_memory("scheduler.py: before load_suiterc")
        self.load_suiterc()
        self.profiler.log_memory("scheduler.py: after load_suiterc")

        self.suite_db_mgr.on_suite_start(self.is_restart)
        if self.config.cfg['scheduling']['hold after point']:
            self.pool_hold_point = get_point(
                self.config.cfg['scheduling']['hold after point'])

        if self.options.hold_point_string:
            self.pool_hold_point = get_point(
                self.options.hold_point_string)

        if self.pool_hold_point:
            LOG.info("Suite will hold after %s" % self.pool_hold_point)

        reqmode = self.config.cfg['cylc']['required run mode']
        if reqmode:
            if reqmode != self.run_mode:
                raise SchedulerError(
                    'this suite requires the %s run mode' % reqmode)

        self.broadcast_mgr.linearized_ancestors.update(
            self.config.get_linearized_ancestors())
        self.task_events_mgr.mail_interval = self._get_cylc_conf(
            "task event mail interval")
        self.task_events_mgr.mail_footer = self._get_events_conf("mail footer")
        self.task_events_mgr.suite_url = self.config.cfg['meta']['URL']
        self.task_events_mgr.suite_cfg = self.config.cfg['meta']
        if self.options.genref or self.options.reftest:
            self.configure_reftest()

        log_extra = {TimestampRotatingFileHandler.FILE_HEADER_FLAG: True}
        log_extra_num = {
            TimestampRotatingFileHandler.FILE_HEADER_FLAG: True,
            TimestampRotatingFileHandler.FILE_NUM: 1}
        LOG.info(
            self.START_MESSAGE_TMPL % {
                'comms_method': 'tcp',
                'host': self.host,
                'port': self.server.port,
                'pid': os.getpid()},
            extra=log_extra,
        )
        LOG.info('Run: (re)start=%d log=%d', n_restart, 1, extra=log_extra_num)
        LOG.info('Cylc version: %s', CYLC_VERSION, extra=log_extra)
        # Note that the following lines must be present at the top of
        # the suite log file for use in reference test runs:
        LOG.info('Run mode: %s', self.run_mode, extra=log_extra)
        LOG.info('Initial point: %s', self.initial_point, extra=log_extra)
        if self.start_point != self.initial_point:
            LOG.info('Start point: %s', self.start_point, extra=log_extra)
        LOG.info('Final point: %s', self.final_point, extra=log_extra)

        self.pool = TaskPool(
            self.config, self.final_point, self.suite_db_mgr,
            self.task_events_mgr, self.proc_pool, self.xtrigger_mgr)

        self.profiler.log_memory("scheduler.py: before load_tasks")
        if self.is_restart:
            self.load_tasks_for_restart()
        else:
            self.load_tasks_for_run()
        self.profiler.log_memory("scheduler.py: after load_tasks")

        self.suite_db_mgr.put_suite_params(self)
        self.suite_db_mgr.put_suite_template_vars(self.template_vars)
        self.suite_db_mgr.put_runtime_inheritance(self.config)

        self.already_timed_out = False
        self.set_suite_timer()

        self.already_inactive = False
        if self._get_events_conf(self.EVENT_INACTIVITY_TIMEOUT):
            self.set_suite_inactivity_timer()

        self.profiler.log_memory("scheduler.py: end configure")

    def load_tasks_for_run(self):
        """Load tasks for a new run."""
        if self.start_point is not None:
            if self.options.warm:
                LOG.info('Warm Start %s' % self.start_point)
            else:
                LOG.info('Cold Start %s' % self.start_point)

        task_list = self.filter_initial_task_list(
            self.config.get_task_name_list())

        for name in task_list:
            if self.start_point is None:
                # No start cycle point at which to load cycling tasks.
                continue
            try:
                self.pool.add_to_runahead_pool(TaskProxy(
                    self.config.get_taskdef(name), self.start_point,
                    is_startup=True))
            except TaskProxySequenceBoundsError as exc:
                LOG.debug(str(exc))
                continue

    def load_tasks_for_restart(self):
        """Load tasks for restart."""
        self.suite_db_mgr.pri_dao.select_suite_params(
            self._load_suite_params_2, self.options.checkpoint)
        if self.cli_start_point_string:
            self.start_point = self.cli_start_point_string
        self.suite_db_mgr.pri_dao.select_broadcast_states(
            self.broadcast_mgr.load_db_broadcast_states,
            self.options.checkpoint)
        self.suite_db_mgr.pri_dao.select_task_job_run_times(
            self._load_task_run_times)
        self.suite_db_mgr.pri_dao.select_task_pool_for_restart(
            self.pool.load_db_task_pool_for_restart, self.options.checkpoint)
        self.suite_db_mgr.pri_dao.select_task_action_timers(
            self.pool.load_db_task_action_timers)
        self.suite_db_mgr.pri_dao.select_xtriggers_for_restart(
            self.xtrigger_mgr.load_xtrigger_for_restart)

        # Re-initialise run directory for user@host for each submitted and
        # running tasks.
        # Note: tasks should all be in the runahead pool at this point.
        auths = set()
        for itask in self.pool.get_rh_tasks():
            if itask.state.status in TASK_STATUSES_ACTIVE:
                auths.add((itask.task_host, itask.task_owner))
        while auths:
            for host, owner in auths.copy():
                if self.task_job_mgr.task_remote_mgr.remote_init(
                        host, owner) is not None:
                    auths.remove((host, owner))
            if auths:
                sleep(1.0)
                # Remote init is done via process pool
                self.proc_pool.process()
        self.command_poll_tasks()

    def _load_suite_params_2(self, row_idx, row):
        """Load previous initial/final cycle point."""
        if row_idx == 0:
            LOG.info("LOADING suite parameters")
        key, value = row
        if key == "is_held":
            self.pool.is_held = bool(value)
            LOG.info("+ hold suite = %s" % (bool(value),))
            return
        for key_str, self_attr, option_ignore_attr in [
                ("initial", "start_point", "ignore_start_point"),
                ("final", "stop_point", "ignore_stop_point")]:
            if key != key_str + "_point" or value is None or value == 'None':
                continue
            # the suite_params table prescribes a start/stop cycle
            # (else we take whatever the suite.rc file gives us)
            point = get_point(value)
            my_point = getattr(self, self_attr)
            if getattr(self.options, option_ignore_attr):
                # ignore it and take whatever the suite.rc file gives us
                if my_point is not None:
                    LOG.warning(
                        "I'm ignoring the old " + key_str +
                        " cycle point as requested,\n"
                        "but I can't ignore the one set"
                        " on the command line or in the suite definition.")
            elif my_point is not None:
                # Given in the suite.rc file
                if my_point != point:
                    LOG.warning(
                        "old %s cycle point %s, overriding suite.rc %s" %
                        (key_str, point, my_point))
                    setattr(self, self_attr, point)
            else:
                # reinstate from old
                setattr(self, self_attr, point)
            LOG.info("+ %s cycle point = %s" % (key_str, value))

    def _load_task_run_times(self, row_idx, row):
        """Load run times of previously succeeded task jobs."""
        if row_idx == 0:
            LOG.info("LOADING task run times")
        name, run_times_str = row
        try:
            taskdef = self.config.taskdefs[name]
            maxlen = TaskDef.MAX_LEN_ELAPSED_TIMES
            for run_time_str in run_times_str.rsplit(",", maxlen)[-maxlen:]:
                run_time = int(run_time_str)
                taskdef.elapsed_times.append(run_time)
            LOG.info("+ %s: %s" % (
                name, ",".join(str(s) for s in taskdef.elapsed_times)))
        except (KeyError, ValueError, AttributeError):
            return

    def process_queued_task_messages(self):
        """Handle incoming task messages for each task proxy."""
        messages = {}
        while self.message_queue.qsize():
            try:
                task_job, event_time, severity, message = (
                    self.message_queue.get(block=False))
            except Empty:
                break
            self.message_queue.task_done()
            if '/' in task_job:  # cycle/task-name/submit-num
                cycle, task_name, submit_num = task_job.split('/', 2)
                task_id = TaskID.get(task_name, cycle)
                submit_num = int(submit_num, 10)
            else:  # back compat: task-name.cycle
                task_id = task_job
                submit_num = None
            messages.setdefault(task_id, [])
            messages[task_id].append(
                (submit_num, event_time, severity, message))
        # Note on to_poll_tasks: If an incoming message is going to cause a
        # reverse change to task state, it is desirable to confirm this by
        # polling.
        to_poll_tasks = []
        for itask in self.pool.get_tasks():
            message_items = messages.get(itask.identity)
            if message_items is None:
                continue
            should_poll = False
            for submit_num, event_time, severity, message in message_items:
                if self.task_events_mgr.process_message(
                        itask, severity, message, event_time,
                        self.task_events_mgr.INCOMING_FLAG, submit_num):
                    should_poll = True
            if should_poll:
                to_poll_tasks.append(itask)
        self.task_job_mgr.poll_task_jobs(
            self.suite, to_poll_tasks, poll_succ=True)

    def process_command_queue(self):
        """Process queued commands."""
        qsize = self.command_queue.qsize()
        if qsize > 0:
            log_msg = 'Processing ' + str(qsize) + ' queued command(s)'
        else:
            return

        while True:
            try:
                name, args, kwargs = self.command_queue.get(False)
            except Empty:
                break
            args_string = ', '.join(str(a) for a in args)
            cmdstr = name + '(' + args_string
            kwargs_string = ', '.join(
                ('%s=%s' % (key, value) for key, value in kwargs.items()))
            if kwargs_string and args_string:
                cmdstr += ', '
            cmdstr += kwargs_string + ')'
            log_msg += '\n+\t' + cmdstr
            try:
                n_warnings = getattr(self, "command_%s" % name)(
                    *args, **kwargs)
            except SchedulerStop:
                LOG.info('Command succeeded: ' + cmdstr)
                raise
            except Exception as exc:
                # Don't let a bad command bring the suite down.
                LOG.warning(traceback.format_exc())
                LOG.warning(str(exc))
                LOG.warning('Command failed: ' + cmdstr)
            else:
                if n_warnings:
                    LOG.info(
                        'Command succeeded with %s warning(s): %s' %
                        (n_warnings, cmdstr))
                else:
                    LOG.info('Command succeeded: ' + cmdstr)
                self.is_updated = True
                if name in self.PROC_CMDS:
                    self.task_events_mgr.pflag = True
            self.command_queue.task_done()
        LOG.info(log_msg)

    def _task_type_exists(self, name_or_id):
        """Does a task name or id match a known task type in this suite?"""
        name = name_or_id
        if TaskID.is_valid_id(name_or_id):
            name = TaskID.split(name_or_id)[0]
        return name in self.config.get_task_name_list()

    @staticmethod
    def get_standardised_point_string(point_string):
        """Return a standardised point string.

        Used to process incoming command arguments.
        """
        try:
            point_string = standardise_point_string(point_string)
        except PointParsingError as exc:
            # (This is only needed to raise a clearer error message).
            raise ValueError(
                "Invalid cycle point: %s (%s)" % (point_string, exc))
        return point_string

    def get_standardised_point(self, point_string):
        """Return a standardised point."""
        return get_point(self.get_standardised_point_string(point_string))

    def get_standardised_taskid(self, task_id):
        """Return task ID with standardised cycle point."""
        name, point_string = TaskID.split(task_id)
        return TaskID.get(
            name, self.get_standardised_point_string(point_string))

    def info_get_task_jobfile_path(self, task_id):
        """Return task job file path."""
        name, point = TaskID.split(task_id)
        return get_task_job_log(
            self.suite, point, name, suffix=JOB_LOG_JOB)

    def info_get_suite_info(self):
        """Return a dict containing the suite title and description."""
        return self.config.cfg['meta']

    def info_get_suite_state_summary(self):
        """Return the global, task, and family summary data structures."""
        return self.state_summary_mgr.get_state_summary()

    def info_get_task_info(self, names):
        """Return info of a task."""
        results = {}
        for name in names:
            try:
                results[name] = self.config.describe(name)
            except KeyError:
                results[name] = {}
        return results

    def info_get_graph_raw(self, cto, ctn, group_nodes=None,
                           ungroup_nodes=None,
                           ungroup_recursive=False, group_all=False,
                           ungroup_all=False):
        """Return raw graph."""
        return (
            self.config.get_graph_raw(
                cto, ctn, group_nodes, ungroup_nodes, ungroup_recursive,
                group_all, ungroup_all),
            self.config.suite_polling_tasks,
            self.config.leaves,
            self.config.feet)

    def info_get_task_requisites(self, items, list_prereqs=False):
        """Return prerequisites of a task."""
        return self.pool.get_task_requisites(items, list_prereqs=list_prereqs)

    def info_ping_task(self, task_id, exists_only=False):
        """Return True if task exists and running."""
        task_id = self.get_standardised_taskid(task_id)
        return self.pool.ping_task(task_id, exists_only)

    def command_set_stop_cleanly(self, kill_active_tasks=False):
        """Stop job submission and set the flag for clean shutdown."""
        self._set_stop()
        if kill_active_tasks:
            self.time_next_kill = time()

    def command_stop_now(self, terminate=False):
        """Shutdown immediately."""
        if terminate:
            self._set_stop(TaskPool.STOP_REQUEST_NOW_NOW)
        else:
            self._set_stop(TaskPool.STOP_REQUEST_NOW)

    def _set_stop(self, stop_mode=None):
        """Set shutdown mode."""
        self.proc_pool.set_stopping()
        if stop_mode is None:
            stop_mode = TaskPool.STOP_REQUEST_CLEAN
        self.stop_mode = stop_mode

    def command_set_stop_after_point(self, point_string):
        """Set stop after ... point."""
        self.set_stop_point(self.get_standardised_point_string(point_string))

    def command_set_stop_after_clock_time(self, arg):
        """Set stop after clock time.

        format: ISO 8601 compatible or YYYY/MM/DD-HH:mm (backwards comp.)
        """
        parser = TimePointParser()
        try:
            stop_point = parser.parse(arg)
        except ValueError as exc:
            try:
                stop_point = parser.strptime(arg, "%Y/%m/%d-%H:%M")
            except ValueError:
                raise exc  # Raise the first (prob. more relevant) ValueError.
        stop_time_in_epoch_seconds = int(stop_point.get(
            "seconds_since_unix_epoch"))
        self.set_stop_clock(stop_time_in_epoch_seconds, str(stop_point))

    def command_set_stop_after_task(self, task_id):
        """Set stop after a task."""
        task_id = self.get_standardised_taskid(task_id)
        if TaskID.is_valid_id(task_id):
            self.set_stop_task(task_id)

    def command_release_tasks(self, items):
        """Release tasks."""
        return self.pool.release_tasks(items)

    def command_poll_tasks(self, items=None, poll_succ=False):
        """Poll pollable tasks or a task/family if options are provided.

        Don't poll succeeded tasks unless poll_succ is True.

        """
        if self.run_mode == 'simulation':
            return
        itasks, bad_items = self.pool.filter_task_proxies(items)
        self.task_job_mgr.poll_task_jobs(self.suite, itasks,
                                         poll_succ=poll_succ)
        return len(bad_items)

    def command_kill_tasks(self, items=None):
        """Kill all tasks or a task/family if options are provided."""
        itasks, bad_items = self.pool.filter_task_proxies(items)
        if self.run_mode == 'simulation':
            for itask in itasks:
                if itask.state.status in TASK_STATUSES_ACTIVE:
                    itask.state.reset_state(TASK_STATUS_FAILED)
            return len(bad_items)
        self.task_job_mgr.kill_task_jobs(self.suite, itasks)
        return len(bad_items)

    def command_release_suite(self):
        """Release all task proxies in the suite."""
        self.release_suite()

    def command_hold_tasks(self, items):
        """Hold selected task proxies in the suite."""
        return self.pool.hold_tasks(items)

    def command_hold_suite(self):
        """Hold all task proxies in the suite."""
        self.hold_suite()

    def command_hold_after_point_string(self, point_string):
        """Hold tasks AFTER this point (itask.point > point)."""
        point = self.get_standardised_point(point_string)
        self.hold_suite(point)
        LOG.info(
            "The suite will pause when all tasks have passed %s" % point)

    @staticmethod
    def command_set_verbosity(lvl):
        """Set suite verbosity."""
        try:
            LOG.setLevel(int(lvl))
        except (TypeError, ValueError):
            return
        cylc.flags.verbose = bool(LOG.isEnabledFor(logging.INFO))
        cylc.flags.debug = bool(LOG.isEnabledFor(logging.DEBUG))
        return True, 'OK'

    def command_remove_tasks(self, items, spawn=False):
        """Remove tasks."""
        return self.pool.remove_tasks(items, spawn)

    def command_insert_tasks(self, items, stop_point_string=None,
                             no_check=False):
        """Insert tasks."""
        return self.pool.insert_tasks(items, stop_point_string, no_check)

    def command_nudge(self):
        """Cause the task processing loop to be invoked"""
        self.task_events_mgr.pflag = True

    def command_reload_suite(self):
        """Reload suite configuration."""
        LOG.info("Reloading the suite definition.")
        old_tasks = set(self.config.get_task_name_list())
        self.suite_db_mgr.checkpoint("reload-init")
        self.load_suiterc(is_reload=True)
        self.broadcast_mgr.linearized_ancestors = (
            self.config.get_linearized_ancestors())
        self.suite_db_mgr.put_runtime_inheritance(self.config)
        if self.stop_point is None:
            stop_point = self.final_point
        else:
            stop_point = self.stop_point
        self.pool.set_do_reload(self.config, stop_point)
        self.task_events_mgr.mail_interval = self._get_cylc_conf(
            "task event mail interval")
        self.task_events_mgr.mail_footer = self._get_events_conf("mail footer")

        # Log tasks that have been added by the reload, removed tasks are
        # logged by the TaskPool.
        add = set(self.config.get_task_name_list()) - old_tasks
        for task in add:
            LOG.warning("Added task: '%s'" % (task,))

        if self.options.genref or self.options.reftest:
            self.configure_reftest(recon=True)
        self.suite_db_mgr.put_suite_params(self)
        self.is_updated = True

    def set_suite_timer(self):
        """Set suite's timeout timer."""
        timeout = self._get_events_conf(self.EVENT_TIMEOUT)
        if timeout is None:
            return
        self.suite_timer_timeout = time() + timeout
        LOG.debug(
            "%s suite timer starts NOW: %s",
            get_seconds_as_interval_string(timeout),
            get_current_time_string())
        self.suite_timer_active = True

    def set_suite_inactivity_timer(self):
        """Set suite's inactivity timer."""
        self.suite_inactivity_timeout = time() + (
            self._get_events_conf(self.EVENT_INACTIVITY_TIMEOUT)
        )
        LOG.debug(
            "%s suite inactivity timer starts NOW: %s",
            get_seconds_as_interval_string(
                self._get_events_conf(self.EVENT_INACTIVITY_TIMEOUT)),
            get_current_time_string())

    def configure_contact(self):
        """Create contact file."""
        # Make sure another suite of the same name has not started while this
        # one is starting
        self.suite_srv_files_mgr.detect_old_contact_file(self.suite)
        # Get "pid,args" process string with "ps"
        pid_str = str(os.getpid())
        proc = Popen(
            ['ps', self.suite_srv_files_mgr.PS_OPTS, pid_str],
            stdin=open(os.devnull), stdout=PIPE, stderr=PIPE)
        out, err = (f.decode() for f in proc.communicate())
        ret_code = proc.wait()
        process_str = None
        for line in out.splitlines():
            if line.split(None, 1)[0].strip() == pid_str:
                process_str = line.strip()
                break
        if ret_code or not process_str:
            raise SchedulerError(
                'cannot get process "args" from "ps": %s' % err)
        # Write suite contact file.
        # Preserve contact data in memory, for regular health check.
        mgr = self.suite_srv_files_mgr
        contact_data = {
            mgr.KEY_API: str(self.server.API),
            mgr.KEY_DIR_ON_SUITE_HOST: os.environ['CYLC_DIR'],
            mgr.KEY_HOST: self.host,
            mgr.KEY_NAME: self.suite,
            mgr.KEY_OWNER: self.owner,
            mgr.KEY_PORT: str(self.server.port),
            mgr.KEY_PROCESS: process_str,
            mgr.KEY_SSH_USE_LOGIN_SHELL: str(glbl_cfg().get_host_item(
                'use login shell')),
            mgr.KEY_SUITE_RUN_DIR_ON_SUITE_HOST: self.suite_run_dir,
            mgr.KEY_TASK_MSG_MAX_TRIES: str(glbl_cfg().get(
                ['task messaging', 'maximum number of tries'])),
            mgr.KEY_TASK_MSG_RETRY_INTVL: str(float(glbl_cfg().get(
                ['task messaging', 'retry interval']))),
            mgr.KEY_TASK_MSG_TIMEOUT: str(float(glbl_cfg().get(
                ['task messaging', 'connection timeout']))),
            mgr.KEY_UUID: self.uuid_str.value,
            mgr.KEY_VERSION: CYLC_VERSION}
        try:
            mgr.dump_contact_file(self.suite, contact_data)
        except IOError as exc:
            raise SchedulerError(
                'cannot write suite contact file: %s: %s' %
                (mgr.get_contact_file(self.suite), exc))
        else:
            self.contact_data = contact_data

    def load_suiterc(self, is_reload=False):
        """Load, and log the suite definition."""
        # Local suite environment set therein.
        self.config = SuiteConfig(
            self.suite, self.suiterc, self.template_vars,
            run_mode=self.run_mode,
            cli_initial_point_string=self.cli_initial_point_string,
            cli_start_point_string=self.cli_start_point_string,
            cli_final_point_string=self.options.final_point_string,
            is_reload=is_reload,
            xtrigger_mgr=self.xtrigger_mgr,
            mem_log_func=self.profiler.log_memory,
            output_fname=os.path.join(
                self.suite_run_dir,
                self.suite_srv_files_mgr.FILE_BASE_SUITE_RC + '.processed'),
            run_dir=self.suite_run_dir,
            log_dir=self.suite_log_dir,
            work_dir=self.suite_work_dir,
            share_dir=self.suite_share_dir,
        )
        self.suiterc_update_time = time()
        # Dump the loaded suiterc for future reference.
        cfg_logdir = glbl_cfg().get_derived_host_item(
            self.suite, 'suite config log directory')
        time_str = get_current_time_string(
            override_use_utc=True, use_basic_format=True,
            display_sub_seconds=False
        )
        if is_reload:
            load_type = "reload"
        elif self.is_restart:
            load_type = "restart"
        else:
            load_type = "run"
        base_name = "%s-%s.rc" % (time_str, load_type)
        file_name = os.path.join(cfg_logdir, base_name)
        try:
            with open(file_name, "wb") as handle:
                handle.write(("# cylc-version: %s\n" % CYLC_VERSION).encode())
                printcfg(self.config.cfg, none_str=None, handle=handle)
        except IOError as exc:
            LOG.exception(exc)
            raise SchedulerError("Unable to log the loaded suite definition")
        # Initial and final cycle times - command line takes precedence.
        # self.config already alters the 'initial cycle point' for CLI.
        self.initial_point = self.config.initial_point
        self.start_point = self.config.start_point
        self.final_point = self.config.final_point

        if not self.initial_point and not self.is_restart:
            LOG.warning('No initial cycle point provided - no cycling tasks '
                        'will be loaded.')

        if self.run_mode != self.config.run_mode:
            self.run_mode = self.config.run_mode

        # Pass static cylc and suite variables to job script generation code
        self.task_job_mgr.job_file_writer.set_suite_env({
            'CYLC_UTC': str(get_utc_mode()),
            'CYLC_DEBUG': str(cylc.flags.debug).lower(),
            'CYLC_VERBOSE': str(cylc.flags.verbose).lower(),
            'CYLC_SUITE_NAME': self.suite,
            'CYLC_CYCLING_MODE': str(
                self.config.cfg['scheduling']['cycling mode']),
            'CYLC_SUITE_INITIAL_CYCLE_POINT': str(self.initial_point),
            'CYLC_SUITE_FINAL_CYCLE_POINT': str(self.final_point),
        })

    def _load_suite_params_1(self, _, row):
        """Load previous initial cycle point or (warm) start cycle point.

        For restart, these may be missing from "suite.rc", but was specified as
        a command line argument on cold/warm start.

        """
        key, value = row
        if key == 'initial_point':
            self.cli_initial_point_string = value
            self.task_events_mgr.pflag = True
        elif key in ['start_point', 'warm_point']:
            # 'warm_point' for back compat <= 7.6.X
            self.cli_start_point_string = value
            self.task_events_mgr.pflag = True
        elif key == 'uuid_str':
            self.uuid_str.value = value

    def _load_template_vars(self, _, row):
        """Load suite start up template variables."""
        key, value = row
        # Command line argument takes precedence
        if key not in self.template_vars:
            self.template_vars[key] = value

    def configure_reftest(self, recon=False):
        """Configure the reference test."""
        if self.options.genref:
            self.config.cfg['cylc']['log resolved dependencies'] = True
            reference_log = os.path.join(self.config.fdir, 'reference.log')
            LOG.addHandler(ReferenceLogFileHandler(reference_log))
        elif self.options.reftest:
            rtc = self.config.cfg['cylc']['reference test']
            req = rtc['required run mode']
            if req and req != self.run_mode:
                raise SchedulerError(
                    'suite allows only ' + req + ' reference tests')
            handlers = self._get_events_conf('shutdown handler')
            if handlers:
                LOG.warning('shutdown handlers replaced by reference test')
            self.config.cfg['cylc']['events']['shutdown handler'] = [
                rtc['suite shutdown event handler']]
            self.config.cfg['cylc']['log resolved dependencies'] = True
            self.config.cfg['cylc']['events'][
                'abort if shutdown handler fails'] = True
            if not recon:
                spec = LogSpec(os.path.join(self.config.fdir, 'reference.log'))
                self.initial_point = get_point(spec.get_initial_point_string())
                self.start_point = get_point(
                    spec.get_start_point_string()) or self.initial_point
                self.final_point = get_point(spec.get_final_point_string())
            self.ref_test_allowed_failures = rtc['expected task failures']
            if (not rtc['allow task failures'] and
                    not self.ref_test_allowed_failures):
                self.config.cfg['cylc']['abort if any task fails'] = True
            self.config.cfg['cylc']['events']['abort on timeout'] = True
            timeout = rtc[self.run_mode + ' mode suite timeout']
            if not timeout:
                raise SchedulerError(
                    'timeout not defined for %s reference tests' % (
                        self.run_mode))
            self.config.cfg['cylc']['events'][self.EVENT_TIMEOUT] = (
                timeout)

    def run_event_handlers(self, event, reason):
        """Run a suite event handler.

        Run suite events in simulation and dummy mode ONLY if enabled.
        """
        try:
            if (self.run_mode in ['simulation', 'dummy'] and
                    self.config.cfg['cylc']['simulation'][
                        'disable suite event handlers']):
                return
        except KeyError:
            pass
        try:
            self.suite_event_handler.handle(self.config, SuiteEventContext(
                event, reason, self.suite, self.uuid_str, self.owner,
                self.host, self.server.port))
        except SuiteEventError as exc:
            if event == self.EVENT_SHUTDOWN and self.options.reftest:
                LOG.error('SUITE REFERENCE TEST FAILED')
            raise SchedulerError(exc.args[0])
        else:
            if event == self.EVENT_SHUTDOWN and self.options.reftest:
                LOG.info('SUITE REFERENCE TEST PASSED')

    def initialise_scheduler(self):
        """Prelude to the main scheduler loop.

        Determines whether suite is held or should be held.
        Determines whether suite can be auto shutdown.
        Begins profile logs if needed.
        """
        if self.pool_hold_point is not None:
            self.hold_suite(self.pool_hold_point)
        if self.options.start_held:
            LOG.info("Held on start-up (no tasks will be submitted)")
            self.hold_suite()
        self.run_event_handlers(self.EVENT_STARTUP, 'suite starting')
        self.profiler.log_memory("scheduler.py: begin run while loop")
        self.time_next_health_check = None
        self.is_updated = True
        if self.options.profile_mode:
            self.previous_profile_point = 0
            self.count = 0
        self.can_auto_stop = (
            not self.config.cfg['cylc']['disable automatic shutdown'] and
            not self.options.no_auto_shutdown)

    def process_task_pool(self):
        """Process ALL TASKS whenever something has changed that might
        require renegotiation of dependencies, etc"""
        LOG.debug("BEGIN TASK PROCESSING")
        time0 = time()
        if self._get_events_conf(self.EVENT_INACTIVITY_TIMEOUT):
            self.set_suite_inactivity_timer()
        self.pool.match_dependencies()
        if self.stop_mode is None and self.auto_restart_time is None:
            itasks = self.pool.get_ready_tasks()
            if itasks:
                self.is_updated = True
            done_tasks = self.task_job_mgr.submit_task_jobs(
                self.suite, itasks, self.run_mode == 'simulation')
            if self.config.cfg['cylc']['log resolved dependencies']:
                for itask in done_tasks:
                    deps = itask.state.get_resolved_dependencies()
                    LOG.info('[%s] -triggered off %s', itask, deps)
        for meth in [
                self.pool.spawn_all_tasks,
                self.pool.remove_spent_tasks,
                self.pool.remove_suiciding_tasks]:
            if meth():
                self.is_updated = True

        self.broadcast_mgr.expire_broadcast(self.pool.get_min_point())
        self.xtrigger_mgr.housekeep()
        self.suite_db_mgr.put_xtriggers(self.xtrigger_mgr.sat_xtrig)
        LOG.debug("END TASK PROCESSING (took %s seconds)" % (time() - time0))

    def process_suite_db_queue(self):
        """Update suite DB."""
        try:
            self.suite_db_mgr.process_queued_ops()
        except OSError as exc:
            LOG.exception(exc)
            raise SchedulerError(str(exc))

    def database_health_check(self):
        """If public database is stuck, blast it away by copying the content
        of the private database into it."""
        try:
            self.suite_db_mgr.recover_pub_from_pri()
        except (IOError, OSError) as exc:
            # Something has to be very wrong here, so stop the suite
            raise SchedulerError(str(exc))

    def late_tasks_check(self):
        """Report tasks that are never active and are late."""
        now = time()
        for itask in self.pool.get_tasks():
            if (not itask.is_late and itask.get_late_time() and
                    itask.state.status in TASK_STATUSES_NEVER_ACTIVE and
                    now > itask.get_late_time()):
                msg = '%s (late-time=%s)' % (
                    self.task_events_mgr.EVENT_LATE,
                    time2str(itask.get_late_time()))
                itask.is_late = True
                LOG.warning('[%s] -%s', itask, msg)
                self.task_events_mgr.setup_event_handlers(
                    itask, self.task_events_mgr.EVENT_LATE, msg)
                self.suite_db_mgr.put_insert_task_late_flags(itask)

    def timeout_check(self):
        """Check suite and task timers."""
        self.check_suite_timer()
        if self._get_events_conf(self.EVENT_INACTIVITY_TIMEOUT):
            self.check_suite_inactive()
        # check submission and execution timeout and polling timers
        if self.run_mode != 'simulation':
            self.task_job_mgr.check_task_jobs(self.suite, self.pool)

    def suite_shutdown(self):
        """Determines if the suite can be shutdown yet."""
        if (self.config.cfg['cylc']['abort if any task fails'] and
                self.pool.any_task_failed()):
            # Task failure + abort if any task fails
            self._set_stop(TaskPool.STOP_AUTO_ON_TASK_FAILURE)
        elif self.options.reftest and self.ref_test_allowed_failures:
            # In reference test mode and unexpected failures occurred
            bad_tasks = []
            for itask in self.pool.get_failed_tasks():
                if itask.identity not in self.ref_test_allowed_failures:
                    bad_tasks.append(itask)
            if bad_tasks:
                LOG.error(
                    'Failed task(s) not in allowed failures list:\n%s',
                    '\n'.join('\t%s' % itask.identity for itask in bad_tasks))
                self._set_stop(TaskPool.STOP_AUTO_ON_TASK_FAILURE)

        # Can suite shut down automatically?
        if self.stop_mode is None and (
                self.stop_clock_done() or self.stop_task_done() or
                self.can_auto_stop and self.pool.check_auto_shutdown()):
            self._set_stop(TaskPool.STOP_AUTO)

        # Is the suite ready to shut down now?
        if self.pool.can_stop(self.stop_mode):
            self.update_state_summary()
            self.proc_pool.close()
            if self.stop_mode != TaskPool.STOP_REQUEST_NOW_NOW:
                # Wait for process pool to complete,
                # unless --now --now is requested
                stop_process_pool_empty_msg = (
                    "Waiting for the command process pool to empty" +
                    " for shutdown")
                while self.proc_pool.is_not_done():
                    sleep(self.INTERVAL_STOP_PROCESS_POOL_EMPTY)
                    if stop_process_pool_empty_msg:
                        LOG.info(stop_process_pool_empty_msg)
                        stop_process_pool_empty_msg = None
                    self.proc_pool.process()
                    self.process_command_queue()
            if self.options.profile_mode:
                self.profiler.log_memory(
                    "scheduler.py: end main loop (total loops %d): %s" %
                    (self.count, get_current_time_string()))
            if self.stop_mode == TaskPool.STOP_AUTO_ON_TASK_FAILURE:
                raise SchedulerError(self.stop_mode)
            else:
                raise SchedulerStop(self.stop_mode)
        elif (self.time_next_kill is not None and
              time() > self.time_next_kill):
            self.command_poll_tasks()
            self.command_kill_tasks()
            self.time_next_kill = time() + self.INTERVAL_STOP_KILL

        # Is the suite set to auto stop [+restart] now ...
        if self.auto_restart_time is None or time() < self.auto_restart_time:
            # ... no
            pass
        elif self.auto_restart_mode == self.AUTO_STOP_RESTART_NORMAL:
            # ... yes - wait for local jobs to complete before restarting
            #           * Avoid polling issues see #2843
            #           * Ensure the host can be safely taken down once the
            #             suite has stopped running.
            for itask in self.pool.get_tasks():
                if (itask.state.status in TASK_STATUSES_ACTIVE and
                        itask.summary['batch_sys_name'] and
                        self.task_job_mgr.batch_sys_mgr.is_job_local_to_host(
                            itask.summary['batch_sys_name'])):
                    LOG.info('Waiting for jobs running on localhost to '
                             'complete before attempting restart')
                    break
            else:
                self._set_stop(TaskPool.STOP_REQUEST_NOW_NOW)
        elif self.auto_restart_mode == self.AUTO_STOP_RESTART_FORCE:
            # ... yes - leave local jobs running then stop the suite
            #           (no restart)
            self._set_stop(TaskPool.STOP_REQUEST_NOW)
        else:
            raise SchedulerError('Invalid auto_restart_mode=%s' %
                                 self.auto_restart_mode)

    def suite_auto_restart(self, max_retries=3):
        """Attempt to restart the suite assuming it has already stopped."""
        cmd = ['cylc', 'restart', quote(self.suite)]

        for attempt_no in range(max_retries):
            new_host = HostAppointer(cached=False).appoint_host()
            LOG.info('Attempting to restart on "%s"', new_host)

            # proc will start with current env (incl CYLC_HOME etc)
            proc = Popen(
                cmd + ['--host=%s' % new_host],
                stdin=open(os.devnull), stdout=PIPE, stderr=PIPE)
            if proc.wait():
                msg = 'Could not restart suite'
                if attempt_no < max_retries:
                    msg += (' will retry in %ss'
                            % self.INTERVAL_AUTO_RESTART_ERROR)
                LOG.critical(msg + '. Restart error:\n%s',
                             proc.communicate()[1].decode())
                sleep(self.INTERVAL_AUTO_RESTART_ERROR)
            else:
                LOG.info('Suite now running on "%s".', new_host)
                return True
        LOG.critical(
            'Suite unable to automatically restart after %s tries - '
            'manual restart required.', max_retries)
        return False

    def set_auto_restart(self, restart_delay=None,
                         mode=AUTO_STOP_RESTART_NORMAL):
        """Configure the suite to automatically stop and restart.

        Restart handled by `suite_auto_restart`.

        Args:
            restart_delay (cylc.cfgvalidate.DurationFloat):
                Suite will wait a random period between 0 and
                `restart_delay` seconds before attempting to stop/restart in
                order to avoid multiple suites restarting simultaneously.
            mode (str): Auto stop-restart mode.

        Return:
            bool: False if it is not possible to automatically stop/restart
            the suite due to its configuration/runtime state.
        """
        # Check that the suite isn't already shutting down.
        if self.stop_mode:
            return True

        # Force mode, stop the suite now, don't restart it.
        if mode == self.AUTO_STOP_RESTART_FORCE:
            if self.auto_restart_time:
                LOG.info('Scheduled automatic restart canceled')
            self.auto_restart_time = time()
            self.auto_restart_mode = mode
            return True

        # Check suite isn't already scheduled to auto-stop.
        if self.auto_restart_time is not None:
            return True

        # Check suite is able to be safely restarted.
        if not self.can_auto_restart():
            return False

        LOG.info('Suite will automatically restart on a new host.')
        if restart_delay is not None and restart_delay != 0:
            if restart_delay > 0:
                # Delay shutdown by a random interval to avoid many
                # suites restarting simultaneously.
                from random import random
                shutdown_delay = int(random() * restart_delay)
            else:
                # Un-documented feature, schedule exact restart interval for
                # testing purposes.
                shutdown_delay = abs(int(restart_delay))
            shutdown_time = time() + shutdown_delay
            LOG.info('Suite will restart in %ss (at %s)', shutdown_delay,
                     time2str(shutdown_time))
            self.auto_restart_time = shutdown_time
        else:
            self.auto_restart_time = time()

        self.auto_restart_mode = self.AUTO_STOP_RESTART_NORMAL

        return True

    def can_auto_restart(self):
        """Determine whether this suite can safely auto stop-restart."""
        # Check the suite is auto-restartable see #2799.
        ret = ['Incompatible configuration: "%s"' % key for key, value in [
            ('can_auto_stop', not self.can_auto_stop),
            ('final_point', self.options.final_point_string),
            ('no_detach', self.options.no_detach),
            ('pool_hold_point', self.pool_hold_point),
            ('run_mode', self.run_mode != 'live'),
            ('stop_clock_time', self.stop_clock_time),
            ('stop_point', (self.stop_point and
                            self.stop_point != self.final_point)),
            # ^ https://github.com/cylc/cylc/issues/2799#issuecomment-436720805
            ('stop_task', self.stop_task)
        ] if value]

        # Check whether there is currently an available host to restart on.
        try:
            HostAppointer(cached=False).appoint_host()
        except EmptyHostList:
            ret.append('No alternative host to restart suite on.')
        except Exception:
            # Any unexpected error in host selection shouldn't be able to take
            # down the suite.
            ret.append('Error in host selection:\n' + traceback.format_exc())

        if ret:
            LOG.critical('Suite cannot automatically restart because:\n' +
                         '\n'.join(ret))
            return False
        return True

    def suite_health_check(self, has_changes):
        """Detect issues with the suite or its environment and act accordingly.

        Check if:

        1. Suite is stalled?
        2. Suite host is condemned?
        3. Suite run directory still there?
        4. Suite contact file has the right info?

        """
        # 1. check if suite is stalled - if so call handler if defined
        if self.stop_mode is None and not has_changes:
            self.check_suite_stalled()

        now = time()
        if (self.time_next_health_check is None or
                now > self.time_next_health_check):
            LOG.debug('Performing suite health check')

            # 2. check if suite host is condemned - if so auto restart.
            if self.stop_mode is None:
                current_glbl_cfg = glbl_cfg(cached=False)
                for host in current_glbl_cfg.get(['suite servers',
                                                  'condemned hosts']):
                    if host.endswith('!'):
                        # host ends in an `!` -> force shutdown mode
                        mode = self.AUTO_STOP_RESTART_FORCE
                        host = host[:-1]
                    else:
                        # normal mode (stop and restart the suite)
                        mode = self.AUTO_STOP_RESTART_NORMAL
                        if self.auto_restart_time is not None:
                            # suite is already scheduled to stop-restart only
                            # AUTO_STOP_RESTART_FORCE can override this.
                            continue

                    if get_fqdn_by_host(host) == self.host:
                        # this host is condemned, take the appropriate action
                        LOG.info('The Cylc suite host will soon become '
                                 'un-available.')
                        if mode == self.AUTO_STOP_RESTART_FORCE:
                            # server is condemned in "force" mode -> stop
                            # the suite, don't attempt to restart
                            LOG.critical(
                                'This suite will be shutdown as the suite '
                                'host is unable to continue running it.\n'
                                'When another suite host becomes available '
                                'the suite can be restarted by:\n'
                                '    $ cylc restart %s', self.suite)
                            if self.set_auto_restart(mode=mode):
                                return  # skip remaining health checks
                        elif (self.set_auto_restart(current_glbl_cfg.get(
                                ['suite servers', 'auto restart delay']))):
                            # server is condemned -> configure the suite to
                            # auto stop-restart if possible, else, report the
                            # issue preventing this
                            return  # skip remaining health checks
                        break

            # 3. check if suite run dir still present - if not shutdown.
            if not os.path.exists(self.suite_run_dir):
                raise SchedulerError(
                    "%s: suite run directory not found" % self.suite_run_dir)

            # 4. check if contact file consistent with current start - if not
            #    shutdown.
            try:
                contact_data = self.suite_srv_files_mgr.load_contact_file(
                    self.suite)
                if contact_data != self.contact_data:
                    raise AssertionError()
            except (AssertionError, IOError, ValueError,
                    SuiteServiceFileError) as exc:
                LOG.exception(exc)
                exc = SchedulerError(
                    ("%s: suite contact file corrupted/modified and" +
                     " may be left") %
                    self.suite_srv_files_mgr.get_contact_file(self.suite))
                raise exc
            self.time_next_health_check = (
                now + self._get_cylc_conf('health check interval'))

    def update_profiler_logs(self, tinit):
        """Update info for profiler."""
        now = time()
        self._update_profile_info("scheduler loop dt (s)", now - tinit,
                                  amount_format="%.3f")
        self._update_cpu_usage()
        if now - self.previous_profile_point >= 60:
            # Only get this every minute.
            self.previous_profile_point = now
            self.profiler.log_memory("scheduler.py: loop #%d: %s" % (
                self.count, get_current_time_string()))
        self.count += 1

    def run(self):
        """Main loop."""
        self.initialise_scheduler()
        while True:  # MAIN LOOP
            tinit = time()

            if self.pool.do_reload:
                self.pool.reload_taskdefs()
                self.suite_db_mgr.checkpoint("reload-done")
                self.is_updated = True

            self.process_command_queue()
            if self.pool.release_runahead_tasks():
                self.is_updated = True
                self.task_events_mgr.pflag = True
            self.proc_pool.process()

            # PROCESS ALL TASKS whenever something has changed that might
            # require renegotiation of dependencies, etc.
            if self.should_process_tasks():
                self.process_task_pool()
            self.late_tasks_check()

            self.process_queued_task_messages()
            self.process_command_queue()
            self.task_events_mgr.process_events(self)

            # Update state summary and database
            self.suite_db_mgr.put_task_event_timers(self.task_events_mgr)
            has_updated = self.update_state_summary()
            self.process_suite_db_queue()

            # If public database is stuck, blast it away by copying the content
            # of the private database into it.
            self.database_health_check()

            # Shutdown suite if timeouts have occurred
            self.timeout_check()

            # Does the suite need to shutdown on task failure?
            self.suite_shutdown()

            # Suite health checks
            self.suite_health_check(has_updated)

            if self.options.profile_mode:
                self.update_profiler_logs(tinit)

            # Sleep a bit for things to catch up.
            # Quick sleep if there are items pending in process pool.
            # (Should probably use quick sleep logic for other queues?)
            elapsed = time() - tinit
            quick_mode = self.proc_pool.is_not_done()
            if (elapsed >= self.INTERVAL_MAIN_LOOP or
                    quick_mode and elapsed >= self.INTERVAL_MAIN_LOOP_QUICK):
                # Main loop has taken quite a bit to get through
                # Still yield control to other threads by sleep(0.0)
                sleep(0.0)
            elif quick_mode:
                sleep(self.INTERVAL_MAIN_LOOP_QUICK - elapsed)
            else:
                sleep(self.INTERVAL_MAIN_LOOP - elapsed)
            # Record latest main loop interval
            self.main_loop_intervals.append(time() - tinit)
            # END MAIN LOOP

    def update_state_summary(self):
        """Update state summary."""
        updated_tasks = [
            t for t in self.pool.get_all_tasks() if t.state.is_updated]
        has_updated = self.is_updated or updated_tasks
        if has_updated:
            self.state_summary_mgr.update(self)
            self.suite_db_mgr.put_task_pool(self.pool)
            self.is_updated = False
            self.is_stalled = False
            for itask in updated_tasks:
                itask.state.is_updated = False
            # Suite can't be stalled, so stop the suite timer.
            if self.suite_timer_active:
                self.suite_timer_active = False
                LOG.debug(
                    "%s suite timer stopped NOW: %s",
                    get_seconds_as_interval_string(
                        self._get_events_conf(self.EVENT_TIMEOUT)),
                    get_current_time_string())
        return has_updated

    def check_suite_timer(self):
        """Check if suite has timed out or not."""
        if (self._get_events_conf(self.EVENT_TIMEOUT) is None or
                self.already_timed_out or not self.is_stalled):
            return
        if time() > self.suite_timer_timeout:
            self.already_timed_out = True
            message = 'suite timed out after %s' % (
                get_seconds_as_interval_string(
                    self._get_events_conf(self.EVENT_TIMEOUT))
            )
            LOG.warning(message)
            self.run_event_handlers(self.EVENT_TIMEOUT, message)
            if self._get_events_conf('abort on timeout'):
                raise SchedulerError('Abort on suite timeout is set')

    def check_suite_inactive(self):
        """Check if suite is inactive or not."""
        if self.already_inactive:
            return
        if time() > self.suite_inactivity_timeout:
            self.already_inactive = True
            message = 'suite timed out after inactivity for %s' % (
                get_seconds_as_interval_string(
                    self._get_events_conf(self.EVENT_INACTIVITY_TIMEOUT)))
            LOG.warning(message)
            self.run_event_handlers(self.EVENT_INACTIVITY_TIMEOUT, message)
            if self._get_events_conf('abort on inactivity'):
                raise SchedulerError('Abort on suite inactivity is set')

    def check_suite_stalled(self):
        """Check if suite is stalled or not."""
        if self.is_stalled:  # already reported
            return
        self.is_stalled = self.pool.is_stalled()
        if self.is_stalled:
            message = 'suite stalled'
            LOG.warning(message)
            self.run_event_handlers(self.EVENT_STALLED, message)
            self.pool.report_stalled_task_deps()
            if self._get_events_conf('abort on stalled'):
                raise SchedulerError('Abort on suite stalled is set')
            # Start suite timeout timer
            if self._get_events_conf(self.EVENT_TIMEOUT):
                self.set_suite_timer()

    def should_process_tasks(self):
        """Return True if waiting tasks are ready."""
        # do we need to do a pass through the main task processing loop?
        process = False

        # New-style xtriggers.
        self.pool.check_xtriggers()
        if self.xtrigger_mgr.pflag:
            process = True
            self.xtrigger_mgr.pflag = False  # reset
        # Old-style external triggers.
        self.broadcast_mgr.add_ext_triggers(self.ext_trigger_queue)
        for itask in self.pool.get_tasks():
            if (itask.state.external_triggers and
                    self.broadcast_mgr.match_ext_trigger(itask)):
                process = True

        if self.task_events_mgr.pflag:
            # This flag is turned on by commands that change task state
            process = True
            self.task_events_mgr.pflag = False  # reset

        if self.task_job_mgr.task_remote_mgr.ready:
            # This flag is turned on when a host init/select command completes
            process = True
            self.task_job_mgr.task_remote_mgr.ready = False  # reset

        broadcast_mgr = self.task_events_mgr.broadcast_mgr
        broadcast_mgr.add_ext_triggers(self.ext_trigger_queue)
        now = time()
        for itask in self.pool.get_tasks():
            # External trigger matching and task expiry must be done
            # regardless, so they need to be in separate "if ..." blocks.
            if broadcast_mgr.match_ext_trigger(itask):
                process = True
            if self.pool.set_expired_task(itask, now):
                process = True
            if itask.is_ready(now):
                process = True
        if self.run_mode == 'simulation' and self.pool.sim_time_check(
                self.message_queue):
            process = True

        return process

    def shutdown(self, reason=None):
        """Shutdown the suite."""
        msg = "Suite shutting down"
        if isinstance(reason, CylcError):
            msg += ' - %s' % reason.args[0]
            if isinstance(reason, SchedulerError):
                LOG.exception(msg)
            reason = reason.args[0]
        elif reason:
            msg += ' - %s' % reason

        LOG.info(msg)

        if self.proc_pool:
            if self.proc_pool.is_not_done():
                # e.g. KeyboardInterrupt
                self.proc_pool.terminate()
            self.proc_pool.process()

        if self.pool is not None:
            self.pool.warn_stop_orphans()
            try:
                self.suite_db_mgr.put_task_event_timers(self.task_events_mgr)
                self.suite_db_mgr.put_task_pool(self.pool)
            except Exception as exc:
                LOG.exception(exc)

        if self.server:
            self.server.stop()

        # Flush errors and info before removing suite contact file
        sys.stdout.flush()
        sys.stderr.flush()

        if self.contact_data:
            fname = self.suite_srv_files_mgr.get_contact_file(self.suite)
            try:
                os.unlink(fname)
            except OSError as exc:
                LOG.warning("failed to remove suite contact file: %s", fname)
                LOG.exception(exc)
            if self.task_job_mgr:
                self.task_job_mgr.task_remote_mgr.remote_tidy()

        # disconnect from suite-db, stop db queue
        try:
            self.suite_db_mgr.process_queued_ops()
            self.suite_db_mgr.on_suite_shutdown()
        except Exception as exc:
            LOG.exception(exc)

        # The getattr() calls and if tests below are used in case the
        # suite is not fully configured before the shutdown is called.
        if getattr(self, "config", None) is not None:
            # run shutdown handlers
            self.run_event_handlers(self.EVENT_SHUTDOWN, str(reason))

    def set_stop_point(self, stop_point_string):
        """Set stop point."""
        stop_point = get_point(stop_point_string)
        self.stop_point = stop_point
        LOG.info("Setting stop cycle point: %s" % stop_point_string)
        self.pool.set_stop_point(self.stop_point)

    def set_stop_clock(self, unix_time, date_time_string):
        """Set stop clock time."""
        LOG.info("Setting stop clock time: %s (unix time: %s)" % (
            date_time_string, unix_time))
        self.stop_clock_time = unix_time
        self.stop_clock_time_string = date_time_string

    def set_stop_task(self, task_id):
        """Set stop after a task."""
        name = TaskID.split(task_id)[0]
        if name in self.config.get_task_name_list():
            task_id = self.get_standardised_taskid(task_id)
            LOG.info("Setting stop task: " + task_id)
            self.stop_task = task_id
        else:
            LOG.warning("Requested stop task name does not exist: %s" % name)

    def stop_task_done(self):
        """Return True if stop task has succeeded."""
        if self.stop_task and self.pool.task_succeeded(self.stop_task):
            LOG.info("Stop task %s finished" % self.stop_task)
            return True
        else:
            return False

    def hold_suite(self, point=None):
        """Hold all tasks in suite."""
        if point is None:
            self.pool.hold_all_tasks()
            sdm = self.suite_db_mgr
            sdm.db_inserts_map[sdm.TABLE_SUITE_PARAMS].append(
                {"key": "is_held", "value": 1})
        else:
            LOG.info("Setting suite hold cycle point: " + str(point))
            self.pool.set_hold_point(point)

    def release_suite(self):
        """Release (un-hold) all tasks in suite."""
        if self.pool.is_held:
            LOG.info("RELEASE: new tasks will be queued when ready")
        self.pool.set_hold_point(None)
        self.pool.release_all_tasks()
        sdm = self.suite_db_mgr
        sdm.db_deletes_map[sdm.TABLE_SUITE_PARAMS].append({"key": "is_held"})

    def paused(self):
        """Is the suite paused?"""
        return self.pool.is_held

    def command_trigger_tasks(self, items, back_out=False):
        """Trigger tasks."""
        return self.pool.trigger_tasks(items, back_out)

    def command_dry_run_tasks(self, items, check_syntax=True):
        """Dry-run tasks, e.g. edit run."""
        itasks, bad_items = self.pool.filter_task_proxies(items)
        n_warnings = len(bad_items)
        if len(itasks) > 1:
            LOG.warning("Unique task match not found: %s" % items)
            return n_warnings + 1
        while self.stop_mode is None:
            prep_tasks, bad_tasks = self.task_job_mgr.prep_submit_task_jobs(
                self.suite, [itasks[0]], dry_run=True,
                check_syntax=check_syntax)
            if itasks[0] in prep_tasks:
                return n_warnings
            elif itasks[0] in bad_tasks:
                return n_warnings + 1
            else:
                self.proc_pool.process()
                sleep(self.INTERVAL_MAIN_LOOP_QUICK)

    def command_reset_task_states(self, items, state=None, outputs=None):
        """Reset the state of tasks."""
        return self.pool.reset_task_states(items, state, outputs)

    def command_spawn_tasks(self, items):
        """Force spawn task successors."""
        return self.pool.spawn_tasks(items)

    def command_take_checkpoints(self, name):
        """Insert current task_pool, etc to checkpoints tables."""
        return self.suite_db_mgr.checkpoint(name)

    def filter_initial_task_list(self, inlist):
        """Return list of initial tasks after applying a filter."""
        included_by_rc = self.config.cfg[
            'scheduling']['special tasks']['include at start-up']
        excluded_by_rc = self.config.cfg[
            'scheduling']['special tasks']['exclude at start-up']
        outlist = []
        for name in inlist:
            if name in excluded_by_rc:
                continue
            if len(included_by_rc) > 0:
                if name not in included_by_rc:
                    continue
            outlist.append(name)
        return outlist

    def stop_clock_done(self):
        """Return True if wall clock stop time reached."""
        if self.stop_clock_time is not None and time() > self.stop_clock_time:
            LOG.info("Wall clock stop time reached: %s" % time2str(
                self.stop_clock_time))
            self.stop_clock_time = None
            return True
        return False

    def _update_profile_info(self, category, amount, amount_format="%s"):
        """Update the 1, 5, 15 minute dt averages for a given category."""
        now = time()
        self._profile_amounts.setdefault(category, [])
        amounts = self._profile_amounts[category]
        amounts.append((now, amount))
        self._profile_update_times.setdefault(category, None)
        last_update = self._profile_update_times[category]
        if last_update is not None and now < last_update + 60:
            return
        self._profile_update_times[category] = now
        averages = {1: [], 5: [], 15: []}
        for then, amount in list(amounts):
            age = (now - then) / 60.0
            if age > 15:
                amounts.remove((then, amount))
                continue
            for minute_num in averages:
                if age <= minute_num:
                    averages[minute_num].append(amount)
        output_text = "PROFILE: %s:" % category
        for minute_num, minute_amounts in sorted(averages.items()):
            averages[minute_num] = sum(minute_amounts) / len(minute_amounts)
            output_text += (" %d: " + amount_format) % (
                minute_num, averages[minute_num])
        LOG.info(output_text)

    def _update_cpu_usage(self):
        """Obtain CPU usage statistics."""
        proc = Popen(
            ["ps", "-o%cpu= ", str(os.getpid())],
            stdin=open(os.devnull), stdout=PIPE)
        try:
            cpu_frac = float(proc.communicate()[0])
        except (TypeError, OSError, IOError, ValueError) as exc:
            LOG.warning("Cannot get CPU % statistics: %s" % exc)
            return
        self._update_profile_info("CPU %", cpu_frac, amount_format="%.1f")

    def _get_cylc_conf(self, key, default=None):
        """Return a named setting under [cylc] from suite.rc or global.rc."""
        for getter in [self.config.cfg['cylc'], glbl_cfg().get(['cylc'])]:
            try:
                value = getter[key]
            except TypeError:
                continue
            except KeyError:
                pass
            else:
                if value is not None:
                    return value
        return default

    def _get_events_conf(self, key, default=None):
        """Return a named [cylc][[events]] configuration."""
        return self.suite_event_handler.get_events_conf(
            self.config, key, default)
