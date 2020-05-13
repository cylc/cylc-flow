# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
"""Cylc scheduler server."""

import asyncio
from collections import deque
from itertools import zip_longest
import logging
import os
from shlex import quote
from queue import Empty, Queue
from shutil import copytree, rmtree
from subprocess import Popen, PIPE, DEVNULL
import sys
from threading import Barrier
from time import sleep, time
import traceback
from uuid import uuid4
import zmq
from zmq.auth.thread import ThreadAuthenticator

from metomi.isodatetime.parsers import TimePointParser

from cylc.flow import LOG
from cylc.flow import main_loop
from cylc.flow.broadcast_mgr import BroadcastMgr
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.config import SuiteConfig
from cylc.flow.cycling.loader import get_point, standardise_point_string
from cylc.flow.daemonize import daemonize
from cylc.flow.exceptions import (
    CylcError,
    PointParsingError,
    TaskProxySequenceBoundsError
)
import cylc.flow.flags
from cylc.flow.host_select import select_suite_host
from cylc.flow.hostuserutil import get_host, get_user
from cylc.flow.job_pool import JobPool
from cylc.flow.loggingutil import (
    TimestampRotatingFileHandler,
    ReferenceLogFileHandler
)
from cylc.flow.network import API
from cylc.flow.network.server import SuiteRuntimeServer
from cylc.flow.network.publisher import WorkflowPublisher
from cylc.flow.parsec.OrderedDict import DictTree
from cylc.flow.parsec.util import printcfg
from cylc.flow.parsec.validate import DurationFloat
from cylc.flow.pathutil import (
    get_suite_run_dir,
    get_suite_run_log_dir,
    get_suite_run_rc_dir,
    get_suite_run_share_dir,
    get_suite_run_work_dir,
    get_suite_test_log_name,
    make_suite_run_tree,
)
from cylc.flow.profiler import Profiler
from cylc.flow.state_summary_mgr import StateSummaryMgr
from cylc.flow.subprocpool import SubProcPool
from cylc.flow.suite_db_mgr import SuiteDatabaseManager
from cylc.flow.suite_events import (
    SuiteEventContext, SuiteEventHandler)
from cylc.flow.suite_status import StopMode, AutoRestartMode
from cylc.flow import suite_files
from cylc.flow.taskdef import TaskDef
from cylc.flow.task_events_mgr import TaskEventsManager
from cylc.flow.task_id import TaskID
from cylc.flow.task_job_logs import JOB_LOG_JOB, get_task_job_log
from cylc.flow.task_job_mgr import TaskJobManager
from cylc.flow.task_pool import TaskPool
from cylc.flow.task_proxy import TaskProxy
from cylc.flow.task_state import (
    TASK_STATUSES_ACTIVE,
    TASK_STATUSES_NEVER_ACTIVE,
    TASK_STATUSES_SUCCESS,
    TASK_STATUS_FAILED)
from cylc.flow.templatevars import load_template_vars
from cylc.flow import __version__ as CYLC_VERSION
from cylc.flow.data_store_mgr import DataStoreMgr
from cylc.flow.wallclock import (
    get_current_time_string,
    get_seconds_as_interval_string,
    get_time_string_from_unix_time as time2str,
    get_utc_mode)
from cylc.flow.xtrigger_mgr import XtriggerManager


class SchedulerStop(CylcError):
    """Scheduler normal stop."""
    pass


