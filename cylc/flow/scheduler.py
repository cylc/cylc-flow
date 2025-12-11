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
from collections import deque
from contextlib import suppress
import logging
import os
from pathlib import Path
from queue import (
    Empty,
    Queue,
)
from shlex import quote
import signal
from subprocess import (
    DEVNULL,
    PIPE,
    Popen,
)
import sys
from threading import (
    Barrier,
    Thread,
)
from time import (
    sleep,
    time,
)
import traceback
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Dict,
    Iterable,
    List,
    Literal,
    NoReturn,
    Optional,
    Set,
    Tuple,
    Union,
)
from uuid import uuid4

from metomi.isodatetime.exceptions import TimePointDumperBoundsError
import psutil

from cylc.flow import (
    LOG,
    __version__ as CYLC_VERSION,
    command_validation,
    commands,
    main_loop,
    workflow_files,
)
from cylc.flow.broadcast_mgr import BroadcastMgr
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.config import WorkflowConfig
from cylc.flow.data_store_mgr import DataStoreMgr
from cylc.flow.exceptions import (
    CommandFailedError,
    CylcError,
    InputError,
)
import cylc.flow.flags
from cylc.flow.flow_mgr import (
    FLOW_NEW,
    FLOW_NONE,
    FlowMgr,
    stringify_flow_nums,
)
from cylc.flow.host_select import (
    HostSelectException,
    select_workflow_host,
)
from cylc.flow.hostuserutil import (
    get_host,
    get_user,
    is_remote_platform,
)
from cylc.flow.id import Tokens
from cylc.flow.log_level import (
    verbosity_to_env,
    verbosity_to_opts,
)
from cylc.flow.loggingutil import (
    ReferenceLogFileHandler,
    RotatingLogFileHandler,
    get_next_log_number,
    get_reload_start_number,
    get_sorted_logs_by_time,
    patch_log_level,
)
from cylc.flow.network import API
from cylc.flow.network.authentication import key_housekeeping
from cylc.flow.network.server import WorkflowRuntimeServer
from cylc.flow.parsec.exceptions import ParsecError
from cylc.flow.parsec.OrderedDict import DictTree
from cylc.flow.parsec.validate import DurationFloat
from cylc.flow.pathutil import (
    get_workflow_name_from_id,
    get_workflow_run_config_log_dir,
    get_workflow_run_dir,
    get_workflow_run_scheduler_log_dir,
    get_workflow_run_share_dir,
    get_workflow_run_work_dir,
    get_workflow_test_log_path,
    make_workflow_run_tree,
)
from cylc.flow.platforms import (
    get_install_target_from_platform,
    get_localhost_install_target,
    get_platform,
    is_platform_with_target_in_list,
)
from cylc.flow.profiler import Profiler
from cylc.flow.resources import get_resources
from cylc.flow.run_modes import RunMode
from cylc.flow.run_modes.simulation import sim_time_check
from cylc.flow.subprocpool import SubProcPool
from cylc.flow.task_events_mgr import TaskEventsManager
from cylc.flow.task_job_mgr import TaskJobManager
from cylc.flow.task_pool import TaskPool
from cylc.flow.task_remote_mgr import (
    REMOTE_FILE_INSTALL_255,
    REMOTE_FILE_INSTALL_DONE,
    REMOTE_FILE_INSTALL_FAILED,
    REMOTE_INIT_255,
    REMOTE_INIT_DONE,
    REMOTE_INIT_FAILED,
)
from cylc.flow.task_state import (
    TASK_STATUS_FAILED,
    TASK_STATUS_PREPARING,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_WAITING,
    TASK_STATUSES_ACTIVE,
    TASK_STATUSES_NEVER_ACTIVE,
)
from cylc.flow.taskdef import TaskDef
from cylc.flow.templatevars import (
    eval_var,
    get_template_vars,
)
from cylc.flow.timer import Timer
from cylc.flow.util import cli_format
from cylc.flow.wallclock import (
    get_current_time_string,
    get_time_string_from_unix_time as time2str,
    get_utc_mode,
)
from cylc.flow.workflow_db_mgr import WorkflowDatabaseManager
from cylc.flow.workflow_events import WorkflowEventHandler
from cylc.flow.workflow_status import (
    AutoRestartMode,
    StopMode,
)
from cylc.flow.xtrigger_mgr import XtriggerManager


if TYPE_CHECKING:
    from optparse import Values

    from cylc.flow.network.resolvers import TaskMsg
    from cylc.flow.task_proxy import TaskProxy


class SchedulerStop(CylcError):
    """Scheduler normal stop."""


class SchedulerError(CylcError):
    """Scheduler expected error stop."""


