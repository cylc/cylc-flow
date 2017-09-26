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

from logging import DEBUG
import os
from Queue import Empty, Queue
from shutil import copytree, rmtree
from subprocess import Popen, PIPE
import sys
from time import sleep, time
import traceback

import isodatetime.data
import isodatetime.parsers
from parsec.util import printcfg

from cylc.cfgspec.globalcfg import GLOBAL_CFG
from cylc.config import SuiteConfig
from cylc.cycling import PointParsingError
from cylc.cycling.loader import get_point, standardise_point_string
from cylc.daemonize import daemonize
from cylc.exceptions import CylcError
import cylc.flags
from cylc.log_diagnosis import LogSpec
from cylc.mp_pool import SuiteProcPool
from cylc.network import PRIVILEGE_LEVELS
from cylc.network.httpserver import HTTPServer
from cylc.state_summary_mgr import StateSummaryMgr
from cylc.suite_db_mgr import SuiteDatabaseManager
from cylc.suite_events import (
    SuiteEventContext, SuiteEventError, SuiteEventHandler)
from cylc.suite_host import get_suite_host, get_user
from cylc.suite_logging import SuiteLog, OUT, ERR, LOG
from cylc.suite_srv_files_mgr import (
    SuiteSrvFilesManager, SuiteServiceFileError)
from cylc.suite_status import (
    KEY_DESCRIPTION, KEY_GROUP, KEY_NAME, KEY_OWNER, KEY_STATES,
    KEY_TASKS_BY_STATE, KEY_TITLE, KEY_UPDATE_TIME)
