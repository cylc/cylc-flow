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
"""Cylc scheduler server."""

from copy import deepcopy
import logging
import os
import pickle
from pipes import quote
from Queue import Empty
import shlex
from shutil import copy, copytree, rmtree
from subprocess import call, Popen, PIPE
import sys
from tempfile import mkstemp
from time import sleep, time
import traceback

import isodatetime.data
import isodatetime.parsers
from parsec.util import printcfg

from cylc.broadcast_report import (
    CHANGE_FMT as BROADCAST_LOAD_FMT,
    CHANGE_PREFIX_SET as BROADCAST_LOAD_PREFIX)
from cylc.cfgspec.globalcfg import GLOBAL_CFG
from cylc.config import SuiteConfig, SuiteConfigError
from cylc.cycling import PointParsingError
from cylc.cycling.loader import get_point, standardise_point_string
from cylc.daemonize import daemonize
from cylc.exceptions import CylcError
import cylc.flags
from cylc.job_file import JobFile
from cylc.job_host import RemoteJobHostManager, RemoteJobHostInitError
from cylc.log_diagnosis import LogSpec
from cylc.mp_pool import SuiteProcContext, SuiteProcPool
from cylc.network import (
    COMMS_SUITEID_OBJ_NAME, COMMS_STATE_OBJ_NAME,
    COMMS_CMD_OBJ_NAME, COMMS_BCAST_OBJ_NAME, COMMS_EXT_TRIG_OBJ_NAME,
    COMMS_INFO_OBJ_NAME, COMMS_LOG_OBJ_NAME)
from cylc.network.ext_trigger_server import ExtTriggerServer
from cylc.network.daemon import CommsDaemon
from cylc.network.suite_broadcast_server import BroadcastServer
from cylc.network.suite_command_server import SuiteCommandServer
from cylc.network.suite_identifier_server import SuiteIdServer
from cylc.network.suite_info_server import SuiteInfoServer
from cylc.network.suite_log_server import SuiteLogServer
from cylc.network.suite_state_server import StateSummaryServer
from cylc.owner import USER
from cylc.suite_host import is_remote_host
from cylc.suite_srv_files_mgr import (
    SuiteSrvFilesManager, SuiteServiceFileError)
from cylc.rundb import CylcSuiteDAO
from cylc.suite_host import get_suite_host
from cylc.suite_logging import SuiteLog, OUT, ERR, LOG
from cylc.taskdef import TaskDef
from cylc.task_id import TaskID
from cylc.task_pool import TaskPool
from cylc.task_proxy import (
    TaskProxy, TaskProxySequenceBoundsError, TaskActionTimer)
from cylc.task_state import (
    TASK_STATUS_HELD, TASK_STATUS_WAITING,
    TASK_STATUS_QUEUED, TASK_STATUS_READY, TASK_STATUS_SUBMITTED,
    TASK_STATUS_SUBMIT_FAILED, TASK_STATUS_SUBMIT_RETRYING,
    TASK_STATUS_RUNNING, TASK_STATUS_SUCCEEDED, TASK_STATUS_FAILED,
    TASK_STATUS_RETRYING)
from cylc.templatevars import load_template_vars
from cylc.version import CYLC_VERSION
from cylc.wallclock import (
    get_current_time_string, get_seconds_as_interval_string)
from cylc.profiler import Profiler


class SchedulerError(CylcError):
    """Scheduler error."""
    pass


class SchedulerStop(CylcError):
    """Scheduler has stopped."""
    pass