class Scheduler:
    """Cylc scheduler server."""

    EVENT_STARTUP = WorkflowEventHandler.EVENT_STARTUP
    EVENT_SHUTDOWN = WorkflowEventHandler.EVENT_SHUTDOWN
    EVENT_ABORTED = WorkflowEventHandler.EVENT_ABORTED
    EVENT_WORKFLOW_TIMEOUT = WorkflowEventHandler.EVENT_WORKFLOW_TIMEOUT
    EVENT_STALL = WorkflowEventHandler.EVENT_STALL
    EVENT_STALL_TIMEOUT = WorkflowEventHandler.EVENT_STALL_TIMEOUT
    EVENT_RESTART_TIMEOUT = WorkflowEventHandler.EVENT_RESTART_TIMEOUT
    EVENT_INACTIVITY_TIMEOUT = WorkflowEventHandler.EVENT_INACTIVITY_TIMEOUT

    # Intervals in seconds
    INTERVAL_MAIN_LOOP = 1.0
    INTERVAL_MAIN_LOOP_QUICK = 0.5
    INTERVAL_STOP_KILL = 10.0
    INTERVAL_STOP_PROCESS_POOL_EMPTY = 0.5
    INTERVAL_AUTO_RESTART_ERROR = 5

    START_MESSAGE_PREFIX = 'Scheduler: '
    START_MESSAGE_TMPL = (
        START_MESSAGE_PREFIX +
        'url=%(comms_method)s://%(host)s:%(port)s pid=%(pid)s')
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
    is_restart: bool
    bad_hosts: Set[str]

    # directories
    workflow_log_dir: str
    workflow_run_dir: str
    workflow_share_dir: str
    workflow_work_dir: str

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
    command_queue: 'Queue[Tuple[str, str, AsyncGenerator]]'
    message_queue: 'Queue[TaskMsg]'
    ext_trigger_queue: Queue

    # configuration
    config: WorkflowConfig  # flow config
    options: 'Values'
    cylc_config: DictTree  # [scheduler] config
    template_vars: Dict[str, Any]

    # tcp / zmq
    server: WorkflowRuntimeServer

    # Note: attributes without a default must come before those with defaults

    # flow information
    contact_data: Optional[dict] = None

    # configuration
    flow_file: Optional[str] = None
    flow_file_update_time: Optional[float] = None

    # workflow params
    stop_mode: Optional[StopMode] = None
    stop_task: Optional[str] = None
    stop_clock_time: Optional[int] = None
    reload_pending: 'Union[Literal[False], str]' = False

    # task event loop
    is_paused = False
    is_updated = False
    is_stalled = False
    is_restart_timeout_wait = False
    is_reloaded = False

    # main loop
    main_loop_intervals: deque = deque(maxlen=10)
    main_loop_plugins: Optional[dict] = None
    auto_restart_mode: Optional[AutoRestartMode] = None
    auto_restart_time: Optional[float] = None

    # profiling
    _profile_amounts: Optional[dict] = None
    _profile_update_times: Optional[dict] = None
    previous_profile_point: float = 0
    count: int = 0

    time_next_kill: Optional[float] = None

    def __init__(self, id_: str, options: 'Values') -> None:
        # flow information
        self.workflow = id_
        self.workflow_name = get_workflow_name_from_id(self.workflow)
        self.owner = get_user()
        self.host = get_host()
        self.tokens = Tokens(
            user=self.owner,
            workflow=self.workflow,
        )
        self.id = self.tokens.id
        self.options = options
        self.template_vars = get_template_vars(self.options)

        # mutable defaults
        self._profile_amounts = {}
        self._profile_update_times = {}
        self.bad_hosts: Set[str] = set()

        self.restored_stop_task_id: Optional[str] = None

        self.timers: Dict[str, Timer] = {}

        self.workflow_run_dir = get_workflow_run_dir(self.workflow)
        self.workflow_work_dir = get_workflow_run_work_dir(self.workflow)
        self.workflow_share_dir = get_workflow_run_share_dir(self.workflow)
        self.workflow_log_dir = get_workflow_run_scheduler_log_dir(
            self.workflow
        )

        self.workflow_db_mgr = WorkflowDatabaseManager(
            pri_d=workflow_files.get_workflow_srv_dir(self.workflow),
            pub_d=os.path.join(self.workflow_run_dir, 'log')
        )
        self.is_restart = Path(self.workflow_db_mgr.pri_path).is_file()
        if (
            not self.is_restart
            and Path(self.workflow_db_mgr.pub_path).is_file()
        ):
            # Delete pub DB if pri DB doesn't exist, as we don't want to
            # load anything (e.g. template variables) from it
            os.unlink(self.workflow_db_mgr.pub_path)

        # Map used to track incomplete remote inits for restart
        # {install_target: platform}
        self.incomplete_ri_map: Dict[str, Dict] = {}

    async def install(self):
        """Get the filesystem in the right state to run the flow.
        * Validate flowfiles
        * Install authentication files.
        * Build the directory tree.
        * Copy Python files.

        """
        if self.is_restart:
            self.workflow_db_mgr.restart_check()

        # Install
        source, _ = workflow_files.get_workflow_source_dir(Path.cwd())
        if source is None:
            # register workflow
            rund = get_workflow_run_dir(self.workflow)
            workflow_files.register(self.workflow, source=rund)

        make_workflow_run_tree(self.workflow)

        # Get & check workflow file
        self.flow_file = workflow_files.get_flow_file(self.workflow)

        # Create ZMQ keys
        key_housekeeping(
            self.workflow, platform=self.options.host or 'localhost'
        )

        # Extract job.sh from library, for use in job scripts.
        get_resources(
            'job.sh',
            os.path.join(
                workflow_files.get_workflow_srv_dir(self.workflow), 'etc',
            ),
        )
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
        self.data_store_mgr = DataStoreMgr(self)
        self.broadcast_mgr = BroadcastMgr(self)

        self.server = WorkflowRuntimeServer(self)

        self.proc_pool = SubProcPool()
        self.command_queue = Queue()
        self.message_queue = Queue()
        self.ext_trigger_queue = Queue()
        self.workflow_event_handler = WorkflowEventHandler(self.proc_pool)

        self.xtrigger_mgr = XtriggerManager(
            self,
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

        self.task_job_mgr = TaskJobManager(
            self.workflow,
            self.proc_pool,
            self.workflow_db_mgr,
            self.task_events_mgr,
            self.data_store_mgr,
            self.bad_hosts,
            self.server,
        )

        self.profiler = Profiler(self, self.options.profile_mode)

    async def configure(self, params):
        """Configure the scheduler.

        * Load the flow configuration.
        * Load/write workflow parameters from the DB.
        * Get the data store rolling.

        """
        # Print workflow name to disambiguate in case of inferred run number
        # while in no-detach mode
        with patch_log_level(LOG):
            LOG.info(f"Workflow: {self.workflow}")

        self.profiler.log_memory("scheduler.py: start configure")

        self._check_startup_opts()

        if self.is_restart:
            run_mode = self.get_run_mode()
            self._set_workflow_params(params)
            # Prevent changing run mode on restart:
            og_run_mode = self.get_run_mode()
            if run_mode != og_run_mode:
                raise InputError(
                    "This workflow was originally run in "
                    f"{og_run_mode.value} mode:"
                    f" You can't restart it in {run_mode.value} mode."
                )

        if self.options.paused_start:
            self.pause_workflow('Paused on start up')

        self.profiler.log_memory("scheduler.py: before load_flow_file")
        try:
            cfg = self.load_flow_file()
            self.apply_new_config(cfg, is_reload=False)
        except ParsecError as exc:
            # Mark this exc as expected (see docstring for .schd_expected):
            exc.schd_expected = True
            raise exc
        self.profiler.log_memory("scheduler.py: after load_flow_file")

        self.workflow_db_mgr.on_workflow_start(self.is_restart)

        if not self.is_restart:
            # Set workflow params that would otherwise be loaded from database:
            self.options.utc_mode = get_utc_mode()
            self.options.cycle_point_tz = (
                self.config.cfg['scheduler']['cycle point time zone'])

        self.flow_mgr = FlowMgr(self.workflow_db_mgr, self.options.utc_mode)

        # Note that daemonization happens after this:
        self.log_start()

        self.broadcast_mgr.linearized_ancestors.update(
            self.config.get_linearized_ancestors())
        self.task_events_mgr.mail_interval = self.cylc_config['mail'][
            "task event batch interval"]
        self.task_events_mgr.mail_smtp = self._get_events_conf("smtp")
        self.task_events_mgr.mail_footer = self._get_events_conf("footer")
        self.task_events_mgr.workflow_cfg = self.config.cfg
        if self.options.genref:
            LOG.addHandler(ReferenceLogFileHandler(
                self.config.get_ref_log_name()))
        elif self.options.reftest:
            LOG.addHandler(ReferenceLogFileHandler(
                get_workflow_test_log_path(self.workflow)))

        self.pool = TaskPool(
            self.tokens,
            self.config,
            self.workflow_db_mgr,
            self.task_events_mgr,
            self.xtrigger_mgr,
            self.data_store_mgr,
            self.flow_mgr
        )

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
            (self.EVENT_STALL_TIMEOUT, False, None),
            (self.EVENT_RESTART_TIMEOUT, False, None)
        ]:
            interval = self._get_events_conf(event)
            if interval is not None:
                timer = Timer(event, interval, log_reset_func)
                if start_now:
                    timer.reset()
                self.timers[event] = timer

        if self.is_restart and (
            # workflow has completed
            not self.pool.get_tasks()
            # workflow has hit the "stop after cycle point"
            or (
                self.config.stop_point
                and all(
                    cycle > self.config.stop_point
                    for cycle in {
                        itask.point for itask in self.pool.get_tasks()
                    }
                )
            )
        ):
            # This workflow will shut down immediately once restarted
            # => Give the user a grace period to intervene first
            with suppress(KeyError):
                self.timers[self.EVENT_RESTART_TIMEOUT].reset()
                self.is_restart_timeout_wait = True
                LOG.warning(
                    "This workflow already ran to completion."
                    "\nTo make it continue, trigger new tasks"
                    " before the restart timeout."
                )

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
            await commands.run_cmd(commands.set_hold_point(self, holdcp))

        self.profiler.log_memory("scheduler.py: begin run while loop")
        self.is_updated = True
        if self.options.profile_mode:
            self.previous_profile_point = 0
            self.count = 0

        self.process_workflow_db_queue()

        self.profiler.log_memory("scheduler.py: end configure")

    def log_start(self) -> None:
        """Log headers, that also get logged on each rollover.

        Note: daemonize polls for 2 of these headers before detaching.
        """
        # Temporarily lower logging level if necessary to log important info
        with patch_log_level(LOG):
            # `daemonize` polls for these next 2 before detaching:
            LOG.info(
                self.START_MESSAGE_TMPL % {
                    'comms_method': 'tcp',
                    'host': self.host,
                    'port': self.server.port,
                    'pid': os.getpid()},
                extra=RotatingLogFileHandler.header_extra,
            )
            LOG.info(
                self.START_PUB_MESSAGE_TMPL % {
                    'comms_method': 'tcp',
                    'host': self.host,
                    'port': self.server.pub_port},
                extra=RotatingLogFileHandler.header_extra,
            )

            restart_num = self.get_restart_num() + 1
            LOG.info(
                f'Run: (re)start number={restart_num}, log rollover=%d',
                # Hard code 1 in args, gets updated on log rollover (NOTE: this
                # must be the only positional arg):
                1,
                extra={
                    **RotatingLogFileHandler.header_extra,
                    RotatingLogFileHandler.ROLLOVER_NUM: 1
                }
            )
            LOG.info(
                f'Cylc version: {CYLC_VERSION}',
                extra=RotatingLogFileHandler.header_extra
            )

            # Note that the following lines must be present at the top of
            # the workflow log file for use in reference test runs.
            LOG.info(
                f'Run mode: {self.get_run_mode().value}',
                extra=RotatingLogFileHandler.header_extra
            )
            LOG.info(
                f'Initial point: {self.config.initial_point}',
                extra=RotatingLogFileHandler.header_extra
            )
            if self.config.start_point != self.config.initial_point:
                LOG.info(
                    f'Start point: {self.config.start_point}',
                    extra=RotatingLogFileHandler.header_extra
                )
            LOG.info(
                f'Final point: {self.config.final_point}',
                extra=RotatingLogFileHandler.header_extra
            )
            if self.config.stop_point:
                LOG.info(
                    f'Stop point: {self.config.stop_point}',
                    extra=RotatingLogFileHandler.header_extra
                )

    async def run_scheduler(self) -> None:
        """Start the scheduler main loop."""
        try:
            if self.is_restart:
                self.task_job_mgr.task_remote_mgr.is_restart = True
                self.task_job_mgr.task_remote_mgr.rsync_includes = (
                    self.config.get_validated_rsync_includes())
                if self.pool.get_tasks():
                    # (If we're not restarting a finished workflow)
                    self.restart_remote_init()
                    await commands.run_cmd(commands.poll_tasks(self, ['*/*']))

                    # If we shut down with manually triggered waiting tasks,
                    # submit them to run now.
                    pre_prep_tasks = []
                    for itask in self.pool.get_tasks():
                        if (
                            itask.is_manual_submit
                            and itask.state(TASK_STATUS_WAITING)
                        ):
                            itask.waiting_on_job_prep = True
                            pre_prep_tasks.append(itask)

                    self.start_job_submission(pre_prep_tasks)

            self.run_event_handlers(self.EVENT_STARTUP, 'workflow starting')
            await asyncio.gather(
                *main_loop.get_runners(
                    self.main_loop_plugins,
                    main_loop.CoroTypes.StartUp,
                    self
                )
            )
            self.server.publish_queue.put(
                self.data_store_mgr.publish_deltas)
            # Non-async sleep - yield to other threads rather than event loop
            sleep(0)
            self.profiler.start()
            while True:  # MAIN LOOP
                await self._main_loop()

        except SchedulerStop as exc:
            # deliberate stop
            await self.shutdown(exc)
            try:
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
            except Exception as exc:
                # Need to log traceback manually because otherwise this
                # exception gets swallowed
                LOG.exception(exc)
                raise

        except asyncio.CancelledError as exc:
            await self.handle_exception(exc)

        except CylcError as exc:  # Includes SchedulerError
            # catch "expected" errors
            await self.handle_exception(exc)

        except Exception as exc:
            # catch "unexpected" errors
            with suppress(Exception):
                LOG.critical(
                    'An uncaught error caused Cylc to shut down.'
                    '\nIf you think this was an issue in Cylc,'
                    ' please report the following traceback to the developers.'
                    '\nhttps://github.com/cylc/cylc-flow/issues/new'
                    '?assignees=&labels=bug&template=bug.md&title=;'
                )
            await self.handle_exception(exc)

        else:
            # main loop ends (not used?)
            await self.shutdown(SchedulerStop(StopMode.AUTO.value))

        finally:
            self.profiler.stop()

    def load_workflow_params_and_tmpl_vars(self) -> List[Tuple[str, str]]:
        """Load workflow params and template variables"""
        with self.workflow_db_mgr.get_pri_dao() as pri_dao:
            # This logic handles lack of initial cycle point in flow.cylc and
            # things that can't change on workflow restart/reload.
            pri_dao.select_workflow_template_vars(self._load_template_vars)
            pri_dao.execute_queued_items()
            return list(pri_dao.select_workflow_params())

    async def start(self):
        """Run the startup sequence but don't set the main loop running.

        Lightweight wrapper for testing convenience.

        """
        if self.is_restart:
            params = self.load_workflow_params_and_tmpl_vars()
        else:
            params = []

        try:
            await self.initialise()

            # Start Server before logging ports/host(s).
            # create thread sync barrier for setup
            barrier = Barrier(2, timeout=10)
            self.server.thread = Thread(
                target=self.server.start,
                args=(barrier,),
                daemon=False
            )
            self.server.thread.start()
            barrier.wait()

            # Get UUID now:
            if self.is_restart:
                self.uuid_str = dict(params)['uuid_str']
            else:
                self.uuid_str = str(uuid4())
            self.task_events_mgr.uuid_str = self.uuid_str

            self._configure_contact()
            await self.configure(params)
        except (KeyboardInterrupt, asyncio.CancelledError, Exception) as exc:
            await self.handle_exception(exc)

    async def run(self):
        """Run the startup sequence and set the main loop running.

        Lightweight wrapper for testing convenience.
        """
        # register signal handlers
        for sig in (
            # ctrl+c
            signal.SIGINT,
            # the "stop please" signal
            signal.SIGTERM,
            # the controlling process bailed
            # (e.g. terminal quit in no detach mode)
            signal.SIGHUP,
        ):
            signal.signal(sig, self._handle_signal)

        await self.start()
        # note run_scheduler handles its own shutdown logic
        await self.run_scheduler()

    def _handle_signal(self, sig: int, frame) -> None:
        """Handle a signal."""
        LOG.critical(f'Signal {signal.Signals(sig).name} received')
        if sig in {signal.SIGINT, signal.SIGTERM, signal.SIGHUP}:
            if self.stop_mode == StopMode.REQUEST_NOW:
                # already shutting down NOW -> escalate to NOW_NOW
                # (i.e. don't run/wait for event handlers)
                stop_mode = StopMode.REQUEST_NOW_NOW
            else:
                # stop NOW (orphan running tasks)
                stop_mode = StopMode.REQUEST_NOW

            self._set_stop(stop_mode)

    def _load_pool_from_tasks(self):
        """Load task pool with specified tasks, for a new run."""
        LOG.info(f"Start task: {self.options.starttask}")
        start_tasks = command_validation.is_tasks(self.options.starttask)
        # flow number set in this call:
        self.pool.set_prereqs_and_outputs(
            start_tasks,
            outputs=[],
            prereqs=["all"],
            flow=[FLOW_NEW],
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
        start_type = (
            "Warm" if self.config.start_point > self.config.initial_point
            else "Cold"
        )
        LOG.info(f"{start_type} start from {self.config.start_point}")
        self.pool.load_from_point()

    def _load_pool_from_db(self):
        """Load task pool from DB, for a restart."""
        self.workflow_db_mgr.pri_dao.select_broadcast_states(
            self.broadcast_mgr.load_db_broadcast_states)
        self.broadcast_mgr.post_load_db_coerce()
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
        self.task_job_mgr.task_remote_mgr.is_restart = True
        distinct_install_target_platforms = []
        for itask in self.pool.get_tasks():
            itask.platform['install target'] = (
                get_install_target_from_platform(itask.platform))
            if (
                # we don't need to remote-init for preparing tasks because
                # they will be reset to waiting on restart
                itask.state(*TASK_STATUSES_ACTIVE)
                and not (
                    is_platform_with_target_in_list(
                        itask.platform['install target'],
                        distinct_install_target_platforms
                    )
                )
            ):
                distinct_install_target_platforms.append(itask.platform)

        for platform in distinct_install_target_platforms:
            # skip remote init for localhost
            install_target = platform['install target']
            if install_target == get_localhost_install_target():
                continue
            # set off remote init
            self.task_job_mgr.task_remote_mgr.remote_init(platform)
            # Remote init/file-install is done via process pool
            self.proc_pool.process()
            # add platform to map (to be picked up on main loop)
            self.incomplete_ri_map[install_target] = platform

    def manage_remote_init(self):
        """Manage the remote init/file install process for restarts.

        * Called within the main loop.
        * Starts file installation when Remote init is complete.
        * Removes complete installations or installations encountering SSH
          error (remote init will take place on next job submission).
        """
        for install_target, platform in list(self.incomplete_ri_map.items()):
            status = self.task_job_mgr.task_remote_mgr.remote_init_map[
                install_target]
            if status == REMOTE_INIT_DONE:
                self.task_job_mgr.task_remote_mgr.file_install(platform)
            if status in [REMOTE_FILE_INSTALL_DONE,
                          REMOTE_INIT_255,
                          REMOTE_FILE_INSTALL_255,
                          REMOTE_INIT_FAILED,
                          REMOTE_FILE_INSTALL_FAILED]:
                # Remove install target
                self.incomplete_ri_map.pop(install_target)

    def _load_task_run_times(self, row_idx, row):
        """Load run times of previously succeeded task jobs."""
        if row_idx == 0:
            LOG.debug("LOADING task run times")
        name, run_times_str = row
        try:
            taskdef = self.config.taskdefs[name]
            maxlen = TaskDef.MAX_LEN_ELAPSED_TIMES
            for run_time_str in run_times_str.rsplit(",", maxlen)[-maxlen:]:
                run_time = int(run_time_str)
                taskdef.elapsed_times.append(run_time)
            LOG.debug("+ %s: %s" % (
                name, ",".join(str(s) for s in taskdef.elapsed_times)))
        except (KeyError, ValueError, AttributeError):
            return

    def process_queued_task_messages(self) -> None:
        """Process incoming task messages for each task proxy.

        """
        messages: dict[str, list[TaskMsg]] = {}

        # Retrieve queued messages
        while self.message_queue.qsize():
            try:
                task_msg = self.message_queue.get(block=False)
            except Empty:
                break
            self.message_queue.task_done()
            # task ID (job stripped)
            task_id = task_msg.job_id.duplicate(job=None).relative_id
            messages.setdefault(task_id, []).append(task_msg)

        unprocessed_messages: List[TaskMsg] = []
        # Poll tasks for which messages caused a backward state change.
        to_poll_tasks: List[TaskProxy] = []
        for task_id, message_items in messages.items():
            itask = self.pool._get_task_by_id(task_id)
            if itask is None:
                unprocessed_messages.extend(message_items)
                continue
            should_poll = False
            for tm in message_items:
                if self.task_events_mgr.process_message(
                    itask, tm.severity, tm.message, tm.event_time,
                    self.task_events_mgr.FLAG_RECEIVED, tm.job_id.submit_num
                ):
                    should_poll = True
            if should_poll:
                to_poll_tasks.append(itask)
        if to_poll_tasks:
            self.task_job_mgr.poll_task_jobs(to_poll_tasks)

        # Remaining unprocessed messages have no corresponding task proxy.
        # For example, if I manually set a running task to succeeded, the
        # proxy can be removed, but the orphaned job still sends messages.
        warn = ""
        for tm in unprocessed_messages:
            job_tokens = self.tokens.duplicate(tm.job_id)
            tdef = self.config.get_taskdef(job_tokens['task'])
            if not self.task_events_mgr.process_job_message(
                job_tokens, tdef, tm.message, tm.event_time
            ):
                warn += f'\n  {tm.job_id}: {tm.severity} - "{tm.message}"'
        if warn:
            LOG.warning(
                f"Undeliverable task messages received and ignored:{warn}"
            )

    async def process_command_queue(self) -> None:
        """Process queued commands."""
        qsize = self.command_queue.qsize()
        if qsize <= 0:
            return
        LOG.debug(f"Processing {qsize} queued command(s)")
        while True:
            uuid: str
            name: str
            cmd: AsyncGenerator
            try:
                uuid, name, cmd = self.command_queue.get(False)
            except Empty:
                break
            msg = f'Command "{name}" ' + '{result}' + f'. ID={uuid}'
            try:
                n_warnings: Optional[int] = None
                with suppress(StopAsyncIteration):
                    n_warnings = await cmd.__anext__()
            except Exception as exc:
                # Don't let a bad command bring the workflow down.
                if (
                    cylc.flow.flags.verbosity > 1 or
                    not isinstance(exc, CommandFailedError)
                ):
                    LOG.error(traceback.format_exc())
                LOG.error(
                    msg.format(result="failed") + f"\n{exc}"
                )
            else:
                if n_warnings:
                    LOG.info(
                        msg.format(
                            result=f"actioned with {n_warnings} warnings"
                        )
                    )
                else:
                    LOG.info(msg.format(result="actioned"))
                self.is_updated = True

            self.command_queue.task_done()

    def _set_stop(self, stop_mode: Optional[StopMode] = None) -> None:
        """Set shutdown mode."""
        self.proc_pool.set_stopping()
        self.stop_mode = stop_mode
        self.update_data_store()

    def kill_tasks(
        self, itasks: 'Iterable[TaskProxy]', warn: bool = True
    ) -> int:
        """Kill tasks if they are in a killable state.

        Args:
            itasks: Tasks to kill.
            warn: Whether to warn about tasks that are not in a killable state.

        Returns number of tasks that could not be killed.
        """
        jobless = self.get_run_mode() == RunMode.SIMULATION
        to_kill: List[TaskProxy] = []
        unkillable: List[TaskProxy] = []
        for itask in itasks:
            if not itask.state(TASK_STATUS_PREPARING, *TASK_STATUSES_ACTIVE):
                unkillable.append(itask)
                continue
            self.pool.hold_active_task(itask)
            if itask.state(TASK_STATUS_PREPARING):
                self.task_job_mgr.kill_prep_task(itask)
            else:
                to_kill.append(itask)
                if jobless:
                    # Directly set failed in sim mode:
                    self.task_events_mgr.process_message(
                        itask, 'CRITICAL', TASK_STATUS_FAILED,
                        flag=self.task_events_mgr.FLAG_RECEIVED
                    )
        if warn and unkillable:
            LOG.warning(
                "Tasks not killable: "
                f"{', '.join(sorted(t.identity for t in unkillable))}"
            )
        if not jobless:
            self.task_job_mgr.kill_task_jobs(to_kill)

        return len(unkillable)

    def get_restart_num(self) -> int:
        """Return the number of the restart, else 0 if not a restart.

        Performs DB restart-check the first time this is called.
        """
        if not self.is_restart:
            return 0
        if self.workflow_db_mgr.n_restart == 0:
            self.workflow_db_mgr.restart_check()
        return self.workflow_db_mgr.n_restart

    def get_contact_data(self) -> Dict[str, str]:
        """Extract contact data from this Scheduler.

        This provides the information that is written to the contact file.
        """
        fields = workflow_files.ContactFileFields
        proc = psutil.Process()
        platform = get_platform()
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
                str(self.server.port),
            fields.PID:
                str(proc.pid),
            fields.COMMAND:
                cli_format(proc.cmdline()),
            fields.PUBLISH_PORT:
                str(self.server.pub_port),
            fields.WORKFLOW_RUN_DIR_ON_WORKFLOW_HOST:
                self.workflow_run_dir,
            fields.UUID:
                self.uuid_str,
            fields.VERSION:
                CYLC_VERSION,
            fields.SCHEDULER_SSH_COMMAND:
                str(platform['ssh command']),
            fields.SCHEDULER_CYLC_PATH:
                str(platform['cylc path']),
            fields.SCHEDULER_USE_LOGIN_SHELL:
                str(platform['use login shell'])
        }
        # fmt: on

    def _configure_contact(self) -> None:
        """Create contact file."""
        # Make sure another workflow of the same name hasn't started while this
        # one is starting
        # NOTE: raises SchedulerAlive if workflow is running
        workflow_files.detect_old_contact_file(self.workflow)

        # Extract contact data.
        contact_data = self.get_contact_data()

        # Write workflow contact file.
        # Preserve contact data in memory, for regular health check.
        workflow_files.dump_contact_file(self.workflow, contact_data)
        self.contact_data = contact_data

    def load_flow_file(self, is_reload=False):
        """Load, and log the workflow definition."""
        return WorkflowConfig(
            self.workflow,
            self.flow_file,
            self.options,
            self.template_vars,
            mem_log_func=self.profiler.log_memory,
            output_fname=os.path.join(
                self.workflow_run_dir, 'log', 'config',
                workflow_files.WorkflowFiles.FLOW_FILE_PROCESSED
            ),
            run_dir=self.workflow_run_dir,
            log_dir=self.workflow_log_dir,
            work_dir=self.workflow_work_dir,
            share_dir=self.workflow_share_dir,
        )

    def apply_new_config(self, config, is_reload=False):
        self.config = config
        self.cylc_config = DictTree(
            self.config.cfg['scheduler'],
            glbl_cfg().get(['scheduler'])
        )
        self.flow_file_update_time = time()
        # Dump the loaded flow.cylc file for future reference.
        config_dir = get_workflow_run_config_log_dir(
            self.workflow)
        config_logs = get_sorted_logs_by_time(config_dir, "*[0-9].cylc")
        log_num = get_next_log_number(config_logs[-1]) if config_logs else 1
        if is_reload:
            load_type = "reload"
            load_type_num = get_reload_start_number(config_logs)
        elif self.is_restart:
            load_type = "restart"
            restart_num = self.get_restart_num() + 1
            load_type_num = f'{restart_num:02d}'
        else:
            load_type = "start"
            load_type_num = '01'
        file_name = get_workflow_run_config_log_dir(
            self.workflow, f"{log_num:02d}-{load_type}-{load_type_num}.cylc")
        with open(file_name, "w") as handle:
            handle.write("# cylc-version: %s\n" % CYLC_VERSION)
            self.config.pcfg.idump(sparse=True, handle=handle)

        # Pass static cylc and workflow variables to job script generation code
        self.task_job_mgr.job_file_writer.set_workflow_env({
            **verbosity_to_env(cylc.flow.flags.verbosity),
            'CYLC_UTC': str(get_utc_mode()),
            'CYLC_WORKFLOW_ID': self.workflow,
            'CYLC_WORKFLOW_NAME': self.workflow_name,
            'CYLC_WORKFLOW_NAME_BASE': str(Path(self.workflow_name).name),
            'CYLC_CYCLING_MODE': str(
                self.config.cfg['scheduling']['cycling mode']
            ),
            'CYLC_WORKFLOW_INITIAL_CYCLE_POINT': str(
                self.config.initial_point
            ),
            'CYLC_WORKFLOW_FINAL_CYCLE_POINT': str(self.config.final_point),
        })

    def _set_workflow_params(
        self, params: Iterable[tuple[str, str | None]]
    ) -> None:
        """Set workflow params on restart/reload.

        This currently includes:
        * Initial/Final cycle points.
        * Start/Stop Cycle points.
        * Stop task.
        * Workflow UUID.
        * A flag to indicate if the workflow should be paused or not.
        * Original workflow run time zone.
        """
        LOG.info("LOADING saved workflow parameters")
        for key, value in params:
            if key == self.workflow_db_mgr.KEY_RUN_MODE:
                self.options.run_mode = value or RunMode.LIVE.value
                LOG.info(f"+ run mode = {value}")
            if value is None:
                continue
            if key == self.workflow_db_mgr.KEY_INITIAL_CYCLE_POINT:
                self.options.icp = value
                LOG.info(f"+ initial point = {value}")
            elif key == self.workflow_db_mgr.KEY_START_CYCLE_POINT:
                self.options.startcp = value
                LOG.info(f"+ start point = {value}")
            elif key == self.workflow_db_mgr.KEY_FINAL_CYCLE_POINT:
                if self.is_restart and self.options.fcp == 'reload':
                    LOG.debug(f"- final point = {value} (ignored)")
                elif self.options.fcp is None:
                    self.options.fcp = value
                    LOG.info(f"+ final point = {value}")
            elif key == self.workflow_db_mgr.KEY_STOP_CYCLE_POINT:
                if self.is_restart and self.options.stopcp == 'reload':
                    LOG.debug(f"- stop point = {value} (ignored)")
                elif self.options.stopcp is None:
                    self.options.stopcp = value
                    LOG.info(f"+ stop point = {value}")
            elif key == self.workflow_db_mgr.KEY_UUID_STR:
                self.uuid_str = value
                LOG.info(f"+ workflow UUID = {value}")
            elif key == self.workflow_db_mgr.KEY_PAUSED:
                bool_val = bool(int(value))
                if bool_val and not self.options.paused_start:
                    self.options.paused_start = bool_val
                    LOG.info(f"+ paused = {bool_val}")
            elif (
                key == self.workflow_db_mgr.KEY_HOLD_CYCLE_POINT
                and self.options.holdcp is None
            ):
                self.options.holdcp = value
                LOG.info(f"+ hold point = {value}")
            elif key == self.workflow_db_mgr.KEY_STOP_CLOCK_TIME:
                int_val = int(value)
                msg = f"stop clock time = {int_val} ({time2str(int_val)})"
                if time() <= int_val:
                    self.stop_clock_time = int_val
                    LOG.info(f"+ {msg}")
                else:
                    LOG.debug(f"- {msg} (ignored)")
            elif key == self.workflow_db_mgr.KEY_STOP_TASK:
                self.restored_stop_task_id = value
                LOG.info(f"+ stop task = {value}")
            elif key == self.workflow_db_mgr.KEY_UTC_MODE:
                bool_val = bool(int(value))
                self.options.utc_mode = bool_val
                LOG.info(f"+ UTC mode = {bool_val}")
            elif key == self.workflow_db_mgr.KEY_CYCLE_POINT_TIME_ZONE:
                self.options.cycle_point_tz = value
                LOG.info(f"+ cycle point time zone = {value}")

    def _load_template_vars(self, _, row):
        """Load workflow start up template variables."""
        key, value = row
        # Command line argument takes precedence
        if key not in self.template_vars:
            self.template_vars[key] = eval_var(value)

    def run_event_handlers(self, event, reason=""):
        """Run a workflow event handler.

        Run workflow events only in live mode or skip mode.
        """
        if self.get_run_mode() in {RunMode.SIMULATION, RunMode.DUMMY}:
            return
        self.workflow_event_handler.handle(self, event, str(reason))

    def release_tasks_to_run(self) -> bool:
        """Release queued or manually submitted tasks, and submit jobs.

        The task queue manages references to task proxies in the task pool.

        Tasks which have entered the submission pipeline but not yet finished
        (pre_prep_tasks) are passed to job submission multiple times until they
        have passed through a series of asynchronous operations (host select,
        remote init, remote file install, etc).

        Note:
            We do not maintain a list of "pre_prep_tasks" between iterations
            of this method as this creates an intermediate task staging pool
            which has nasty consequences:

            * https://github.com/cylc/cylc-flow/pull/4620
            * https://github.com/cylc/cylc-flow/issues/4974

        Returns:
            True if tasks were passed through the submit-pipeline
            (i.e. new waiting tasks have entered the preparing state OR
            preparing tasks have been passed back through for
            submission).

        """
        pre_prep_tasks: Set['TaskProxy'] = set()
        if (
            not self.stop_mode
            and self.auto_restart_time is None
            and self.reload_pending is False
        ):
            if self.pool.tasks_to_trigger_now:
                # manually triggered tasks to run now.
                pre_prep_tasks.update(self.pool.tasks_to_trigger_now)
                self.pool.tasks_to_trigger_now = set()

            if not self.is_paused:
                # release queued tasks
                pre_prep_tasks.update(self.pool.release_queued_tasks())

        if (
            # Manually triggered tasks will be preparing and should
            # be submitted even if paused (unless workflow is stopping).
            self.is_paused and not self.stop_mode
        ) or (
            # Need to get preparing tasks to submit before auto restart
            self.should_auto_restart_now()
            and self.auto_restart_mode == AutoRestartMode.RESTART_NORMAL
        ) or (
            # Need to get preparing tasks to submit before reload
            self.reload_pending
        ):
            pre_prep_tasks.update({
                itask
                for itask in self.pool.get_tasks()
                if itask.waiting_on_job_prep
            })

        # Return, if no tasks to submit.
        if not pre_prep_tasks:
            return False

        return self.start_job_submission(pre_prep_tasks)

    def start_job_submission(self, itasks: 'Iterable[TaskProxy]') -> bool:
        """Start the job submission process for some tasks.

        Return True if any were started, else False.

        """
        if self.stop_mode is not None:
            return False

        self.is_updated = True
        self.reset_inactivity_timer()

        self.task_job_mgr.task_remote_mgr.rsync_includes = (
            self.config.get_validated_rsync_includes())

        submitted = self.submit_task_jobs(itasks)
        if not submitted:
            return False

        log_lvl = logging.DEBUG
        if self.options.reftest or self.options.genref:
            log_lvl = logging.INFO

        for itask in submitted:
            flow = stringify_flow_nums(itask.flow_nums) or FLOW_NONE
            if itask.is_manual_submit:
                off = f"[] in flow {flow}"
            else:
                off = (
                    f"{itask.state.get_resolved_dependencies()}"
                    f" in flow {flow}"
                )
            LOG.log(log_lvl, f"{itask.identity} -triggered off {off}")

        # one or more tasks were passed through the submission pipeline
        return True

    def submit_task_jobs(
        self, itasks: 'Iterable[TaskProxy]'
    ) -> 'List[TaskProxy]':
        """Submit task jobs, return tasks that attempted submission."""
        # Note: keep this as simple wrapper for task job mgr's method
        return self.task_job_mgr.submit_task_jobs(itasks, self.get_run_mode())

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
        if self.get_run_mode() != RunMode.SIMULATION:
            self.task_job_mgr.check_task_jobs(self.pool)

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
                    await self.process_command_queue()
            if self.options.profile_mode:
                self.profiler.log_memory(
                    "scheduler.py: end main loop (total loops %d): %s" %
                    (self.count, get_current_time_string()))
            if self.stop_mode == StopMode.AUTO_ON_TASK_FAILURE:
                raise SchedulerError(self.stop_mode.value)
            else:
                raise SchedulerStop(self.stop_mode.value)
        elif (
            self.time_next_kill is not None
            and time() > self.time_next_kill
        ):
            self.task_job_mgr.poll_task_jobs(self.pool.get_tasks())
            self.kill_tasks(self.pool.get_tasks(), warn=False)
            self.time_next_kill = time() + self.INTERVAL_STOP_KILL

        # Is the workflow set to auto stop [+restart] now ...
        if not self.should_auto_restart_now():
            # ... no
            pass
        elif self.auto_restart_mode == AutoRestartMode.RESTART_NORMAL:
            # ... yes - wait for preparing jobs to see if they're local and
            # wait for local jobs to complete before restarting
            #    * Avoid polling issues - see #2843
            #    * Ensure the host can be safely taken down once the
            #      workflow has stopped running.
            for itask in self.pool.get_tasks():
                if itask.state(TASK_STATUS_PREPARING):
                    LOG.info(
                        "Waiting for preparing jobs to submit before "
                        "attempting restart"
                    )
                    break
                if (
                    itask.state(*TASK_STATUSES_ACTIVE)
                    and itask.summary['job_runner_name']
                    and not is_remote_platform(itask.platform)
                    and self.task_job_mgr.job_runner_mgr.is_job_local_to_host(
                        itask.summary['job_runner_name'])
                ):
                    LOG.info('Waiting for jobs running on localhost to '
                             'complete before attempting restart')
                    break
            else:  # no break
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

    def should_auto_restart_now(self) -> bool:
        """Is it time for the scheduler to auto stop + restart?"""
        return (
            self.auto_restart_time is not None and
            time() >= self.auto_restart_time
        )

    def workflow_auto_restart(self, max_retries: int = 3) -> bool:
        """Attempt to restart the workflow assuming it has already stopped."""
        cmd = [
            'cylc', 'play', quote(self.workflow),
            *verbosity_to_opts(cylc.flow.flags.verbosity)
        ]
        if self.options.abort_if_any_task_fails:
            cmd.append('--abort-if-any-task-fails')
        for attempt_no in range(max_retries):
            error: Optional[str] = None
            proc = None
            try:
                new_host = select_workflow_host(cached=False)[0]
            except HostSelectException as exc:
                error = str(exc)
            else:
                LOG.info(f'Attempting to restart on "{new_host}"')
                # proc will start with current env (incl CYLC_HOME etc)
                proc = Popen(  # nosec
                    [*cmd, f'--host={new_host}'],
                    stdin=DEVNULL,
                    stdout=PIPE,
                    stderr=PIPE,
                    text=True
                )
                if proc.wait():
                    error = proc.communicate()[1]
            # * new_host comes from internal interface which can only return
            #   host names
            if error is not None:
                msg = 'Could not restart workflow'
                if attempt_no < max_retries:
                    msg += (
                        f' will retry in {self.INTERVAL_AUTO_RESTART_ERROR}s')
                LOG.critical(f"{msg}. Restart error:\n{error}")
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

    async def _main_loop(self) -> None:
        """A single iteration of the main loop."""
        tinit = time()

        # Useful for debugging core scheduler issues:
        # import logging
        # self.pool.log_task_pool(logging.CRITICAL)
        if self.incomplete_ri_map:
            self.manage_remote_init()

        await self.process_command_queue()
        self.proc_pool.process()

        # Unqueued tasks with satisfied prerequisites must be waiting on
        # xtriggers or ext_triggers. Check these and queue tasks if ready.
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
                self.xtrigger_mgr.call_xtriggers_async(itask)

            if (
                itask.state.external_triggers
                and not itask.state.external_triggers_all_satisfied()
            ):
                self.broadcast_mgr.check_ext_triggers(
                    itask, self.ext_trigger_queue)

            if itask.is_ready_to_run() and not itask.is_manual_submit:
                self.pool.queue_task(itask)

        if self.xtrigger_mgr.do_housekeeping:
            self.xtrigger_mgr.housekeep(self.pool.get_tasks())
        self.pool.clock_expire_tasks()
        self.release_tasks_to_run()

        if (
            self.get_run_mode() == RunMode.SIMULATION
            and sim_time_check(
                self.task_events_mgr,
                self.pool.get_tasks(),
                self.workflow_db_mgr,
            )
        ):
            # A simulated task state change occurred.
            self.reset_inactivity_timer()

        # auto expire broadcasts
        if not self.is_paused:
            # NOTE: Don't auto-expire broadcasts whilst the scheduler is
            # paused. This allows broadcast-and-trigger beyond the expiry
            # limit, by pausing before doing it (after which the expiry
            # limit moves back).
            with suppress(TimePointDumperBoundsError):
                # NOTE: TimePointDumperBoundsError will be raised for negative
                # cycle points, we skip broadcast expiry in this circumstance
                # (pre-initial condition)
                if min_point := self.pool.get_min_point():
                    # NOTE: the broadcast expire limit is the oldest active
                    # cycle MINUS the longest cycling interval
                    self.broadcast_mgr.expire_broadcast(
                        min_point - self.config.interval_of_longest_sequence
                    )

        self.late_tasks_check()

        self.process_queued_task_messages()
        await self.process_command_queue()
        self.task_events_mgr.process_events(self)

        # Update state summary, database, and uifeed
        self.workflow_db_mgr.put_task_event_timers(self.task_events_mgr)

        # List of task whose states have changed.
        updated_task_list = [
            t for t in self.pool.get_tasks() if t.state.is_updated]
        has_updated = updated_task_list or self.is_updated

        if updated_task_list and self.is_restart_timeout_wait:
            # Stop restart timeout if action has been triggered.
            with suppress(KeyError):
                self.timers[self.EVENT_RESTART_TIMEOUT].stop()
                self.is_restart_timeout_wait = False

        if has_updated or self.data_store_mgr.updates_pending:
            # Update the datastore.
            await self.update_data_structure()

        if has_updated:
            if not self.is_reloaded:
                # (A reload cannot un-stall workflow by itself)
                self.is_stalled = False
            self.is_reloaded = False

            # Reset workflow and task updated flags.
            self.is_updated = False
            for itask in updated_task_list:
                itask.state.is_updated = False

            if not self.is_stalled:
                # Stop the stalled timer.
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
            duration: float = 0
        elif quick_mode:
            duration = self.INTERVAL_MAIN_LOOP_QUICK - elapsed
        else:
            duration = self.INTERVAL_MAIN_LOOP - elapsed
        await asyncio.sleep(duration)
        # Record latest main loop interval
        self.main_loop_intervals.append(time() - tinit)
        # END MAIN LOOP

    def _update_workflow_state(self):
        """Update workflow state in the data store and push out any deltas.

        A cut-down version of update_data_structure which only considers
        workflow state changes e.g. status, status message, state totals, etc.
        """
        # Publish any existing before potentially creating more
        self._publish_deltas()
        # update the workflow state in the data store
        self.data_store_mgr.update_workflow_states()
        self._publish_deltas()

    async def update_data_structure(self, reloaded: bool = False):
        """Update DB, UIS, Summary data elements"""
        # Publish any existing before potentially creating more
        self._publish_deltas()
        # Collect/apply data store updates/deltas
        self.data_store_mgr.update_data_structure()
        self._publish_deltas()
        # Database update
        self.workflow_db_mgr.put_task_pool(self.pool)

    def _publish_deltas(self):
        """Publish pending deltas."""
        if self.data_store_mgr.publish_pending:
            self.data_store_mgr.publish_pending = False
            self.server.publish_queue.put(
                self.data_store_mgr.publish_deltas)
            # Non-async sleep - yield to other threads rather
            # than event loop
            sleep(0)

    def check_workflow_timers(self):
        """Check timers, and abort or run event handlers as configured."""
        for event, timer in self.timers.items():
            if not timer.timed_out():
                continue
            self.run_event_handlers(event)
            abort_conf = f"abort on {event}"
            if self._get_events_conf(abort_conf):
                # "cylc play" needs to exit with error status here.
                raise SchedulerError(f'"{abort_conf}" is set')
            if event == self.EVENT_RESTART_TIMEOUT:
                # Unset wait flag to allow normal shutdown.
                self.is_restart_timeout_wait = False

    def check_workflow_stalled(self) -> bool:
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
            LOG.critical("Workflow stalled")
            self.run_event_handlers(self.EVENT_STALL, 'workflow stalled')
            with suppress(KeyError):
                # Start stall timeout timer
                self.timers[self.EVENT_STALL_TIMEOUT].reset()
        return self.is_stalled

    async def shutdown(self, reason: BaseException) -> None:
        """Gracefully shut down the scheduler."""
        # At the moment this method must be called from the main_loop.
        # In the future it should shutdown the main_loop itself but
        # we're not quite there yet.

        # cancel signal handlers
        def _handle_signal(sig, frame):
            LOG.warning(
                f'Signal {signal.Signals(sig).name} received,'
                ' already shutting down'
            )

        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(sig, _handle_signal)

        try:
            # action shutdown
            await self._shutdown(reason)
        except (asyncio.CancelledError, Exception) as exc:
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

    async def _shutdown(self, reason: BaseException) -> None:
        """Shutdown the workflow."""
        self._log_shutdown_reason(reason)

        if hasattr(self, 'proc_pool'):
            try:
                self.proc_pool.close()
                if self.proc_pool.is_not_done():
                    self.proc_pool.terminate()
                self.proc_pool.process()
            except Exception as exc:
                LOG.exception(exc)

        if hasattr(self, 'pool'):
            try:
                if not self.is_stalled:
                    # (else already logged)
                    # Log partially satisfied dependencies and incomplete tasks
                    self.pool.is_stalled()
                self.pool.warn_stop_orphans()
                self.workflow_db_mgr.put_task_event_timers(
                    self.task_events_mgr
                )
                self.workflow_db_mgr.put_task_pool(self.pool)
            except Exception as exc:
                LOG.exception(exc)

        if self.server:
            await self.server.stop(reason)

        # Flush errors and info before removing workflow contact file
        sys.stdout.flush()
        sys.stderr.flush()

        if (
            self.workflow_db_mgr.pri_path
            and Path(self.workflow_db_mgr.pri_path).exists()
        ):
            # only attempt remote tidy if the workflow has been started
            self.task_job_mgr.task_remote_mgr.remote_tidy()

        try:
            # Remove ZMQ keys from scheduler
            LOG.debug("Removing authentication keys from scheduler")
            key_housekeeping(self.workflow, create=False)
        except Exception as ex:
            LOG.exception(ex)
        # disconnect from workflow-db, stop db queue
        try:
            self.process_workflow_db_queue()
            self.workflow_db_mgr.on_workflow_shutdown()
        except Exception as exc:
            LOG.exception(exc)

        # NOTE: Removing the contact file should happen last of all (apart
        # from running event handlers), because the existence of the file is
        # used to determine if the workflow is running
        if self.contact_data:
            fname = workflow_files.get_contact_file_path(self.workflow)
            try:
                os.unlink(fname)
            except OSError as exc:
                LOG.warning(f"failed to remove workflow contact file: {fname}")
                LOG.exception(exc)
            else:
                # Useful to identify that this Scheduler has shut down
                # properly (e.g. in tests):
                self.contact_data = None

        # The getattr() calls and if tests below are used in case the
        # workflow is not fully configured before the shutdown is called.
        if getattr(self, "config", None) is not None:
            # run shutdown handlers
            if isinstance(reason, CylcError):
                self.run_event_handlers(self.EVENT_SHUTDOWN, reason.args[0])
            else:
                self.run_event_handlers(self.EVENT_ABORTED, str(reason))

    def _log_shutdown_reason(self, reason: BaseException) -> None:
        """Appropriately log the reason for scheduler shutdown."""
        shutdown_msg = "Workflow shutting down"
        with patch_log_level(LOG):
            if isinstance(reason, SchedulerStop):
                LOG.info(f'{shutdown_msg} - {reason.args[0]}')
                # Unset the "paused" status of the workflow if not
                # auto-restarting
                if self.auto_restart_mode != AutoRestartMode.RESTART_NORMAL:
                    self.resume_workflow(quiet=True)
            elif isinstance(reason, SchedulerError):
                LOG.error(f"{shutdown_msg} - {reason}")
            elif isinstance(reason, CylcError) or (
                isinstance(reason, ParsecError) and reason.schd_expected
            ):
                LOG.error(
                    f"{shutdown_msg} - {type(reason).__name__}: {reason}"
                )
                if cylc.flow.flags.verbosity > 1:
                    # Print traceback
                    LOG.exception(reason)
            else:
                LOG.exception(reason)
                if str(reason):
                    shutdown_msg += f" - {reason}"
                LOG.critical(shutdown_msg)

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
            self.workflow_db_mgr.put_workflow_stop_clock_time(None)
            self.update_data_store()
            return True
        LOG.debug("stop time=%d; current time=%d", self.stop_clock_time, now)
        return False

    def check_auto_shutdown(self):
        """Check if we should shut down now."""
        if (
            self.is_paused or
            self.is_restart_timeout_wait or
            self.check_workflow_stalled() or
            # if more tasks to run (if waiting and not
            # runahead, then held, queued, or xtriggered).
            any(
                itask for itask in self.pool.get_tasks()
                if itask.state(
                    TASK_STATUS_PREPARING,
                    TASK_STATUS_SUBMITTED,
                    TASK_STATUS_RUNNING,
                ) or (
                    # This is because runahead limit gets truncated
                    # to stop_point if there is one, so tasks spawned
                    # beyond the stop_point must be runahead limited.
                    itask.state(TASK_STATUS_WAITING)
                    and not itask.state.is_runahead
                )
            )
        ):
            return False

        # Can shut down.
        if self.pool.stop_point:
            # Forget early stop point in case of a restart.
            self.workflow_db_mgr.put_workflow_stop_cycle_point(None)

        return True

    def pause_workflow(self, msg: Optional[str] = None) -> None:
        """Pause the workflow.

        Args:
            msg:
                A user-facing string explaining why the workflow was paused if
                helpful.

        """
        if self.is_paused:
            LOG.info("Workflow is already paused")
            return
        _msg = "Pausing the workflow"
        if msg:
            _msg += f': {msg}'
        LOG.info(_msg)
        self.is_paused = True
        self.workflow_db_mgr.put_workflow_paused(True)
        self.update_data_store()

    def resume_workflow(self, quiet: bool = False) -> None:
        """Resume the workflow.

        Args:
            quiet:
                Whether to log anything in the event the workflow is not
                paused.

        """
        if self.reload_pending:
            LOG.warning('Cannot resume - workflow is reloading')
            return
        if not self.is_paused:
            if not quiet:
                LOG.info("No need to resume - workflow is not paused")
            return
        if not quiet:
            LOG.info("RESUMING the workflow now")
        self.is_paused = False
        self.workflow_db_mgr.put_workflow_paused(False)
        self.update_data_store()

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
                    raise InputError(
                        f"option --{opt} is not valid for restart"
                    )
            elif value == 'reload':
                raise InputError(
                    f"option --{opt}=reload is not valid "
                    "(only --fcp and --stopcp can be 'reload')"
                )
        if not self.is_restart:
            for opt in ('fcp', 'stopcp'):
                if getattr(self.options, opt, None) == 'reload':
                    raise InputError(
                        f"option --{opt}=reload is only valid for restart"
                    )

    def get_run_mode(self) -> RunMode:
        return RunMode.get(self.options)

    async def handle_exception(self, exc: BaseException) -> NoReturn:
        """Gracefully shut down the scheduler given a caught exception.

        Re-raises the exception to be caught higher up (sets the exit code).

        Args:
            exc: The caught exception to be logged during the shutdown.
        """
        await self.shutdown(exc)
        raise exc from None

    def update_data_store(self):
        """Sets the update flag on the data store.

        Call this method whenever the Scheduler's state has changed in a way
        that requires a data store update.
        See cylc.flow.workflow_status.get_workflow_status_msg() for a
        (non-exhaustive?) list of properties that if changed will require
        this update.

        This call should often be associated with a database update.

        Note that must updates e.g. task / job states are handled elsewhere,
        this applies to changes made directly to scheduler attributes etc.
        """
        self.data_store_mgr.updates_pending = True
