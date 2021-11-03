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
"""Cylc scheduler server."""

import asyncio
from contextlib import suppress
from collections import deque
from dataclasses import dataclass
import logging
from optparse import Values
import os
from pathlib import Path
from queue import Empty, Queue
from shlex import quote
from subprocess import Popen, PIPE, DEVNULL
import sys
from threading import Barrier
from time import sleep, time
import traceback
from typing import Iterable, NoReturn, Optional, List, Set, Dict, Union
from uuid import uuid4

import psutil
import zmq
from zmq.auth.thread import ThreadAuthenticator

from metomi.isodatetime.parsers import TimePointParser

from cylc.flow import (
    LOG, main_loop, ID_DELIM, __version__ as CYLC_VERSION
)
from cylc.flow.broadcast_mgr import BroadcastMgr
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.config import WorkflowConfig
from cylc.flow.cycling.loader import get_point
from cylc.flow.data_store_mgr import DataStoreMgr, parse_job_item
from cylc.flow.flow_mgr import FlowMgr
from cylc.flow.exceptions import (
    CommandFailedError, CyclingError, CylcError, UserInputError
)
import cylc.flow.flags
from cylc.flow.host_select import select_workflow_host
from cylc.flow.hostuserutil import (
    get_host,
    get_user,
    is_remote_platform
)
from cylc.flow.loggingutil import (
    TimestampRotatingFileHandler,
    ReferenceLogFileHandler
)
from cylc.flow.timer import Timer
from cylc.flow.network import API
from cylc.flow.network.authentication import key_housekeeping
from cylc.flow.network.publisher import WorkflowPublisher
from cylc.flow.network.schema import WorkflowStopMode
from cylc.flow.network.server import WorkflowRuntimeServer
from cylc.flow.option_parsers import verbosity_to_env
from cylc.flow.parsec.exceptions import TemplateVarLanguageClash
from cylc.flow.parsec.OrderedDict import DictTree
from cylc.flow.parsec.util import printcfg
from cylc.flow.parsec.validate import DurationFloat
from cylc.flow.pathutil import (
    get_workflow_run_dir,
    get_workflow_run_log_dir,
    get_workflow_run_config_log_dir,
    get_workflow_run_share_dir,
    get_workflow_run_work_dir,
    get_workflow_test_log_name,
    make_workflow_run_tree,
    get_workflow_name_from_id
)
from cylc.flow.platforms import (
    get_install_target_from_platform,
    get_platform,
    is_platform_with_target_in_list)
from cylc.flow.profiler import Profiler
from cylc.flow.resources import extract_resources
from cylc.flow.subprocpool import SubProcPool
from cylc.flow.workflow_db_mgr import WorkflowDatabaseManager
from cylc.flow.workflow_events import (
    WorkflowEventContext, WorkflowEventHandler)
from cylc.flow.workflow_status import StopMode, AutoRestartMode
from cylc.flow import workflow_files
from cylc.flow.taskdef import TaskDef
from cylc.flow.task_events_mgr import TaskEventsManager
from cylc.flow.task_id import TaskID
from cylc.flow.task_job_mgr import TaskJobManager
from cylc.flow.task_pool import TaskPool
from cylc.flow.task_proxy import TaskProxy
from cylc.flow.task_remote_mgr import (
    REMOTE_FILE_INSTALL_IN_PROGRESS, REMOTE_INIT_DONE,
    REMOTE_INIT_IN_PROGRESS)
from cylc.flow.task_state import (
    TASK_STATUSES_ACTIVE,
    TASK_STATUSES_NEVER_ACTIVE,
    TASK_STATUS_PREPARING,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_WAITING,
    TASK_STATUS_FAILED)
from cylc.flow.templatevars import load_template_vars
from cylc.flow.util import cli_format
from cylc.flow.wallclock import (
    get_current_time_string,
    get_time_string_from_unix_time as time2str,
    get_utc_mode)
from cylc.flow.xtrigger_mgr import XtriggerManager


class SchedulerStop(CylcError):
    """Scheduler normal stop."""
    pass


class SchedulerError(CylcError):
    """Scheduler expected error stop."""
    pass


