#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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

from copy import copy, deepcopy
import logging
import os
from pipes import quote
from Queue import Empty
from shutil import copy as copyfile, copytree, rmtree
import signal
from subprocess import call, Popen, PIPE
import sys
from tempfile import mkstemp
import threading
import time
import traceback

import isodatetime.data
import isodatetime.parsers
from parsec.util import printcfg

from cylc.broadcast_report import (
    CHANGE_FMT as BROADCAST_LOAD_FMT,
    CHANGE_PREFIX_SET as BROADCAST_LOAD_PREFIX)
from cylc.cfgspec.globalcfg import GLOBAL_CFG
from cylc.config import SuiteConfig, TaskNotDefinedError
from cylc.cycling import PointParsingError
from cylc.cycling.loader import get_point, standardise_point_string
from cylc.daemonize import daemonize, SUITE_SCAN_INFO_TMPL
from cylc.exceptions import CylcError
import cylc.flags
from cylc.get_task_proxy import get_task_proxy
from cylc.job_file import JobFile
from cylc.job_host import RemoteJobHostManager, RemoteJobHostInitError
from cylc.log_diagnosis import LogSpec
from cylc.mp_pool import SuiteProcContext, SuiteProcPool
from cylc.network import (
    PYRO_SUITEID_OBJ_NAME, PYRO_STATE_OBJ_NAME,
    PYRO_CMD_OBJ_NAME, PYRO_BCAST_OBJ_NAME, PYRO_EXT_TRIG_OBJ_NAME,
    PYRO_INFO_OBJ_NAME, PYRO_LOG_OBJ_NAME)
from cylc.network.ext_trigger import ExtTriggerServer
from cylc.network.pyro_daemon import PyroDaemon
from cylc.network.suite_broadcast import BroadcastServer
from cylc.network.suite_command import SuiteCommandServer
from cylc.network.suite_identifier import SuiteIdServer
from cylc.network.suite_info import SuiteInfoServer
from cylc.network.suite_log import SuiteLogServer
from cylc.network.suite_state import StateSummaryServer
from cylc.owner import USER
from cylc.registration import RegistrationDB
from cylc.regpath import RegPath
from cylc.rundb import CylcSuiteDAO
from cylc.suite_env import CylcSuiteEnv
from cylc.suite_host import get_suite_host
from cylc.suite_logging import suite_log
from cylc.task_id import TaskID
from cylc.task_pool import TaskPool
from cylc.task_proxy import TaskProxy, TaskProxySequenceBoundsError
from cylc.task_state import (
    TASK_STATUS_HELD, TASK_STATUS_WAITING,
    TASK_STATUS_QUEUED, TASK_STATUS_READY, TASK_STATUS_SUBMITTED,
    TASK_STATUS_SUBMIT_FAILED, TASK_STATUS_SUBMIT_RETRYING,
    TASK_STATUS_RUNNING, TASK_STATUS_SUCCEEDED, TASK_STATUS_FAILED,
    TASK_STATUS_RETRYING)
from cylc.version import CYLC_VERSION
from cylc.wallclock import (
    get_current_time_string, get_seconds_as_interval_string)


class SchedulerError(CylcError):
    """Scheduler error."""
    pass


class SchedulerStop(CylcError):
    """Scheduler has stopped."""
    pass


class PyroRequestHandler(threading.Thread):
    """Pyro request handler."""

    def __init__(self, pyro):
        threading.Thread.__init__(self)
        self.pyro = pyro
        self.quit = False
        self.log = logging.getLogger('main')
        self.log.debug("request handling thread starting")

    def run(self):
        while True:
            self.pyro.handle_requests(timeout=1)
            if self.quit:
                break
        self.log.debug("request handling thread exiting")