class SchedulerError(CylcError):
    """Scheduler expected error stop."""
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
    EVENT_ABORTED = SuiteEventHandler.EVENT_ABORTED
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
    START_PUB_MESSAGE_PREFIX = 'Suite publisher: '
    START_PUB_MESSAGE_TMPL = (
        START_PUB_MESSAGE_PREFIX +
        'url=%(comms_method)s://%(host)s:%(port)s')

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
        if self.options.no_detach:
            self.options.format = 'plain'
        self.profiler = Profiler(self.options.profile_mode)
        self.suite = args[0]
        self.uuid_str = SchedulerUUID()
        self.suite_dir = suite_files.get_suite_source_dir(
            self.suite)
        self.suiterc = suite_files.get_suite_rc(self.suite)
        self.suiterc_update_time = None
        # For user-defined batch system handlers
        sys.path.append(os.path.join(self.suite_dir, 'python'))
        sys.path.append(os.path.join(self.suite_dir, 'lib', 'python'))
        self.suite_run_dir = get_suite_run_dir(self.suite)
        self.suite_work_dir = get_suite_run_work_dir(self.suite)
        self.suite_share_dir = get_suite_run_share_dir(self.suite)
        self.suite_log_dir = get_suite_run_log_dir(self.suite)

        self.config = None
        self.cylc_config = None

        self.is_restart = is_restart
        self.template_vars = load_template_vars(
            self.options.templatevars, self.options.templatevars_file)

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
        self.zmq_context = None
        self.server = None
        self.port = None
        self.publisher = None
        self.pub_port = None
        self.command_queue = None
        self.message_queue = None
        self.ext_trigger_queue = None
        self.data_store_mgr = None
        self.job_pool = None

        self._profile_amounts = {}
        self._profile_update_times = {}

        self.stop_mode = None

        # TODO - stop task should be held by the task pool.
        self.stop_task = None
        self.stop_clock_time = None  # When not None, in Unix time

        self.suite_timer_timeout = 0.0
        self.suite_timer_active = False
        self.suite_inactivity_timeout = 0.0
        self.already_inactive = False

        self.time_next_kill = None
        self.already_timed_out = False

        self.suite_db_mgr = SuiteDatabaseManager(
            suite_files.get_suite_srv_dir(self.suite),  # pri_d
            os.path.join(self.suite_run_dir, 'log'))                 # pub_d
        self.broadcast_mgr = BroadcastMgr(self.suite_db_mgr)
        self.xtrigger_mgr = None  # type: XtriggerManager

        # Last 10 durations (in seconds) of the main loop
        self.main_loop_intervals = deque(maxlen=10)

        self.can_auto_stop = True
        self.previous_profile_point = 0
        self.count = 0

        # auto-restart settings
        self.auto_restart_mode = None
        self.auto_restart_time = None

        self.main_loop_plugins = None

    def start(self):
        """Start the server."""
        if self.options.format == 'plain':
            self._start_print_blurb()

        make_suite_run_tree(self.suite)

        if self.is_restart:
            self.suite_db_mgr.restart_upgrade()
        try:
            if not self.options.no_detach:
                daemonize(self)
            self._setup_suite_logger()
            self.data_store_mgr = DataStoreMgr(self)

            # *** Network Related ***
            # TODO: this in zmq asyncio context?
            # Requires the Cylc main loop in asyncio first
            # And use of concurrent.futures.ThreadPoolExecutor?
            self.zmq_context = zmq.Context()
            # create an authenticator for the ZMQ context
            self.curve_auth = ThreadAuthenticator(self.zmq_context, log=LOG)
            self.curve_auth.start()  # start the authentication thread

            # Setting the location means that the CurveZMQ auth will only
            # accept public client certificates from the given directory, as
            # generated by a user when they initiate a ZMQ socket ready to
            # connect to a server.
            suite_srv_dir = suite_files.get_suite_srv_dir(self.suite)
            client_pub_keyinfo = suite_files.KeyInfo(
                suite_files.KeyType.PUBLIC,
                suite_files.KeyOwner.CLIENT,
                suite_srv_dir=suite_srv_dir)
            self.client_pub_key_dir = client_pub_keyinfo.key_path

            # Initial load for the localhost key.
            self.curve_auth.configure_curve(
                domain='*',
                location=(self.client_pub_key_dir)
            )
            # create thread sync barrier for setup
            barrier = Barrier(3, timeout=10)
            port_range = glbl_cfg().get(['suite servers', 'run ports'])
            self.server = SuiteRuntimeServer(
                self, context=self.zmq_context, barrier=barrier)
            self.server.start(port_range[0], port_range[-1])
            self.publisher = WorkflowPublisher(
                self.suite, context=self.zmq_context, barrier=barrier)
            self.publisher.start(port_range[0], port_range[-1])
            # wait for threads to setup socket ports before continuing
            barrier.wait()
            self.port = self.server.port
            self.pub_port = self.publisher.port

            self.configure()
            self.profiler.start()
            self.run()
        except SchedulerStop as exc:
            # deliberate stop
            self.shutdown(exc)
            if self.auto_restart_mode == AutoRestartMode.RESTART_NORMAL:
                self.suite_auto_restart()
            # run shutdown coros
            asyncio.get_event_loop().run_until_complete(
                asyncio.gather(
                    *main_loop.get_runners(
                        self.main_loop_plugins,
                        main_loop.CoroTypes.ShutDown,
                        self
                    )
                )
            )
            self.close_logs()

        except SchedulerError as exc:
            self.shutdown(exc)
            self.close_logs()
            sys.exit(1)

        except KeyboardInterrupt as exc:
            try:
                self.shutdown(exc)
            except Exception as exc2:
                # In case of exceptions in the shutdown method itself.
                LOG.exception(exc2)
                sys.exit(1)
            self.close_logs()

        except Exception as exc:
            try:
                self.shutdown(exc)
            except Exception as exc2:
                # In case of exceptions in the shutdown method itself
                LOG.exception(exc2)
            self.close_logs()
            raise exc

        else:
            # main loop ends (not used?)
            self.shutdown(SchedulerStop(StopMode.AUTO.value))
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
            ('{0} {1: ^%s}' % lmax).format(*x) for x in zip_longest(
                logo_lines, license_lines, fillvalue=' ' * (
                    len(logo_lines[-1]) + 1))))))

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
        self.job_pool = JobPool(self)
        self.task_events_mgr = TaskEventsManager(
            self.suite, self.proc_pool, self.suite_db_mgr, self.broadcast_mgr,
            self.job_pool)
        self.task_events_mgr.uuid_str = self.uuid_str
        self.task_job_mgr = TaskJobManager(
            self.suite, self.proc_pool, self.suite_db_mgr,
            self.task_events_mgr, self.job_pool)
        self.task_job_mgr.task_remote_mgr.uuid_str = self.uuid_str

        self.xtrigger_mgr = XtriggerManager(
            self.suite, self.owner,
            broadcast_mgr=self.broadcast_mgr,
            proc_pool=self.proc_pool,
            suite_run_dir=self.suite_run_dir,
            suite_share_dir=self.suite_share_dir,
            suite_source_dir=self.suite_dir)

        if self.is_restart:
            # This logic handles the lack of initial cycle point in "suite.rc".
            # Things that can't change on suite reload.
            pri_dao = self.suite_db_mgr.get_pri_dao()
            pri_dao.select_suite_params(self._load_suite_params)
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

        reqmode = self.config.cfg['cylc']['required run mode']
        if reqmode and not self.config.run_mode(reqmode):
            raise ValueError('this suite requires the %s run mode' % reqmode)

        self.broadcast_mgr.linearized_ancestors.update(
            self.config.get_linearized_ancestors())
        self.task_events_mgr.mail_interval = self.cylc_config[
            "task event mail interval"]
        self.task_events_mgr.mail_footer = self._get_events_conf("mail footer")
        self.task_events_mgr.suite_url = self.config.cfg['meta']['URL']
        self.task_events_mgr.suite_cfg = self.config.cfg['meta']
        if self.options.genref:
            LOG.addHandler(ReferenceLogFileHandler(
                self.config.get_ref_log_name()))
        elif self.options.reftest:
            LOG.addHandler(ReferenceLogFileHandler(
                get_suite_test_log_name(self.suite)))
        log_extra = {TimestampRotatingFileHandler.FILE_HEADER_FLAG: True}
        log_extra_num = {
            TimestampRotatingFileHandler.FILE_HEADER_FLAG: True,
            TimestampRotatingFileHandler.FILE_NUM: 1}
        LOG.info(
            self.START_MESSAGE_TMPL % {
                'comms_method': 'tcp',
                'host': self.host,
                'port': self.port,
                'pid': os.getpid()},
            extra=log_extra,
        )
        LOG.info(
            self.START_PUB_MESSAGE_TMPL % {
                'comms_method': 'tcp',
                'host': self.host,
                'port': self.pub_port},
            extra=log_extra,
        )
        LOG.info('Run: (re)start=%d log=%d', n_restart, 1, extra=log_extra_num)
        LOG.info('Cylc version: %s', CYLC_VERSION, extra=log_extra)
        # Note that the following lines must be present at the top of
        # the suite log file for use in reference test runs:
        LOG.info('Run mode: %s', self.config.run_mode(), extra=log_extra)
        LOG.info(
            'Initial point: %s', self.config.initial_point, extra=log_extra)
        if self.config.start_point != self.config.initial_point:
            LOG.info(
                'Start point: %s', self.config.start_point, extra=log_extra)
        LOG.info('Final point: %s', self.config.final_point, extra=log_extra)

        self.pool = TaskPool(
            self.config,
            self.suite_db_mgr,
            self.task_events_mgr,
            self.job_pool)

        self.profiler.log_memory("scheduler.py: before load_tasks")
        if self.is_restart:
            self.load_tasks_for_restart()
        else:
            self.load_tasks_for_run()
        if self.options.stopcp:
            self.pool.set_stop_point(get_point(self.options.stopcp))
        self.profiler.log_memory("scheduler.py: after load_tasks")

        self.suite_db_mgr.put_suite_params(self)
        self.suite_db_mgr.put_suite_template_vars(self.template_vars)
        self.suite_db_mgr.put_runtime_inheritance(self.config)

        self.already_timed_out = False
        self.set_suite_timer()

        # Inactivity setting
        self.already_inactive = False
        key = self.EVENT_INACTIVITY_TIMEOUT
        if self.options.reftest:
            self.config.cfg['cylc']['events'][f'abort on {key}'] = True
            if not self.config.cfg['cylc']['events'][key]:
                self.config.cfg['cylc']['events'][key] = DurationFloat(180)
        if self._get_events_conf(key):
            self.set_suite_inactivity_timer()

        # Main loop plugins
        self.main_loop_plugins = main_loop.load(
            # TODO: this doesn't work, we need to merge the two configs
            self.cylc_config.get('main loop', {}),
            self.options.main_loop
        )

        asyncio.get_event_loop().run_until_complete(
            asyncio.gather(
                *main_loop.get_runners(
                    self.main_loop_plugins,
                    main_loop.CoroTypes.StartUp,
                    self
                )
            )
        )

        self.profiler.log_memory("scheduler.py: end configure")

    def load_tasks_for_run(self):
        """Load tasks for a new run."""
        if self.config.start_point is not None:
            if self.options.warm:
                LOG.info('Warm Start %s' % self.config.start_point)
            else:
                LOG.info('Cold Start %s' % self.config.start_point)

        task_list = self.filter_initial_task_list(
            self.config.get_task_name_list())

        for name in task_list:
            if self.config.start_point is None:
                # No start cycle point at which to load cycling tasks.
                continue
            try:
                self.pool.add_to_runahead_pool(TaskProxy(
                    self.config.get_taskdef(name), self.config.start_point,
                    is_startup=True))
            except TaskProxySequenceBoundsError as exc:
                LOG.debug(str(exc))
                continue

    def load_tasks_for_restart(self):
        """Load tasks for restart."""
        if self.options.startcp:
            self.config.start_point = self.get_standardised_point(
                self.options.startcp)
        self.suite_db_mgr.pri_dao.select_broadcast_states(
            self.broadcast_mgr.load_db_broadcast_states,
            self.options.checkpoint)
        self.suite_db_mgr.pri_dao.select_task_job_run_times(
            self._load_task_run_times)
        self.suite_db_mgr.pri_dao.select_task_pool_for_restart(
            self.pool.load_db_task_pool_for_restart, self.options.checkpoint)
        self.suite_db_mgr.pri_dao.select_job_pool_for_restart(
            self.job_pool.insert_db_job, self.options.checkpoint)
        self.suite_db_mgr.pri_dao.select_task_action_timers(
            self.pool.load_db_task_action_timers)
        self.suite_db_mgr.pri_dao.select_xtriggers_for_restart(
            self.xtrigger_mgr.load_xtrigger_for_restart)

        # Re-initialise run directory for user@host for each submitted and
        # running tasks.
        # Note: tasks should all be in the runahead pool at this point.
        auths = set()
        for itask in self.pool.get_rh_tasks():
            if itask.state(*TASK_STATUSES_ACTIVE):
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
            cycle, task_name, submit_num = (
                self.job_pool.parse_job_item(task_job))
            task_id = TaskID.get(task_name, cycle)
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
                        self.task_events_mgr.FLAG_RECEIVED, submit_num):
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
        """Return prerequisites and outputs etc. of a task.

        Result in a dict of a dict:
        {
            "task_id": {
                "meta": {key: value, ...},
                "prerequisites": {key: value, ...},
                "outputs": {key: value, ...},
                "extras": {key: value, ...},
            },
            ...
        }
        """
        itasks, bad_items = self.pool.filter_task_proxies(items)
        results = {}
        now = time()
        for itask in itasks:
            if list_prereqs:
                results[itask.identity] = {
                    'prerequisites': itask.state.prerequisites_dump(
                        list_prereqs=True)}
                continue
            extras = {}
            if itask.tdef.clocktrigger_offset is not None:
                extras['Clock trigger time reached'] = (
                    itask.is_waiting_clock_done(now))
                extras['Triggers at'] = time2str(
                    itask.clock_trigger_time)
            for trig, satisfied in itask.state.external_triggers.items():
                key = f'External trigger "{trig}"'
                if satisfied:
                    extras[key] = 'satisfied'
                else:
                    extras[key] = 'NOT satisfied'
            for label, satisfied in itask.state.xtriggers.items():
                sig = self.xtrigger_mgr.get_xtrig_ctx(
                    itask, label).get_signature()
                extra = f'xtrigger "{label} = {sig}"'
                if satisfied:
                    extras[extra] = 'satisfied'
                else:
                    extras[extra] = 'NOT satisfied'
            outputs = []
            for _, msg, is_completed in itask.state.outputs.get_all():
                outputs.append(
                    [f"{itask.identity} {msg}", is_completed])
            results[itask.identity] = {
                "meta": itask.tdef.describe(),
                "prerequisites": itask.state.prerequisites_dump(),
                "outputs": outputs,
                "extras": extras}
        return results, bad_items

    def info_ping_task(self, task_id, exists_only=False):
        """Return True if task exists and running."""
        task_id = self.get_standardised_taskid(task_id)
        return self.pool.ping_task(task_id, exists_only)

    def command_stop(
            self,
            mode=None,
            cycle_point=None,
            # NOTE clock_time YYYY/MM/DD-HH:mm back-compat removed
            clock_time=None,
            task=None
    ):
        # immediate shutdown
        if mode:
            self._set_stop(mode)
        elif not any([mode, cycle_point, clock_time, task]):
            # if no arguments provided do a standard clean shutdown
            self._set_stop(StopMode.REQUEST_CLEAN)

        # schedule shutdown after tasks pass provided cycle point
        if cycle_point:
            point = self.get_standardised_point(cycle_point)
            if self.pool.set_stop_point(point):
                self.options.stopcp = str(point)
                self.suite_db_mgr.put_suite_stop_cycle_point(
                    self.options.stopcp)
            else:
                # TODO: yield warning
                pass

        # schedule shutdown after wallclock time passes provided time
        if clock_time:
            parser = TimePointParser()
            clock_time = parser.parse(clock_time)
            self.set_stop_clock(
                int(clock_time.get("seconds_since_unix_epoch")))

        # schedule shutdown after task succeeds
        if task:
            task_id = self.get_standardised_taskid(task)
            if TaskID.is_valid_id(task_id):
                self.set_stop_task(task_id)
            else:
                # TODO: yield warning
                pass

    def command_set_stop_cleanly(self, kill_active_tasks=False):
        """Stop job submission and set the flag for clean shutdown."""
        # TODO: deprecated by command_stop()
        self._set_stop()
        if kill_active_tasks:
            self.time_next_kill = time()

    def command_stop_now(self, terminate=False):
        """Shutdown immediately."""
        # TODO: deprecated by command_stop()
        if terminate:
            self._set_stop(StopMode.REQUEST_NOW_NOW)
        else:
            self._set_stop(StopMode.REQUEST_NOW)

    def _set_stop(self, stop_mode=None):
        """Set shutdown mode."""
        self.proc_pool.set_stopping()
        if stop_mode is None:
            stop_mode = StopMode.REQUEST_CLEAN
        self.stop_mode = stop_mode

    def command_set_stop_after_point(self, point_string):
        """Set stop after ... point."""
        # TODO: deprecated by command_stop()
        stop_point = self.get_standardised_point(point_string)
        if self.pool.set_stop_point(stop_point):
            self.options.stopcp = str(stop_point)
            self.suite_db_mgr.put_suite_stop_cycle_point(self.options.stopcp)

    def command_set_stop_after_clock_time(self, arg):
        """Set stop after clock time.

        format: ISO 8601 compatible or YYYY/MM/DD-HH:mm (backwards comp.)
        """
        # TODO: deprecate
        parser = TimePointParser()
        try:
            stop_time = parser.parse(arg)
        except ValueError as exc:
            try:
                stop_time = parser.strptime(arg, "%Y/%m/%d-%H:%M")
            except ValueError:
                raise exc  # Raise the first (prob. more relevant) ValueError.
        self.set_stop_clock(int(stop_time.get("seconds_since_unix_epoch")))

    def command_set_stop_after_task(self, task_id):
        """Set stop after a task."""
        # TODO: deprecate
        task_id = self.get_standardised_taskid(task_id)
        if TaskID.is_valid_id(task_id):
            self.set_stop_task(task_id)

    def command_release(self, ids=None):
        if ids:
            return self.pool.release_tasks(ids)
        self.release_suite()

    def command_release_tasks(self, items):
        """Release tasks."""
        # TODO: deprecated by command_release()
        return self.pool.release_tasks(items)

    def command_poll_tasks(self, items=None, poll_succ=False):
        """Poll pollable tasks or a task/family if options are provided.

        Don't poll succeeded tasks unless poll_succ is True.

        """
        if self.config.run_mode('simulation'):
            return
        itasks, bad_items = self.pool.filter_task_proxies(items)
        self.task_job_mgr.poll_task_jobs(self.suite, itasks,
                                         poll_succ=poll_succ)
        return len(bad_items)

    def command_kill_tasks(self, items=None):
        """Kill all tasks or a task/family if options are provided."""
        itasks, bad_items = self.pool.filter_task_proxies(items)
        if self.config.run_mode('simulation'):
            for itask in itasks:
                if itask.state(*TASK_STATUSES_ACTIVE):
                    itask.state.reset(TASK_STATUS_FAILED)
            return len(bad_items)
        self.task_job_mgr.kill_task_jobs(self.suite, itasks)
        return len(bad_items)

    def command_release_suite(self):
        """Release all task proxies in the suite."""
        # TODO: deprecated by command_release()
        self.release_suite()

    def command_hold(self, tasks=None, time=None):
        if tasks:
            self.pool.hold_tasks(tasks)
        if time:
            point = self.get_standardised_point(time)
            self.hold_suite(point)
            LOG.info(
                'The suite will pause when all tasks have passed %s', point)
        if not (tasks or time):
            self.hold_suite()

    def command_hold_tasks(self, items):
        """Hold selected task proxies in the suite."""
        # TODO: deprecated by command_hold()
        return self.pool.hold_tasks(items)

    def command_hold_suite(self):
        """Hold all task proxies in the suite."""
        # TODO: deprecated by command_hold()
        self.hold_suite()

    def command_hold_after_point_string(self, point_string):
        """Hold tasks AFTER this point (itask.point > point)."""
        # TODO: deprecated by command_hold()
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
        cylc.flow.flags.verbose = bool(LOG.isEnabledFor(logging.INFO))
        cylc.flow.flags.debug = bool(LOG.isEnabledFor(logging.DEBUG))
        return True, 'OK'

    def command_remove_tasks(self, items, spawn=False):
        """Remove tasks."""
        return self.pool.remove_tasks(items, spawn)

    def command_insert_tasks(self, items, stop_point_string=None,
                             check_point=True):
        """Insert tasks."""
        return self.pool.insert_tasks(items, stop_point_string, check_point)

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
        self.pool.set_do_reload(self.config)
        self.task_events_mgr.mail_interval = self.cylc_config[
            'task event mail interval']
        self.task_events_mgr.mail_footer = self._get_events_conf("mail footer")

        # Log tasks that have been added by the reload, removed tasks are
        # logged by the TaskPool.
        add = set(self.config.get_task_name_list()) - old_tasks
        for task in add:
            LOG.warning("Added task: '%s'" % (task,))
        self.suite_db_mgr.put_suite_template_vars(self.template_vars)
        self.suite_db_mgr.put_runtime_inheritance(self.config)
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
        suite_files.detect_old_contact_file(self.suite)
        # Get "pid,args" process string with "ps"
        pid_str = str(os.getpid())
        proc = Popen(
            ['ps', suite_files.PS_OPTS, pid_str],
            stdin=DEVNULL, stdout=PIPE, stderr=PIPE)
        out, err = (f.decode() for f in proc.communicate())
        ret_code = proc.wait()
        process_str = None
        for line in out.splitlines():
            if line.split(None, 1)[0].strip() == pid_str:
                process_str = line.strip()
                break
        if ret_code or not process_str:
            raise RuntimeError(
                'cannot get process "args" from "ps": %s' % err)
        # Write suite contact file.
        # Preserve contact data in memory, for regular health check.
        fields = suite_files.ContactFileFields
        contact_data = {
            fields.API:
                str(API),
            fields.HOST:
                self.host,
            fields.NAME:
                self.suite,
            fields.OWNER:
                self.owner,
            fields.PORT:
                str(self.server.port),
            fields.PROCESS:
                process_str,
            fields.PUBLISH_PORT:
                str(self.publisher.port),
            fields.SSH_USE_LOGIN_SHELL:
                str(glbl_cfg().get_host_item('use login shell')),
            fields.SUITE_RUN_DIR_ON_SUITE_HOST:
                self.suite_run_dir,
            fields.UUID:
                self.uuid_str.value,
            fields.VERSION:
                CYLC_VERSION
        }
        suite_files.dump_contact_file(self.suite, contact_data)
        self.contact_data = contact_data

    def load_suiterc(self, is_reload=False):
        """Load, and log the suite definition."""
        # Local suite environment set therein.
        self.config = SuiteConfig(
            self.suite,
            self.suiterc,
            self.options,
            self.template_vars,
            is_reload=is_reload,
            xtrigger_mgr=self.xtrigger_mgr,
            mem_log_func=self.profiler.log_memory,
            output_fname=os.path.join(
                self.suite_run_dir,
                suite_files.SuiteFiles.SUITE_RC + '.processed'),
            run_dir=self.suite_run_dir,
            log_dir=self.suite_log_dir,
            work_dir=self.suite_work_dir,
            share_dir=self.suite_share_dir,
        )
        self.cylc_config = DictTree(
            self.config.cfg['cylc'],
            glbl_cfg().get(['cylc'])
        )
        self.suiterc_update_time = time()
        # Dump the loaded suiterc for future reference.
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
        file_name = get_suite_run_rc_dir(
            self.suite, f"{time_str}-{load_type}.rc")
        with open(file_name, "wb") as handle:
            handle.write(b"# cylc-version: %s\n" % CYLC_VERSION.encode())
            printcfg(self.config.cfg, none_str=None, handle=handle)

        if not self.config.initial_point and not self.is_restart:
            LOG.warning('No initial cycle point provided - no cycling tasks '
                        'will be loaded.')

        # Pass static cylc and suite variables to job script generation code
        self.task_job_mgr.job_file_writer.set_suite_env({
            'CYLC_UTC': str(get_utc_mode()),
            'CYLC_DEBUG': str(cylc.flow.flags.debug).lower(),
            'CYLC_VERBOSE': str(cylc.flow.flags.verbose).lower(),
            'CYLC_SUITE_NAME': self.suite,
            'CYLC_CYCLING_MODE': str(
                self.config.cfg['scheduling']['cycling mode']),
            'CYLC_SUITE_INITIAL_CYCLE_POINT': str(self.config.initial_point),
            'CYLC_SUITE_FINAL_CYCLE_POINT': str(self.config.final_point),
        })

    def _load_suite_params(self, row_idx, row):
        """Load a row in the "suite_params" table in a restart.

        This currently includes:
        * Initial/Final cycle points.
        * Start/Stop Cycle points.
        * Suite UUID.
        * A flag to indicate if the suite should be held or not.
        """
        if row_idx == 0:
            LOG.info('LOADING suite parameters')
        key, value = row
        if key in self.suite_db_mgr.KEY_INITIAL_CYCLE_POINT_COMPATS:
            if self.options.ignore_icp:
                LOG.debug('- initial point = %s (ignored)' % value)
            elif self.options.icp is None:
                self.options.icp = value
                LOG.info('+ initial point = %s' % value)
        elif key in self.suite_db_mgr.KEY_START_CYCLE_POINT_COMPATS:
            # 'warm_point' for back compat <= 7.6.X
            if self.options.ignore_startcp:
                LOG.debug('- start point = %s (ignored)' % value)
            elif self.options.startcp is None:
                self.options.startcp = value
                LOG.info('+ start point = %s' % value)
        elif key in self.suite_db_mgr.KEY_FINAL_CYCLE_POINT_COMPATS:
            if self.options.ignore_fcp:
                LOG.debug('- override final point = %s (ignored)' % value)
            elif self.options.fcp is None:
                self.options.fcp = value
                LOG.info('+ override final point = %s' % value)
        elif key == self.suite_db_mgr.KEY_STOP_CYCLE_POINT:
            if self.options.ignore_stopcp:
                LOG.debug('- stop point = %s (ignored)' % value)
            elif self.options.stopcp is None:
                self.options.stopcp = value
                LOG.info('+ stop point = %s' % value)
        elif key == self.suite_db_mgr.KEY_RUN_MODE:
            if self.options.run_mode is None:
                self.options.run_mode = value
                LOG.info('+ run mode = %s' % value)
        elif key == self.suite_db_mgr.KEY_UUID_STR:
            self.uuid_str.value = value
            LOG.info('+ suite UUID = %s', value)
        elif key == self.suite_db_mgr.KEY_HOLD:
            if self.options.hold_start is None:
                self.options.hold_start = bool(value)
                LOG.info('+ hold suite = %s', bool(value))
        elif key == self.suite_db_mgr.KEY_HOLD_CYCLE_POINT:
            if self.options.holdcp is None:
                self.options.holdcp = value
                LOG.info('+ hold point = %s', value)
        elif key == self.suite_db_mgr.KEY_NO_AUTO_SHUTDOWN:
            value = bool(int(value))
            if self.options.no_auto_shutdown is None:
                self.options.no_auto_shutdown = value
                LOG.info('+ no auto shutdown = %s', value)
            else:
                LOG.debug('- no auto shutdown = %s (ignored)', value)
        elif key == self.suite_db_mgr.KEY_STOP_CLOCK_TIME:
            value = int(value)
            if time() <= value:
                self.stop_clock_time = value
                LOG.info('+ stop clock time = %d (%s)', value, time2str(value))
            else:
                LOG.debug(
                    '- stop clock time = %d (%s) (ignored)',
                    value,
                    time2str(value))
        elif key == self.suite_db_mgr.KEY_STOP_TASK:
            self.stop_task = value
            LOG.info('+ stop task = %s', value)

    def _load_template_vars(self, _, row):
        """Load suite start up template variables."""
        key, value = row
        # Command line argument takes precedence
        if key not in self.template_vars:
            self.template_vars[key] = value

    def run_event_handlers(self, event, reason):
        """Run a suite event handler.

        Run suite events in simulation and dummy mode ONLY if enabled.
        """
        conf = self.config
        try:
            if (
                conf.run_mode('simulation', 'dummy') and
                conf.cfg['cylc']['simulation']['disable suite event handlers']
            ):
                return
        except KeyError:
            pass
        self.suite_event_handler.handle(conf, SuiteEventContext(
            event, str(reason), self.suite, self.uuid_str, self.owner,
            self.host, self.server.port))

    def initialise_scheduler(self):
        """Prelude to the main scheduler loop.

        Determines whether suite is held or should be held.
        Determines whether suite can be auto shutdown.
        Begins profile logs if needed.
        """
        holdcp = None
        if self.options.holdcp:
            holdcp = self.options.holdcp
        elif self.config.cfg['scheduling']['hold after point']:
            holdcp = self.config.cfg['scheduling']['hold after point']
        if holdcp is not None:
            self.hold_suite(get_point(holdcp))
        if self.options.hold_start:
            LOG.info("Held on start-up (no tasks will be submitted)")
            self.hold_suite()
        self.run_event_handlers(self.EVENT_STARTUP, 'suite starting')
        self.profiler.log_memory("scheduler.py: begin run while loop")
        self.is_updated = True
        if self.options.profile_mode:
            self.previous_profile_point = 0
            self.count = 0
        if self.options.no_auto_shutdown is not None:
            self.can_auto_stop = not self.options.no_auto_shutdown
        elif self.config.cfg['cylc']['disable automatic shutdown'] is not None:
            self.can_auto_stop = (
                not self.config.cfg['cylc']['disable automatic shutdown'])

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
            for itask in self.task_job_mgr.submit_task_jobs(
                    self.suite,
                    itasks,
                    self.curve_auth,
                    self.client_pub_key_dir,
                    self.config.run_mode('simulation')
            ):
                LOG.info(
                    '[%s] -triggered off %s',
                    itask, itask.state.get_resolved_dependencies())
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
        self.suite_db_mgr.process_queued_ops()

    def database_health_check(self):
        """If public database is stuck, blast it away by copying the content
        of the private database into it."""
        self.suite_db_mgr.recover_pub_from_pri()

    def late_tasks_check(self):
        """Report tasks that are never active and are late."""
        now = time()
        for itask in self.pool.get_tasks():
            if (
                    not itask.is_late
                    and itask.get_late_time()
                    and itask.state(*TASK_STATUSES_NEVER_ACTIVE)
                    and now > itask.get_late_time()
            ):
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
        if not self.config.run_mode('simulation'):
            self.task_job_mgr.check_task_jobs(self.suite, self.pool)

    async def suite_shutdown(self):
        """Determines if the suite can be shutdown yet."""
        if self.pool.check_abort_on_task_fails():
            self._set_stop(StopMode.AUTO_ON_TASK_FAILURE)

        # Can suite shut down automatically?
        if self.stop_mode is None and (
            self.stop_clock_done() or
            self.stop_task_done() or
            self.check_auto_shutdown()
        ):
            self._set_stop(StopMode.AUTO)

        # Is the suite ready to shut down now?
        if self.pool.can_stop(self.stop_mode):
            await self.update_data_structure()
            self.proc_pool.close()
            if self.stop_mode != StopMode.REQUEST_NOW_NOW:
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
            if self.stop_mode == StopMode.AUTO_ON_TASK_FAILURE:
                raise SchedulerError(self.stop_mode.value)
            else:
                raise SchedulerStop(self.stop_mode.value)
        elif (self.time_next_kill is not None and
              time() > self.time_next_kill):
            self.command_poll_tasks()
            self.command_kill_tasks()
            self.time_next_kill = time() + self.INTERVAL_STOP_KILL

        # Is the suite set to auto stop [+restart] now ...
        if self.auto_restart_time is None or time() < self.auto_restart_time:
            # ... no
            pass
        elif self.auto_restart_mode == AutoRestartMode.RESTART_NORMAL:
            # ... yes - wait for local jobs to complete before restarting
            #           * Avoid polling issues see #2843
            #           * Ensure the host can be safely taken down once the
            #             suite has stopped running.
            for itask in self.pool.get_tasks():
                if (
                        itask.state(*TASK_STATUSES_ACTIVE)
                        and itask.summary['batch_sys_name']
                        and self.task_job_mgr.batch_sys_mgr
                        .is_job_local_to_host(
                            itask.summary['batch_sys_name'])
                ):
                    LOG.info('Waiting for jobs running on localhost to '
                             'complete before attempting restart')
                    break
            else:
                self._set_stop(StopMode.REQUEST_NOW_NOW)
        elif self.auto_restart_mode == AutoRestartMode.FORCE_STOP:
            # ... yes - leave local jobs running then stop the suite
            #           (no restart)
            self._set_stop(StopMode.REQUEST_NOW)
        else:
            raise SchedulerError(
                'Invalid auto_restart_mode=%s' % self.auto_restart_mode)

    def suite_auto_restart(self, max_retries=3):
        """Attempt to restart the suite assuming it has already stopped."""
        cmd = ['cylc', 'restart', quote(self.suite)]

        for attempt_no in range(max_retries):
            new_host = select_suite_host(cached=False)[0]
            LOG.info('Attempting to restart on "%s"', new_host)

            # proc will start with current env (incl CYLC_HOME etc)
            proc = Popen(
                cmd + ['--host=%s' % new_host],
                stdin=DEVNULL, stdout=PIPE, stderr=PIPE)
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
        """Run the main loop."""
        self.initialise_scheduler()
        self.data_store_mgr.initiate_data_model()
        asyncio.get_event_loop().run_until_complete(
            self.publisher.publish(self.data_store_mgr.get_publish_deltas())
        )
        asyncio.get_event_loop().run_until_complete(self.main_loop())

    async def main_loop(self):
        """The scheduler main loop."""
        while True:  # MAIN LOOP
            tinit = time()
            has_reloaded = False

            if self.pool.do_reload:
                self.pool.reload_taskdefs()
                self.suite_db_mgr.checkpoint("reload-done")
                self.is_updated = True
                has_reloaded = True

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

            # Re-initialise data model on reload
            if has_reloaded:
                self.data_store_mgr.initiate_data_model(reloaded=True)
                await self.publisher.publish(
                    self.data_store_mgr.get_publish_deltas())
            # Update state summary, database, and uifeed
            self.suite_db_mgr.put_task_event_timers(self.task_events_mgr)
            has_updated = await self.update_data_structure()

            self.process_suite_db_queue()

            # If public database is stuck, blast it away by copying the content
            # of the private database into it.
            self.database_health_check()

            # Shutdown suite if timeouts have occurred
            self.timeout_check()

            # Does the suite need to shutdown on task failure?
            await self.suite_shutdown()

            if self.options.profile_mode:
                self.update_profiler_logs(tinit)

            # Run plugin functions
            await asyncio.gather(
                *main_loop.get_runners(
                    self.main_loop_plugins,
                    main_loop.CoroTypes.Periodic,
                    self
                )
            )

            if not has_updated and not self.stop_mode:
                # Has the suite stalled?
                self.check_suite_stalled()

            # Sleep a bit for things to catch up.
            # Quick sleep if there are items pending in process pool.
            # (Should probably use quick sleep logic for other queues?)
            elapsed = time() - tinit
            quick_mode = self.proc_pool.is_not_done()
            if (elapsed >= self.INTERVAL_MAIN_LOOP or
                    quick_mode and elapsed >= self.INTERVAL_MAIN_LOOP_QUICK):
                # Main loop has taken quite a bit to get through
                # Still yield control to other threads by sleep(0.0)
                duration = 0
            elif quick_mode:
                duration = self.INTERVAL_MAIN_LOOP_QUICK - elapsed
            else:
                duration = self.INTERVAL_MAIN_LOOP - elapsed
            await asyncio.sleep(duration)
            # Record latest main loop interval
            self.main_loop_intervals.append(time() - tinit)
            # END MAIN LOOP

    async def update_data_structure(self):
        """Update DB, UIS, Summary data elements"""
        updated_tasks = [
            t for t in self.pool.get_all_tasks() if t.state.is_updated]
        has_updated = self.is_updated or updated_tasks
        # Add tasks that have moved moved from runahead to live pool.
        updated_nodes = set(updated_tasks).union(
            self.pool.get_pool_change_tasks())
        if has_updated:
            # WServer incremental data store update
            self.data_store_mgr.update_data_structure(updated_nodes)
            # Publish updates:
            await self.publisher.publish(
                self.data_store_mgr.get_publish_deltas())
            # TODO: deprecate after CLI GraphQL migration
            self.state_summary_mgr.update(self)
            # Database update
            self.suite_db_mgr.put_task_pool(self.pool)
            # Reset suite and task updated flags.
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
        self.xtrigger_mgr.check_xtriggers(self.pool.get_tasks())
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
        if (
            self.config.run_mode('simulation') and
            self.pool.sim_time_check(self.message_queue)
        ):
            process = True

        return process

    def shutdown(self, reason):
        """Shutdown the suite."""
        if isinstance(reason, SchedulerStop):
            LOG.info('Suite shutting down - %s', reason.args[0])
        elif isinstance(reason, SchedulerError):
            LOG.error('Suite shutting down - %s', reason)
        else:
            LOG.exception(reason)
            LOG.critical('Suite shutting down - %s', reason)

        if self.proc_pool:
            self.proc_pool.close()
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
        if self.publisher:
            asyncio.get_event_loop().run_until_complete(
                self.publisher.publish(
                    [(b'shutdown', f'{str(reason)}'.encode('utf-8'))]
                )
            )
            self.publisher.stop()
        self.curve_auth.stop()  # stop the authentication thread

        # Flush errors and info before removing suite contact file
        sys.stdout.flush()
        sys.stderr.flush()

        if self.contact_data:
            fname = suite_files.get_contact_file(self.suite)
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
            if isinstance(reason, CylcError):
                self.run_event_handlers(self.EVENT_SHUTDOWN, reason.args[0])
            else:
                self.run_event_handlers(self.EVENT_ABORTED, str(reason))

    def set_stop_clock(self, unix_time):
        """Set stop clock time."""
        LOG.info(
            "Setting stop clock time: %s (unix time: %s)",
            time2str(unix_time),
            unix_time)
        self.stop_clock_time = unix_time
        self.suite_db_mgr.put_suite_stop_clock_time(self.stop_clock_time)

    def set_stop_task(self, task_id):
        """Set stop after a task."""
        name = TaskID.split(task_id)[0]
        if name in self.config.get_task_name_list():
            task_id = self.get_standardised_taskid(task_id)
            LOG.info("Setting stop task: " + task_id)
            self.stop_task = task_id
            self.suite_db_mgr.put_suite_stop_task(self.stop_task)
        else:
            LOG.warning("Requested stop task name does not exist: %s" % name)

    def stop_clock_done(self):
        """Return True if wall clock stop time reached."""
        if self.stop_clock_time is None:
            return
        now = time()
        if now > self.stop_clock_time:
            LOG.info("Wall clock stop time reached: %s", time2str(
                self.stop_clock_time))
            self.stop_clock_time = None
            self.suite_db_mgr.delete_suite_stop_clock_time()
            return True
        else:
            LOG.debug(
                "stop time=%d; current time=%d", self.stop_clock_time, now)
            return False

    def stop_task_done(self):
        """Return True if stop task has succeeded."""
        if self.stop_task and self.pool.task_succeeded(self.stop_task):
            LOG.info("Stop task %s finished" % self.stop_task)
            self.stop_task = None
            self.suite_db_mgr.delete_suite_stop_task()
            return True
        else:
            return False

    def check_auto_shutdown(self):
        """Check if we should do a normal automatic shutdown."""
        if not self.can_auto_stop:
            return False
        can_shutdown = True
        for itask in self.pool.get_all_tasks():
            if self.pool.stop_point is None:
                # Don't if any unsucceeded task exists.
                if not itask.state(*TASK_STATUSES_SUCCESS):
                    can_shutdown = False
                    break
            elif (
                    itask.point <= self.pool.stop_point
                    and not itask.state(*TASK_STATUSES_SUCCESS)
            ):
                # Don't if any unsucceeded task exists < stop point...
                if itask.identity not in self.pool.held_future_tasks:
                    # ...unless it has a future trigger extending > stop point.
                    can_shutdown = False
                    break
        if can_shutdown and self.pool.stop_point:
            self.options.stopcp = None
            self.pool.stop_point = None
            self.suite_db_mgr.delete_suite_stop_cycle_point()
        return can_shutdown

    def hold_suite(self, point=None):
        """Hold all tasks in suite."""
        if point is None:
            self.pool.hold_all_tasks()
            self.task_events_mgr.pflag = True
            self.suite_db_mgr.put_suite_hold()
        else:
            LOG.info(
                'Setting suite hold cycle point: %s.'
                '\nThe suite will hold once all tasks have passed this point.',
                point
            )
            self.pool.set_hold_point(point)
            self.suite_db_mgr.put_suite_hold_cycle_point(point)

    def release_suite(self):
        """Release (un-hold) all tasks in suite."""
        if self.pool.is_held:
            LOG.info("RELEASE: new tasks will be queued when ready")
        self.pool.set_hold_point(None)
        self.pool.release_all_tasks()
        self.suite_db_mgr.delete_suite_hold()

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
            stdin=DEVNULL, stdout=PIPE)
        try:
            cpu_frac = float(proc.communicate()[0])
        except (TypeError, OSError, IOError, ValueError) as exc:
            LOG.warning("Cannot get CPU % statistics: %s" % exc)
            return
        self._update_profile_info("CPU %", cpu_frac, amount_format="%.1f")

    def _get_events_conf(self, key, default=None):
        """Return a named [cylc][[events]] configuration."""
        return self.suite_event_handler.get_events_conf(
            self.config, key, default)