@dataclass
class Scheduler:
    """Cylc scheduler server."""

    EVENT_STARTUP = WorkflowEventHandler.EVENT_STARTUP
    EVENT_SHUTDOWN = WorkflowEventHandler.EVENT_SHUTDOWN
    EVENT_ABORTED = WorkflowEventHandler.EVENT_ABORTED
    EVENT_WORKFLOW_TIMEOUT = WorkflowEventHandler.EVENT_WORKFLOW_TIMEOUT
    EVENT_STALL_TIMEOUT = WorkflowEventHandler.EVENT_STALL_TIMEOUT
    EVENT_INACTIVITY_TIMEOUT = WorkflowEventHandler.EVENT_INACTIVITY_TIMEOUT
    EVENT_STALL = WorkflowEventHandler.EVENT_STALL

    # Intervals in seconds
    INTERVAL_MAIN_LOOP = 1.0
    INTERVAL_MAIN_LOOP_QUICK = 0.5
    INTERVAL_STOP_KILL = 10.0
    INTERVAL_STOP_PROCESS_POOL_EMPTY = 0.5
    INTERVAL_AUTO_RESTART_ERROR = 5

    START_MESSAGE_PREFIX = 'Scheduler: '
    START_MESSAGE_TMPL = (
        START_MESSAGE_PREFIX +
        'url=%(comms_method)s://%(host)s:%(port)s/ pid=%(pid)s')
    START_PUB_MESSAGE_PREFIX = 'Workflow publisher: '
    START_PUB_MESSAGE_TMPL = (
        START_PUB_MESSAGE_PREFIX +
        'url=%(comms_method)s://%(host)s:%(port)s')

    # flow information
    workflow: str
    owner: str
    host: str
    id: str  # noqa: A003 (instance attr not local)
    uuid_str: str

    # managers
    profiler: Profiler
    pool: TaskPool
    proc_pool: SubProcPool
    task_job_mgr: TaskJobManager
    task_events_mgr: TaskEventsManager
    workflow_event_handler: WorkflowEventHandler
    data_store_mgr: DataStoreMgr
    workflow_db_mgr: WorkflowDatabaseManager
    broadcast_mgr: BroadcastMgr
    xtrigger_mgr: XtriggerManager
    flow_mgr: FlowMgr

    # queues
    command_queue: Queue
    message_queue: Queue
    ext_trigger_queue: Queue

    # configuration
    options: Values
    cylc_config: DictTree  # [scheduler] config

    # Note: attributes without a default must come before those with defaults

    # flow information
    contact_data: Optional[dict] = None
    bad_hosts: Optional[Set[str]] = None

    # configuration
    config: Optional[WorkflowConfig] = None  # flow config
    flow_file: Optional[str] = None
    flow_file_update_time: Optional[float] = None

    # run options
    is_restart: Optional[bool] = None
    template_vars: Optional[dict] = None

    # workflow params
    stop_mode: Optional[StopMode] = None
    stop_task: Optional[str] = None
    stop_clock_time: Optional[int] = None

    # directories
    workflow_dir: Optional[str] = None
    workflow_log_dir: Optional[str] = None
    workflow_run_dir: Optional[str] = None
    workflow_share_dir: Optional[str] = None
    workflow_work_dir: Optional[str] = None

    # task event loop
    is_paused: Optional[bool] = None
    is_updated: Optional[bool] = None
    is_stalled: Optional[bool] = None
    is_reloaded: Optional[bool] = None

    # main loop
    main_loop_intervals: deque = deque(maxlen=10)
    main_loop_plugins: Optional[dict] = None
    auto_restart_mode: Optional[AutoRestartMode] = None
    auto_restart_time: Optional[float] = None

    # tcp / zmq
    zmq_context: zmq.Context = None
    port: Optional[int] = None
    pub_port: Optional[int] = None
    server: Optional[WorkflowRuntimeServer] = None
    publisher: Optional[WorkflowPublisher] = None
    barrier: Optional[Barrier] = None
    curve_auth: ThreadAuthenticator = None
    client_pub_key_dir: Optional[str] = None

    # queue-released tasks still in prep
    pre_submit_tasks: Optional[List[TaskProxy]] = None

    # profiling
    _profile_amounts: Optional[dict] = None
    _profile_update_times: Optional[dict] = None
    previous_profile_point: float = 0
    count: int = 0

    time_next_kill: Optional[float] = None

    def __init__(self, reg: str, options: Values) -> None:
        # flow information
        self.workflow = reg
        self.workflow_name = get_workflow_name_from_id(self.workflow)
        self.owner = get_user()
        self.host = get_host()
        self.id = f'{self.owner}{ID_DELIM}{self.workflow}'
        self.uuid_str = str(uuid4())
        self.options = options
        self.template_vars = load_template_vars(
            self.options.templatevars,
            self.options.templatevars_file
        )

        # mutable defaults
        self._profile_amounts = {}
        self._profile_update_times = {}
        self.pre_submit_tasks = []
        self.bad_hosts: Set[str] = set()

        self.restored_stop_task_id = None

        # create thread sync barrier for setup
        self.barrier = Barrier(3, timeout=10)

        self.timers: Dict[str, Timer] = {}

    async def install(self):
        """Get the filesystem in the right state to run the flow.
        * Validate flowfiles
        * Install authentication files.
        * Build the directory tree.
        * Copy Python files.

        """
        # Install
        source, _ = workflow_files.get_workflow_source_dir(Path.cwd())
        if source is None:
            # register workflow
            rund = get_workflow_run_dir(self.workflow)
            workflow_files.register(self.workflow, source=rund)

        make_workflow_run_tree(self.workflow)

        # directory information
        self.flow_file = workflow_files.get_flow_file(self.workflow)
        self.workflow_run_dir = get_workflow_run_dir(self.workflow)
        self.workflow_work_dir = get_workflow_run_work_dir(self.workflow)
        self.workflow_share_dir = get_workflow_run_share_dir(self.workflow)
        self.workflow_log_dir = get_workflow_run_log_dir(self.workflow)

        # Create ZMQ keys
        key_housekeeping(
            self.workflow, platform=self.options.host or 'localhost'
        )

        # Extract job.sh from library, for use in job scripts.
        extract_resources(
            workflow_files.get_workflow_srv_dir(self.workflow),
            ['etc/job.sh'])
        # Add python dirs to sys.path
        for sub_dir in ["python", os.path.join("lib", "python")]:
            # TODO - eventually drop the deprecated "python" sub-dir.
            workflow_py = os.path.join(self.workflow_run_dir, sub_dir)
            if os.path.isdir(workflow_py):
                sys.path.append(os.path.join(self.workflow_run_dir, sub_dir))

    async def initialise(self):
        """Initialise the components and sub-systems required to run the flow.

        * Initialise the network components.
        * Initialise managers.

        """
        self.workflow_db_mgr = WorkflowDatabaseManager(
            workflow_files.get_workflow_srv_dir(self.workflow),  # pri_d
            os.path.join(self.workflow_run_dir, 'log'))  # pub_d
        self.data_store_mgr = DataStoreMgr(self)
        self.broadcast_mgr = BroadcastMgr(
            self.workflow_db_mgr, self.data_store_mgr)
        self.flow_mgr = FlowMgr(self.workflow_db_mgr)

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
        workflow_srv_dir = workflow_files.get_workflow_srv_dir(self.workflow)
        client_pub_keyinfo = workflow_files.KeyInfo(
            workflow_files.KeyType.PUBLIC,
            workflow_files.KeyOwner.CLIENT,
            workflow_srv_dir=workflow_srv_dir)
        self.client_pub_key_dir = client_pub_keyinfo.key_path

        # Initial load for the localhost key.
        self.curve_auth.configure_curve(
            domain='*',
            location=(self.client_pub_key_dir)
        )

        self.server = WorkflowRuntimeServer(
            self, context=self.zmq_context, barrier=self.barrier)
        self.publisher = WorkflowPublisher(
            self.workflow, context=self.zmq_context, barrier=self.barrier)
        self.proc_pool = SubProcPool()
        self.command_queue = Queue()
        self.message_queue = Queue()
        self.ext_trigger_queue = Queue()
        self.workflow_event_handler = WorkflowEventHandler(self.proc_pool)

        self.xtrigger_mgr = XtriggerManager(
            self.workflow,
            user=self.owner,
            broadcast_mgr=self.broadcast_mgr,
            data_store_mgr=self.data_store_mgr,
            proc_pool=self.proc_pool,
            workflow_run_dir=self.workflow_run_dir,
            workflow_share_dir=self.workflow_share_dir,
        )

        self.task_events_mgr = TaskEventsManager(
            self.workflow,
            self.proc_pool,
            self.workflow_db_mgr,
            self.broadcast_mgr,
            self.xtrigger_mgr,
            self.data_store_mgr,
            self.options.log_timestamp,
            self.bad_hosts,
            self.reset_inactivity_timer
        )
        self.task_events_mgr.uuid_str = self.uuid_str

        self.task_job_mgr = TaskJobManager(
            self.workflow,
            self.proc_pool,
            self.workflow_db_mgr,
            self.task_events_mgr,
            self.data_store_mgr,
            self.bad_hosts
        )
        self.task_job_mgr.task_remote_mgr.uuid_str = self.uuid_str

        self.profiler = Profiler(self, self.options.profile_mode)

    async def configure(self):
        """Configure the scheduler.

        * Load the flow configuration.
        * Load/write workflow parameters from the DB.
        * Get the data store rolling.

        """
        self.profiler.log_memory("scheduler.py: start configure")

        # Print workflow name to disambiguate in case of inferred run number
        LOG.info(f"Workflow: {self.workflow}")

        self.is_restart = self.workflow_db_mgr.restart_check()
        # Note: since cylc play replaced cylc run/restart, we wait until this
        # point before setting self.is_restart as we couldn't tell if
        # we're restarting until now.

        self._check_startup_opts()

        if self.is_restart:
            pri_dao = self.workflow_db_mgr.get_pri_dao()
            try:
                # This logic handles lack of initial cycle point in flow.cylc
                # Things that can't change on workflow reload.
                pri_dao.select_workflow_params(self._load_workflow_params)
                pri_dao.select_workflow_template_vars(self._load_template_vars)
                pri_dao.execute_queued_items()
            finally:
                pri_dao.close()

        self.profiler.log_memory("scheduler.py: before load_flow_file")
        self.load_flow_file()
        self.profiler.log_memory("scheduler.py: after load_flow_file")

        self.workflow_db_mgr.on_workflow_start(self.is_restart)

        if not self.is_restart:
            # Set workflow params that would otherwise be loaded from database:
            self.options.utc_mode = get_utc_mode()
            self.options.cycle_point_tz = (
                self.config.cfg['scheduler']['cycle point time zone'])

        self.broadcast_mgr.linearized_ancestors.update(
            self.config.get_linearized_ancestors())
        self.task_events_mgr.mail_interval = self.cylc_config['mail'][
            "task event batch interval"]
        self.task_events_mgr.mail_smtp = self._get_events_conf("smtp")
        self.task_events_mgr.mail_footer = self._get_events_conf("footer")
        self.task_events_mgr.workflow_url = self.config.cfg['meta']['URL']
        self.task_events_mgr.workflow_cfg = self.config.cfg
        if self.options.genref:
            LOG.addHandler(ReferenceLogFileHandler(
                self.config.get_ref_log_name()))
        elif self.options.reftest:
            LOG.addHandler(ReferenceLogFileHandler(
                get_workflow_test_log_name(self.workflow)))

        self.pool = TaskPool(
            self.config,
            self.workflow_db_mgr,
            self.task_events_mgr,
            self.data_store_mgr,
            self.flow_mgr
        )

        self.is_reloaded = False
        self.data_store_mgr.initiate_data_model()

        self.profiler.log_memory("scheduler.py: before load_tasks")
        if self.is_restart:
            self._load_pool_from_db()
            if self.restored_stop_task_id is not None:
                self.pool.set_stop_task(self.restored_stop_task_id)
        elif self.options.starttask:
            self._load_pool_from_tasks()
        else:
            self._load_pool_from_point()

        self.process_cylc_stop_point()
        self.profiler.log_memory("scheduler.py: after load_tasks")

        self.workflow_db_mgr.put_workflow_params(self)
        self.workflow_db_mgr.put_workflow_template_vars(self.template_vars)
        self.workflow_db_mgr.put_runtime_inheritance(self.config)

        # Create and set workflow timers.
        event = self.EVENT_INACTIVITY_TIMEOUT
        if self.options.reftest:
            self.config.cfg['scheduler']['events'][f'abort on {event}'] = True
            if not self.config.cfg['scheduler']['events'][event]:
                self.config.cfg['scheduler']['events'][event] = DurationFloat(
                    180
                )
        for event, start_now, log_reset_func in [
            (self.EVENT_INACTIVITY_TIMEOUT, True, LOG.debug),
            (self.EVENT_WORKFLOW_TIMEOUT, True, None),
            (self.EVENT_STALL_TIMEOUT, False, None)
        ]:
            interval = self._get_events_conf(event)
            if interval is not None:
                timer = Timer(event, interval, log_reset_func)
                if start_now:
                    timer.reset()
                self.timers[event] = timer

        # Main loop plugins
        self.main_loop_plugins = main_loop.load(
            self.cylc_config.get('main loop', {}),
            self.options.main_loop
        )

        holdcp = None
        if self.options.holdcp:
            holdcp = self.options.holdcp
        elif self.config.cfg['scheduling']['hold after cycle point']:
            holdcp = self.config.cfg['scheduling']['hold after cycle point']
        if holdcp is not None:
            self.command_set_hold_point(holdcp)

        if self.options.paused_start:
            LOG.info("Paused on start up")
            self.pause_workflow()

        self.profiler.log_memory("scheduler.py: begin run while loop")
        self.is_updated = True
        if self.options.profile_mode:
            self.previous_profile_point = 0
            self.count = 0

        self.profiler.log_memory("scheduler.py: end configure")

    async def start_servers(self):
        """Start the TCP servers."""
        port_range = glbl_cfg().get(['scheduler', 'run hosts', 'ports'])
        self.server.start(port_range[0], port_range[-1])
        self.publisher.start(port_range[0], port_range[-1])
        # wait for threads to setup socket ports before continuing
        self.barrier.wait()
        self.port = self.server.port
        self.pub_port = self.publisher.port
        self.data_store_mgr.delta_workflow_ports()

    async def log_start(self):
        if self.is_restart:
            n_restart = self.workflow_db_mgr.n_restart
        else:
            n_restart = 0

        is_quiet = (cylc.flow.flags.verbosity < 0)
        log_level = LOG.getEffectiveLevel()
        if is_quiet:
            # Temporarily change logging level to log important info
            LOG.setLevel(logging.INFO)

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
        LOG.info(
            'Run: (re)start=%d log=%d', n_restart, 1, extra=log_extra_num)
        LOG.info('Cylc version: %s', CYLC_VERSION, extra=log_extra)
        # Note that the following lines must be present at the top of
        # the workflow log file for use in reference test runs:
        LOG.info('Run mode: %s', self.config.run_mode(), extra=log_extra)
        LOG.info(
            'Initial point: %s', self.config.initial_point, extra=log_extra)
        if self.config.start_point != self.config.initial_point:
            LOG.info(
                'Start point: %s', self.config.start_point, extra=log_extra)
        LOG.info('Final point: %s', self.config.final_point, extra=log_extra)

        if is_quiet:
            LOG.info("Quiet mode on")
            LOG.setLevel(log_level)

    async def start_scheduler(self):
        """Start the scheduler main loop."""
        try:
            self._configure_contact()
            if self.is_restart:
                self.restart_remote_init()
            self.run_event_handlers(self.EVENT_STARTUP, 'workflow starting')
            await asyncio.gather(
                *main_loop.get_runners(
                    self.main_loop_plugins,
                    main_loop.CoroTypes.StartUp,
                    self
                )
            )
            await self.publisher.publish(self.data_store_mgr.publish_deltas)
            self.profiler.start()
            await self.main_loop()

        except SchedulerStop as exc:
            # deliberate stop
            await self.shutdown(exc)
            if self.auto_restart_mode == AutoRestartMode.RESTART_NORMAL:
                self.workflow_auto_restart()
            # run shutdown coros
            await asyncio.gather(
                *main_loop.get_runners(
                    self.main_loop_plugins,
                    main_loop.CoroTypes.ShutDown,
                    self
                )
            )

        except (KeyboardInterrupt, asyncio.CancelledError, Exception) as exc:
            # Includes SchedulerError
            await self.handle_exception(exc)

        else:
            # main loop ends (not used?)
            await self.shutdown(SchedulerStop(StopMode.AUTO.value))

        finally:
            self.profiler.stop()

    async def run(self):
        """Run the startup sequence.

        * initialise
        * configure
        * start_servers
        * start_scheduler

        Lightweight wrapper for convenience.

        """
        try:
            await self.initialise()
            await self.configure()
            await self.start_servers()
            await self.log_start()
        except (KeyboardInterrupt, asyncio.CancelledError, Exception) as exc:
            await self.handle_exception(exc)
        else:
            # note start_scheduler handles its own shutdown logic
            await self.start_scheduler()

    def _load_pool_from_tasks(self):
        """Load task pool with specified tasks, for a new run."""
        LOG.info(f"Start task: {self.options.starttask}")
        # flow number set in this call:
        self.pool.force_trigger_tasks(
            self.options.starttask,
            reflow=True,
            flow_descr=f"original flow from {self.options.starttask}"
        )

    def _load_pool_from_point(self):
        """Load task pool for a cycle point, for a new run.

        Iterate through all sequences to find the first instance of each task.
        Add it to the pool if it has no parents at or after the start point.

        (Later on, tasks with parents will be spawned on demand, and tasks with
        no parents will be auto-spawned when their previous instances are
        released from runhead.)

        """
        if self.config.start_point is not None:
            start_type = "Warm" if self.options.startcp else "Cold"
            LOG.info(f"{start_type} start from {self.config.start_point}")

        flow_num = self.flow_mgr.get_new_flow(
            f"original flow from {self.config.start_point}"
        )
        for name in self.config.get_task_name_list():
            if self.config.start_point is None:
                # No start cycle point at which to load cycling tasks.
                continue
            tdef = self.config.get_taskdef(name)
            try:
                point = sorted([
                    point for point in
                    (seq.get_first_point(self.config.start_point)
                     for seq in tdef.sequences) if point
                ])[0]
            except IndexError:
                # No points
                continue
            parent_points = tdef.get_parent_points(point)
            if not parent_points or all(
                    x < self.config.start_point for x in parent_points):
                self.pool.add_to_pool(
                    TaskProxy(tdef, point, {flow_num})
                )

    def _load_pool_from_db(self):
        """Load task pool from DB, for a restart."""
        if self.options.startcp:
            self.config.start_point = TaskID.get_standardised_point(
                self.options.startcp)
        self.workflow_db_mgr.pri_dao.select_broadcast_states(
            self.broadcast_mgr.load_db_broadcast_states)
        self.workflow_db_mgr.pri_dao.select_task_job_run_times(
            self._load_task_run_times)
        self.workflow_db_mgr.pri_dao.select_task_pool_for_restart(
            self.pool.load_db_task_pool_for_restart)
        self.workflow_db_mgr.pri_dao.select_jobs_for_restart(
            self.data_store_mgr.insert_db_job)
        self.workflow_db_mgr.pri_dao.select_task_action_timers(
            self.pool.load_db_task_action_timers)
        self.workflow_db_mgr.pri_dao.select_xtriggers_for_restart(
            self.xtrigger_mgr.load_xtrigger_for_restart)
        self.workflow_db_mgr.pri_dao.select_abs_outputs_for_restart(
            self.pool.load_abs_outputs_for_restart)
        self.pool.load_db_tasks_to_hold()
        self.pool.update_flow_mgr()

    def restart_remote_init(self):
        """Remote init for all submitted/running tasks in the pool."""
        distinct_install_target_platforms = []
        for itask in self.pool.get_tasks():
            itask.platform['install target'] = (
                get_install_target_from_platform(itask.platform))
            if (
                itask.state(*TASK_STATUSES_ACTIVE)
                and not (
                    is_platform_with_target_in_list(
                        itask.platform['install target'],
                        distinct_install_target_platforms
                    )
                )
            ):
                distinct_install_target_platforms.append(itask.platform)

        incomplete_init = False
        for platform in distinct_install_target_platforms:
            self.task_job_mgr.task_remote_mgr.remote_init(
                platform, self.curve_auth,
                self.client_pub_key_dir)
            status = self.task_job_mgr.task_remote_mgr.remote_init_map[
                platform['install target']]
            if status in (REMOTE_INIT_IN_PROGRESS,
                          REMOTE_FILE_INSTALL_IN_PROGRESS):
                incomplete_init = True
                break
            if status == REMOTE_INIT_DONE:
                self.task_job_mgr.task_remote_mgr.file_install(platform)
        if incomplete_init:
            # TODO: Review whether this sleep is needed.
            sleep(1.0)
            # Remote init/file-install is done via process pool
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
            cycle, task_name, submit_num = parse_job_item(task_job)
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
            self.workflow, to_poll_tasks)

    def get_command_method(self, command_name):
        """Return a command processing method or raise AttributeError."""
        return getattr(self, f'command_{command_name}')

    def process_command_queue(self) -> None:
        """Process queued commands."""
        qsize = self.command_queue.qsize()
        if qsize <= 0:
            return
        LOG.info(f"Processing {qsize} queued command(s)")
        while True:
            try:
                name, args, kwargs = self.command_queue.get(False)
            except Empty:
                break
            args_string = ', '.join(str(a) for a in args)
            kwargs_string = ', '.join(
                f"{key}={value}" for key, value in kwargs.items()
            )
            sep = ', ' if kwargs_string and args_string else ''
            cmdstr = f"{name}({args_string}{sep}{kwargs_string})"
            try:
                n_warnings: Optional[int] = self.get_command_method(name)(
                    *args, **kwargs)
            except SchedulerStop:
                LOG.info(f"Command succeeded: {cmdstr}")
                raise
            except (CommandFailedError, Exception) as exc:
                # Don't let a bad command bring the workflow down.
                if (
                    cylc.flow.flags.verbosity > 1 or
                    not isinstance(exc, CommandFailedError)
                ):
                    LOG.warning(traceback.format_exc())
                LOG.warning(str(exc))
                LOG.warning(f"Command failed: {cmdstr}")
            else:
                if n_warnings:
                    LOG.info(
                        'Command succeeded with %s warning(s): %s' %
                        (n_warnings, cmdstr))
                else:
                    LOG.info(f"Command succeeded: {cmdstr}")
                self.is_updated = True
            self.command_queue.task_done()

    def info_get_graph_raw(self, cto, ctn, grouping=None):
        """Return raw graph."""
        return (
            self.config.get_graph_raw(cto, ctn, grouping),
            self.config.workflow_polling_tasks,
            self.config.leaves,
            self.config.feet
        )

    def command_stop(
        self,
        mode: Union[str, 'StopMode'],
        cycle_point: Optional[str] = None,
        # NOTE clock_time YYYY/MM/DD-HH:mm back-compat removed
        clock_time: Optional[str] = None,
        task: Optional[str] = None,
        flow_num: Optional[int] = None
    ) -> None:
        if flow_num:
            self.pool.stop_flow(flow_num)
            return

        if cycle_point:
            # schedule shutdown after tasks pass provided cycle point
            point = TaskID.get_standardised_point(cycle_point)
            if self.pool.set_stop_point(point):
                self.options.stopcp = str(point)
                self.workflow_db_mgr.put_workflow_stop_cycle_point(
                    self.options.stopcp)
            else:
                # TODO: yield warning
                pass
        elif clock_time:
            # schedule shutdown after wallclock time passes provided time
            parser = TimePointParser()
            self.set_stop_clock(
                int(parser.parse(clock_time).get("seconds_since_unix_epoch"))
            )
        elif task:
            # schedule shutdown after task succeeds
            task_id = TaskID.get_standardised_taskid(task)
            if TaskID.is_valid_id(task_id):
                self.pool.set_stop_task(task_id)
            else:
                # TODO: yield warning
                pass
        else:
            # immediate shutdown
            with suppress(KeyError):
                # By default, mode from mutation is a name from the
                # WorkflowStopMode graphene.Enum, but we need the value
                mode = WorkflowStopMode[mode]  # type: ignore[misc]
            try:
                mode = StopMode(mode)
            except ValueError:
                raise CommandFailedError(f"Invalid stop mode: '{mode}'")
            self._set_stop(mode)
            if mode is StopMode.REQUEST_KILL:
                self.time_next_kill = time()

    def _set_stop(self, stop_mode: Optional[StopMode] = None) -> None:
        """Set shutdown mode."""
        self.proc_pool.set_stopping()
        self.stop_mode = stop_mode
        self.update_data_store()

    def command_release(self, task_globs: Iterable[str]) -> int:
        """Release held tasks."""
        return self.pool.release_held_tasks(task_globs)

    def command_release_hold_point(self) -> None:
        """Release all held tasks and unset workflow hold after cycle point,
        if set."""
        LOG.info("Releasing all tasks and removing hold cycle point.")
        self.pool.release_hold_point()

    def command_resume(self) -> None:
        """Resume paused workflow."""
        self.resume_workflow()

    def command_poll_tasks(self, items=None):
        """Poll pollable tasks or a task or family if options are provided."""
        if self.config.run_mode('simulation'):
            return
        itasks, bad_items = self.pool.filter_task_proxies(items)
        self.task_job_mgr.poll_task_jobs(self.workflow, itasks)
        # (Could filter itasks by state here if needed)
        return len(bad_items)

    def command_kill_tasks(self, items=None):
        """Kill all tasks or a task/family if options are provided."""
        itasks, bad_items = self.pool.filter_task_proxies(items)
        if self.config.run_mode('simulation'):
            for itask in itasks:
                if itask.state(*TASK_STATUSES_ACTIVE):
                    itask.state_reset(TASK_STATUS_FAILED)
                    self.data_store_mgr.delta_task_state(itask)
            return len(bad_items)
        self.task_job_mgr.kill_task_jobs(self.workflow, itasks)
        return len(bad_items)

    def command_hold(self, task_globs: Iterable[str]) -> int:
        """Hold specified tasks."""
        return self.pool.hold_tasks(task_globs)

    def command_set_hold_point(self, point: str) -> None:
        """Hold all tasks after the specified cycle point."""
        cycle_point = TaskID.get_standardised_point(point)
        if cycle_point is None:
            raise CyclingError("Cannot set hold point to None")
        LOG.info(
            f"Setting hold cycle point: {cycle_point}\n"
            "All tasks after this point will be held.")
        self.pool.set_hold_point(cycle_point)

    def command_pause(self) -> None:
        """Pause the workflow."""
        self.pause_workflow()

    @staticmethod
    def command_set_verbosity(lvl):
        """Set workflow verbosity."""
        try:
            LOG.setLevel(int(lvl))
        except (TypeError, ValueError):
            return
        if lvl <= logging.DEBUG:
            cylc.flow.flags.verbosity = 2
        elif lvl < logging.INFO:
            cylc.flow.flags.verbosity = 1
        elif lvl == logging.INFO:
            cylc.flow.flags.verbosity = 0
        else:
            cylc.flow.flags.verbosity = -1
        return True, 'OK'

    def command_remove_tasks(self, items):
        """Remove tasks."""
        return self.pool.remove_tasks(items)

    def command_reload_workflow(self):
        """Reload workflow configuration."""
        LOG.info("Reloading the workflow definition.")
        old_tasks = set(self.config.get_task_name_list())
        # Things that can't change on workflow reload:
        pri_dao = self.workflow_db_mgr.get_pri_dao()
        pri_dao.select_workflow_params(self._load_workflow_params)

        self.load_flow_file(is_reload=True)
        self.broadcast_mgr.linearized_ancestors = (
            self.config.get_linearized_ancestors())
        self.pool.set_do_reload(self.config)
        self.task_events_mgr.mail_interval = self.cylc_config['mail'][
            'task event batch interval']
        self.task_events_mgr.mail_smtp = self._get_events_conf("smtp")
        self.task_events_mgr.mail_footer = self._get_events_conf("footer")

        # Log tasks that have been added by the reload, removed tasks are
        # logged by the TaskPool.
        add = set(self.config.get_task_name_list()) - old_tasks
        for task in add:
            LOG.warning("Added task: '%s'" % (task,))
        self.workflow_db_mgr.put_workflow_template_vars(self.template_vars)
        self.workflow_db_mgr.put_runtime_inheritance(self.config)
        self.workflow_db_mgr.put_workflow_params(self)
        self.is_updated = True

    def get_contact_data(self) -> Dict[str, str]:
        """Extract contact data from this Scheduler.

        This provides the information that is written to the contact file.
        """
        fields = workflow_files.ContactFileFields
        proc = psutil.Process()
        # fmt: off
        return {
            fields.API:
                str(API),
            fields.HOST:
                self.host,
            fields.NAME:
                self.workflow,
            fields.OWNER:
                self.owner,
            fields.PORT:
                str(self.server.port),  # type: ignore
            fields.PID:
                str(proc.pid),
            fields.COMMAND:
                cli_format(proc.cmdline()),
            fields.PUBLISH_PORT:
                str(self.publisher.port),  # type: ignore
            fields.WORKFLOW_RUN_DIR_ON_WORKFLOW_HOST:  # type: ignore
                self.workflow_run_dir,
            fields.UUID:
                self.uuid_str,
            fields.VERSION:
                CYLC_VERSION,
            fields.SCHEDULER_SSH_COMMAND:
                str(get_platform()['ssh command']),
            fields.SCHEDULER_CYLC_PATH:
                str(get_platform()['cylc path']),
            fields.SCHEDULER_USE_LOGIN_SHELL:
                str(get_platform()['use login shell'])
        }
        # fmt: on

    def _configure_contact(self) -> None:
        """Create contact file."""
        # Make sure another workflow of the same name hasn't started while this
        # one is starting
        # NOTE: raises ServiceFileError if workflow is running
        workflow_files.detect_old_contact_file(self.workflow)

        # Extract contact data.
        contact_data = self.get_contact_data()

        # Write workflow contact file.
        # Preserve contact data in memory, for regular health check.
        workflow_files.dump_contact_file(self.workflow, contact_data)
        self.contact_data = contact_data

    def load_flow_file(self, is_reload=False):
        """Load, and log the workflow definition."""
        # Local workflow environment set therein.
        self.config = WorkflowConfig(
            self.workflow,
            self.flow_file,
            self.options,
            self.template_vars,
            is_reload=is_reload,
            xtrigger_mgr=self.xtrigger_mgr,
            mem_log_func=self.profiler.log_memory,
            output_fname=os.path.join(
                self.workflow_run_dir, 'log', 'flow-config',
                workflow_files.WorkflowFiles.FLOW_FILE_PROCESSED
            ),
            run_dir=self.workflow_run_dir,
            log_dir=self.workflow_log_dir,
            work_dir=self.workflow_work_dir,
            share_dir=self.workflow_share_dir,
        )
        self.cylc_config = DictTree(
            self.config.cfg['scheduler'],
            glbl_cfg().get(['scheduler'])
        )
        self.flow_file_update_time = time()
        # Dump the loaded flow.cylc file for future reference.
        time_str = get_current_time_string(
            override_use_utc=True, use_basic_format=True,
            display_sub_seconds=False
        )
        if is_reload:
            load_type = "reload"
        elif self.is_restart:
            load_type = "restart"
        else:
            load_type = "start"
        file_name = get_workflow_run_config_log_dir(
            self.workflow, f"{time_str}-{load_type}.cylc")
        with open(file_name, "wb") as handle:
            handle.write(b"# cylc-version: %s\n" % CYLC_VERSION.encode())
            printcfg(self.config.cfg, none_str=None, handle=handle)

        if not self.config.initial_point and not self.is_restart:
            LOG.warning('No initial cycle point provided - no cycling tasks '
                        'will be loaded.')

        # Pass static cylc and workflow variables to job script generation code
        self.task_job_mgr.job_file_writer.set_workflow_env({
            **verbosity_to_env(cylc.flow.flags.verbosity),
            'CYLC_UTC': str(get_utc_mode()),
            'CYLC_WORKFLOW_ID': self.workflow,
            'CYLC_WORKFLOW_NAME': self.workflow_name,
            'CYLC_CYCLING_MODE': str(
                self.config.cfg['scheduling']['cycling mode']
            ),
            'CYLC_WORKFLOW_INITIAL_CYCLE_POINT': str(
                self.config.initial_point
            ),
            'CYLC_WORKFLOW_FINAL_CYCLE_POINT': str(self.config.final_point),
        })

    def _load_workflow_params(self, row_idx, row):
        """Load a row in the "workflow_params" table in a restart/reload.

        This currently includes:
        * Initial/Final cycle points.
        * Start/Stop Cycle points.
        * Stop task.
        * Workflow UUID.
        * A flag to indicate if the workflow should be paused or not.
        * Original workflow run time zone.
        """
        if row_idx == 0:
            LOG.info('LOADING workflow parameters')
        key, value = row
        if key in self.workflow_db_mgr.KEY_INITIAL_CYCLE_POINT_COMPATS:
            if self.is_restart and self.options.icp == 'reload':
                LOG.debug(f"- initial point = {value} (ignored)")
            elif self.options.icp is None:
                self.options.icp = value
                LOG.info(f"+ initial point = {value}")
        elif key in self.workflow_db_mgr.KEY_START_CYCLE_POINT_COMPATS:
            if self.is_restart and self.options.startcp == 'reload':
                LOG.debug(f"- start point = {value} (ignored)")
            elif self.options.startcp is None:
                self.options.startcp = value
                LOG.info(f"+ start point = {value}")
        elif key in self.workflow_db_mgr.KEY_FINAL_CYCLE_POINT_COMPATS:
            if self.is_restart and self.options.fcp == 'reload':
                LOG.debug(f"- override final point = {value} (ignored)")
            elif self.options.fcp is None:
                self.options.fcp = value
                LOG.info(f"+ override final point = {value}")
        elif key == self.workflow_db_mgr.KEY_STOP_CYCLE_POINT:
            if self.is_restart and self.options.stopcp == 'reload':
                LOG.debug(f"- stop point = {value} (ignored)")
            elif self.options.stopcp is None:
                self.options.stopcp = value
                LOG.info(f"+ stop point = {value}")
        elif key == self.workflow_db_mgr.KEY_RUN_MODE:
            if self.options.run_mode is None:
                self.options.run_mode = value
                LOG.info(f"+ run mode = {value}")
        elif key == self.workflow_db_mgr.KEY_UUID_STR:
            self.uuid_str = value
            LOG.info('+ workflow UUID = %s', value)
        elif key == self.workflow_db_mgr.KEY_PAUSED:
            if self.options.paused_start is None:
                self.options.paused_start = bool(value)
                LOG.info(f'+ paused = {bool(value)}')
        elif key == self.workflow_db_mgr.KEY_HOLD_CYCLE_POINT:
            if self.options.holdcp is None:
                self.options.holdcp = value
                LOG.info('+ hold point = %s', value)
        elif key == self.workflow_db_mgr.KEY_STOP_CLOCK_TIME:
            value = int(value)
            if time() <= value:
                self.stop_clock_time = value
                LOG.info('+ stop clock time = %d (%s)', value, time2str(value))
            else:
                LOG.debug(
                    '- stop clock time = %d (%s) (ignored)',
                    value,
                    time2str(value))
        elif key == self.workflow_db_mgr.KEY_STOP_TASK:
            self.restored_stop_task_id = value
            LOG.info('+ stop task = %s', value)
        elif key == self.workflow_db_mgr.KEY_UTC_MODE:
            value = bool(int(value))
            self.options.utc_mode = value
            LOG.info(f"+ UTC mode = {value}")
        elif key == self.workflow_db_mgr.KEY_CYCLE_POINT_TIME_ZONE:
            self.options.cycle_point_tz = value
            LOG.info(f"+ cycle point time zone = {value}")

    def _load_template_vars(self, _, row):
        """Load workflow start up template variables."""
        key, value = row
        # Command line argument takes precedence
        if key not in self.template_vars:
            self.template_vars[key] = value

    def run_event_handlers(self, event, reason=""):
        """Run a workflow event handler.

        Run workflow events in simulation and dummy mode ONLY if enabled.
        """
        conf = self.config
        with suppress(KeyError):
            if (
                conf.run_mode('simulation', 'dummy')
            ):
                return
        self.workflow_event_handler.handle(conf, WorkflowEventContext(
            event, str(reason), self.workflow, self.uuid_str, self.owner,
            self.host, self.server.port))

    def release_queued_tasks(self):
        """Release queued tasks, and submit task jobs.

        The task queue manages references to task proxies in the task pool.

        Newly released tasks are passed to job submission multiple times until
        associated asynchronous host select, remote init, and remote install
        processes are done.

        """
        # Forget tasks that are no longer preparing for job submission.
        self.pre_submit_tasks = [
            itask for itask in self.pre_submit_tasks if
            itask.waiting_on_job_prep
        ]

        # Add newly released tasks to those still preparing.
        self.pre_submit_tasks += self.pool.release_queued_tasks()

        if (
            self.pre_submit_tasks and
            not self.is_paused and
            self.stop_mode is None and
            self.auto_restart_time is None
        ):
            # Start the job submission process.
            self.is_updated = True

            self.task_job_mgr.task_remote_mgr.rsync_includes = (
                self.config.get_validated_rsync_includes())

            for itask in self.task_job_mgr.submit_task_jobs(
                self.workflow,
                self.pre_submit_tasks,
                self.curve_auth,
                self.client_pub_key_dir,
                self.config.run_mode('simulation')
            ):
                # (Not using f"{itask}"_here to avoid breaking func tests)
                LOG.info(
                    f"[{itask.identity}] -triggered off "
                    f"{itask.state.get_resolved_dependencies()}"
                )

    def process_workflow_db_queue(self):
        """Update workflow DB."""
        self.workflow_db_mgr.process_queued_ops()

    def database_health_check(self):
        """If public database is stuck, blast it away by copying the content
        of the private database into it."""
        self.workflow_db_mgr.recover_pub_from_pri()

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
                LOG.warning(f"[{itask}] {msg}")
                self.task_events_mgr.setup_event_handlers(
                    itask, self.task_events_mgr.EVENT_LATE, msg)
                self.workflow_db_mgr.put_insert_task_late_flags(itask)

    def reset_inactivity_timer(self):
        """Reset inactivity timer - method passed to task event manager."""
        with suppress(KeyError):
            self.timers[self.EVENT_INACTIVITY_TIMEOUT].reset()

    def timeout_check(self):
        """Check workflow and task timers."""
        self.check_workflow_timers()
        # check submission and execution timeout and polling timers
        if not self.config.run_mode('simulation'):
            self.task_job_mgr.check_task_jobs(self.workflow, self.pool)

    async def workflow_shutdown(self):
        """Determines if the workflow can be shutdown yet."""
        if self.pool.check_abort_on_task_fails():
            self._set_stop(StopMode.AUTO_ON_TASK_FAILURE)

        # Can workflow shut down automatically?
        if self.stop_mode is None and (
            self.stop_clock_done() or
            self.pool.stop_task_done() or
            self.check_auto_shutdown()
        ):
            self._set_stop(StopMode.AUTO)

        # Is the workflow ready to shut down now?
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

        # Is the workflow set to auto stop [+restart] now ...
        if self.auto_restart_time is None or time() < self.auto_restart_time:
            # ... no
            pass
        elif self.auto_restart_mode == AutoRestartMode.RESTART_NORMAL:
            # ... yes - wait for local jobs to complete before restarting
            #           * Avoid polling issues see #2843
            #           * Ensure the host can be safely taken down once the
            #             workflow has stopped running.
            for itask in self.pool.get_tasks():
                if (
                        itask.state(*TASK_STATUSES_ACTIVE)
                        and itask.summary['job_runner_name']
                        and not is_remote_platform(itask.platform)
                        and self.task_job_mgr.job_runner_mgr
                        .is_job_local_to_host(
                            itask.summary['job_runner_name'])
                ):
                    LOG.info('Waiting for jobs running on localhost to '
                             'complete before attempting restart')
                    break
            else:
                self._set_stop(StopMode.REQUEST_NOW_NOW)
        elif (  # noqa: SIM106
            self.auto_restart_mode == AutoRestartMode.FORCE_STOP
        ):
            # ... yes - leave local jobs running then stop the workflow
            #           (no restart)
            self._set_stop(StopMode.REQUEST_NOW)
        else:
            raise SchedulerError(
                'Invalid auto_restart_mode=%s' % self.auto_restart_mode)

    def workflow_auto_restart(self, max_retries=3):
        """Attempt to restart the workflow assuming it has already stopped."""
        cmd = ['cylc', 'play', quote(self.workflow)]
        if self.options.abort_if_any_task_fails:
            cmd.append('--abort-if-any-task-fails')

        for attempt_no in range(max_retries):
            new_host = select_workflow_host(cached=False)[0]
            LOG.info(f'Attempting to restart on "{new_host}"')

            # proc will start with current env (incl CYLC_HOME etc)
            proc = Popen(  # nosec
                [*cmd, f'--host={new_host}'],
                stdin=DEVNULL,
                stdout=PIPE,
                stderr=PIPE,
            )
            # * new_host comes from internal interface which can only return
            #   host names
            if proc.wait():
                msg = 'Could not restart workflow'
                if attempt_no < max_retries:
                    msg += (
                        f' will retry in {self.INTERVAL_AUTO_RESTART_ERROR}s')
                LOG.critical(
                    f"{msg}. Restart error:\n",
                    f"{proc.communicate()[1].decode()}")
                sleep(self.INTERVAL_AUTO_RESTART_ERROR)
            else:
                LOG.info(f'Workflow now running on "{new_host}".')
                return True
        LOG.critical(
            'Workflow unable to automatically restart after '
            f'{max_retries} tries - manual restart required.')
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

    async def main_loop(self):
        """The scheduler main loop."""
        while True:  # MAIN LOOP
            tinit = time()

            # Useful for debugging core scheduler issues:
            # self.pool.log_task_pool(logging.CRITICAL)

            if self.pool.do_reload:
                # Re-initialise data model on reload
                self.data_store_mgr.initiate_data_model(reloaded=True)
                self.pool.reload_taskdefs()
                # Load jobs from DB
                self.workflow_db_mgr.pri_dao.select_jobs_for_restart(
                    self.data_store_mgr.insert_db_job)
                LOG.info("Reload completed.")
                self.is_reloaded = True
                self.is_updated = True

            self.process_command_queue()

            if self.pool.release_runahead_tasks():
                self.is_updated = True
                self.reset_inactivity_timer()

            self.proc_pool.process()

            # Tasks in the main pool that are waiting but not queued must be
            # waiting on external dependencies, i.e. xtriggers or ext_triggers.
            # For these tasks, call any unsatisfied xtrigger functions, and
            # queue tasks that have become ready. (Tasks do not appear in the
            # main pool at all until all other-task deps are satisfied, and are
            # queued immediately on release from runahead limiting if they are
            # not waiting on external deps).
            housekeep_xtriggers = False
            for itask in self.pool.get_tasks():
                if (
                    not itask.state(TASK_STATUS_WAITING)
                    or itask.state.is_queued
                    or itask.state.is_runahead
                ):
                    continue

                if (
                    itask.state.xtriggers
                    and not itask.state.xtriggers_all_satisfied()
                ):
                    # Call unsatisfied xtriggers if not already in-process.
                    # Results are returned asynchronously.
                    self.xtrigger_mgr.call_xtriggers_async(itask)
                    # Check for satisfied xtriggers, and queue if ready.
                    if self.xtrigger_mgr.check_xtriggers(
                            itask, self.workflow_db_mgr.put_xtriggers):
                        housekeep_xtriggers = True
                        if all(itask.is_ready_to_run()):
                            self.pool.queue_task(itask)

                # Check for satisfied ext_triggers, and queue if ready.
                if (
                    itask.state.external_triggers
                    and not itask.state.external_triggers_all_satisfied()
                    and self.broadcast_mgr.check_ext_triggers(
                        itask, self.ext_trigger_queue)
                    and all(itask.is_ready_to_run())
                ):
                    self.pool.queue_task(itask)

            if housekeep_xtriggers:
                # (Could do this periodically?)
                self.xtrigger_mgr.housekeep(self.pool.get_tasks())

            self.pool.set_expired_tasks()

            self.release_queued_tasks()

            if self.pool.sim_time_check(self.message_queue):
                # A simulated task state change occurred.
                self.reset_inactivity_timer()

            self.broadcast_mgr.expire_broadcast(self.pool.get_min_point())
            self.late_tasks_check()

            self.process_queued_task_messages()
            self.process_command_queue()
            self.task_events_mgr.process_events(self)

            # Update state summary, database, and uifeed
            self.workflow_db_mgr.put_task_event_timers(self.task_events_mgr)
            has_updated = await self.update_data_structure()
            if has_updated:
                # Workflow can't be stalled, so stop the stalled timer.
                with suppress(KeyError):
                    self.timers[self.EVENT_STALL_TIMEOUT].stop()

            self.process_workflow_db_queue()

            # If public database is stuck, blast it away by copying the content
            # of the private database into it.
            self.database_health_check()

            # Shutdown workflow if timeouts have occurred
            self.timeout_check()

            # Does the workflow need to shutdown on task failure?
            await self.workflow_shutdown()

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
                # Has the workflow stalled?
                self.check_workflow_stalled()

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
            t for t in self.pool.get_tasks() if t.state.is_updated]
        has_updated = self.is_updated or updated_tasks
        # Add tasks that have moved moved from runahead to live pool.
        if has_updated or self.data_store_mgr.updates_pending:
            # Collect/apply data store updates/deltas
            self.data_store_mgr.update_data_structure(
                reloaded=self.is_reloaded)
            self.is_reloaded = False
            # Publish updates:
            if self.data_store_mgr.publish_pending:
                self.data_store_mgr.publish_pending = False
                await self.publisher.publish(
                    self.data_store_mgr.publish_deltas)
        if has_updated:
            # Database update
            self.workflow_db_mgr.put_task_pool(self.pool)
            # Reset workflow and task updated flags.
            self.is_updated = False
            self.is_stalled = False
            for itask in updated_tasks:
                itask.state.is_updated = False
            self.update_data_store()
        return has_updated

    def check_workflow_timers(self):
        """Check timers, and abort or run event handlers as configured."""
        for event, timer in self.timers.items():
            if not timer.timed_out():
                continue
            abort_conf = f"abort on {event}"
            if self._get_events_conf(abort_conf):
                # "cylc play" needs to exit with error status here.
                raise SchedulerError(f'"{abort_conf}" is set')
            if self._get_events_conf(f"{event} handlers") is not None:
                self.run_event_handlers(event)

    def check_workflow_stalled(self):
        """Check if workflow is stalled or not."""
        if self.is_stalled:  # already reported
            return True
        if self.is_paused:  # cannot be stalled it's not even running
            return False
        is_stalled = self.pool.is_stalled()
        if is_stalled != self.is_stalled:
            self.update_data_store()
            self.is_stalled = is_stalled
        if self.is_stalled:
            self.run_event_handlers(self.EVENT_STALL, 'workflow stalled')
            with suppress(KeyError):
                # Start stall timeout timer
                self.timers[self.EVENT_STALL_TIMEOUT].reset()
        return self.is_stalled

    async def shutdown(self, reason: Exception) -> None:
        """Gracefully shut down the scheduler."""
        # At the moment this method must be called from the main_loop.
        # In the future it should shutdown the main_loop itself but
        # we're not quite there yet.
        try:
            await self._shutdown(reason)
        except (KeyboardInterrupt, asyncio.CancelledError, Exception) as exc:
            # In case of exception in the shutdown method itself.
            LOG.error("Error during shutdown")
            # Suppress the reason for shutdown, which is logged separately
            exc.__suppress_context__ = True
            if isinstance(exc, CylcError):
                LOG.error(f"{exc.__class__.__name__}: {exc}")
                if cylc.flow.flags.verbosity > 1:
                    LOG.exception(exc)
            else:
                LOG.exception(exc)
            # Re-raise exception to be caught higher up (sets the exit code)
            raise exc from None

    async def _shutdown(self, reason: Exception) -> None:
        """Shutdown the workflow."""
        if isinstance(reason, SchedulerStop):
            LOG.info(f'Workflow shutting down - {reason.args[0]}')
            # Unset the "paused" status of the workflow if not auto-restarting
            if self.auto_restart_mode != AutoRestartMode.RESTART_NORMAL:
                self.resume_workflow(quiet=True)
        elif isinstance(reason, SchedulerError):
            LOG.error(f'Workflow shutting down - {reason}')
        elif isinstance(reason, (CylcError, TemplateVarLanguageClash)):
            LOG.error(
                "Workflow shutting down - "
                f"{reason.__class__.__name__}: {reason}")
            if cylc.flow.flags.verbosity > 1:
                LOG.exception(reason)
        else:
            LOG.exception(reason)
            if str(reason):
                LOG.critical(f'Workflow shutting down - {reason}')
            else:
                LOG.critical('Workflow shutting down')

        if hasattr(self, 'proc_pool'):
            self.proc_pool.close()
            if self.proc_pool.is_not_done():
                # e.g. KeyboardInterrupt
                self.proc_pool.terminate()
            self.proc_pool.process()

        if hasattr(self, 'pool'):
            if not self.is_stalled:
                # (else already logged)
                # Log partially satisfied dependencies and incomplete tasks.
                self.pool.is_stalled()
            self.pool.warn_stop_orphans()
            try:
                self.workflow_db_mgr.put_task_event_timers(
                    self.task_events_mgr
                )
                self.workflow_db_mgr.put_task_pool(self.pool)
            except Exception as exc:
                LOG.exception(exc)

        if self.server:
            self.server.stop()
        if self.publisher:
            await self.publisher.publish(
                [(b'shutdown', str(reason).encode('utf-8'))]
            )
            self.publisher.stop()
        self.curve_auth.stop()  # stop the authentication thread

        # Flush errors and info before removing workflow contact file
        sys.stdout.flush()
        sys.stderr.flush()

        try:
            # Remove ZMQ keys from scheduler
            LOG.debug("Removing authentication keys from scheduler")
            key_housekeeping(self.workflow, create=False)
        except Exception as ex:
            LOG.exception(ex)
        # disconnect from workflow-db, stop db queue
        try:
            self.workflow_db_mgr.process_queued_ops()
            self.workflow_db_mgr.on_workflow_shutdown()
        except Exception as exc:
            LOG.exception(exc)

        # NOTE: Removing the contact file should happen last of all (apart
        # from running event handlers), because the existence of the file is
        # used to determine if the workflow is running
        if self.contact_data:
            fname = workflow_files.get_contact_file(self.workflow)
            try:
                os.unlink(fname)
            except OSError as exc:
                LOG.warning(f"failed to remove workflow contact file: {fname}")
                LOG.exception(exc)
            if self.task_job_mgr:
                self.task_job_mgr.task_remote_mgr.remote_tidy()

        # The getattr() calls and if tests below are used in case the
        # workflow is not fully configured before the shutdown is called.
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
        self.workflow_db_mgr.put_workflow_stop_clock_time(self.stop_clock_time)
        self.update_data_store()

    def stop_clock_done(self):
        """Return True if wall clock stop time reached."""
        if self.stop_clock_time is None:
            return
        now = time()
        if now > self.stop_clock_time:
            LOG.info("Wall clock stop time reached: %s", time2str(
                self.stop_clock_time))
            self.stop_clock_time = None
            self.workflow_db_mgr.delete_workflow_stop_clock_time()
            self.update_data_store()
            return True
        LOG.debug("stop time=%d; current time=%d", self.stop_clock_time, now)
        return False

    def check_auto_shutdown(self):
        """Check if we should shut down now."""
        if self.is_paused:
            # Don't if paused.
            return False

        self.pool.release_runahead_tasks()

        if self.check_workflow_stalled():
            return False

        if any(
            itask for itask in self.pool.get_tasks()
            if itask.state(
                TASK_STATUS_PREPARING,
                TASK_STATUS_SUBMITTED,
                TASK_STATUS_RUNNING
            )
            or (itask.state(TASK_STATUS_WAITING)
                and not itask.state.is_runahead)
        ):
            # Don't if there are more tasks to run (if waiting and not
            # runahead, then held, queued, or xtriggered).
            return False

        # Can shut down.
        if self.pool.stop_point:
            self.options.stopcp = None
            self.pool.stop_point = None
            self.workflow_db_mgr.delete_workflow_stop_cycle_point()
            self.update_data_store()

        return True

    def pause_workflow(self) -> None:
        """Pause the workflow."""
        if self.is_paused:
            LOG.info("Workflow is already paused")
            return
        LOG.info("PAUSING the workflow now")
        self.is_paused = True
        self.workflow_db_mgr.put_workflow_paused()
        self.update_data_store()

    def resume_workflow(self, quiet: bool = False) -> None:
        """Resume the workflow.

        Args:
            quiet: whether to log anything.
        """
        if not self.is_paused:
            if not quiet:
                LOG.warning("Cannot resume - workflow is not paused")
            return
        if not quiet:
            LOG.info("RESUMING the workflow now")
        self.is_paused = False
        self.workflow_db_mgr.delete_workflow_paused()
        self.update_data_store()

    def command_force_trigger_tasks(self, items, reflow, flow_descr):
        """Trigger tasks."""
        return self.pool.force_trigger_tasks(items, reflow, flow_descr)

    def command_force_spawn_children(self, items, outputs, flow_num):
        """Force spawn task successors.

        User-facing method name: set_outputs.

        """
        return self.pool.force_spawn_children(items, outputs, flow_num)

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
        proc = Popen(  # nosec
            ["ps", "-o%cpu= ", str(os.getpid())],
            stdin=DEVNULL,
            stdout=PIPE,
        )
        # * there is no untrusted input
        try:
            cpu_frac = float(proc.communicate()[0])
        except (TypeError, OSError, ValueError) as exc:
            LOG.warning("Cannot get CPU % statistics: %s" % exc)
            return
        self._update_profile_info("CPU %", cpu_frac, amount_format="%.1f")

    def _get_events_conf(self, key, default=None):
        """Return a named [scheduler][[events]] configuration."""
        return self.workflow_event_handler.get_events_conf(
            self.config, key, default)

    def _check_startup_opts(self) -> None:
        """Abort if "cylc play" options are not consistent with type of start.

        * Start from cycle point or task is not valid for a restart.
        * Reloading of cycle points is not valid for a new run.
        """
        for opt in ('icp', 'startcp', 'starttask'):
            value = getattr(self.options, opt, None)
            if self.is_restart:
                if value is not None:
                    raise UserInputError(
                        f"option --{opt} is not valid for restart"
                    )
            elif value == 'reload':
                raise UserInputError(
                    f"option --{opt}=reload is not valid "
                    "(only --fcp and --stopcp can be 'reload')"
                )
        if not self.is_restart:
            for opt in ('fcp', 'stopcp'):
                if getattr(self.options, opt, None) == 'reload':
                    raise UserInputError(
                        f"option --{opt}=reload is only valid for restart"
                    )

    def process_cylc_stop_point(self):
        """
        Set stop point.

        In decreasing priority, stop cycle point (``stopcp``) is set:
        * From the final point for ``cylc play --stopcp=reload``.
        * From the command line (``cylc play --stopcp=XYZ``).
        * From the database.
        * From the flow.cylc file (``[scheduling]stop after cycle point``).
        """
        stoppoint = None
        if self.is_restart and self.options.stopcp == 'reload':
            stoppoint = self.config.final_point
        elif self.options.stopcp:
            stoppoint = self.options.stopcp
        # Tests whether pool has stopcp from database on restart.
        elif (
            self.pool.stop_point and
            self.pool.stop_point != self.config.final_point
        ):
            stoppoint = self.pool.stop_point
        elif 'stop after cycle point' in self.config.cfg['scheduling']:
            stoppoint = self.config.cfg['scheduling']['stop after cycle point']

        if stoppoint is not None:
            self.options.stopcp = str(stoppoint)
            self.pool.set_stop_point(get_point(self.options.stopcp))
            self.validate_finalcp()
            self.update_data_store()

    async def handle_exception(self, exc: Exception) -> NoReturn:
        """Gracefully shut down the scheduler given a caught exception.

        Re-raises the exception to be caught higher up (sets the exit code).

        Args:
            exc: The caught exception to be logged during the shutdown.
        """
        await self.shutdown(exc)
        raise exc from None

    def validate_finalcp(self):
        """Warn if Stop Cycle point is on or after the final cycle point
        """
        if self.config.final_point is None:
            return
        if get_point(self.options.stopcp) > self.config.final_point:
            LOG.warning(
                f"Stop cycle point '{self.options.stopcp}' will have no "
                "effect as it is after the final cycle "
                f"point '{self.config.final_point}'.")

    def update_data_store(self):
        """Sets the update flag on the data store.

        Call this method whenever the Scheduler's state has changed in a way
        that requires a data store update.

        This call should often be associated with a database update.

        Note that must updates e.g. task / job states are handled elsewhere,
        this applies to changes made directly to scheduler attributes etc.
        """
        self.data_store_mgr.updates_pending = True