from cylc.taskdef import TaskDef
from cylc.task_id import TaskID
from cylc.task_job_mgr import TaskJobManager, RemoteJobHostInitError
from cylc.task_pool import TaskPool
from cylc.task_proxy import TaskProxy, TaskProxySequenceBoundsError
from cylc.task_state import TASK_STATUSES_ACTIVE, TASK_STATUS_FAILED
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

    EVENT_STARTUP = SuiteEventHandler.EVENT_STARTUP
    EVENT_SHUTDOWN = SuiteEventHandler.EVENT_SHUTDOWN
    EVENT_TIMEOUT = SuiteEventHandler.EVENT_TIMEOUT
    EVENT_INACTIVITY_TIMEOUT = SuiteEventHandler.EVENT_INACTIVITY_TIMEOUT
    EVENT_STALLED = SuiteEventHandler.EVENT_STALLED

    # Intervals in seconds
    INTERVAL_MAIN_LOOP = 1.0
    INTERVAL_STOP_KILL = 10.0
    INTERVAL_STOP_PROCESS_POOL_EMPTY = 0.5

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
        if self.is_restart:
            self.restart_warm_point = None
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

        self.owner = get_user()
        self.host = get_suite_host()
        self.port = None

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
        self.httpserver = None
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

        self.suite_log = None

        self.ref_test_allowed_failures = []

    def start(self):
        """Start the server."""
        self._start_print_blurb()

        GLOBAL_CFG.create_cylc_run_tree(self.suite)

        if self.is_restart:
            self.suite_db_mgr.restart_upgrade()

        try:
            detach = not (self.options.no_detach or cylc.flags.debug)

            if detach:
                daemonize(self)

            # Setup the suite log.
            slog = SuiteLog.get_inst(self.suite)
            if cylc.flags.debug:
                slog.pimp(detach, DEBUG)
            else:
                slog.pimp(detach)

            self.proc_pool = SuiteProcPool()
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

    def configure(self):
        """Configure suite daemon."""
        self.profiler.log_memory("scheduler.py: start configure")

        # Start up essential services
        self.suite_log = SuiteLog.get_inst(self.suite)
        self.state_summary_mgr = StateSummaryMgr()
        self.command_queue = Queue()
        self.message_queue = Queue()
        self.ext_trigger_queue = Queue()
        self.suite_event_handler = SuiteEventHandler(self.proc_pool)
        self.task_job_mgr = TaskJobManager(
            self.suite, self.proc_pool, self.suite_db_mgr,
            self.suite_srv_files_mgr)
        self.task_events_mgr = self.task_job_mgr.task_events_mgr

        if self.is_restart:
            # This logic handles the lack of initial cycle point in "suite.rc".
            # Things that can't change on suite reload.
            pri_dao = self.suite_db_mgr.get_pri_dao()
            pri_dao.select_suite_params(self._load_initial_cycle_point)
            pri_dao.select_suite_template_vars(self._load_template_vars)
            pri_dao.select_suite_params(self._load_warm_cycle_point)
            # Take checkpoint and commit immediately so that checkpoint can be
            # copied to the public database.
            pri_dao.take_checkpoints("restart")
            pri_dao.execute_queued_items()

        self.profiler.log_memory("scheduler.py: before load_suiterc")
        self.load_suiterc()
        self.profiler.log_memory("scheduler.py: after load_suiterc")
        self.httpserver.connect(self)

        self.suite_db_mgr.on_suite_start(self.is_restart)
        if self.config.cfg['scheduling']['hold after point']:
            self.pool_hold_point = get_point(
                self.config.cfg['scheduling']['hold after point'])

        if self.options.hold_point_string:
            self.pool_hold_point = get_point(
                self.options.hold_point_string)

        if self.pool_hold_point:
            OUT.info("Suite will hold after %s" % self.pool_hold_point)

        reqmode = self.config.cfg['cylc']['required run mode']
        if reqmode:
            if reqmode != self.run_mode:
                raise SchedulerError(
                    'ERROR: this suite requires the %s run mode' % reqmode)

        self.task_events_mgr.broadcast_mgr.linearized_ancestors.update(
            self.config.get_linearized_ancestors())
        self.task_events_mgr.mail_interval = self._get_cylc_conf(
            "task event mail interval")
        self.task_events_mgr.mail_footer = self._get_events_conf("mail footer")
        self.task_events_mgr.suite_url = self.config.cfg['meta']['URL']
        self.task_events_mgr.suite_cfg = self.config.cfg['meta']
        if self.options.genref or self.options.reftest:
            self.configure_reftest()

        LOG.info(self.START_MESSAGE_TMPL % {
            'host': self.host, 'port': self.port, 'pid': os.getpid()})
        # Note that the following lines must be present at the top of
        # the suite log file for use in reference test runs:
        LOG.info('Run mode: ' + self.run_mode)
        LOG.info('Initial point: ' + str(self.initial_point))
        if self.start_point != self.initial_point:
            LOG.info('Start point: ' + str(self.start_point))
        LOG.info('Final point: ' + str(self.final_point))

        self.pool = TaskPool(
            self.config, self.final_point, self.suite_db_mgr,
            self.task_events_mgr)

        self.profiler.log_memory("scheduler.py: before load_tasks")
        if self.is_restart:
            self.load_tasks_for_restart()
        else:
            self.load_tasks_for_run()
        self.profiler.log_memory("scheduler.py: after load_tasks")

        self.suite_db_mgr.put_suite_params(
            self.run_mode,
            self.initial_point,
            self.final_point,
            self.pool.is_held,
            self.config.cfg['cylc']['cycle point format'],
            self._cli_start_point_string)
        self.suite_db_mgr.put_suite_template_vars(self.template_vars)
        self.suite_db_mgr.put_runtime_inheritance(self.config)
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
            self._load_suite_params, self.options.checkpoint)
        if self.restart_warm_point:
            self.start_point = self.restart_warm_point
        self.suite_db_mgr.pri_dao.select_broadcast_states(
            self.task_events_mgr.broadcast_mgr.load_db_broadcast_states,
            self.options.checkpoint)
        self.suite_db_mgr.pri_dao.select_task_job_run_times(
            self._load_task_run_times)
        self.suite_db_mgr.pri_dao.select_task_pool_for_restart(
            self.pool.load_db_task_pool_for_restart, self.options.checkpoint)
        self.suite_db_mgr.pri_dao.select_task_action_timers(
            self.pool.load_db_task_action_timers)
        # Re-initialise run directory for user@host for each submitted and
        # running tasks.
        # Note: tasks should all be in the runahead pool at this point.
        for itask in self.pool.get_rh_tasks():
            if itask.state.status in TASK_STATUSES_ACTIVE:
                try:
                    self.task_job_mgr.init_host(
                        self.suite, itask.task_host, itask.task_owner)
                except RemoteJobHostInitError as exc:
                    LOG.error(str(exc))
        self.command_poll_tasks()

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

    def process_queued_task_messages(self):
        """Handle incoming task messages for each task proxy."""
        task_id_messages = {}
        while self.message_queue.qsize():
            try:
                task_id, priority, message = self.message_queue.get(
                    block=False)
            except Empty:
                break
            self.message_queue.task_done()
            task_id_messages.setdefault(task_id, [])
            task_id_messages[task_id].append((priority, message))
        for itask in self.pool.get_tasks():
            if itask.identity in task_id_messages:
                for priority, message in task_id_messages[itask.identity]:
                    self.task_events_mgr.process_message(
                        itask, priority, message, is_incoming=True)

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
                cylc.flags.iflag = True
                if name in self.PROC_CMDS:
                    self.task_events_mgr.pflag = True
            self.command_queue.task_done()
        OUT.info(log_msg)

    def _task_type_exists(self, name_or_id):
        """Does a task name or id match a known task type in this suite?"""
        name = name_or_id
        if TaskID.is_valid_id(name_or_id):
            name = TaskID.split(name_or_id)[0]
        return name in self.config.get_task_name_list()

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

    def info_get_err_lines(self, prev_size, max_lines):
        """Read content from err log file up to max_lines from prev_size."""
        return self.suite_log.get_lines(
            self.suite_log.ERR, prev_size, max_lines)

    def info_get_update_times(self):
        """Return latest update time of ERR."""
        return (self.state_summary_mgr.summary_update_time, ERR.update_time)

    def info_get_task_jobfile_path(self, task_id):
        """Return task job file path."""
        name, point = TaskID.split(task_id)
        return self.task_events_mgr.get_task_job_log(
            self.suite, point, name, tail=self.task_job_mgr.JOB_FILE_BASE)

    def info_get_state_summary(self):
        """Return the global, task, and family summary data structures."""
        return self.state_summary_mgr.get_state_summary()

    def info_get_suite_info(self):
        """Return a dict containing the suite title and description."""
        return {'title': self.config.cfg['meta']['title'],
                'description': self.config.cfg['meta']['description']}

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
        return self.config.get_first_parent_descendants()

    def info_get_first_parent_ancestors(self, pruned=False):
        """Single-inheritance hierarchy based on first parents"""
        return self.config.get_first_parent_ancestors(pruned)

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

    def info_get_identity(self, privileges):
        """Return suite identity, (description, (states))."""
        result = {}
        if PRIVILEGE_LEVELS[0] in privileges:
            result[KEY_NAME] = self.suite
            result[KEY_OWNER] = self.owner
        if PRIVILEGE_LEVELS[1] in privileges:
            result[KEY_TITLE] = self.config.cfg['meta'][KEY_TITLE]
            result[KEY_DESCRIPTION] = self.config.cfg['meta'][KEY_DESCRIPTION]
            result[KEY_GROUP] = self.config.cfg[KEY_GROUP]
        if PRIVILEGE_LEVELS[2] in privileges:
            result[KEY_UPDATE_TIME] = self.info_get_update_times()[0]
            result[KEY_STATES] = self.state_summary_mgr.get_state_totals()
            result[KEY_TASKS_BY_STATE] = (
                self.state_summary_mgr.get_tasks_by_state())
        return result

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
        self.proc_pool.stop_job_submission()
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

    def command_poll_tasks(self, items=None):
        """Poll all tasks or a task/family if options are provided."""
        if self.run_mode == 'simulation':
            return
        itasks, bad_items = self.pool.filter_task_proxies(items)
        self.task_job_mgr.poll_task_jobs(self.suite, itasks, items is not None)
        return len(bad_items)

    def command_kill_tasks(self, items=None):
        """Kill all tasks or a task/family if options are provided."""
        itasks, bad_items = self.pool.filter_task_proxies(items)
        if self.run_mode == 'simulation':
            for itask in itasks:
                if itask.state.status in TASK_STATUSES_ACTIVE:
                    itask.state.reset_state(TASK_STATUS_FAILED)
            return len(bad_items)
        self.task_job_mgr.kill_task_jobs(self.suite, itasks, items is not None)
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

    def command_set_verbosity(self, lvl):
        """Remove suite verbosity."""
        LOG.logger.setLevel(lvl)
        cylc.flags.debug = (lvl == DEBUG)
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
        self.task_events_mgr.broadcast_mgr.linearized_ancestors = (
            self.config.get_linearized_ancestors())
        self.suite_db_mgr.put_runtime_inheritance(self.config)
        self.pool.set_do_reload(self.config, self.final_point)
        self.task_events_mgr.mail_interval = self._get_cylc_conf(
            "task event mail interval")
        self.task_events_mgr.mail_footer = self._get_events_conf("mail footer")

        # Log tasks that have been added by the reload, removed tasks are
        # logged by the TaskPool.
        add = set(self.config.get_task_name_list()) - old_tasks
        for task in add:
            LOG.warning("Added task: '%s'" % (task,))

        self.configure_suite_environment()
        if self.options.genref or self.options.reftest:
            self.configure_reftest(recon=True)
        self.suite_db_mgr.put_suite_params(
            self.run_mode,
            self.initial_point,
            self.final_point,
            self.pool.is_held,
            self.config.cfg['cylc']['cycle point format'])
        cylc.flags.iflag = True

    def command_set_runahead(self, interval=None):
        """Set runahead limit."""
        if self.pool.set_runahead(interval=interval):
            self.task_events_mgr.pflag = True

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
        self.httpserver = HTTPServer(self.suite)
        self.port = self.httpserver.get_port()
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
            mgr.KEY_VERSION: CYLC_VERSION,
            mgr.KEY_COMMS_PROTOCOL: GLOBAL_CFG.get(
                ['communication', 'method'])}
        try:
            mgr.dump_contact_file(self.suite, contact_data)
        except IOError as exc:
            raise SchedulerError(
                'ERROR, cannot write suite contact file: %s: %s' %
                (mgr.get_contact_file(self.suite), exc))
        else:
            self.contact_data = contact_data

    def load_suiterc(self, is_reload=False):
        """Load and log the suite definition."""
        self.config = SuiteConfig(
            self.suite, self.suiterc, self.template_vars,
            run_mode=self.run_mode,
            cli_initial_point_string=self._cli_initial_point_string,
            cli_start_point_string=self._cli_start_point_string,
            cli_final_point_string=self.options.final_point_string,
            is_reload=is_reload,
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
                handle.write("# cylc-version: %s\n" % CYLC_VERSION)
                printcfg(self.config.cfg, none_str=None, handle=handle)
        except IOError as exc:
            ERR.error(str(exc))
            raise SchedulerError("Unable to log the loaded suite definition")
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

    def _load_initial_cycle_point(self, _, row):
        """Load previous initial cycle point.

        For restart, it may be missing from "suite.rc", but was specified as a
        command line argument on cold/warm start.
        """
        key, value = row
        if key == "initial_point":
            self._cli_initial_point_string = value
            self.task_events_mgr.pflag = True

    def _load_warm_cycle_point(self, _, row):
        """Load previous warm start point on restart"""
        key, value = row
        if key == "warm_point":
            self._cli_start_point_string = value
            self.restart_warm_point = value

    def _load_template_vars(self, _, row):
        """Load suite start up template variables."""
        key, value = row
        # Command line argument takes precedence
        if key not in self.template_vars:
            self.template_vars[key] = value

    def configure_suite_environment(self):
        """Configure suite environment."""
        # Pass static cylc and suite variables to job script generation code
        self.task_job_mgr.job_file_writer.set_suite_env({
            'CYLC_UTC': str(cylc.flags.utc),
            'CYLC_DEBUG': str(cylc.flags.debug),
            'CYLC_VERBOSE': str(cylc.flags.verbose),
            'CYLC_SUITE_NAME': self.suite,
            'CYLC_CYCLING_MODE': str(cylc.flags.cycling_mode),
            'CYLC_SUITE_INITIAL_CYCLE_POINT': str(self.initial_point),
            'CYLC_SUITE_FINAL_CYCLE_POINT': str(self.final_point),
        })

        # Make suite vars available to [cylc][environment]:
        for var, val in self.task_job_mgr.job_file_writer.suite_env.items():
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
        # path to suite bin directory for suite and event handlers
        cenv['PATH'] = os.pathsep.join([
            os.path.join(self.suite_dir, 'bin'), os.environ['PATH']])

        # and to suite event handlers in this process.
        for var, val in cenv.items():
            os.environ[var] = val

    def configure_reftest(self, recon=False):
        """Configure the reference test."""
        if self.options.genref:
            self.config.cfg['cylc']['log resolved dependencies'] = True

        elif self.options.reftest:
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

    def run_event_handlers(self, event, reason):
        """Run a suite event handler.

        Run suite event hooks in simulation and dummy mode ONLY if enabled.
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
                event, reason, self.suite, self.owner, self.host, self.port))
        except SuiteEventError as exc:
            if event == self.EVENT_SHUTDOWN and self.options.reftest:
                ERR.error('SUITE REFERENCE TEST FAILED')
            raise SchedulerError(exc.args[0])
        else:
            if event == self.EVENT_SHUTDOWN and self.options.reftest:
                OUT.info('SUITE REFERENCE TEST PASSED')

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
        self.time_next_fs_check = None
        cylc.flags.iflag = True
        if self.options.profile_mode:
            self.previous_profile_point = 0
            self.count = 0
        self.can_auto_stop = (
            not self.config.cfg['cylc']['disable automatic shutdown'] and
            not self.options.no_auto_shutdown)

    def process_task_pool(self):
        """Process ALL TASKS whenever something has changed that might
        require renegotiation of dependencies, etc"""
        if cylc.flags.debug:
            LOG.debug("BEGIN TASK PROCESSING")
            time0 = time()
        self.pool.match_dependencies()
        if self.stop_mode is None:
            itasks = self.pool.get_ready_tasks()
            if itasks:
                cylc.flags.iflag = True
            if self.config.cfg['cylc']['log resolved dependencies']:
                for itask in itasks:
                    if itask.local_job_file_path:
                        continue
                    deps = itask.state.get_resolved_dependencies()
                    LOG.info('triggered off %s' % deps, itask=itask)

            self.task_job_mgr.submit_task_jobs(
                self.suite, itasks, self.run_mode == 'simulation')
        for meth in [
                self.pool.spawn_all_tasks,
                self.pool.remove_spent_tasks,
                self.pool.remove_suiciding_tasks]:
            if meth():
                cylc.flags.iflag = True

        self.task_events_mgr.broadcast_mgr.expire_broadcast(
            self.pool.get_min_point())
        if cylc.flags.debug:
            LOG.debug("END TASK PROCESSING (took %s seconds)" %
                      (time() - time0))

    def process_queued_task_operations(self):
        try:
            self.suite_db_mgr.process_queued_ops()
        except OSError as err:
            if cylc.flags.debug:
                ERR.debug(traceback.format_exc())
            raise SchedulerError(str(err))

    def database_health_check(self):
        """If public database is stuck, blast it away by copying the content
        of the private database into it."""
        try:
            self.suite_db_mgr.recover_pub_from_pri()
        except (IOError, OSError) as exc:
            # Something has to be very wrong here, so stop the suite
            raise SchedulerError(str(exc))

    def timeout_check(self):
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
                while not self.proc_pool.is_dead():
                    sleep(self.INTERVAL_STOP_PROCESS_POOL_EMPTY)
                    if stop_process_pool_empty_msg:
                        LOG.info(stop_process_pool_empty_msg)
                        OUT.info(stop_process_pool_empty_msg)
                        stop_process_pool_empty_msg = None
                    self.proc_pool.handle_results_async()
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

    def suite_health_check(self, has_changes):
        if self.stop_mode is None and not has_changes:
            self.check_suite_stalled()
        now = time()

        if self.time_next_fs_check is None or now > self.time_next_fs_check:
            if not os.path.exists(self.suite_run_dir):
                raise SchedulerError(
                    "%s: suite run directory not found" % self.suite_run_dir)
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
            self.time_next_fs_check = (
                now + self._get_cylc_conf('health check interval'))

    def update_profiler_logs(self, tinit):
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
                cylc.flags.iflag = True

            self.process_command_queue()
            if self.pool.release_runahead_tasks():
                cylc.flags.iflag = True
                self.task_events_mgr.pflag = True
            self.proc_pool.handle_results_async()

            # PROCESS ALL TASKS whenever something has changed that might
            # require renegotiation of dependencies, etc.
            if self.process_tasks():
                self.process_task_pool()

            self.process_queued_task_messages()
            self.process_command_queue()
            self.task_events_mgr.process_events(self)

            # Update database
            self.suite_db_mgr.put_task_event_timers(self.task_events_mgr)
            has_changes = cylc.flags.iflag
            if cylc.flags.iflag:
                self.suite_db_mgr.put_task_pool(self.pool)
                self.update_state_summary()  # Will reset cylc.flags.iflag

            # Process queued operations for each task proxy
            self.process_queued_task_operations()

            # If public database is stuck, blast it away by copying the content
            # of the private database into it.
            self.database_health_check()

            # Shutdown suite if timeouts have occurred
            self.timeout_check()

            # Does the suite need to shutdown on task failure?
            self.suite_shutdown()

            # Suite health checks
            self.suite_health_check(has_changes)

            if self.options.profile_mode:
                self.update_profiler_logs(tinit)

            sleep(self.INTERVAL_MAIN_LOOP)
            # END MAIN LOOP

    def update_state_summary(self):
        """Update state summary, e.g. for GUI."""
        self.state_summary_mgr.update(self)
        cylc.flags.iflag = False
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

    def process_tasks(self):
        """Return True if waiting tasks are ready."""
        # do we need to do a pass through the main task processing loop?
        process = False

        # External triggers must be matched now. If any are matched pflag
        # is set to tell process_tasks() that task processing is required.
        broadcast_mgr = self.task_events_mgr.broadcast_mgr
        broadcast_mgr.add_ext_triggers(self.ext_trigger_queue)
        for itask in self.pool.get_tasks():
            if (itask.state.external_triggers and
                    broadcast_mgr.match_ext_trigger(itask)):
                process = True

        if self.task_events_mgr.pflag:
            # this flag is turned on by commands that change task state
            process = True
            self.task_events_mgr.pflag = False  # reset

        self.pool.set_expired_tasks()
        if self.pool.waiting_tasks_ready():
            process = True

        if self.run_mode == 'simulation' and self.pool.sim_time_check(
                self.message_queue):
            process = True

        if (process and
                self._get_events_conf(self.EVENT_INACTIVITY_TIMEOUT) and
                self._get_events_conf('reset inactivity timer')):
            self.set_suite_inactivity_timer()

        return process

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
        LOG.info(msg)

        if self.options.genref:
            try:
                handle = open(
                    os.path.join(self.config.fdir, 'reference.log'), 'wb')
                for line in open(self.suite_log.get_log_path(SuiteLog.LOG)):
                    if any(text in line for text in self.REF_LOG_TEXTS):
                        handle.write(line)
                handle.close()
            except IOError as exc:
                ERR.error(str(exc))

        if self.proc_pool:
            if not self.proc_pool.is_dead():
                # e.g. KeyboardInterrupt
                self.proc_pool.terminate()
            self.proc_pool.join()
            self.proc_pool.handle_results_async()

        if self.pool is not None:
            self.pool.warn_stop_orphans()
            try:
                self.suite_db_mgr.put_task_event_timers(self.task_events_mgr)
                self.suite_db_mgr.put_task_pool(self.pool)
            except Exception as exc:
                ERR.error(str(exc))

        if self.httpserver:
            self.httpserver.shutdown()

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
            if self.task_job_mgr:
                self.task_job_mgr.unlink_hosts_contacts(self.suite)

        # disconnect from suite-db, stop db queue
        try:
            self.suite_db_mgr.process_queued_ops()
            self.suite_db_mgr.on_suite_shutdown()
        except StandardError as exc:
            ERR.error(str(exc))

        if getattr(self, "config", None) is not None:
            # run shutdown handlers
            self.run_event_handlers(self.EVENT_SHUTDOWN, str(reason))

        OUT.info("DONE")  # main thread exit

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

    def clear_stop_times(self):
        """Clear attributes associated with stop time."""
        self.stop_point = None
        self.stop_clock_time = None
        self.stop_clock_time_string = None
        self.stop_task = None

    def paused(self):
        """Is the suite paused?"""
        return self.pool.is_held

    def command_trigger_tasks(self, items):
        """Trigger tasks."""
        return self.pool.trigger_tasks(items)

    def command_dry_run_tasks(self, items):
        """Dry-run tasks, e.g. edit run."""
        itasks, bad_items = self.pool.filter_task_proxies(items)
        n_warnings = len(bad_items)
        if len(itasks) > 1:
            LOG.warning("Unique task match not found: %s" % items)
            return n_warnings + 1
        if self.task_job_mgr.prep_submit_task_jobs(
                self.suite, [itasks[0]], dry_run=True):
            return n_warnings
        else:
            return n_warnings + 1

    def command_reset_task_states(self, items, state=None, outputs=None):
        """Reset the state of tasks."""
        return self.pool.reset_task_states(items, state, outputs)

    def command_spawn_tasks(self, items):
        """Force spawn task successors."""
        return self.pool.spawn_tasks(items)

    def command_take_checkpoints(self, items):
        """Insert current task_pool, etc to checkpoints tables."""
        return self.suite_db_mgr.checkpoint(items[0])

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
            LOG.info("Wall clock stop time reached: %s" % time_point)
            self.stop_clock_time = None
            return True
        else:
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
            for minute_num in averages.keys():
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
        proc = Popen(["ps", "-o%cpu= ", str(os.getpid())], stdout=PIPE)
        try:
            cpu_frac = float(proc.communicate()[0])
        except (TypeError, OSError, IOError, ValueError) as exc:
            LOG.warning("Cannot get CPU % statistics: %s" % exc)
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
        return self.suite_event_handler.get_events_conf(
            self.config, key, default)