class Scheduler(object):
    """Cylc scheduler server."""

    EVENT_STARTUP = 'startup'
    EVENT_SHUTDOWN = 'shutdown'
    EVENT_TIMEOUT = 'timeout'
    EVENT_INACTIVITY_TIMEOUT = 'inactivity'
    EVENT_STALLED = 'stalled'

    # Intervals in seconds
    INTERVAL_MAIN_LOOP = 1.0
    INTERVAL_STOP_KILL = 10.0
    INTERVAL_STOP_PROCESS_POOL_EMPTY = 0.5

    SUITE_EVENT_HANDLER = 'suite-event-handler'
    SUITE_EVENT_MAIL = 'suite-event-mail'

    START_MESSAGE_PREFIX = 'Suite starting: '
    START_MESSAGE_TMPL = (
        START_MESSAGE_PREFIX + 'server=%(host)s:%(port)s pid=%(pid)s')

    # Dependency negotation etc. will run after these commands
    PROC_CMDS = (
        'release_suite',
        'release_tasks',
        'kill_tasks',
        'set_runahead',
        'reset_task_states',
        'spawn_tasks',
        'trigger_tasks',
        'nudge',
        'insert_tasks',
        'reload_suite'
    )

    REF_LOG_TEXTS = (
        'triggered off', 'Initial point', 'Start point', 'Final point')

    def __init__(self, is_restart, options, args):
        self.options = options
        self.suite = args[0]
        self.profiler = Profiler(self.options.profile_mode)
        self.suite_srv_files_mgr = SuiteSrvFilesManager()
        try:
            self.suite_srv_files_mgr.register(self.suite, options.source)
        except SuiteServiceFileError:
            sys.exit(1)
        # Register suite if not already done
        self.suite_dir = self.suite_srv_files_mgr.get_suite_source_dir(
            self.suite)
        self.suiterc = self.suite_srv_files_mgr.get_suite_rc(self.suite)
        # For user-defined batch system handlers
        sys.path.append(os.path.join(self.suite_dir, 'python'))
        self.suite_run_dir = GLOBAL_CFG.get_derived_host_item(
            self.suite, 'suite run directory')
        self.config = None

        self.is_restart = is_restart
        self._cli_initial_point_string = None
        self._cli_start_point_string = None
        start_point_str = None
        if len(args) > 1:
            start_point_str = args[1]
        if getattr(self.options, 'warm', None):
            self._cli_start_point_string = start_point_str
        else:
            self._cli_initial_point_string = start_point_str
        self.template_vars = load_template_vars(
            self.options.templatevars, self.options.templatevars_file)

        self.run_mode = self.options.run_mode

        # For persistence of reference test settings across reloads:
        self.reference_test_mode = self.options.reftest
        self.gen_reference_log = self.options.genref

        self.owner = USER
        self.host = get_suite_host()
        self.port = None

        self.is_stalled = False

        self.graph_warned = {}

        self.task_event_handler_env = {}
        self.contact_data = None

        self.do_process_tasks = False
        self.do_update_state_summary = True

        # initialize some items in case of early shutdown
        # (required in the shutdown() method)
        self.suite_state = None
        self.command_queue = None
        self.pool = None
        self.request_handler = None
        self.comms_daemon = None
        self.info_interface = None

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

        self.pri_dao = None
        self.pub_dao = None

        self.suite_log = None
        self.log = LOG

        self.ref_test_allowed_failures = []
        self.next_task_event_mail_time = None

    def start(self):
        """Start the server."""
        self._start_print_blurb()

        GLOBAL_CFG.create_cylc_run_tree(self.suite)

        if self.is_restart:
            self._start_db_upgrade()

        try:
            if not self.options.no_detach and not cylc.flags.debug:
                daemonize(self)

            slog = SuiteLog.get_inst(self.suite)
            if cylc.flags.debug:
                slog.pimp(logging.DEBUG)
            else:
                slog.pimp()

            SuiteProcPool.get_inst()
            self.configure_comms_daemon()
            self.configure()
            self.profiler.start()
            self.run()
        except SchedulerStop as exc:
            # deliberate stop
            self.shutdown(exc)

        except SchedulerError as exc:
            self.shutdown(exc)
            sys.exit(1)

        except KeyboardInterrupt as exc:
            try:
                self.shutdown(str(exc))
            except Exception:
                # In case of exceptions in the shutdown method itself.
                ERR.warning(traceback.format_exc())
                sys.exit(1)

        except Exception as exc:
            ERR.critical(traceback.format_exc())
            ERR.error("error caught: cleaning up before exit")
            try:
                self.shutdown('ERROR: ' + str(exc))
            except Exception:
                # In case of exceptions in the shutdown method itself
                ERR.warning(traceback.format_exc())
            if cylc.flags.debug:
                raise
            else:
                sys.exit(1)

        else:
            # main loop ends (not used?)
            self.shutdown()

        self.profiler.stop()

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
Copyright (C) 2008-2017 NIWA
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
This program comes with ABSOLUTELY NO WARRANTY;
see `cylc warranty`.  It is free software, you
are welcome to redistribute it under certain
conditions; see `cylc conditions`.

  """ % CYLC_VERSION

        logo_lines = logo.splitlines()
        license_lines = cylc_license.splitlines()
        lmax = max(len(line) for line in license_lines)
        for i in range(len(logo_lines)):
            print logo_lines[i], ('{0: ^%s}' % lmax).format(license_lines[i])

    def _start_db_upgrade(self):
        """Vacuum/upgrade runtime DB on restart."""
        pri_db_path = os.path.join(
            self.suite_srv_files_mgr.get_suite_srv_dir(self.suite),
            CylcSuiteDAO.DB_FILE_BASE_NAME)

        # Backward compat, upgrade database with state file if necessary
        old_pri_db_path = os.path.join(
            self.suite_run_dir, 'state', CylcSuiteDAO.OLD_DB_FILE_BASE_NAME)
        old_pri_db_path_611 = os.path.join(
            self.suite_run_dir, CylcSuiteDAO.OLD_DB_FILE_BASE_NAME_611[0])
        old_state_file_path = os.path.join(
            self.suite_run_dir, "state", "state")
        if (os.path.exists(old_pri_db_path) and
                os.path.exists(old_state_file_path) and
                not os.path.exists(pri_db_path)):
            # Upgrade pre-6.11.X runtime database + state file
            copy(old_pri_db_path, pri_db_path)
            pri_dao = CylcSuiteDAO(pri_db_path)
            pri_dao.upgrade_with_state_file(old_state_file_path)
            target = os.path.join(self.suite_run_dir, "state.tar.gz")
            cmd = ["tar", "-C", self.suite_run_dir, "-czf", target, "state"]
            if call(cmd) == 0:
                rmtree(
                    os.path.join(self.suite_run_dir, "state"),
                    ignore_errors=True)
            else:
                try:
                    os.unlink(os.path.join(self.suite_run_dir, "state.tar.gz"))
                except OSError:
                    pass
                ERR.error("cannot tar-gzip + remove old state/ directory")
            # Remove old files as well
            try:
                os.unlink(os.path.join(self.suite_run_dir, "cylc-suite-env"))
            except OSError:
                pass
        elif os.path.exists(old_pri_db_path_611):
            # Upgrade 6.11.X runtime database
            os.rename(old_pri_db_path_611, pri_db_path)
            pri_dao = CylcSuiteDAO(pri_db_path)
            pri_dao.upgrade_from_611()
            # Remove old files as well
            for name in [
                    CylcSuiteDAO.OLD_DB_FILE_BASE_NAME_611[1],
                    "cylc-suite-env"]:
                try:
                    os.unlink(os.path.join(self.suite_run_dir, name))
                except OSError:
                    pass
        else:
            pri_dao = CylcSuiteDAO(pri_db_path)

        # Vacuum the primary/private database file
        OUT.info("Vacuuming the suite db ...")
        pri_dao.vacuum()
        OUT.info("...done")
        pri_dao.close()

    def configure(self):
        """Configure suite daemon."""
        self.profiler.log_memory("scheduler.py: start configure")

        self.profiler.log_memory("scheduler.py: before configure_suite")
        self.configure_suite()
        self.profiler.log_memory("scheduler.py: after configure_suite")

        reqmode = self.config.cfg['cylc']['required run mode']
        if reqmode:
            if reqmode != self.run_mode:
                raise SchedulerError(
                    'ERROR: this suite requires the %s run mode' % reqmode)

        if self.gen_reference_log or self.reference_test_mode:
            self.configure_reftest()

        self.log.info(self.START_MESSAGE_TMPL % {
            'host': self.host, 'port': self.port, 'pid': os.getpid()})
        # Note that the following lines must be present at the top of
        # the suite log file for use in reference test runs:
        self.log.info('Run mode: ' + self.run_mode)
        self.log.info('Initial point: ' + str(self.initial_point))
        if self.start_point != self.initial_point:
            self.log.info('Start point: ' + str(self.start_point))
        self.log.info('Final point: ' + str(self.final_point))

        self.pool = TaskPool(
            self.suite, self.pri_dao, self.pub_dao, self.final_point,
            self.comms_daemon, self.log, self.run_mode)

        self.profiler.log_memory("scheduler.py: before load_tasks")
        if self.is_restart:
            self.load_tasks_for_restart()
        else:
            self.load_tasks_for_run()
        self.profiler.log_memory("scheduler.py: after load_tasks")

        self.pool.put_rundb_suite_params(
            self.initial_point,
            self.final_point,
            self.config.cfg['cylc']['cycle point format'])
        self.pool.put_rundb_suite_template_vars(self.template_vars)
        self.configure_suite_environment()

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

        self.already_timed_out = False
        self.set_suite_timer()

        # self.nudge_timer_start = None
        # self.nudge_timer_on = False
        # self.auto_nudge_interval = 5  # seconds

        self.already_inactive = False
        if self._get_events_conf(self.EVENT_INACTIVITY_TIMEOUT):
            self.set_suite_inactivity_timer()

        self.profiler.log_memory("scheduler.py: end configure")

    def load_tasks_for_run(self):
        """Load tasks for a new run."""
        if self.start_point is not None:
            if self.options.warm:
                self.log.info('Warm Start %s' % self.start_point)
            else:
                self.log.info('Cold Start %s' % self.start_point)

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
                self.log.debug(str(exc))
                continue

    def load_tasks_for_restart(self):
        """Load tasks for restart."""
        self.pri_dao.select_suite_params(
            self._load_suite_params, self.options.checkpoint)
        self.pri_dao.select_broadcast_states(
            self._load_broadcast_states, self.options.checkpoint)
        self.pri_dao.select_task_job_run_times(self._load_task_run_times)
        self.pri_dao.select_task_pool_for_restart(
            self._load_task_pool, self.options.checkpoint)
        self.pri_dao.select_task_action_timers(self._load_task_action_timers)
        # Re-initialise run directory for user@host for each submitted and
        # running tasks.
        # Note: tasks should all be in the runahead pool at this point.
        for itask in self.pool.get_rh_tasks():
            if itask.state.status in [
                    TASK_STATUS_SUBMITTED, TASK_STATUS_RUNNING]:
                try:
                    RemoteJobHostManager.get_inst().init_suite_run_dir(
                        self.suite, itask.task_host, itask.task_owner)
                except RemoteJobHostInitError as exc:
                    self.log.error(str(exc))
        self.pool.poll_task_jobs()

    def _load_broadcast_states(self, row_idx, row):
        """Load a setting in the previous broadcast states."""
        if row_idx == 0:
            OUT.info("LOADING broadcast states")
        point, namespace, key, value = row
        BroadcastServer.get_inst().load_state(point, namespace, key, value)
        OUT.info(BROADCAST_LOAD_FMT.strip() % {
            "change": BROADCAST_LOAD_PREFIX,
            "point": point,
            "namespace": namespace,
            "key": key,
            "value": value})

    def _load_suite_params(self, row_idx, row):
        """Load previous initial/final cycle point."""
        if row_idx == 0:
            OUT.info("LOADING suite parameters")
        key, value = row
        if key == "is_held":
            self.pool.is_held = bool(value)
            OUT.info("+ hold suite = %s" % (bool(value),))
            return
        for key_str, self_attr, option_ignore_attr in [
                ("initial", "start_point", "ignore_start_point"),
                ("final", "stop_point", "ignore_stop_point")]:
            if key != key_str + "_point" or value is None:
                continue
            # the suite_params table prescribes a start/stop cycle
            # (else we take whatever the suite.rc file gives us)
            point = get_point(value)
            my_point = getattr(self, self_attr)
            if getattr(self.options, option_ignore_attr):
                # ignore it and take whatever the suite.rc file gives us
                if my_point is not None:
                    ERR.warning(
                        "I'm ignoring the old " + key_str +
                        " cycle point as requested,\n"
                        "but I can't ignore the one set"
                        " on the command line or in the suite definition.")
            elif my_point is not None:
                # Given in the suite.rc file
                if my_point != point:
                    ERR.warning(
                        "old %s cycle point %s, overriding suite.rc %s" %
                        (key_str, point, my_point))
                    setattr(self, self_attr, point)
            else:
                # reinstate from old
                setattr(self, self_attr, point)
            OUT.info("+ %s cycle point = %s" % (key_str, value))

    def _load_task_run_times(self, row_idx, row):
        """Load run times of previously succeeded task jobs."""
        if row_idx == 0:
            OUT.info("LOADING task run times")
        name, run_times_str = row
        try:
            taskdef = self.config.taskdefs[name]
            maxlen = TaskDef.MAX_LEN_ELAPSED_TIMES
            for run_time_str in run_times_str.rsplit(",", maxlen)[-maxlen:]:
                run_time = int(run_time_str)
                taskdef.elapsed_times.append(run_time)
            OUT.info("+ %s: %s" % (
                name, ",".join(str(s) for s in taskdef.elapsed_times)))
        except (KeyError, ValueError, AttributeError):
            return

    def _load_task_pool(self, row_idx, row):
        """Load a task from previous task pool.

        The state of task prerequisites (satisfied or not) and outputs
        (completed or not) is determined by the recorded TASK_STATUS:

        TASK_STATUS_WAITING    - prerequisites and outputs unsatisified
        TASK_STATUS_HELD       - ditto (only waiting tasks can be held)
        TASK_STATUS_QUEUED     - prereqs satisfied, outputs not completed
                                 (only tasks ready to run can get queued)
        TASK_STATUS_READY      - ditto
        TASK_STATUS_SUBMITTED  - ditto (but see *)
        TASK_STATUS_SUBMIT_RETRYING - ditto
        TASK_STATUS_RUNNING    - ditto (but see *)
        TASK_STATUS_FAILED     - ditto (tasks must run in order to fail)
        TASK_STATUS_RETRYING   - ditto (tasks must fail in order to retry)
        TASK_STATUS_SUCCEEDED  - prerequisites satisfied, outputs completed

        (*) tasks reloaded with TASK_STATUS_SUBMITTED or TASK_STATUS_RUNNING
        are polled to determine what their true status is.
        """
        if row_idx == 0:
            OUT.info("LOADING task proxies")
        (cycle, name, spawned, status, hold_swap, submit_num, try_num,
         user_at_host) = row
        try:
            itask = TaskProxy(
                self.config.get_taskdef(name),
                get_point(cycle),
                status=status,
                hold_swap=hold_swap,
                has_spawned=bool(spawned),
                submit_num=submit_num,
                is_reload_or_restart=True)
        except SuiteConfigError as exc:
            if cylc.flags.debug:
                ERR.error(traceback.format_exc())
            else:
                ERR.error(str(exc))
            ERR.warning((
                "ignoring task %s from the suite run database\n"
                "(its task definition has probably been deleted).") % name)
        except Exception:
            ERR.error(traceback.format_exc())
            ERR.error("could not load task %s" % name)
        else:
            if status in (TASK_STATUS_SUBMITTED, TASK_STATUS_RUNNING):
                itask.state.set_prerequisites_all_satisfied()
                # update the task proxy with user@host
                try:
                    itask.task_owner, itask.task_host = user_at_host.split(
                        "@", 1)
                except ValueError:
                    itask.task_owner = None
                    itask.task_host = user_at_host

            elif status in (TASK_STATUS_SUBMIT_FAILED, TASK_STATUS_FAILED):
                itask.state.set_prerequisites_all_satisfied()

            elif status in (TASK_STATUS_QUEUED, TASK_STATUS_READY):
                itask.state.set_prerequisites_all_satisfied()
                # reset to waiting as these had not been submitted yet.
                itask.state.set_state(TASK_STATUS_WAITING)

            elif status in (TASK_STATUS_SUBMIT_RETRYING, TASK_STATUS_RETRYING):
                itask.state.set_prerequisites_all_satisfied()

            elif status == TASK_STATUS_SUCCEEDED:
                itask.state.set_prerequisites_all_satisfied()
                # TODO - just poll for outputs in the job status file.
                itask.state.outputs.set_all_completed()

            if user_at_host:
                itask.summary['job_hosts'][int(submit_num)] = user_at_host
            if hold_swap:
                OUT.info("+ %s.%s %s (%s)" % (name, cycle, status, hold_swap))
            else:
                OUT.info("+ %s.%s %s" % (name, cycle, status))
            self.pool.add_to_runahead_pool(itask)

    def _load_task_action_timers(self, row_idx, row):
        """Load a task action timer, e.g. event handlers, retry states."""
        if row_idx == 0:
            OUT.info("LOADING task action timers")
        (
            cycle, name, ctx_key_pickle, ctx_pickle, delays_pickle, num, delay,
            timeout,
        ) = row
        id_ = TaskID.get(name, cycle)
        itask = self.pool.get_task_by_id(id_)
        if itask is None:
            ERR.warning("%(id)s: task not found, skip" % {"id": id_})
            return
        ctx_key = "?"
        try:
            ctx_key = pickle.loads(str(ctx_key_pickle))
            ctx = pickle.loads(str(ctx_pickle))
            delays = pickle.loads(str(delays_pickle))
            if ctx_key and ctx_key[0] in ["poll_timers", "try_timers"]:
                getattr(itask, ctx_key[0])[ctx_key[1]] = TaskActionTimer(
                    ctx, delays, num, delay, timeout)
            else:
                itask.event_handler_try_timers[ctx_key] = TaskActionTimer(
                    ctx, delays, num, delay, timeout)
        except (EOFError, TypeError, LookupError, ValueError):
            ERR.warning(
                "%(id)s: skip action timer %(ctx_key)s" %
                {"id": id_, "ctx_key": ctx_key})
            ERR.warning(traceback.format_exc())
            return
        OUT.info("+ %s.%s %s" % (name, cycle, ctx_key))

    def process_command_queue(self):
        """Process queued commands."""
        queue = self.command_queue.get_queue()
        qsize = queue.qsize()
        if qsize > 0:
            log_msg = 'Processing ' + str(qsize) + ' queued command(s)'
        else:
            return

        while True:
            try:
                name, args, kwargs = queue.get(False)
            except Empty:
                break
            args_string = ', '.join([str(a) for a in args])
            cmdstr = name + '(' + args_string
            kwargs_string = ', '.join(
                [key + '=' + str(value) for key, value in kwargs.items()])
            if kwargs_string and args_string:
                cmdstr += ', '
            cmdstr += kwargs_string + ')'
            log_msg += '\n+\t' + cmdstr
            try:
                n_warnings = getattr(self, "command_%s" % name)(
                    *args, **kwargs)
            except SchedulerStop:
                self.log.info('Command succeeded: ' + cmdstr)
                raise
            except Exception as exc:
                # Don't let a bad command bring the suite down.
                self.log.warning(traceback.format_exc())
                self.log.warning(str(exc))
                self.log.warning('Command failed: ' + cmdstr)
            else:
                if n_warnings:
                    self.log.info(
                        'Command succeeded with %s warning(s): %s' %
                        (n_warnings, cmdstr))
                else:
                    self.log.info('Command succeeded: ' + cmdstr)
                self.do_update_state_summary = True
                if name in self.PROC_CMDS:
                    self.do_process_tasks = True
            queue.task_done()
        OUT.info(log_msg)

    def _task_type_exists(self, name_or_id):
        """Does a task name or id match a known task type in this suite?"""
        name = name_or_id
        if TaskID.is_valid_id(name_or_id):
            name = TaskID.split(name_or_id)[0]
        return name in self.config.get_task_name_list()

    def info_ping_suite(self):
        """Return True to indicate that the suite is alive!"""
        return True

    def info_get_cylc_version(self):
        """Return the cylc version running this suite daemon."""
        return CYLC_VERSION

    def get_standardised_point_string(self, point_string):
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

    def info_ping_task(self, task_id, exists_only=False):
        """Return True if task exists and running."""
        task_id = self.get_standardised_taskid(task_id)
        return self.pool.ping_task(task_id, exists_only)

    def info_get_task_jobfile_path(self, task_id):
        """Return task job file path."""
        task_id = self.get_standardised_taskid(task_id)
        return self.pool.get_task_jobfile_path(task_id)

    def info_get_suite_info(self):
        """Return a dict containing the suite title and description."""
        return {'title': self.config.cfg['title'],
                'description': self.config.cfg['description']}

    def info_get_task_info(self, names):
        """Return info of a task."""
        results = {}
        for name in names:
            try:
                results[name] = self.config.describe(name)
            except KeyError:
                results[name] = {}
        return results

    def info_get_all_families(self, exclude_root=False):
        """Return info of all families."""
        fams = self.config.get_first_parent_descendants().keys()
        if exclude_root:
            return fams[:-1]
        else:
            return fams

    def info_get_first_parent_descendants(self):
        """Families for single-inheritance hierarchy based on first parents"""
        return deepcopy(self.config.get_first_parent_descendants())

    def info_get_first_parent_ancestors(self, pruned=False):
        """Single-inheritance hierarchy based on first parents"""
        return deepcopy(self.config.get_first_parent_ancestors(pruned))

    def info_get_graph_raw(self, cto, ctn, group_nodes=None,
                           ungroup_nodes=None,
                           ungroup_recursive=False, group_all=False,
                           ungroup_all=False):
        """Return raw graph."""
        rgraph = self.config.get_graph_raw(
            cto, ctn, group_nodes, ungroup_nodes, ungroup_recursive, group_all,
            ungroup_all)
        return (
            rgraph, self.config.suite_polling_tasks, self.config.leaves,
            self.config.feet)

    def info_get_task_requisites(self, items, list_prereqs=False):
        """Return prerequisites of a task."""
        return self.pool.get_task_requisites(items, list_prereqs=list_prereqs)

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
        SuiteProcPool.get_inst().stop_job_submission()
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
        parser = isodatetime.parsers.TimePointParser()
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

    def command_poll_tasks(self, items):
        """Poll all tasks or a task/family if options are provided."""
        return self.pool.poll_task_jobs(items)

    def command_kill_tasks(self, items):
        """Kill all tasks or a task/family if options are provided."""
        return self.pool.kill_task_jobs(items)

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
        self.log.info(
            "The suite will pause when all tasks have passed %s" % point)

    def command_set_verbosity(self, lvl):
        """Remove suite verbosity."""
        self.log.logger.setLevel(lvl)
        cylc.flags.debug = (lvl == logging.DEBUG)
        return True, 'OK'

    def command_remove_cycle(self, point_string, spawn=False):
        """Remove tasks in a cycle."""
        return self.pool.remove_tasks(point_string + "/*", spawn)

    def command_remove_tasks(self, items, spawn=False):
        """Remove tasks."""
        return self.pool.remove_tasks(items, spawn)

    def command_insert_tasks(self, items, stop_point_string=None,
                             no_check=False):
        """Insert tasks."""
        return self.pool.insert_tasks(items, stop_point_string, no_check)

    def command_nudge(self):
        """Cause the task processing loop to be invoked"""
        pass

    def command_reload_suite(self):
        """Reload suite configuration."""
        self.log.info("Reloading the suite definition.")
        old_tasks = set(self.config.get_task_name_list())
        self.configure_suite(reconfigure=True)
        self.pool.reconfigure(self.final_point)

        # Log tasks that have been added by the reload, removed tasks are
        # logged by the TaskPool.
        add = set(self.config.get_task_name_list()) - old_tasks
        for task in add:
            LOG.warning("Added task: '%s'" % (task,))

        self.configure_suite_environment()
        if self.gen_reference_log or self.reference_test_mode:
            self.configure_reftest(recon=True)
        self.pool.put_rundb_suite_params(
            self.initial_point,
            self.final_point,
            self.config.cfg['cylc']['cycle point format'])
        self.do_update_state_summary = True

    def command_set_runahead(self, interval=None):
        """Set runahead limit."""
        self.pool.set_runahead(interval=interval)

    def set_suite_timer(self):
        """Set suite's timeout timer."""
        timeout = self._get_events_conf(self.EVENT_TIMEOUT)
        if timeout is None:
            return
        self.suite_timer_timeout = time() + timeout
        if cylc.flags.verbose:
            OUT.info("%s suite timer starts NOW: %s" % (
                get_seconds_as_interval_string(timeout),
                get_current_time_string()))
        self.suite_timer_active = True

    def set_suite_inactivity_timer(self):
        """Set suite's inactivity timer."""
        self.suite_inactivity_timeout = time() + (
            self._get_events_conf(self.EVENT_INACTIVITY_TIMEOUT)
        )
        if cylc.flags.verbose:
            OUT.info("%s suite inactivity timer starts NOW: %s" % (
                get_seconds_as_interval_string(
                    self._get_events_conf(self.EVENT_INACTIVITY_TIMEOUT)),
                get_current_time_string()))

    def configure_comms_daemon(self):
        """Create and configure daemon."""
        self.comms_daemon = CommsDaemon(self.suite)
        self.port = self.comms_daemon.get_port()
        # Make sure another suite of the same name has not started while this
        # one is starting
        self.suite_srv_files_mgr.detect_old_contact_file(self.suite)
        # Get "pid,args" process string with "ps"
        pid_str = str(os.getpid())
        proc = Popen(
            ["ps", "h", "-opid,args", pid_str], stdout=PIPE, stderr=PIPE)
        out, err = proc.communicate()
        ret_code = proc.wait()
        process_str = None
        for line in out.splitlines():
            if line.split(None, 1)[0].strip() == pid_str:
                process_str = line.strip()
                break
        if ret_code or not process_str:
            raise SchedulerError(
                'ERROR, cannot get process "args" from "ps": %s' % err)
        # Write suite contact file.
        # Preserve contact data in memory, for regular health check.
        mgr = self.suite_srv_files_mgr
        contact_data = {
            mgr.KEY_DIR_ON_SUITE_HOST: os.environ['CYLC_DIR'],
            mgr.KEY_NAME: self.suite,
            mgr.KEY_HOST: self.host,
            mgr.KEY_PROCESS: process_str,
            mgr.KEY_PORT: str(self.port),
            mgr.KEY_OWNER: self.owner,
            mgr.KEY_SUITE_RUN_DIR_ON_SUITE_HOST: self.suite_run_dir,
            mgr.KEY_TASK_MSG_MAX_TRIES: str(GLOBAL_CFG.get(
                ['task messaging', 'maximum number of tries'])),
            mgr.KEY_TASK_MSG_RETRY_INTVL: str(float(GLOBAL_CFG.get(
                ['task messaging', 'retry interval']))),
            mgr.KEY_TASK_MSG_TIMEOUT: str(float(GLOBAL_CFG.get(
                ['task messaging', 'connection timeout']))),
            mgr.KEY_VERSION: CYLC_VERSION}
        try:
            mgr.dump_contact_file(self.suite, contact_data)
        except IOError as exc:
            raise SchedulerError(
                'ERROR, cannot write suite contact file: %s: %s' %
                (mgr.get_contact_file(self.suite), exc))
        else:
            self.contact_data = contact_data

    def load_suiterc(self, reconfigure):
        """Load and log the suite definition."""
        self.config = SuiteConfig.get_inst(
            self.suite, self.suiterc, self.template_vars,
            run_mode=self.run_mode,
            cli_initial_point_string=self._cli_initial_point_string,
            cli_start_point_string=self._cli_start_point_string,
            cli_final_point_string=self.options.final_point_string,
            is_reload=reconfigure,
            mem_log_func=self.profiler.log_memory,
            output_fname=os.path.join(
                self.suite_run_dir,
                self.suite_srv_files_mgr.FILE_BASE_SUITE_RC + '.processed'),
        )
        # Dump the loaded suiterc for future reference.
        cfg_logdir = GLOBAL_CFG.get_derived_host_item(
            self.suite, 'suite config log directory')
        time_str = get_current_time_string(
            override_use_utc=True, use_basic_format=True,
            display_sub_seconds=False
        )
        if reconfigure:
            load_type = "reload"
        elif self.is_restart:
            load_type = "restart"
        else:
            load_type = "run"
        base_name = "%s-%s.rc" % (time_str, load_type)
        file_name = os.path.join(cfg_logdir, base_name)
        try:
            with open(file_name, "wb") as handle:
                handle.write("# cylc-version: %s\n" % CYLC_VERSION)
                printcfg(self.config.cfg, none_str=None, handle=handle)
        except IOError as exc:
            ERR.error(str(exc))
            raise SchedulerError("Unable to log the loaded suite definition")

    def _load_initial_cycle_point(self, _, row):
        """Load previous initial cycle point.

        For restart, it may be missing from "suite.rc", but was specified as a
        command line argument on cold/warm start.
        """
        key, value = row
        if key == "initial_point":
            self._cli_initial_point_string = value
            self.do_process_tasks = True

    def _load_template_vars(self, _, row):
        """Load suite start up template variables."""
        key, value = row
        # Command line argument takes precedence
        if key not in self.template_vars:
            self.template_vars[key] = value

    def configure_suite(self, reconfigure=False):
        """Load and process the suite definition."""

        if reconfigure:
            self.pri_dao.take_checkpoints(
                "reload-init", other_daos=[self.pub_dao])
        elif self.is_restart:
            # This logic handles the lack of initial cycle point in "suite.rc".
            # Things that can't change on suite reload.
            pri_db_path = os.path.join(
                self.suite_srv_files_mgr.get_suite_srv_dir(self.suite),
                CylcSuiteDAO.DB_FILE_BASE_NAME)
            self.pri_dao = CylcSuiteDAO(pri_db_path)
            self.pri_dao.select_suite_params(self._load_initial_cycle_point)
            self.pri_dao.select_suite_template_vars(self._load_template_vars)
            # Take checkpoint and commit immediately so that checkpoint can be
            # copied to the public database.
            self.pri_dao.take_checkpoints("restart")
            self.pri_dao.execute_queued_items()

        self.load_suiterc(reconfigure)

        # Initial and final cycle times - command line takes precedence.
        # self.config already alters the 'initial cycle point' for CLI.
        self.initial_point = self.config.initial_point
        self.start_point = self.config.start_point
        self.final_point = get_point(
            self.options.final_point_string or
            self.config.cfg['scheduling']['final cycle point']
        )
        if self.final_point is not None:
            self.final_point.standardise()

        if not self.initial_point and not self.is_restart:
            ERR.warning('No initial cycle point provided - no cycling tasks '
                        'will be loaded.')

        if self.run_mode != self.config.run_mode:
            self.run_mode = self.config.run_mode

        if reconfigure:
            BroadcastServer.get_inst().linearized_ancestors = (
                self.config.get_linearized_ancestors())
        else:
            # Things that can't change on suite reload.
            pri_db_path = os.path.join(
                self.suite_srv_files_mgr.get_suite_srv_dir(self.suite),
                CylcSuiteDAO.DB_FILE_BASE_NAME)
            pub_db_path = os.path.join(
                self.suite_run_dir, 'log', CylcSuiteDAO.DB_FILE_BASE_NAME)
            if not self.is_restart:
                # Remove database created by previous runs
                try:
                    os.unlink(pri_db_path)
                except OSError:
                    # Just in case the path is a directory!
                    rmtree(pri_db_path, ignore_errors=True)
            # Ensure that:
            # * public database is in sync with private database
            # * private database file is private
            self.pri_dao = CylcSuiteDAO(pri_db_path)
            os.chmod(pri_db_path, 0600)
            self.pub_dao = CylcSuiteDAO(pub_db_path, is_public=True)
            self._copy_pri_db_to_pub_db()
            pub_db_path_symlink = os.path.join(
                self.suite_run_dir, CylcSuiteDAO.OLD_DB_FILE_BASE_NAME)
            try:
                orig_source = os.readlink(pub_db_path_symlink)
            except OSError:
                orig_source = None
            source = os.path.join('log', CylcSuiteDAO.DB_FILE_BASE_NAME)
            if orig_source != source:
                try:
                    os.unlink(pub_db_path_symlink)
                except OSError:
                    pass
                os.symlink(source, pub_db_path_symlink)

            if self.config.cfg['scheduling']['hold after point']:
                self.pool_hold_point = get_point(
                    self.config.cfg['scheduling']['hold after point'])

            if self.options.hold_point_string:
                self.pool_hold_point = get_point(
                    self.options.hold_point_string)

            if self.pool_hold_point:
                OUT.info("Suite will hold after " + str(self.pool_hold_point))

            suite_id = SuiteIdServer.get_inst(self.suite, self.owner)
            self.comms_daemon.connect(suite_id, COMMS_SUITEID_OBJ_NAME)

            bcast = BroadcastServer.get_inst(
                self.config.get_linearized_ancestors())
            self.comms_daemon.connect(bcast, COMMS_BCAST_OBJ_NAME)

            self.command_queue = SuiteCommandServer()
            self.comms_daemon.connect(self.command_queue, COMMS_CMD_OBJ_NAME)

            ets = ExtTriggerServer.get_inst()
            self.comms_daemon.connect(ets, COMMS_EXT_TRIG_OBJ_NAME)

            info_commands = {}
            for attr_name in dir(self):
                attr = getattr(self, attr_name)
                if callable(attr) and attr_name.startswith('info_'):
                    info_commands[attr_name.replace('info_', '')] = attr
            self.info_interface = SuiteInfoServer(info_commands)
            self.comms_daemon.connect(self.info_interface, COMMS_INFO_OBJ_NAME)

            self.suite_log = SuiteLog.get_inst(self.suite)
            log_interface = SuiteLogServer(self.suite_log)
            self.comms_daemon.connect(log_interface, COMMS_LOG_OBJ_NAME)

            self.suite_state = StateSummaryServer.get_inst(self.run_mode)
            self.comms_daemon.connect(self.suite_state, COMMS_STATE_OBJ_NAME)

        for namespace in self.config.cfg['runtime']:
            ancestors = (' ').join(
                self.config.runtime['linearized ancestors'][namespace])
            self.pri_dao.add_insert_item(CylcSuiteDAO.TABLE_INHERITANCE,
                                         [namespace, ancestors])
            self.pub_dao.add_insert_item(CylcSuiteDAO.TABLE_INHERITANCE,
                                         [namespace, ancestors])

    def configure_suite_environment(self):
        """Configure suite environment."""
        # Pass static cylc and suite variables to job script generation code
        JobFile.get_inst().set_suite_env({
            'CYLC_UTC': str(cylc.flags.utc),
            'CYLC_DEBUG': str(cylc.flags.debug),
            'CYLC_VERBOSE': str(cylc.flags.verbose),
            'CYLC_SUITE_NAME': self.suite,
            'CYLC_CYCLING_MODE': str(cylc.flags.cycling_mode),
            'CYLC_SUITE_INITIAL_CYCLE_POINT': str(self.initial_point),
            'CYLC_SUITE_FINAL_CYCLE_POINT': str(self.final_point),
        })

        # Make suite vars available to [cylc][environment]:
        for var, val in JobFile.get_inst().suite_env.items():
            os.environ[var] = val
        # Set local values of variables that are potenitally task-specific
        # due to different directory paths on different task hosts. These
        # are overridden by tasks prior to job submission, but in
        # principle they could be needed locally by event handlers:
        for var, val in [
                ('CYLC_SUITE_RUN_DIR', self.suite_run_dir),
                ('CYLC_SUITE_LOG_DIR', self.suite_log.get_dir()),
                ('CYLC_SUITE_WORK_DIR', GLOBAL_CFG.get_derived_host_item(
                    self.suite, 'suite work directory')),
                ('CYLC_SUITE_SHARE_DIR', GLOBAL_CFG.get_derived_host_item(
                    self.suite, 'suite share directory')),
                ('CYLC_SUITE_DEF_PATH', self.suite_dir)]:
            os.environ[var] = val

        # (global config auto expands environment variables in local paths)
        cenv = self.config.cfg['cylc']['environment'].copy()
        for var, val in cenv.items():
            cenv[var] = os.path.expandvars(val)
        # path to suite bin directory for suite and task event handlers
        cenv['PATH'] = os.pathsep.join([
            os.path.join(self.suite_dir, 'bin'), os.environ['PATH']])

        # Make [cylc][environment] available to task event handlers in worker
        # processes,
        self.task_event_handler_env = cenv
        # and to suite event handlers in this process.
        for var, val in cenv.items():
            os.environ[var] = val

    def configure_reftest(self, recon=False):
        """Configure the reference test."""
        if self.gen_reference_log:
            self.config.cfg['cylc']['log resolved dependencies'] = True

        elif self.reference_test_mode:
            rtc = self.config.cfg['cylc']['reference test']
            req = rtc['required run mode']
            if req and req != self.run_mode:
                raise SchedulerError(
                    'ERROR: suite allows only ' + req + ' reference tests')
            handlers = self._get_events_conf('shutdown handler')
            if handlers:
                ERR.warning('shutdown handlers replaced by reference test')
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
                    'ERROR: timeout not defined for %s reference tests' % (
                        self.run_mode))
            self.config.cfg['cylc']['events'][self.EVENT_TIMEOUT] = (
                timeout)
            self.config.cfg['cylc']['events']['reset timer'] = False

    def run_event_handlers(self, event, message):
        """Run a suite event handler."""
        if (self.run_mode in ['simulation', 'dummy'] and
            self.config.cfg['cylc']['simulation'][
                'disable suite event handlers']):
            return
        self._run_event_mail(event, message)
        self._run_event_custom_handlers(event, message)

    def _run_event_mail(self, event, message):
        """Helper for "run_event_handlers", do mail notification."""
        if event in self._get_events_conf('mail events', []):
            # SMTP server
            env = dict(os.environ)
            mail_smtp = self._get_events_conf('mail smtp')
            if mail_smtp:
                env['smtp'] = mail_smtp
            subject = '[suite %(event)s] %(suite)s' % {
                'suite': self.suite, 'event': event}
            stdin_str = ''
            for name, value in [
                    ('suite event', event),
                    ('reason', message),
                    ('suite', self.suite),
                    ('host', self.host),
                    ('port', self.port),
                    ('owner', self.owner)]:
                if value:
                    stdin_str += '%s: %s\n' % (name, value)
            mail_footer_tmpl = self._get_events_conf('mail footer')
            if mail_footer_tmpl:
                stdin_str += (mail_footer_tmpl + '\n') % {
                    'host': self.host,
                    'port': self.port,
                    'owner': self.owner,
                    'suite': self.suite}
            ctx = SuiteProcContext(
                (self.SUITE_EVENT_HANDLER, event),
                [
                    'mail',
                    '-s', subject,
                    '-r', self._get_events_conf(
                        'mail from', 'notifications@' + get_suite_host()),
                    self._get_events_conf('mail to', USER),
                ],
                env=env,
                stdin_str=stdin_str)
            if SuiteProcPool.get_inst().is_closed():
                # Run command in foreground if process pool is closed
                SuiteProcPool.get_inst().run_command(ctx)
                self._run_event_handlers_callback(ctx)
            else:
                # Run command using process pool otherwise
                SuiteProcPool.get_inst().put_command(
                    ctx, self._run_event_mail_callback)

    def _run_event_custom_handlers(self, event, message):
        """Helper for "run_event_handlers", custom event handlers."""
        # Look for event handlers
        # 1. Handlers for specific event
        # 2. General handlers
        handlers = self._get_events_conf('%s handler' % event)
        if (not handlers and
                event in self._get_events_conf('handler events', [])):
            handlers = self._get_events_conf('handlers')
        if not handlers:
            return

        for i, handler in enumerate(handlers):
            cmd_key = ('%s-%02d' % (self.SUITE_EVENT_HANDLER, i), event)
            # Handler command may be a string for substitution
            cmd = handler % {
                'event': quote(event),
                'suite': quote(self.suite),
                'message': quote(message),
                'suite_url': quote(self.config.cfg['URL'])
            }
            if cmd == handler:
                # Nothing substituted, assume classic interface
                cmd = "%s '%s' '%s' '%s'" % (
                    handler, event, self.suite, message)
            ctx = SuiteProcContext(
                cmd_key, cmd, env=dict(os.environ), shell=True)
            abort_on_error = self._get_events_conf(
                'abort if %s handler fails' % event)
            if abort_on_error or SuiteProcPool.get_inst().is_closed():
                # Run command in foreground if abort on failure is set or if
                # process pool is closed
                SuiteProcPool.get_inst().run_command(ctx)
                self._run_event_handlers_callback(
                    ctx, abort_on_error=abort_on_error)
            else:
                # Run command using process pool otherwise
                SuiteProcPool.get_inst().put_command(
                    ctx, self._run_event_handlers_callback)

    def _run_event_handlers_callback(self, ctx, abort_on_error=False):
        """Callback on completion of a suite event handler."""
        if ctx.ret_code:
            self.log.warning(str(ctx))
            ERR.error('%s EVENT HANDLER FAILED' % ctx.cmd_key[1])
            if (ctx.cmd_key[1] == self.EVENT_SHUTDOWN and
                    self.reference_test_mode):
                ERR.error('SUITE REFERENCE TEST FAILED')
            if abort_on_error:
                raise SchedulerError(ctx.err)
        else:
            self.log.info(str(ctx))
            if (ctx.cmd_key[1] == self.EVENT_SHUTDOWN and
                    self.reference_test_mode):
                OUT.info('SUITE REFERENCE TEST PASSED\n')

    def _run_event_mail_callback(self, ctx):
        """Callback the mail command for notification of a suite event."""
        if ctx.ret_code:
            self.log.warning(str(ctx))
        else:
            self.log.info(str(ctx))

    def run(self):
        """Main loop."""
        if self.pool_hold_point is not None:
            self.hold_suite(self.pool_hold_point)

        if self.options.start_held:
            self.log.info("Held on start-up (no tasks will be submitted)")
            self.hold_suite()

        self.run_event_handlers(self.EVENT_STARTUP, 'suite starting')

        self.profiler.log_memory("scheduler.py: begin run while loop")
        proc_pool = SuiteProcPool.get_inst()

        time_next_fs_check = None

        if self.options.profile_mode:
            previous_profile_point = 0
            count = 0

        can_auto_stop = (
            not self.config.cfg['cylc']['disable automatic shutdown'] and
            not self.options.no_auto_shutdown)

        while True:  # MAIN LOOP
            tinit = time()

            if self.pool.do_reload:
                self.pool.reload_taskdefs()
                self.do_update_state_summary = True

            self.process_command_queue()
            if self.pool.release_runahead_tasks():
                self.do_update_state_summary = True
            proc_pool.handle_results_async()

            # External triggers must be matched now. If any are matched pflag
            # is set to tell process_tasks() that task processing is required.
            self.pool.match_ext_triggers()

            # PROCESS ALL TASKS whenever something has changed that might
            # require renegotiation of dependencies, etc.
            if self.process_tasks():
                if cylc.flags.debug:
                    self.log.debug("BEGIN TASK PROCESSING")
                    time0 = time()

                self.pool.match_dependencies()
                if self.stop_mode is None and self.pool.submit_tasks():
                    self.do_update_state_summary = True
                for meth in [
                        self.pool.spawn_all_tasks,
                        self.pool.remove_spent_tasks,
                        self.pool.remove_suiciding_tasks]:
                    if meth():
                        self.do_update_state_summary = True

                BroadcastServer.get_inst().expire(self.pool.get_min_point())

                if cylc.flags.debug:
                    self.log.debug(
                        "END TASK PROCESSING (took %s seconds)" %
                        (time() - time0))

            self.pool.process_queued_task_messages()
            self.process_queued_task_event_handlers()
            self.process_command_queue()
            has_changes = cylc.flags.iflag or self.do_update_state_summary
            if has_changes:
                self.pool.put_rundb_task_pool()
                self.update_state_summary()
            try:
                self.pool.process_queued_db_ops()
            except OSError as err:
                raise SchedulerError(str(err))
            # If public database is stuck, blast it away by copying the content
            # of the private database into it.
            if self.pub_dao.n_tries >= self.pub_dao.MAX_TRIES:
                try:
                    self._copy_pri_db_to_pub_db()
                except (IOError, OSError) as exc:
                    # Something has to be very wrong here, so stop the suite
                    raise SchedulerError(str(exc))
                else:
                    # No longer stuck
                    self.log.warning(
                        "%(pub_db_name)s: recovered from %(pri_db_name)s" % {
                            "pub_db_name": self.pub_dao.db_file_name,
                            "pri_db_name": self.pri_dao.db_file_name})
                    self.pub_dao.n_tries = 0

            self.check_suite_timer()
            if self._get_events_conf(self.EVENT_INACTIVITY_TIMEOUT):
                self.check_suite_inactive()
            # check submission and execution timeout and polling timers
            if self.run_mode != 'simulation':
                self.pool.check_task_timers()

            # Does the suite need to shutdown on task failure?
            if (self.config.cfg['cylc']['abort if any task fails'] and
                    self.pool.any_task_failed()):
                # Task failure + abort if any task fails
                self._set_stop(TaskPool.STOP_AUTO_ON_TASK_FAILURE)
            elif self.reference_test_mode and self.ref_test_allowed_failures:
                # In reference test mode and unexpected failures occured
                bad_tasks = []
                for itask in self.pool.get_failed_tasks():
                    if itask.identity not in self.ref_test_allowed_failures:
                        bad_tasks.append(itask)
                if bad_tasks:
                    sys.stderr.write(
                        'Failed task(s) not in allowed failures list:\n')
                    for itask in bad_tasks:
                        sys.stderr.write("\t%s\n" % itask.identity)
                    self._set_stop(TaskPool.STOP_AUTO_ON_TASK_FAILURE)

            # Can suite shut down automatically?
            if self.stop_mode is None and (
                    self.stop_clock_done() or self.stop_task_done() or
                    can_auto_stop and self.pool.check_auto_shutdown()):
                self._set_stop(TaskPool.STOP_AUTO)

            # Is the suite ready to shut down now?
            if self.pool.can_stop(self.stop_mode):
                self.update_state_summary()
                proc_pool.close()
                if self.stop_mode != TaskPool.STOP_REQUEST_NOW_NOW:
                    # Wait for process pool to complete,
                    # unless --now --now is requested
                    stop_process_pool_empty_msg = (
                        "Waiting for the command process pool to empty" +
                        " for shutdown")
                    while not proc_pool.is_dead():
                        sleep(self.INTERVAL_STOP_PROCESS_POOL_EMPTY)
                        if stop_process_pool_empty_msg:
                            self.log.info(stop_process_pool_empty_msg)
                            OUT.info(stop_process_pool_empty_msg)
                            stop_process_pool_empty_msg = None
                        proc_pool.handle_results_async()
                        self.process_command_queue()
                if self.options.profile_mode:
                    self.profiler.log_memory(
                        "scheduler.py: end main loop (total loops %d): %s" %
                        (count, get_current_time_string()))
                if self.stop_mode == TaskPool.STOP_AUTO_ON_TASK_FAILURE:
                    raise SchedulerError(self.stop_mode)
                else:
                    raise SchedulerStop(self.stop_mode)
            elif (self.time_next_kill is not None and
                    time() > self.time_next_kill):
                self.pool.poll_task_jobs()
                self.pool.kill_task_jobs()
                self.time_next_kill = time() + self.INTERVAL_STOP_KILL

            # Suite health checks
            if self.stop_mode is None and not has_changes:
                self.check_suite_stalled()
            now = time()
            if time_next_fs_check is None or now > time_next_fs_check:
                if not os.path.exists(self.suite_run_dir):
                    raise SchedulerError(
                        "%s: suite run directory not found" %
                        self.suite_run_dir)
                try:
                    contact_data = self.suite_srv_files_mgr.load_contact_file(
                        self.suite)
                    assert contact_data == self.contact_data
                except (AssertionError, IOError, ValueError,
                        SuiteServiceFileError):
                    ERR.critical(traceback.format_exc())
                    exc = SchedulerError(
                        ("%s: suite contact file corrupted/modified and" +
                         " may be left") %
                        self.suite_srv_files_mgr.get_contact_file(self.suite))
                    raise exc
                time_next_fs_check = (
                    now + self._get_cylc_conf('health check interval'))

            if self.options.profile_mode:
                now = time()
                self._update_profile_info("scheduler loop dt (s)", now - tinit,
                                          amount_format="%.3f")
                self._update_cpu_usage()
                if now - previous_profile_point >= 60:
                    # Only get this every minute.
                    previous_profile_point = now
                    self.profiler.log_memory("scheduler.py: loop #%d: %s" % (
                        count, get_current_time_string()))
                count += 1

            sleep(self.INTERVAL_MAIN_LOOP)
            # END MAIN LOOP

    def update_state_summary(self):
        """Update state summary, e.g. for GUI."""
        self.suite_state.update(
            self.pool.get_tasks(), self.pool.get_rh_tasks(),
            self.pool.get_min_point(), self.pool.get_max_point(),
            self.pool.get_max_point_runahead(), self.paused(),
            self.will_pause_at(), self.stop_mode is not None,
            self.will_stop_at(), self.config.ns_defn_order,
            self.pool.do_reload)
        cylc.flags.iflag = False
        self.do_update_state_summary = False
        self.is_stalled = False
        if self.suite_timer_active:
            self.suite_timer_active = False
            if cylc.flags.verbose:
                OUT.info("%s suite timer stopped NOW: %s" % (
                    get_seconds_as_interval_string(
                        self._get_events_conf(self.EVENT_TIMEOUT)),
                    get_current_time_string()))

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
            self.log.warning(message)
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
            self.log.warning(message)
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
            self.log.warning(message)
            self.run_event_handlers(self.EVENT_STALLED, message)
            self.pool.report_stalled_task_deps()
            if self._get_events_conf('abort on stalled'):
                raise SchedulerError('Abort on suite stalled is set')
            # Start suite timeout timer
            if self._get_events_conf(self.EVENT_TIMEOUT):
                self.set_suite_timer()

    def process_tasks(self):
        """Return True if waiting tasks are ready."""
        # do we need to do a pass through the main task processing loop?
        process = False

        if self.do_process_tasks:
            # this flag is turned on by commands that change task state
            process = True
            self.do_process_tasks = False  # reset

        if cylc.flags.pflag:
            process = True
            cylc.flags.pflag = False  # reset

            if (self._get_events_conf(self.EVENT_INACTIVITY_TIMEOUT) and
                    self._get_events_conf('reset inactivity timer')):
                self.set_suite_inactivity_timer()

        if self.pool.waiting_tasks_ready():
            process = True

        if self.run_mode == 'simulation' and self.pool.sim_time_check():
            process = True

        # if not process:
        #    # If we neglect to set cylc.flags.pflag on some event that
        #    # makes re-negotiation of dependencies necessary then if
        #    # that event ever happens in isolation the suite could stall
        #    # unless manually nudged ("cylc nudge SUITE").  If this
        #    # happens turn on debug logging to see what happens
        #    # immediately before the stall,
        #    # then set cylc.flags.pflag = True in
        #    # the corresponding code section. Alternatively,
        #    # for an undiagnosed stall you can uncomment this section to
        #    # stimulate task processing every few seconds even during
        #    # lulls in activity.  THIS SHOULD NOT BE NECESSARY, HOWEVER.
        #    if not self.nudge_timer_on:
        #        self.nudge_timer_start = now()
        #        self.nudge_timer_on = True
        #    else:
        #        timeout = self.nudge_timer_start + \
        #              datetime.timedelta(seconds=self.auto_nudge_interval)
        #      if now() > timeout:
        #          process = True
        #          self.nudge_timer_on = False

        return process

    def process_queued_task_event_handlers(self):
        """Process task event handlers."""
        ctx_groups = {}
        env = None
        now = time()
        for itask in self.pool.get_tasks():
            for key, try_timer in itask.event_handler_try_timers.items():
                # This should not happen, ignore for now.
                if try_timer.ctx is None:
                    del itask.event_handler_try_timers[key]
                    continue
                if try_timer.is_waiting:
                    continue
                # Set timer if timeout is None.
                if not try_timer.is_timeout_set():
                    if try_timer.next() is None:
                        itask.log(logging.WARNING, "%s failed" % str(key))
                        del itask.event_handler_try_timers[key]
                        continue
                    # Report retries and delayed 1st try
                    tmpl = None
                    if try_timer.num > 1:
                        tmpl = "%s failed, retrying in %s (after %s)"
                    elif try_timer.delay:
                        tmpl = "%s will run after %s (after %s)"
                    if tmpl:
                        itask.log(logging.DEBUG, tmpl % (
                            str(key),
                            try_timer.delay_as_seconds(),
                            try_timer.timeout_as_str()))
                # Ready to run?
                if not try_timer.is_delay_done() or (
                    # Avoid flooding user's mail box with mail notification.
                    # Group together as many notifications as possible within a
                    # given interval.
                    try_timer.ctx.ctx_type == TaskProxy.EVENT_MAIL and
                    not self.stop_mode and
                    self.next_task_event_mail_time is not None and
                    self.next_task_event_mail_time > now
                ):
                    continue

                try_timer.set_waiting()
                if try_timer.ctx.ctx_type == TaskProxy.CUSTOM_EVENT_HANDLER:
                    # Run custom event handlers on their own
                    if env is None:
                        env = dict(os.environ)
                        if self.task_event_handler_env:
                            env.update(self.task_event_handler_env)
                    SuiteProcPool.get_inst().put_command(
                        SuiteProcContext(
                            key, try_timer.ctx.cmd, env=env, shell=True,
                        ),
                        itask.custom_event_handler_callback)
                else:
                    # Group together built-in event handlers, where possible
                    if try_timer.ctx not in ctx_groups:
                        ctx_groups[try_timer.ctx] = []
                    # "itask.submit_num" may have moved on at this point
                    key1, submit_num = key
                    ctx_groups[try_timer.ctx].append(
                        (key1, str(itask.point), itask.tdef.name, submit_num))

        next_task_event_mail_time = (
            now + self._get_cylc_conf("task event mail interval"))
        for ctx, id_keys in ctx_groups.items():
            if ctx.ctx_type == TaskProxy.EVENT_MAIL:
                # Set next_task_event_mail_time if any mail sent
                self.next_task_event_mail_time = next_task_event_mail_time
                self._process_task_event_email(ctx, id_keys)
            elif ctx.ctx_type == TaskProxy.JOB_LOGS_RETRIEVE:
                self._process_task_job_logs_retrieval(ctx, id_keys)

    def _process_task_event_email(self, ctx, id_keys):
        """Process event notification, by email."""
        if len(id_keys) == 1:
            # 1 event from 1 task
            (_, event), point, name, submit_num = id_keys[0]
            subject = "[%s/%s/%02d %s] %s" % (
                point, name, submit_num, event, self.suite)
        else:
            event_set = set([id_key[0][1] for id_key in id_keys])
            if len(event_set) == 1:
                # 1 event from n tasks
                subject = "[%d tasks %s] %s" % (
                    len(id_keys), event_set.pop(), self.suite)
            else:
                # n events from n tasks
                subject = "[%d task events] %s" % (len(id_keys), self.suite)
        cmd = ["mail", "-s", subject]
        # From: and To:
        cmd.append("-r")
        cmd.append(ctx.mail_from)
        cmd.append(ctx.mail_to)
        # STDIN for mail, tasks
        stdin_str = ""
        for id_key in sorted(id_keys):
            (_, event), point, name, submit_num = id_key
            stdin_str += "%s: %s/%s/%02d\n" % (event, point, name, submit_num)
        # STDIN for mail, event info + suite detail
        stdin_str += "\n"
        for name, value in [
                ('suite', self.suite),
                ("host", self.host),
                ("port", self.port),
                ("owner", self.owner)]:
            if value:
                stdin_str += "%s: %s\n" % (name, value)
        mail_footer_tmpl = self._get_events_conf("mail footer")
        if mail_footer_tmpl:
            stdin_str += (mail_footer_tmpl + "\n") % {
                "host": self.host,
                "port": self.port,
                "owner": self.owner,
                "suite": self.suite}
        # SMTP server
        env = dict(os.environ)
        mail_smtp = ctx.mail_smtp
        if mail_smtp:
            env["smtp"] = mail_smtp
        SuiteProcPool.get_inst().put_command(
            SuiteProcContext(
                ctx, cmd, env=env, stdin_str=stdin_str, id_keys=id_keys,
            ),
            self._task_event_email_callback)

    def _task_event_email_callback(self, ctx):
        """Call back when email notification command exits."""
        tasks = {}
        for itask in self.pool.get_tasks():
            if itask.point is not None and itask.submit_num:
                tasks[(str(itask.point), itask.tdef.name)] = itask
        for id_key in ctx.cmd_kwargs["id_keys"]:
            key1, point, name, submit_num = id_key
            try:
                itask = tasks[(point, name)]
                try_timers = itask.event_handler_try_timers
                if ctx.ret_code == 0:
                    del try_timers[(key1, submit_num)]
                    log_ctx = SuiteProcContext((key1, submit_num), None)
                    log_ctx.ret_code = 0
                    itask.command_log(log_ctx)
                else:
                    try_timers[(key1, submit_num)].unset_waiting()
            except KeyError:
                if cylc.flags.debug:
                    ERR.debug(traceback.format_exc())

    def _process_task_job_logs_retrieval(self, ctx, id_keys):
        """Process retrieval of task job logs from remote user@host."""
        if ctx.user_at_host and "@" in ctx.user_at_host:
            s_user, s_host = ctx.user_at_host.split("@", 1)
        else:
            s_user, s_host = (None, ctx.user_at_host)
        ssh_str = str(GLOBAL_CFG.get_host_item("ssh command", s_host, s_user))
        rsync_str = str(GLOBAL_CFG.get_host_item(
            "retrieve job logs command", s_host, s_user))

        cmd = shlex.split(rsync_str) + ["--rsh=" + ssh_str]
        if cylc.flags.debug:
            cmd.append("-v")
        if ctx.max_size:
            cmd.append("--max-size=%s" % (ctx.max_size,))
        # Includes and excludes
        includes = set()
        for _, point, name, submit_num in id_keys:
            # Include relevant directories, all levels needed
            includes.add("/%s" % (point))
            includes.add("/%s/%s" % (point, name))
            includes.add("/%s/%s/%02d" % (point, name, submit_num))
            includes.add("/%s/%s/%02d/**" % (point, name, submit_num))
        cmd += ["--include=%s" % (include) for include in sorted(includes)]
        cmd.append("--exclude=/**")  # exclude everything else
        # Remote source
        cmd.append(ctx.user_at_host + ":" + GLOBAL_CFG.get_derived_host_item(
            self.suite, "suite job log directory", s_host, s_user) + "/")
        # Local target
        cmd.append(GLOBAL_CFG.get_derived_host_item(
            self.suite, "suite job log directory") + "/")
        SuiteProcPool.get_inst().put_command(
            SuiteProcContext(ctx, cmd, env=dict(os.environ), id_keys=id_keys),
            self._task_job_logs_retrieval_callback)

    def _task_job_logs_retrieval_callback(self, ctx):
        """Call back when log job retrieval completes."""
        tasks = {}
        for itask in self.pool.get_tasks():
            if itask.point is not None and itask.submit_num:
                tasks[(str(itask.point), itask.tdef.name)] = itask
        for id_key in ctx.cmd_kwargs["id_keys"]:
            key1, point, name, submit_num = id_key
            try:
                itask = tasks[(point, name)]
                try_timers = itask.event_handler_try_timers
                # All completed jobs are expected to have a "job.out".
                names = ["job.out"]
                # Failed jobs are expected to have a "job.err".
                if itask.state.status != TASK_STATUS_SUCCEEDED:
                    names.append("job.err")
                name_oks = {}
                for name in names:
                    name_oks[name] = os.path.exists(itask.get_job_log_path(
                        itask.HEAD_MODE_LOCAL, submit_num, name))
                # All expected paths must exist to record a good attempt
                log_ctx = SuiteProcContext((key1, submit_num), None)
                if all(name_oks.values()):
                    log_ctx.ret_code = 0
                    del try_timers[(key1, submit_num)]
                else:
                    log_ctx.ret_code = 1
                    log_ctx.err = "File(s) not retrieved:"
                    for name, exist_ok in sorted(name_oks.items()):
                        if not exist_ok:
                            log_ctx.err += " %s" % name
                    try_timers[(key1, submit_num)].unset_waiting()
                itask.command_log(log_ctx)
            except KeyError:
                if cylc.flags.debug:
                    ERR.debug(traceback.format_exc())

    def shutdown(self, reason=None):
        """Shutdown the suite."""
        msg = "Suite shutting down"
        if isinstance(reason, CylcError):
            msg += ' - %s' % reason.args[0]
            if isinstance(reason, SchedulerError):
                sys.stderr.write(msg + '\n')
            reason = reason.args[0]
        elif reason:
            msg += ' - %s' % reason
        OUT.info(msg)

        # The getattr() calls and if tests below are used in case the
        # suite is not fully configured before the shutdown is called.
        if getattr(self, "log", None) is not None:
            self.log.info(msg)

        if self.gen_reference_log:
            try:
                handle = open(
                    os.path.join(self.config.fdir, 'reference.log'), 'wb')
                for line in open(self.suite_log.get_log_path(SuiteLog.LOG)):
                    if any([text in line for text in self.REF_LOG_TEXTS]):
                        handle.write(line)
                handle.close()
            except IOError as exc:
                ERR.error(str(exc))

        if self.pool is not None:
            self.pool.warn_stop_orphans()
            try:
                self.pool.put_rundb_task_pool()
                self.pool.process_queued_db_ops()
            except Exception as exc:
                ERR.error(str(exc))

        proc_pool = SuiteProcPool.get_inst()
        if proc_pool:
            if not proc_pool.is_dead():
                # e.g. KeyboardInterrupt
                proc_pool.terminate()
            proc_pool.join()
            proc_pool.handle_results_async()

        if self.comms_daemon:
            ifaces = [self.command_queue,
                      SuiteIdServer.get_inst(), StateSummaryServer.get_inst(),
                      ExtTriggerServer.get_inst(), BroadcastServer.get_inst()]
            if self.pool is not None:
                ifaces.append(self.pool.message_queue)
            for iface in ifaces:
                try:
                    self.comms_daemon.disconnect(iface)
                except KeyError:
                    # Wasn't connected yet.
                    pass
            self.comms_daemon.shutdown()

        # Flush errors and info before removing suite contact file
        sys.stdout.flush()
        sys.stderr.flush()

        if self.contact_data:
            fname = self.suite_srv_files_mgr.get_contact_file(self.suite)
            try:
                os.unlink(fname)
            except OSError as exc:
                ERR.warning("failed to remove suite contact file: %s\n%s\n" % (
                    fname, exc))
        RemoteJobHostManager.get_inst().unlink_suite_contact_files(self.suite)

        # disconnect from suite-db, stop db queue
        if getattr(self, "db", None) is not None:
            self.pri_dao.close()
            self.pub_dao.close()

        if getattr(self, "config", None) is not None:
            # run shutdown handlers
            self.run_event_handlers(self.EVENT_SHUTDOWN, str(reason))

        OUT.info("DONE")  # main thread exit

    def set_stop_point(self, stop_point_string):
        """Set stop point."""
        stop_point = get_point(stop_point_string)
        self.stop_point = stop_point
        self.log.info("Setting stop cycle point: %s" % stop_point_string)
        self.pool.set_stop_point(self.stop_point)

    def set_stop_clock(self, unix_time, date_time_string):
        """Set stop clock time."""
        self.log.info("Setting stop clock time: %s (unix time: %s)" % (
            date_time_string, unix_time))
        self.stop_clock_time = unix_time
        self.stop_clock_time_string = date_time_string

    def set_stop_task(self, task_id):
        """Set stop after a task."""
        name = TaskID.split(task_id)[0]
        if name in self.config.get_task_name_list():
            task_id = self.get_standardised_taskid(task_id)
            self.log.info("Setting stop task: " + task_id)
            self.stop_task = task_id
        else:
            self.log.warning(
                "Requested stop task name does not exist: %s" % name)

    def stop_task_done(self):
        """Return True if stop task has succeeded."""
        id_ = self.stop_task
        if (id_ is None or not self.pool.task_succeeded(id_)):
            return False
        self.log.info("Stop task " + id_ + " finished")
        return True

    def hold_suite(self, point=None):
        """Hold all tasks in suite."""
        if point is None:
            self.pool.hold_all_tasks()
        else:
            self.log.info("Setting suite hold cycle point: " + str(point))
            self.pool.set_hold_point(point)

    def release_suite(self):
        """Release (un-hold) all tasks in suite."""
        if self.pool.is_held:
            self.log.info("RELEASE: new tasks will be queued when ready")
        self.pool.set_hold_point(None)
        self.pool.release_all_tasks()

    def will_stop_at(self):
        """Return stop point, if set."""
        if self.stop_point:
            return str(self.stop_point)
        elif self.stop_clock_time is not None:
            return self.stop_clock_time_string
        elif self.stop_task:
            return self.stop_task
        elif self.final_point:
            return self.final_point
        else:
            return None

    def clear_stop_times(self):
        """Clear attributes associated with stop time."""
        self.stop_point = None
        self.stop_clock_time = None
        self.stop_clock_time_string = None
        self.stop_task = None

    def paused(self):
        """Is the suite paused?"""
        return self.pool.is_held

    def will_pause_at(self):
        """Return self.pool.get_hold_point()."""
        return self.pool.get_hold_point()

    def command_trigger_tasks(self, items):
        """Trigger tasks."""
        return self.pool.trigger_tasks(items)

    def command_dry_run_tasks(self, items):
        """Dry-run tasks, e.g. edit run."""
        return self.pool.dry_run_task(items)

    def command_reset_task_states(self, items, state=None):
        """Reset the state of tasks."""
        return self.pool.reset_task_states(items, state)

    def command_spawn_tasks(self, items):
        """Force spawn task successors."""
        return self.pool.spawn_tasks(items)

    def command_take_checkpoints(self, items):
        """Insert current task_pool, etc to checkpoints tables."""
        return self.pri_dao.take_checkpoints(
            items[0], other_daos=[self.pub_dao])

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
            time_point = (
                isodatetime.data.get_timepoint_from_seconds_since_unix_epoch(
                    self.stop_clock_time
                )
            )
            self.log.info("Wall clock stop time reached: " + str(time_point))
            self.stop_clock_time = None
            return True
        else:
            return False

    def _copy_pri_db_to_pub_db(self):
        """Copy content of primary database file to public database file.

        Use temporary file to ensure that we do not end up with a partial file.

        """
        temp_pub_db_file_name = None
        self.pub_dao.close()
        try:
            self.pub_dao.conn = None  # reset connection
            open(self.pub_dao.db_file_name, "a").close()  # touch
            st_mode = os.stat(self.pub_dao.db_file_name).st_mode
            temp_pub_db_file_name = mkstemp(
                prefix=self.pub_dao.DB_FILE_BASE_NAME,
                dir=os.path.dirname(self.pub_dao.db_file_name))[1]
            copy(self.pri_dao.db_file_name, temp_pub_db_file_name)
            os.rename(temp_pub_db_file_name, self.pub_dao.db_file_name)
            os.chmod(self.pub_dao.db_file_name, st_mode)
        except (IOError, OSError):
            if temp_pub_db_file_name:
                os.unlink(temp_pub_db_file_name)
            raise

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
            for minute_num in averages.keys():
                if age <= minute_num:
                    averages[minute_num].append(amount)
        output_text = "PROFILE: %s:" % category
        for minute_num, minute_amounts in sorted(averages.items()):
            averages[minute_num] = sum(minute_amounts) / len(minute_amounts)
            output_text += (" %d: " + amount_format) % (
                minute_num, averages[minute_num])
        self.log.info(output_text)

    def _update_cpu_usage(self):
        """Obtain CPU usage statistics."""
        proc = Popen(["ps", "-o%cpu= ", str(os.getpid())], stdout=PIPE)
        try:
            cpu_frac = float(proc.communicate()[0])
        except (TypeError, OSError, IOError, ValueError) as exc:
            self.log.warning("Cannot get CPU % statistics: %s" % exc)
            return
        self._update_profile_info("CPU %", cpu_frac, amount_format="%.1f")

    def _get_cylc_conf(self, key, default=None):
        """Return a named setting under [cylc] from suite.rc or global.rc."""
        for getter in [self.config.cfg['cylc'], GLOBAL_CFG.get(['cylc'])]:
            try:
                value = getter[key]
            except KeyError:
                pass
            else:
                if value is not None:
                    return value
        return default

    def _get_events_conf(self, key, default=None):
        """Return a named [cylc][[events]] configuration."""
        for getter in [
                self.config.cfg['cylc']['events'],
                GLOBAL_CFG.get(['cylc', 'events'])]:
            try:
                value = getter[key]
            except KeyError:
                pass
            else:
                if value is not None:
                    return value
        return default