class Scheduler(object):
    """Cylc scheduler server."""

    EVENT_STARTUP = 'startup'
    EVENT_SHUTDOWN = 'shutdown'
    EVENT_TIMEOUT = 'timeout'
    EVENT_INACTIVITY_TIMEOUT = 'inactivity'
    EVENT_STALLED = 'stalled'
    SUITE_EVENT_HANDLER = 'suite-event-handler'
    SUITE_EVENT_MAIL = 'suite-event-mail'
    FS_CHECK_PERIOD = 600.0  # 600 seconds

    # Dependency negotation etc. will run after these commands
    PROC_CMDS = (
        'release_suite',
        'release_task',
        'kill_tasks',
        'set_runahead',
        'reset_task_state',
        'spawn_tasks',
        'trigger_task',
        'nudge',
        'insert_task',
        'reload_suite')

    def __init__(self, is_restart, options, args):

        self.options = options
        self.suite = args[0]
        self.suiterc = RegistrationDB(self.options.db).get_suiterc(self.suite)
        self.suite_dir = os.path.dirname(self.suiterc)
        # For user-defined job submission methods:
        sys.path.append(os.path.join(self.suite_dir, 'python'))

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

        self.run_mode = self.options.run_mode

        # For persistence of reference test settings across reloads:
        self.reference_test_mode = self.options.reftest
        self.gen_reference_log = self.options.genref

        self.owner = USER
        self.host = get_suite_host()
        self.port = None
        self.port_file = None

        self.is_stalled = False
        self.stalled_last = False

        self.graph_warned = {}

        self.suite_env = {}
        self.suite_task_env = {}
        self.suite_env_dumper = None

        self.do_process_tasks = False
        self.do_update_state_summary = True

        # initialize some items in case of early shutdown
        # (required in the shutdown() method)
        self.suite_state = None
        self.command_queue = None
        self.pool = None
        self.request_handler = None
        self.pyro = None

        self._profile_amounts = {}
        self._profile_update_times = {}

        self.shut_down_cleanly = False
        self.shut_down_now = False

        # TODO - stop task should be held by the task pool.
        self.stop_task = None
        self.stop_point = None
        self.stop_clock_time = None  # When not None, in Unix time
        self.stop_clock_time_string = None  # Human-readable format.

        self.initial_point = None
        self.start_point = None
        self.final_point = None
        self.pool_hold_point = None
        self.hold_suite_now = False
        self.suite_timer_timeout = 0.0
        self.suite_timer_active = False

        self.next_kill_issue = None
        self.already_timed_out = False
        self.kill_on_shutdown = False

        self.pri_dao = None
        self.pub_dao = None

        self.suite_log = None
        self.log = None

        # FIXME: can this be a local variable?
        self.old_user_at_host_set = set()

        self.ref_test_allowed_failures = []

    def start(self):
        """Start the server."""
        self._check_port_file_does_not_exist(self.suite)
        self._print_blurb()

        GLOBAL_CFG.create_cylc_run_tree(self.suite)

        if self.is_restart:
            run_dir = GLOBAL_CFG.get_derived_host_item(
                self.suite, 'suite run directory')
            pri_db_path = os.path.join(
                run_dir, CylcSuiteDAO.PRI_DB_FILE_BASE_NAME)

            # Backward compat, upgrade database with state file if necessary
            old_pri_db_path = os.path.join(
                run_dir, 'state', CylcSuiteDAO.DB_FILE_BASE_NAME)
            old_state_file_path = os.path.join(run_dir, "state", "state")
            if (os.path.exists(old_pri_db_path) and
                    os.path.exists(old_state_file_path) and
                    not os.path.exists(pri_db_path)):
                copyfile(old_pri_db_path, pri_db_path)
                pri_dao = CylcSuiteDAO(pri_db_path)
                pri_dao.upgrade_with_state_file(old_state_file_path)
                target = os.path.join(run_dir, "state.tar.gz")
                cmd = ["tar", "-C", run_dir, "-czf", target, "state"]
                if call(cmd) == 0:
                    rmtree(os.path.join(run_dir, "state"), ignore_errors=True)
                else:
                    try:
                        os.unlink(os.path.join(run_dir, "state.tar.gz"))
                    except OSError:
                        pass
                    print >> sys.stderr, (
                        "ERROR: cannot tar-gzip + remove old state/ directory")
            else:
                pri_dao = CylcSuiteDAO(pri_db_path)

            # Vacuum the primary/private database file
            sys.stdout.write("Vacuuming the suite db ...")
            pri_dao.vacuum()
            sys.stdout.write(" done\n")
            pri_dao.close()

        try:
            self._configure_pyro()
            if not self.options.no_detach and not cylc.flags.debug:
                daemonize(self)
            self.configure()
            if self.options.profile_mode:
                import cProfile
                import pstats
                prof = cProfile.Profile()
                prof.enable()
            self.run()
        except SchedulerStop as exc:
            # deliberate stop
            print str(exc)
            self.shutdown()

        except SchedulerError as exc:
            print >> sys.stderr, str(exc)
            self.shutdown()
            sys.exit(1)

        except KeyboardInterrupt as exc:
            try:
                self.shutdown(str(exc))
            except Exception as exc1:
                # In case of exceptions in the shutdown method itself.
                traceback.print_exc(exc1)
                sys.exit(1)

        except Exception as exc:
            traceback.print_exc()
            print >> sys.stderr, "ERROR CAUGHT: cleaning up before exit"
            try:
                self.shutdown('ERROR: ' + str(exc))
            except Exception, exc1:
                # In case of exceptions in the shutdown method itself
                traceback.print_exc(exc1)
            if cylc.flags.debug:
                raise
            else:
                sys.exit(1)

        else:
            # main loop ends (not used?)
            self.shutdown()

        if self.options.profile_mode:
            prof.disable()
            import StringIO
            string_stream = StringIO.StringIO()
            stats = pstats.Stats(prof, stream=string_stream)
            stats.sort_stats('cumulative')
            stats.print_stats()
            print string_stream.getvalue()
        print

    @staticmethod
    def _check_port_file_does_not_exist(suite):
        """Fail if port file exists. Return port file path otherwise."""
        port_file_path = os.path.join(
            GLOBAL_CFG.get(['pyro', 'ports directory']), suite)
        try:
            port, host = open(port_file_path).read().splitlines()
        except (IOError, ValueError):
            # Suite is not likely to be running if port file does not exist
            # or if port file does not contain good values of port and host.
            return port_file_path
        else:
            sys.stderr.write(
                (
                    r"""ERROR: port file exists: %(port_file_path)s

If %(suite)s is not running, delete the port file and try again.  If it is
running but not responsive, kill any left over suite processes too.""" +
                    SUITE_SCAN_INFO_TMPL
                ) % {
                    "host": host,
                    "port": port,
                    "port_file_path": port_file_path,
                    "suite": suite,
                }
            )
            raise SchedulerError(
                "ERROR, port file exists: %s" % port_file_path)

    @staticmethod
    def _print_blurb():
        """Print copyright and license information."""
        logo = (
            "            ,_,       \n"
            "            | |       \n"
            ",_____,_, ,_| |_____, \n"
            "| ,___| | | | | ,___| \n"
            "| |___| |_| | | |___, \n"
            "\_____\___, |_\_____| \n"
            "      ,___| |         \n"
            "      \_____|         \n"
        )
        cylc_license = """
The Cylc Suite Engine [%s]
Copyright (C) 2008-2016 NIWA
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
        print

    def _configure_pyro(self):
        """Create and configure Pyro daemon."""
        self.pyro = PyroDaemon(self.suite, self.suite_dir)
        self.port = self.pyro.get_port()
        port_file_path = self._check_port_file_does_not_exist(self.suite)
        try:
            with open(port_file_path, 'w') as handle:
                handle.write("%d\n%s\n" % (self.port, self.host))
        except IOError as exc:
            sys.stderr.write(str(exc) + "\n")
            raise SchedulerError(
                'ERROR, cannot write port file: %s' % port_file_path)
        else:
            self.port_file = port_file_path

    def configure(self):
        """Configure suite daemon."""
        self.log_memory("scheduler.py: start configure")
        SuiteProcPool.get_inst()

        self.log_memory("scheduler.py: before configure_suite")
        self.configure_suite()
        self.log_memory("scheduler.py: after configure_suite")

        reqmode = self.config.cfg['cylc']['required run mode']
        if reqmode:
            if reqmode != self.run_mode:
                raise SchedulerError(
                    'ERROR: this suite requires the %s run mode' % reqmode)

        if self.gen_reference_log or self.reference_test_mode:
            self.configure_reftest()

        self.log.info('Suite starting on %s:%s' % (self.host, self.port))
        # Note that the following lines must be present at the top of
        # the suite log file for use in reference test runs:
        self.log.info('Run mode: ' + self.run_mode)
        self.log.info('Initial point: ' + str(self.initial_point))
        if self.start_point != self.initial_point:
            self.log.info('Start point: ' + str(self.start_point))
        self.log.info('Final point: ' + str(self.final_point))

        self.pool = TaskPool(
            self.suite, self.pri_dao, self.pub_dao, self.final_point,
            self.pyro, self.log, self.run_mode)
        self.request_handler = PyroRequestHandler(self.pyro)
        self.request_handler.start()

        self.log_memory("scheduler.py: before load_tasks")
        if self.is_restart:
            self.load_tasks_for_restart()
        else:
            self.load_tasks_for_run()
        self.log_memory("scheduler.py: after load_tasks")

        self.pool.put_rundb_suite_params(self.initial_point, self.final_point)
        self.configure_suite_environment()

        # Write suite contact environment file
        suite_run_dir = GLOBAL_CFG.get_derived_host_item(
            self.suite, 'suite run directory')
        self.suite_env_dumper.dump(suite_run_dir)

        # Copy local python modules from source to run directory
        for sub_dir in ["python", os.path.join("lib", "python")]:
            # TODO - eventually drop the deprecated "python" sub-dir.
            suite_py = os.path.join(self.suite_dir, sub_dir)
            if (os.path.realpath(self.suite_dir) !=
                    os.path.realpath(suite_run_dir) and
                    os.path.isdir(suite_py)):
                suite_run_py = os.path.join(suite_run_dir, sub_dir)
                try:
                    rmtree(suite_run_py)
                except OSError:
                    pass
                copytree(suite_py, suite_run_py)

        # 2) restart only: copy to other accounts with still-running tasks
        for user_at_host in self.old_user_at_host_set:
            try:
                RemoteJobHostManager.get_inst().init_suite_run_dir(
                    self.suite, user_at_host)
            except RemoteJobHostInitError as exc:
                self.log.error(str(exc))
        self.old_user_at_host_set.clear()

        self.already_timed_out = False
        if self._get_events_conf(self.EVENT_TIMEOUT):
            self.set_suite_timer()

        # self.nudge_timer_start = None
        # self.nudge_timer_on = False
        # self.auto_nudge_interval = 5  # seconds

        self.already_inactive = False
        if self._get_events_conf(self.EVENT_INACTIVITY_TIMEOUT):
            self.set_suite_inactivity_timer()

        self.log_memory("scheduler.py: end configure")

    def load_tasks_for_run(self):
        """Load tasks for a new run."""
        if self.start_point is not None:
            if self.options.warm:
                self.log.info('Warm Start %s' % self.start_point)
            else:
                self.log.info('Cold Start %s' % self.start_point)

        task_list = self.filter_initial_task_list(
            self.config.get_task_name_list())
        coldstart_tasks = self.config.get_coldstart_task_list()

        for name in task_list:
            if self.start_point is None:
                # No start cycle point at which to load cycling tasks.
                continue
            try:
                itask = get_task_proxy(
                    name, self.start_point, is_startup=True,
                    message_queue=self.pool.message_queue)
            except TaskProxySequenceBoundsError as exc:
                self.log.debug(str(exc))
                continue
            if name in coldstart_tasks and self.options.warm:
                itask.state.set_state(TASK_STATUS_SUCCEEDED)
                itask.state.set_prerequisites_all_satisfied()
                itask.state.outputs.set_all_completed()
            # Load task.
            self.pool.add_to_runahead_pool(itask)

    def load_tasks_for_restart(self):
        """Load tasks for restart."""
        self.pri_dao.select_suite_params(self._load_suite_params)
        self.pri_dao.select_broadcast_states(self._load_broadcast_states)
        self.pri_dao.select_task_pool_for_restart(self._load_task_pool)
        self.pool.poll_task_jobs()

    def _load_broadcast_states(self, row_idx, row):
        """Load a setting in the previous broadcast states."""
        if row_idx == 0:
            print "LOADING broadcast states"
        point, namespace, key, value = row
        BroadcastServer.get_inst().load_state(point, namespace, key, value)
        print BROADCAST_LOAD_FMT.strip() % {
            "change": BROADCAST_LOAD_PREFIX,
            "point": point,
            "namespace": namespace,
            "key": key,
            "value": value}

    def _load_suite_params(self, row_idx, row):
        """Load previous initial/final cycle point."""
        if row_idx == 0:
            print "LOADING suite parameters"
        key, value = row
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
                    print >> sys.stderr, (
                        "WARNING: I'm ignoring the old " + key_str +
                        " cycle point as requested,\n"
                        "but I can't ignore the one set"
                        " on the command line or in the suite definition.")
            elif my_point is not None:
                # Given in the suite.rc file
                if my_point != point:
                    print >> sys.stderr, (
                        "WARNING: old %s cycle point " +
                        "%s, overriding suite.rc %s"
                    ) % (key_str, point, my_point)
                    setattr(self, self_attr, point)
            else:
                # reinstate from old
                setattr(self, self_attr, point)
            print "+ %s cycle point = %s" % (key_str, value)

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
            print "LOADING task proxies"
        cycle, name, spawned, status, submit_num, try_num, user_at_host = row
        try:
            itask = get_task_proxy(
                name,
                get_point(cycle),
                status,
                bool(spawned),
                submit_num=submit_num,
                is_reload_or_restart=True,
                message_queue=self.pool.message_queue)
        except TaskNotDefinedError as exc:
            if cylc.flags.debug:
                traceback.print_exc()
            else:
                print >> sys.stderr, str(exc)
            print >> sys.stderr, (
                "WARNING: ignoring task %s " % name +
                "from the suite run database file")
            print >> sys.stderr, (
                "(the task definition has probably been "
                "deleted from the suite).")
        except Exception:
            traceback.print_exc()
            print >> sys.stderr, (
                "ERROR: could not load task %s " % name)
        else:
            if status == TASK_STATUS_HELD:
                # Only waiting tasks get held. These need to be released
                # on restart to avoid the automatic shutdown criterion:
                # if all tasks are succeeded or held (e.g. because they
                # passed the final cycle point) shut down automatically.
                itask.state.set_state(TASK_STATUS_WAITING)

            elif status in (TASK_STATUS_SUBMITTED, TASK_STATUS_RUNNING):
                itask.state.set_prerequisites_all_satisfied()
                # update the task proxy with submit ID etc.
                itask.try_number = try_num
                itask.user_at_host = user_at_host
                self.old_user_at_host_set.add(itask.user_at_host)
                if itask.user_at_host is None:
                    itask.user_at_host = "localhost"
                # update timers in case regular polling is configured for itask
                if '@' in itask.user_at_host:
                    host = itask.user_at_host.split('@', 1)[1]
                else:
                    host = itask.user_at_host
                itask.submission_poll_timer.set_host(host, set_timer=True)
                itask.execution_poll_timer.set_host(host, set_timer=True)

            elif status in (TASK_STATUS_SUBMIT_FAILED, TASK_STATUS_FAILED):
                itask.state.set_prerequisites_all_satisfied()

            elif status in (
                    TASK_STATUS_QUEUED,
                    TASK_STATUS_READY,
                    TASK_STATUS_SUBMIT_RETRYING,
                    TASK_STATUS_RETRYING):
                itask.state.set_prerequisites_all_satisfied()
                # reset to waiting as these had not been submitted yet.
                itask.state.set_state('waiting')

            elif itask.state.status == TASK_STATUS_SUCCEEDED:
                itask.state.set_prerequisites_all_satisfied()
                # TODO - just poll for outputs in the job status file.
                itask.state.outputs.set_all_completed()

            itask.summary['job_hosts'][int(submit_num)] = user_at_host
            print "+ %s.%s %s" % (name, cycle, status)
            self.pool.add_to_runahead_pool(itask)

    def process_command_queue(self):
        """Process queued commands."""
        queue = self.command_queue.get_queue()
        qsize = queue.qsize()
        if qsize > 0:
            print 'Processing ' + str(qsize) + ' queued command(s)'
        else:
            return

        while True:
            try:
                name, args = queue.get(False)
            except Empty:
                break
            print '  +', name
            cmdstr = name + '(' + ','.join([str(a) for a in args]) + ')'
            try:
                n_warnings = getattr(self, "command_%s" % name)(*args)
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

    def info_get_task_info(self, name):
        """Return info of a task."""
        try:
            return self.config.describe(name)
        except KeyError:
            return {}

    def info_get_all_families(self, exclude_root=False):
        """Return info of all families."""
        fams = self.config.get_first_parent_descendants().keys()
        if exclude_root:
            return fams[:-1]
        else:
            return fams

    def info_get_triggering_families(self):
        """Return info of triggering families."""
        return self.config.triggering_families

    def info_get_first_parent_descendants(self):
        """Families for single-inheritance hierarchy based on first parents"""
        return deepcopy(self.config.get_first_parent_descendants())

    def info_get_first_parent_ancestors(self, pruned=False):
        """Single-inheritance hierarchy based on first parents"""
        return deepcopy(self.config.get_first_parent_ancestors(pruned))

    def info_get_graph_raw(self, cto, ctn, group_nodes, ungroup_nodes,
                           ungroup_recursive, group_all, ungroup_all):
        """Return raw graph."""
        rgraph = self.config.get_graph_raw(
            cto, ctn, group_nodes, ungroup_nodes, ungroup_recursive, group_all,
            ungroup_all)
        return (
            rgraph, self.config.suite_polling_tasks, self.config.leaves,
            self.config.feet)

    def info_get_task_requisites(self, name, point_string):
        """Return prerequisites of a task."""
        return self.pool.get_task_requisites(
            TaskID.get(name, self.get_standardised_point_string(point_string)))

    def command_set_stop_cleanly(self, kill_active_tasks=False):
        """Stop job submission and set the flag for clean shutdown."""
        SuiteProcPool.get_inst().stop_job_submission()
        TaskProxy.stop_sim_mode_job_submission = True
        self.shut_down_cleanly = True
        self.kill_on_shutdown = kill_active_tasks
        self.next_kill_issue = time.time()

    def command_stop_now(self):
        """Shutdown immediately."""
        proc_pool = SuiteProcPool.get_inst()
        proc_pool.stop_job_submission()
        TaskProxy.stop_sim_mode_job_submission = True
        proc_pool.terminate()
        raise SchedulerStop("Stopping NOW")

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

    def command_release_task(self, items, compat=None, _=None):
        """Release tasks."""
        return self.pool.release_tasks(items, compat)

    def command_poll_tasks(self, items, compat=None, _=None):
        """Poll all tasks or a task/family if options are provided."""
        return self.pool.poll_task_jobs(items, compat)

    def command_kill_tasks(self, items, compat=None, _=False):
        """Kill all tasks or a task/family if options are provided."""
        return self.pool.kill_task_jobs(items, compat)

    def command_release_suite(self):
        """Release all task proxies in the suite."""
        self.release_suite()

    def command_hold_task(self, items, compat=None, _=False):
        """Hold selected task proxies in the suite."""
        return self.pool.hold_tasks(items, compat)

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
        self.log.setLevel(lvl)
        cylc.flags.debug = (lvl == logging.DEBUG)
        return True, 'OK'

    def command_remove_cycle(self, point_string, spawn=False):
        """Remove tasks in a cycle."""
        return self.pool.remove_tasks(point_string + "/*", spawn)

    def command_remove_task(self, items, compat=None, _=None, spawn=False):
        """Remove tasks."""
        return self.pool.remove_tasks(items, spawn, compat)

    def command_insert_task(
            self, items, compat=None, _=None, stop_point_string=None):
        """Insert tasks."""
        return self.pool.insert_tasks(items, stop_point_string, compat)

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
            logging.getLogger("main").log(
                logging.WARNING, "Added task: '%s'" % (task,))

        self.configure_suite_environment()
        if self.gen_reference_log or self.reference_test_mode:
            self.configure_reftest(recon=True)
        self.pool.put_rundb_suite_params(self.initial_point, self.final_point)
        self.do_update_state_summary = True

    def command_set_runahead(self, *args):
        """Set runahead limit."""
        self.pool.set_runahead(*args)

    def set_suite_timer(self):
        """Set suite's timeout timer."""
        self.suite_timer_timeout = time.time() + (
            self._get_events_conf(self.EVENT_TIMEOUT)
        )
        if cylc.flags.verbose:
            print "%s suite timer starts NOW: %s" % (
                get_seconds_as_interval_string(
                    self._get_events_conf(self.EVENT_TIMEOUT)),
                get_current_time_string())
        self.suite_timer_active = True

    def set_suite_inactivity_timer(self, reset=False):
        """Set suite's inactivity timer."""
        self.suite_inactivity_timeout = time.time() + (
            self._get_events_conf(self.EVENT_INACTIVITY_TIMEOUT)
        )
        if cylc.flags.verbose:
            print "%s suite inactivity timer starts NOW: %s" % (
                get_seconds_as_interval_string(
                    self._get_events_conf(self.EVENT_INACTIVITY_TIMEOUT)),
                get_current_time_string())

    def load_suiterc(self, reconfigure):
        """Load and log the suite definition."""

        SuiteConfig._FORCE = True  # Reset the singleton!
        self.config = SuiteConfig.get_inst(
            self.suite, self.suiterc,
            self.options.templatevars,
            self.options.templatevars_file, run_mode=self.run_mode,
            cli_initial_point_string=self._cli_initial_point_string,
            cli_start_point_string=self._cli_start_point_string,
            cli_final_point_string=self.options.final_point_string,
            is_restart=self.is_restart, is_reload=reconfigure,
            mem_log_func=self.log_memory
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
            handle = open(file_name, "wb")
        except IOError as exc:
            sys.stderr.write(str(exc) + "\n")
            raise SchedulerError("Unable to log the loaded suite definition")
        handle.write("# cylc-version: %s\n" % CYLC_VERSION)
        printcfg(self.config.cfg, handle=handle)
        handle.close()

    def _load_initial_cycle_point(self, _, row):
        """Load previous initial cycle point.

        For restart, it may be missing from "suite.rc", but was specified as a
        command line argument on cold/warm start.
        """
        key, value = row
        if key == "initial_point":
            self._cli_initial_point_string = value
            self.do_process_tasks = True

    def configure_suite(self, reconfigure=False):
        """Load and process the suite definition."""

        if reconfigure:
            self.pri_dao.take_checkpoints(
                "reload-init", other_daos=[self.pub_dao])
        elif self.is_restart:
            # This logic handles the lack of initial cycle point in "suite.rc".
            # Things that can't change on suite reload.
            run_dir = GLOBAL_CFG.get_derived_host_item(
                self.suite, 'suite run directory')
            pri_db_path = os.path.join(
                run_dir, CylcSuiteDAO.PRI_DB_FILE_BASE_NAME)
            self.pri_dao = CylcSuiteDAO(pri_db_path)
            self.pri_dao.select_suite_params(self._load_initial_cycle_point)
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

        if (not self.initial_point and not self.is_restart):
            sys.stderr.write(
                'WARNING: No initial cycle point provided ' +
                ' - no cycling tasks will be loaded.\n')

        if self.run_mode != self.config.run_mode:
            self.run_mode = self.config.run_mode

        if reconfigure:
            BroadcastServer.get_inst().linearized_ancestors = (
                self.config.get_linearized_ancestors())
        else:
            # Things that can't change on suite reload.
            run_dir = GLOBAL_CFG.get_derived_host_item(
                self.suite, 'suite run directory')
            pri_db_path = os.path.join(
                run_dir, CylcSuiteDAO.PRI_DB_FILE_BASE_NAME)
            pub_db_path = os.path.join(
                run_dir, CylcSuiteDAO.PUB_DB_FILE_BASE_NAME)
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
                run_dir, CylcSuiteDAO.DB_FILE_BASE_NAME)
            try:
                source = os.readlink(pub_db_path_symlink)
            except OSError:
                source = None
            if source != CylcSuiteDAO.PUB_DB_FILE_BASE_NAME:
                try:
                    os.unlink(pub_db_path_symlink)
                except OSError:
                    pass
                os.symlink(
                    CylcSuiteDAO.PUB_DB_FILE_BASE_NAME, pub_db_path_symlink)

            if self.config.cfg['scheduling']['hold after point']:
                self.pool_hold_point = get_point(
                    self.config.cfg['scheduling']['hold after point'])

            if self.options.hold_point_string:
                self.pool_hold_point = get_point(
                    self.options.hold_point_string)

            if self.pool_hold_point:
                print "Suite will hold after " + str(self.pool_hold_point)

            suite_id = SuiteIdServer.get_inst(self.suite, self.owner)
            self.pyro.connect(suite_id, PYRO_SUITEID_OBJ_NAME)

            bcast = BroadcastServer.get_inst(
                self.config.get_linearized_ancestors())
            self.pyro.connect(bcast, PYRO_BCAST_OBJ_NAME)

            self.command_queue = SuiteCommandServer()
            self.pyro.connect(self.command_queue, PYRO_CMD_OBJ_NAME)

            ets = ExtTriggerServer.get_inst()
            self.pyro.connect(ets, PYRO_EXT_TRIG_OBJ_NAME)

            info_commands = {}
            for attr_name in dir(self):
                attr = getattr(self, attr_name)
                if callable(attr) and attr_name.startswith('info_'):
                    info_commands[attr_name.replace('info_', '')] = attr
            self.pyro.connect(
                SuiteInfoServer(info_commands), PYRO_INFO_OBJ_NAME)

            self.suite_log = suite_log(self.suite)
            self.log = self.suite_log.get_log()
            if cylc.flags.debug:
                self.suite_log.pimp(logging.DEBUG)
            else:
                self.suite_log.pimp(logging.INFO)
            self.pyro.connect(
                SuiteLogServer(self.suite_log), PYRO_LOG_OBJ_NAME)

            self.suite_state = StateSummaryServer.get_inst(self.run_mode)
            self.pyro.connect(self.suite_state, PYRO_STATE_OBJ_NAME)

    def configure_suite_environment(self):
        """Configure suite environment."""
        # static cylc and suite-specific variables:
        self.suite_env = {
            'CYLC_UTC': str(cylc.flags.utc),
            'CYLC_CYCLING_MODE': str(cylc.flags.cycling_mode),
            'CYLC_MODE': 'scheduler',
            'CYLC_DEBUG': str(cylc.flags.debug),
            'CYLC_VERBOSE': str(cylc.flags.verbose),
            'CYLC_DIR_ON_SUITE_HOST': os.environ['CYLC_DIR'],
            'CYLC_SUITE_NAME': self.suite,
            'CYLC_SUITE_REG_NAME': self.suite,  # DEPRECATED
            'CYLC_SUITE_HOST': str(self.host),
            'CYLC_SUITE_OWNER': self.owner,
            'CYLC_SUITE_PORT': str(self.pyro.get_port()),
            # DEPRECATED
            'CYLC_SUITE_REG_PATH': RegPath(self.suite).get_fpath(),
            'CYLC_SUITE_DEF_PATH_ON_SUITE_HOST': self.suite_dir,
            # may be "None"
            'CYLC_SUITE_INITIAL_CYCLE_POINT': str(self.initial_point),
            # may be "None"
            'CYLC_SUITE_FINAL_CYCLE_POINT': str(self.final_point),
            # may be "None"
            'CYLC_SUITE_INITIAL_CYCLE_TIME': str(self.initial_point),
            # may be "None"
            'CYLC_SUITE_FINAL_CYCLE_TIME': str(self.final_point),
            # needed by the test battery
            'CYLC_SUITE_LOG_DIR': self.suite_log.get_dir(),
        }

        # Contact details for remote tasks, written to file on task
        # hosts because the details can change on restarting a suite.
        self.suite_env_dumper = CylcSuiteEnv(self.suite_env)
        self.suite_env_dumper.suite_cylc_version = CYLC_VERSION

        # Set local values of variables that are potenitally task-specific
        # due to different directory paths on different task hosts. These
        # are overridden by tasks prior to job submission, but in
        # principle they could be needed locally by event handlers:
        self.suite_task_env = {
            'CYLC_SUITE_RUN_DIR': GLOBAL_CFG.get_derived_host_item(
                self.suite, 'suite run directory'),
            'CYLC_SUITE_WORK_DIR': GLOBAL_CFG.get_derived_host_item(
                self.suite, 'suite work directory'),
            'CYLC_SUITE_SHARE_DIR': GLOBAL_CFG.get_derived_host_item(
                self.suite, 'suite share directory'),
            'CYLC_SUITE_SHARE_PATH': '$CYLC_SUITE_SHARE_DIR',  # DEPRECATED
            'CYLC_SUITE_DEF_PATH': self.suite_dir
        }
        # (global config auto expands environment variables in local paths)

        # Pass these to the job script generation code.
        JobFile.get_inst().set_suite_env(self.suite_env)
        # And pass contact env to the task module

        # make suite vars available to [cylc][environment]:
        for var, val in self.suite_env.items():
            os.environ[var] = val
        for var, val in self.suite_task_env.items():
            os.environ[var] = val
        cenv = copy(self.config.cfg['cylc']['environment'])
        for var, val in cenv.items():
            cenv[var] = os.path.expandvars(val)
        # path to suite bin directory for suite and task event handlers
        cenv['PATH'] = os.pathsep.join([
            os.path.join(self.suite_dir, 'bin'), os.environ['PATH']])

        # Make [cylc][environment] available to task event handlers in worker
        # processes,
        TaskProxy.event_handler_env = cenv
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
                sys.stderr.write(
                    'WARNING: shutdown handlers replaced by reference test\n')
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
        # Run suite event hooks in simulation and dummy mode ONLY if enabled
        for mode_name in ['simulation', 'dummy']:
            key = mode_name + ' mode'
            if (self.run_mode == mode_name and
                    self.config.cfg['cylc'][key]['disable suite event hooks']):
                return

        # Email notification
        if event in self._get_events_conf('mail events', []):
            # SMTP server
            env = dict(os.environ)
            mail_smtp = self._get_events_conf('mail smtp')
            if mail_smtp:
                env['smtp'] = mail_smtp
            subject = '[suite %(event)s] %(suite)s' % {
                'suite': self.suite, 'event': event}
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
                stdin_str=subject + '\n')
            if SuiteProcPool.get_inst().is_closed():
                # Run command in foreground if process pool is closed
                SuiteProcPool.get_inst().run_command(ctx)
                self._run_event_handlers_callback(ctx)
            else:
                # Run command using process pool otherwise
                SuiteProcPool.get_inst().put_command(
                    ctx, self._run_event_mail_callback)

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
            sys.stderr.write(
                'ERROR: %s EVENT HANDLER FAILED\n' % ctx.cmd_key[1])
            if (ctx.cmd_key[1] == self.EVENT_SHUTDOWN and
                    self.reference_test_mode):
                sys.stderr.write('ERROR: SUITE REFERENCE TEST FAILED\n')
            if abort_on_error:
                raise SchedulerError(ctx.err)
        else:
            self.log.info(str(ctx))
            if (ctx.cmd_key[1] == self.EVENT_SHUTDOWN and
                    self.reference_test_mode):
                sys.stdout.write('SUITE REFERENCE TEST PASSED\n')

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

        self.log_memory("scheduler.py: begin run while loop")
        proc_pool = SuiteProcPool.get_inst()

        next_fs_check = time.time() + self.FS_CHECK_PERIOD

        suite_run_dir = GLOBAL_CFG.get_derived_host_item(
            self.suite, 'suite run directory')

        while True:  # MAIN LOOP

            # Periodic check that the suite directory still exists
            # - designed to catch stalled suite daemons where the suite
            # directory has been deleted out from under itself
            if time.time() > next_fs_check:
                if not os.path.exists(suite_run_dir):
                    os.kill(os.getpid(), signal.SIGKILL)
                else:
                    next_fs_check = time.time() + self.FS_CHECK_PERIOD

            # PROCESS ALL TASKS whenever something has changed that might
            # require renegotiation of dependencies, etc.

            if self.shut_down_now:
                warned = False
                while not proc_pool.is_dead():
                    proc_pool.handle_results_async()
                    if not warned:
                        print("Waiting for the command process " +
                              "pool to empty for shutdown")
                        print("(you can \"stop now\" to shut " +
                              "down immediately if you like).")
                        warned = True
                    self.process_command_queue()
                    time.sleep(0.5)
                raise SchedulerStop("Finished")

            tinit = time.time()

            if self.pool.do_reload:
                self.pool.reload_taskdefs()
                self.do_update_state_summary = True

            self.process_command_queue()
            self.pool.release_runahead_tasks()
            proc_pool.handle_results_async()

            # External triggers must be matched now. If any are matched pflag
            # is set to tell process_tasks() that task processing is required.
            self.pool.match_ext_triggers()

            if self.process_tasks():
                if cylc.flags.debug:
                    self.log.debug("BEGIN TASK PROCESSING")
                    main_loop_start_time = time.time()

                changes = 0
                self.pool.match_dependencies()
                if not self.shut_down_cleanly:
                    changes += self.pool.submit_tasks()
                changes += self.pool.spawn_all_tasks()
                changes += self.pool.remove_spent_tasks()
                changes += self.pool.remove_suiciding_tasks()

                if changes:
                    self.do_update_state_summary = True

                BroadcastServer.get_inst().expire(self.pool.get_min_point())

                if cylc.flags.debug:
                    seconds = time.time() - main_loop_start_time
                    self.log.debug(
                        "END TASK PROCESSING (took " + str(seconds) + " sec)")

            self.pool.process_queued_task_messages()
            self.pool.process_queued_task_event_handlers()
            self.process_command_queue()
            if cylc.flags.iflag or self.do_update_state_summary:
                cylc.flags.iflag = False
                self.do_update_state_summary = False
                self.pool.put_rundb_task_pool()
                self.update_state_summary()
            try:
                self.pool.process_queued_db_ops()
            except OSError as err:
                self.shutdown(str(err))
                raise
            # If public database is stuck, blast it away by copying the content
            # of the private database into it.
            if self.pub_dao.n_tries >= self.pub_dao.MAX_TRIES:
                try:
                    self._copy_pri_db_to_pub_db()
                except (IOError, OSError) as exc:
                    # Something has to be very wrong here, so stop the suite
                    self.shutdown(str(exc))
                    raise
                else:
                    # No longer stuck
                    self.log.warning(
                        "%(pub_db_name)s: recovered from %(pri_db_name)s" % {
                            "pub_db_name": self.pub_dao.db_file_name,
                            "pri_db_name": self.pri_dao.db_file_name})
                    self.pub_dao.n_tries = 0

            if self._get_events_conf(self.EVENT_TIMEOUT):
                self.check_suite_timer()

            if self._get_events_conf(self.EVENT_INACTIVITY_TIMEOUT):
                self.check_suite_inactive()

            if self.config.cfg['cylc']['abort if any task fails']:
                if self.pool.any_task_failed():
                    raise SchedulerError(
                        'Task(s) failed and "abort if any task fails" is set')

            # the run is a reference test, and unexpected failures occured
            if self.reference_test_mode:
                if len(self.ref_test_allowed_failures) > 0:
                    for itask in self.pool.get_failed_tasks():
                        if (itask.identity not in
                                self.ref_test_allowed_failures):
                            sys.stderr.write(str(itask.identity) + "\n")
                            raise SchedulerError(
                                'Failed task is not in allowed failures list')

            # check submission and execution timeout and polling timers
            if self.run_mode != 'simulation':
                self.pool.check_task_timers()

            if (self.config.cfg['cylc']['disable automatic shutdown'] or
                    self.options.no_auto_shutdown):
                auto_stop = False
            else:
                auto_stop = self.pool.check_auto_shutdown()

            if self.stop_clock_done() or self.stop_task_done() or auto_stop:
                self.command_set_stop_cleanly()

            if ((self.shut_down_cleanly or auto_stop) and
                    self.pool.no_active_tasks()):
                self.update_state_summary()
                proc_pool.close()
                self.shut_down_now = True

            if (self.shut_down_cleanly and self.kill_on_shutdown):
                if self.pool.has_unkillable_tasks_only():
                    if not self.pool.no_active_tasks():
                        self.log.warning(
                            'some tasks were not killable at shutdown')
                    self.update_state_summary()
                    proc_pool.close()
                    self.shut_down_now = True
                else:
                    if time.time() > self.next_kill_issue:
                        self.pool.poll_task_jobs()
                        self.pool.kill_task_jobs()
                        self.next_kill_issue = time.time() + 10.0

            if self.options.profile_mode:
                now = time.time()
                self._update_profile_info("scheduler loop dt (s)", now - tinit,
                                          amount_format="%.3f")
                self._update_cpu_usage()
                if (int(now) % 60 == 0):
                    # Only get this every minute.
                    self.log_memory("scheduler.py: loop: " +
                                    get_current_time_string())

            if not (self.shut_down_cleanly or auto_stop):
                self.check_suite_stalled()

            time.sleep(1)

        self.log_memory("scheduler.py: end main loop")
        # END MAIN LOOP

    def update_state_summary(self):
        """Update state summary, e.g. for GUI."""
        self.suite_state.update(
            self.pool.get_tasks(), self.pool.get_rh_tasks(),
            self.pool.get_min_point(), self.pool.get_max_point(),
            self.pool.get_max_point_runahead(), self.paused(),
            self.will_pause_at(), self.shut_down_cleanly, self.will_stop_at(),
            self.config.ns_defn_order, self.pool.do_reload)

    def check_suite_timer(self):
        """Check if suite has timed out or not."""
        if self.already_timed_out or not self.is_stalled:
            return
        if time.time() > self.suite_timer_timeout:
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
        if self.already_inactive:
            return
        if time.time() > self.suite_inactivity_timeout:
            self.already_inactive = True
            message = 'suite timed out after inactivity for %s' % (
                get_seconds_as_interval_string(
                    self._get_events_conf(self.EVENT_INACTIVITY_TIMEOUT))
            )
            self.log.warning(message)
            self.run_event_handlers(self.EVENT_INACTIVITY_TIMEOUT, message)
            if self._get_events_conf('abort on inactivity'):
                raise SchedulerError('Abort on suite inactivity is set')

    def check_suite_stalled(self):
        """Check if suite is stalled or not."""
        if self.is_stalled:
            return
        # Suite should only be considered stalled if two consecutive
        # scheduler loops meet the criteria. This caters for pauses between
        # tasks succeeding and those triggering off them moving to ready
        # e.g. foo[-P1D] => foo
        if self.stalled_last and self.pool.pool_is_stalled():
            self.is_stalled = True
            message = 'suite stalled'
            self.log.warning(message)
            self.run_event_handlers(self.EVENT_STALLED, message)
            self.pool.report_stalled_task_deps()
            if self._get_events_conf('abort on stalled'):
                raise SchedulerError('Abort on suite stalled is set')
            # start suite timer
            self.set_suite_timer()
        else:
            self.stalled_last = self.pool.pool_is_stalled()

        # De-activate suite timeout timer if not stalled
        if self.suite_timer_active and not self.stalled_last:
            self.suite_timer_active = False
            if cylc.flags.verbose:
                print "%s suite timer stopped NOW: %s" % (
                    get_seconds_as_interval_string(
                        self._get_events_conf(self.EVENT_TIMEOUT)),
                    get_current_time_string())

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

            # New suite activity, so reset the stalled flag.
            self.stalled_last = False
            self.is_stalled = False

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

    def shutdown(self, reason=''):
        """Shutdown the suite."""
        msg = "Suite shutting down at " + get_current_time_string()
        if reason:
            msg += ' (' + reason + ')'
        print msg

        # The getattr() calls and if tests below are used in case the
        # suite is not fully configured before the shutdown is called.

        if getattr(self, "log", None) is not None:
            self.log.info(msg)

        if self.gen_reference_log:
            print '\nCOPYING REFERENCE LOG to suite definition directory'
            copyfile(
                self.suite_log.get_path(),
                os.path.join(self.config.fdir, 'reference.log'))

        proc_pool = SuiteProcPool.get_inst()
        if proc_pool:
            if not proc_pool.is_dead():
                # e.g. KeyboardInterrupt
                proc_pool.terminate()
            proc_pool.join()
            proc_pool.handle_results_async()

        if self.pool:
            self.pool.shutdown()

        if self.request_handler:
            self.request_handler.quit = True
            self.request_handler.join()

        for iface in [self.command_queue,
                      SuiteIdServer.get_inst(), StateSummaryServer.get_inst(),
                      ExtTriggerServer.get_inst(), BroadcastServer.get_inst()]:
            try:
                self.pyro.disconnect(iface)
            except KeyError:
                # Wasn't connected yet.
                pass

        if self.pyro:
            self.pyro.shutdown()

        try:
            os.unlink(self.port_file)
        except OSError as exc:
            sys.stderr.write(
                "WARNING, failed to remove port file: %s\n%s\n" % (
                    self.port_file, exc))

        # disconnect from suite-db, stop db queue
        if getattr(self, "db", None) is not None:
            self.pri_dao.close()
            self.pub_dao.close()

        if getattr(self, "config", None) is not None:
            # run shutdown handlers
            self.run_event_handlers(self.EVENT_SHUTDOWN, reason)

        print "DONE"  # main thread exit

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
            self.hold_suite_now = True
            self.pool.hold_all_tasks()
        else:
            self.log.info("Setting suite hold cycle point: " + str(point))
            self.pool.set_hold_point(point)

    def release_suite(self):
        """Release (un-hold) all tasks in suite."""
        if self.hold_suite_now:
            self.log.info("RELEASE: new tasks will be queued when ready")
            self.hold_suite_now = False
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
        return self.hold_suite_now

    def will_pause_at(self):
        """Return self.pool.get_hold_point()."""
        return self.pool.get_hold_point()

    def command_trigger_task(self, items, compat=None, _=None):
        """Trigger tasks."""
        return self.pool.trigger_tasks(items, compat)

    def command_dry_run_task(self, items, compat=None):
        """Dry-run a task, e.g. edit run."""
        return self.pool.dry_run_task(items, compat)

    def command_reset_task_state(self, items, compat=None, state=None, _=None):
        """Reset the state of tasks."""
        return self.pool.reset_task_states(items, state, compat)

    def command_spawn_tasks(self, items, compat=None, _=None):
        """Force spawn task successors."""
        return self.pool.spawn_tasks(items, compat)

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
        if (self.stop_clock_time is not None and
                time.time() > self.stop_clock_time):
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
                prefix=self.pub_dao.PUB_DB_FILE_BASE_NAME,
                dir=os.path.dirname(self.pub_dao.db_file_name))[1]
            copyfile(
                self.pri_dao.db_file_name, temp_pub_db_file_name)
            os.rename(temp_pub_db_file_name, self.pub_dao.db_file_name)
            os.chmod(self.pub_dao.db_file_name, st_mode)
        except (IOError, OSError):
            if temp_pub_db_file_name:
                os.unlink(temp_pub_db_file_name)
            raise

    def log_memory(self, message):
        """Print a message to standard out with the current memory usage."""
        if not self.options.profile_mode:
            return
        proc = Popen(["ps", "h", "-orss", str(os.getpid())], stdout=PIPE)
        memory = int(proc.communicate()[0])
        print "PROFILE: Memory: %d KiB: %s" % (memory, message)

    def _update_profile_info(self, category, amount, amount_format="%s"):
        """Update the 1, 5, 15 minute dt averages for a given category."""
        tnow = time.time()
        self._profile_amounts.setdefault(category, [])
        amounts = self._profile_amounts[category]
        amounts.append((tnow, amount))
        self._profile_update_times.setdefault(category, None)
        last_update = self._profile_update_times[category]
        if last_update is not None and tnow < last_update + 60:
            return
        self._profile_update_times[category] = tnow
        averages = {1: [], 5: [], 15: []}
        for then, amount in list(amounts):
            age = (tnow - then) / 60.0
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

    def _get_events_conf(self, key, default=None):
        """Return a named event hooks configuration."""
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
