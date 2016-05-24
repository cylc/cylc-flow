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
import subprocess
import sys
from tempfile import mkstemp
import threading
import time
import traceback

import isodatetime.data
import isodatetime.parsers
from parsec.util import printcfg

from cylc.cfgspec.globalcfg import GLOBAL_CFG
from cylc.config import SuiteConfig
from cylc.cycling import PointParsingError
from cylc.cycling.loader import get_point, standardise_point_string
from cylc.exceptions import CylcError
import cylc.flags
from cylc.job_file import JOB_FILE
from cylc.job_host import RemoteJobHostManager, RemoteJobHostInitError
from cylc.LogDiagnosis import LogSpec
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
from cylc.regpath import RegPath
from cylc.rundb import CylcSuiteDAO
from cylc.suite_env import CylcSuiteEnv
from cylc.suite_host import get_suite_host
from cylc.suite_logging import suite_log
from cylc.suite_state_dumping import SuiteStateDumper
from cylc.task_id import TaskID
from cylc.task_pool import TaskPool
from cylc.task_proxy import TaskProxy
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
    EVENT_STALLED = 'stalled'
    SUITE_EVENT_HANDLER = 'suite-event-handler'
    SUITE_EVENT_MAIL = 'suite-event-mail'
    FS_CHECK_PERIOD = 600.0  # 600 seconds

    def __init__(self, is_restart=False):
        self.suite = None
        self.owner = USER
        self.host = get_suite_host()
        self.port = None
        self.port_file = None

        self.is_restart = is_restart
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
        self.state_dumper = None

        self._profile_amounts = {}
        self._profile_update_times = {}

        # For persistence of reference test settings across reloads:
        self.reference_test_mode = False
        self.gen_reference_log = False

        self.shut_down_cleanly = False
        self.shut_down_now = False

        # TODO - stop task should be held by the task pool.
        self.stop_task = None
        self.stop_point = None
        self.stop_clock_time = None  # When not None, in Unix time
        self.stop_clock_time_string = None  # Human-readable format.

        self.initial_point = None
        self.start_point = None
        self._cli_initial_point_string = None
        self._cli_start_point_string = None

        self.parser.add_option(
            "--until",
            help=("Shut down after all tasks have PASSED " +
                  "this cycle point."),
            metavar="CYCLE_POINT", action="store",
            dest="final_point_string")

        self.parser.add_option(
            "--hold",
            help="Hold (don't run tasks) immediately on starting.",
            action="store_true", default=False, dest="start_held")

        self.parser.add_option(
            "--hold-after",
            help="Hold (don't run tasks) AFTER this cycle point.",
            metavar="CYCLE_POINT", action="store", dest="hold_point_string")

        self.parser.add_option(
            "-m", "--mode",
            help="Run mode: live, simulation, or dummy; default is live.",
            metavar="STRING", action="store", default='live', dest="run_mode")

        self.parser.add_option(
            "--reference-log",
            help="Generate a reference log for use in reference tests.",
            action="store_true", default=False, dest="genref")

        self.parser.add_option(
            "--reference-test",
            help="Do a test run against a previously generated reference log.",
            action="store_true", default=False, dest="reftest")

        self.parse_commandline()

    def configure(self):
        self.log_memory("scheduler.py: start configure")
        SuiteProcPool.get_inst()

        self.info_commands = {}
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if not callable(attr):
                continue
            if attr_name.startswith('info_'):
                self.info_commands[attr_name.replace('info_', '')] = attr

        # Run dependency negotation etc. after these commands.
        self.proc_cmds = [
            'release_suite',
            'release_task',
            'kill_tasks',
            'set_runahead',
            'reset_task_state',
            'spawn_tasks',
            'trigger_task',
            'nudge',
            'insert_task',
            'reload_suite',
        ]

        self.log_memory("scheduler.py: before configure_suite")
        self.configure_suite()
        self.log_memory("scheduler.py: after configure_suite")

        reqmode = self.config.cfg['cylc']['required run mode']
        if reqmode:
            if reqmode != self.run_mode:
                raise SchedulerError(
                    'ERROR: this suite requires the %s run mode' % reqmode)

        self.reflogfile = os.path.join(self.config.fdir, 'reference.log')

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
        self.state_dumper.pool = self.pool
        self.request_handler = PyroRequestHandler(self.pyro)
        self.request_handler.start()

        self.old_user_at_host_set = set()
        self.log_memory("scheduler.py: before load_tasks")
        self.load_tasks()
        self.log_memory("scheduler.py: after load_tasks")

        self.state_dumper.set_cts(self.initial_point, self.final_point)
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

        self.already_timed_out = False
        if self._get_events_conf(self.EVENT_TIMEOUT):
            self.set_suite_timer()

        self.nudge_timer_start = None
        self.nudge_timer_on = False
        self.auto_nudge_interval = 5  # seconds
        self.log_memory("scheduler.py: end configure")

    def process_command_queue(self):
        queue = self.command_queue.get_queue()
        n = queue.qsize()
        if n > 0:
            print 'Processing ' + str(n) + ' queued command(s)'
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
            except Exception, x:
                # Don't let a bad command bring the suite down.
                self.log.warning(traceback.format_exc())
                self.log.warning(str(x))
                self.log.warning('Command failed: ' + cmdstr)
            else:
                if n_warnings:
                    self.log.info(
                        'Command succeeded with %s warning(s): %s' %
                        (n_warnings, cmdstr))
                else:
                    self.log.info('Command succeeded: ' + cmdstr)
                self.do_update_state_summary = True
                if name in self.proc_cmds:
                    self.do_process_tasks = True
            queue.task_done()

    def _task_type_exists(self, name_or_id):
        # does a task name or id match a known task type in this suite?
        name = name_or_id
        if TaskID.is_valid_id(name_or_id):
            name = TaskID.split(name_or_id)[0]
        return name in self.config.get_task_name_list()

    def info_ping_suite(self):
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
        task_id = self.get_standardised_taskid(task_id)
        return self.pool.ping_task(task_id, exists_only)

    def info_get_task_jobfile_path(self, task_id):
        task_id = self.get_standardised_taskid(task_id)
        return self.pool.get_task_jobfile_path(task_id)

    def info_get_suite_info(self):
        info = {}
        for item in 'title', 'description':
            info[item] = self.config.cfg[item]
        return info

    def info_get_task_info(self, name):
        try:
            return self.config.describe(name)
        except KeyError:
            return {}

    def info_get_all_families(self, exclude_root=False):
        fams = self.config.get_first_parent_descendants().keys()
        if exclude_root:
            return fams[:-1]
        else:
            return fams

    def info_get_triggering_families(self):
        return self.config.triggering_families

    def info_get_first_parent_descendants(self):
        # families for single-inheritance hierarchy based on first parents
        return deepcopy(self.config.get_first_parent_descendants())

    def info_get_first_parent_ancestors(self, pruned=False):
        # single-inheritance hierarchy based on first parents
        return deepcopy(self.config.get_first_parent_ancestors(pruned))

    def info_get_graph_raw(self, cto, ctn, group_nodes, ungroup_nodes,
                           ungroup_recursive, group_all, ungroup_all):
        rgraph = self.config.get_graph_raw(
            cto, ctn, group_nodes, ungroup_nodes, ungroup_recursive, group_all,
            ungroup_all)
        return (
            rgraph, self.config.suite_polling_tasks, self.config.leaves,
            self.config.feet)

    def info_get_task_requisites(self, name, point_string):
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
        self.set_stop_point(self.get_standardised_point_string(point_string))

    def command_set_stop_after_clock_time(self, arg):
        # format: ISO 8601 compatible or YYYY/MM/DD-HH:mm (backwards comp.)
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
        self.configure_suite(reconfigure=True)
        self.pool.reconfigure(self.final_point)
        self.configure_suite_environment()
        if self.gen_reference_log or self.reference_test_mode:
            self.configure_reftest(recon=True)
        # update SuiteStateDumper state
        self.state_dumper.set_cts(self.initial_point, self.final_point)
        self.do_update_state_summary = True

    def command_set_runahead(self, *args):
        self.pool.set_runahead(*args)

    def set_suite_timer(self, reset=False):
        """Set suite's timeout timer."""
        self.suite_timer_timeout = time.time() + (
            self._get_events_conf(self.EVENT_TIMEOUT)
        )
        if cylc.flags.verbose:
            print "%s suite timer starts NOW: %s" % (
                get_seconds_as_interval_string(
                    self._get_events_conf(self.EVENT_TIMEOUT)),
                get_current_time_string())

    def parse_commandline(self):
        if self.options.run_mode not in [
                'live', 'dummy', 'simulation']:
            self.parser.error(
                'Illegal run mode: %s\n' % self.options.run_mode)
        self.run_mode = self.options.run_mode

        if cylc.flags.debug:
            self.logging_level = logging.DEBUG
        else:
            self.logging_level = logging.INFO

        if self.options.reftest:
            self.reference_test_mode = self.options.reftest

        if self.options.genref:
            self.gen_reference_log = self.options.genref

    def configure_pyro(self):
        """Create and configure Pyro daemon."""
        self.pyro = PyroDaemon(self.suite, self.suite_dir)
        self.port = self.pyro.get_port()
        self.port_file = os.path.join(
            GLOBAL_CFG.get(['pyro', 'ports directory']), self.suite)
        try:
            port, host = open(self.port_file).read().splitlines()
        except (IOError, ValueError):
            # Suite is not likely to be running if port file does not exist
            # or if port file does not contain good values of port and host.
            pass
        else:
            sys.stderr.write(
                (
                    r"""ERROR: port file exists: %(port_file)s

If %(suite)s is not running, delete the port file and try again.  If it is
running but not responsive, kill any left over suite processes too.

To see if %(suite)s is running on '%(host)s:%(port)s':
 * cylc scan -n '\b%(suite)s\b' %(host)s
 * cylc ping -v --host=%(host)s %(suite)s
 * ssh %(host)s "pgrep -a -P 1 -fu $USER 'cylc-r.* \b%(suite)s\b'"

"""
                ) % {
                    "host": host,
                    "port": port,
                    "port_file": self.port_file,
                    "suite": self.suite,
                }
            )
            raise SchedulerError(
                "ERROR, port file exists: %s" % self.port_file)
        try:
            with open(self.port_file, 'w') as handle:
                handle.write("%d\n%s\n" % (self.port, self.host))
        except IOError as exc:
            sys.stderr.write(str(exc) + "\n")
            raise SchedulerError(
                'ERROR, cannot write port file: %s' % self.port_file)

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

    def configure_suite(self, reconfigure=False):
        """Load and process the suite definition."""

        if self.is_restart:
            self._cli_initial_point_string = (
                self.get_state_initial_point_string())
            self.do_process_tasks = True

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

        if not reconfigure:
            # Things that can't change on suite reload.

            self.state_dumper = SuiteStateDumper(
                self.suite, self.run_mode, self.initial_point,
                self.final_point)

            run_dir = GLOBAL_CFG.get_derived_host_item(
                self.suite, 'suite run directory')
            pri_db_path = os.path.join(
                run_dir, 'state', CylcSuiteDAO.DB_FILE_BASE_NAME)
            pub_db_path = os.path.join(
                run_dir, CylcSuiteDAO.DB_FILE_BASE_NAME)
            if self.is_restart:
                if (os.path.exists(pub_db_path) and
                        not os.path.exists(pri_db_path)):
                    # Backwards compatibility code for restarting at move to
                    # new db location should be deleted at database refactoring
                    print('Copy "cylc.suite.db" to "state/cylc.suite.db"')
                    copyfile(pub_db_path, pri_db_path)
            else:
                # Remove database created by previous runs
                if os.path.isdir(pri_db_path):
                    rmtree(pri_db_path)
                else:
                    try:
                        os.unlink(pri_db_path)
                    except OSError:
                        pass
            # Ensure that:
            # * public database is in sync with private database
            # * private database file is private
            self.pri_dao = CylcSuiteDAO(pri_db_path)
            os.chmod(pri_db_path, 0600)
            if self.is_restart:
                sys.stdout.write("Rebuilding the suite db ...")
                self.pri_dao.vacuum()
                sys.stdout.write(" done\n")
            self.pub_dao = CylcSuiteDAO(pub_db_path, is_public=True)
            self._copy_pri_db_to_pub_db()

            self.hold_suite_now = False
            self._pool_hold_point = None

            if self.config.cfg['scheduling']['hold after point']:
                self._pool_hold_point = get_point(
                    self.config.cfg['scheduling']['hold after point'])

            if self.options.hold_point_string:
                self._pool_hold_point = get_point(
                    self.options.hold_point_string)

            if self._pool_hold_point:
                print "Suite will hold after " + str(self._pool_hold_point)

            slog = suite_log(self.suite)
            self.suite_log_dir = slog.get_dir()
            slog.pimp(self.logging_level)
            self.log = slog.get_log()
            self.logfile = slog.get_path()

            suite_id = SuiteIdServer.get_inst(self.suite, self.owner)
            self.pyro.connect(suite_id, PYRO_SUITEID_OBJ_NAME)

            bcast = BroadcastServer.get_inst(
                self.config.get_linearized_ancestors())
            self.pyro.connect(bcast, PYRO_BCAST_OBJ_NAME)

            self.command_queue = SuiteCommandServer()
            self.pyro.connect(self.command_queue, PYRO_CMD_OBJ_NAME)

            ets = ExtTriggerServer.get_inst()
            self.pyro.connect(ets, PYRO_EXT_TRIG_OBJ_NAME)

            self.info_interface = SuiteInfoServer(self.info_commands)
            self.pyro.connect(self.info_interface, PYRO_INFO_OBJ_NAME)

            self.log_interface = SuiteLogServer(slog)
            self.pyro.connect(self.log_interface, PYRO_LOG_OBJ_NAME)

            self.suite_state = StateSummaryServer.get_inst(self.run_mode)
            self.pyro.connect(self.suite_state, PYRO_STATE_OBJ_NAME)

    def configure_suite_environment(self):
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
            'CYLC_SUITE_LOG_DIR': self.suite_log_dir,
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
        JOB_FILE.set_suite_env(self.suite_env)
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
            self.config.cfg['cylc']['event hooks']['shutdown handler'] = [
                rtc['suite shutdown event handler']]
            self.config.cfg['cylc']['log resolved dependencies'] = True
            self.config.cfg['cylc']['event hooks'][
                'abort if shutdown handler fails'] = True
            if not recon:
                spec = LogSpec(self.reflogfile)
                self.initial_point = get_point(spec.get_initial_point_string())
                self.start_point = get_point(
                    spec.get_start_point_string()) or self.initial_point
                self.final_point = get_point(spec.get_final_point_string())
            self.ref_test_allowed_failures = rtc['expected task failures']
            if (not rtc['allow task failures'] and
                    not self.ref_test_allowed_failures):
                self.config.cfg['cylc']['abort if any task fails'] = True
            self.config.cfg['cylc']['event hooks']['abort on timeout'] = True
            timeout = rtc[self.run_mode + ' mode suite timeout']
            if not timeout:
                raise SchedulerError(
                    'ERROR: timeout not defined for %s reference tests' % (
                        self.run_mode))
            self.config.cfg['cylc']['event hooks'][self.EVENT_TIMEOUT] = (
                timeout)
            self.config.cfg['cylc']['event hooks']['reset timer'] = False

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

        if self._pool_hold_point is not None:
            self.hold_suite(self._pool_hold_point)

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

            t0 = time.time()

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

            if cylc.flags.iflag or self.do_update_state_summary:
                cylc.flags.iflag = False
                self.do_update_state_summary = False
                self.update_state_summary()
                self.state_dumper.dump()

            if self._get_events_conf(self.EVENT_TIMEOUT):
                self.check_suite_timer()

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
                t1 = time.time()
                self._update_profile_info("scheduler loop dt (s)", t1 - t0,
                                          amount_format="%.3f")
                self._update_cpu_usage()
                if (int(t1) % 60 == 0):
                    # Only get this every minute.
                    self.log_memory("scheduler.py: loop: " +
                                    get_current_time_string())

            if not (self.shut_down_cleanly or auto_stop):
                self.check_suite_stalled()

            time.sleep(1)

        self.log_memory("scheduler.py: end main loop")
        # END MAIN LOOP

    def update_state_summary(self):
        self.suite_state.update(
            self.pool.get_tasks(), self.pool.get_rh_tasks(),
            self.pool.get_min_point(), self.pool.get_max_point(),
            self.pool.get_max_point_runahead(), self.paused(),
            self.will_pause_at(), self.shut_down_cleanly, self.will_stop_at(),
            self.config.ns_defn_order, self.pool.do_reload)

    def check_suite_timer(self):
        if self.already_timed_out:
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

    def check_suite_stalled(self):
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
            if self._get_events_conf('abort on stalled'):
                raise SchedulerError('Abort on suite stalled is set')
        else:
            self.stalled_last = self.pool.pool_is_stalled()

    def process_tasks(self):
        # do we need to do a pass through the main task processing loop?
        process = False

        if self.do_process_tasks:
            # this flag is turned on by commands that change task state
            process = True
            self.do_process_tasks = False  # reset

        if cylc.flags.pflag:
            process = True
            cylc.flags.pflag = False  # reset
            # New suite activity, so reset the suite timer.
            if (self._get_events_conf(self.EVENT_TIMEOUT) and
                    self._get_events_conf('reset timer')):
                self.set_suite_timer()

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
            copyfile(self.logfile, self.reflogfile)

        proc_pool = SuiteProcPool.get_inst()
        if proc_pool:
            if not proc_pool.is_dead():
                # e.g. KeyboardInterrupt
                proc_pool.terminate()
            proc_pool.join()
            proc_pool.handle_results_async()

        if self.pool:
            self.pool.shutdown()
            if self.state_dumper:
                try:
                    self.state_dumper.dump()
                except (OSError, IOError) as exc:
                    # (see comments in the state dumping module)
                    # ignore errors here in order to shut down cleanly
                    self.log.warning('Final state dump failed: ' + str(exc))

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
        stop_point = get_point(stop_point_string)
        self.stop_point = stop_point
        self.log.info("Setting stop cycle point: %s" % stop_point_string)
        self.pool.set_stop_point(self.stop_point)

    def set_stop_clock(self, unix_time, date_time_string):
        self.log.info("Setting stop clock time: %s (unix time: %s)" % (
                      date_time_string, unix_time))
        self.stop_clock_time = unix_time
        self.stop_clock_time_string = date_time_string

    def set_stop_task(self, task_id):
        name, point_string = TaskID.split(task_id)
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
        if point is None:
            self.hold_suite_now = True
            self.pool.hold_all_tasks()
        else:
            self.log.info("Setting suite hold cycle point: " + str(point))
            self.pool.set_hold_point(point)

    def release_suite(self):
        if self.hold_suite_now:
            self.log.info("RELEASE: new tasks will be queued when ready")
            self.hold_suite_now = False
        self.pool.set_hold_point(None)
        self.pool.release_all_tasks()

    def will_stop_at(self):
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
        self.stop_point = None
        self.stop_clock_time = None
        self.stop_clock_time_string = None
        self.stop_task = None

    def paused(self):
        return self.hold_suite_now

    def will_pause_at(self):
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
        if (self.stop_clock_time is not None and
                time.time() > self.stop_clock_time):
            time_point = (
                isodatetime.data.get_timepoint_from_seconds_since_unix_epoch(
                    self.stop_clock_time
                )
            )
            self.log.info("Wall clock stop time reached: " + str(time_point))
            self.stop_clock_time = None
            self.stop_clock_time_description = None
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
        proc = subprocess.Popen(["ps", "h", "-orss", str(os.getpid())],
                                stdout=subprocess.PIPE)
        memory = int(proc.communicate()[0])
        print "PROFILE: Memory: %d KiB: %s" % (memory, message)

    def _update_profile_info(self, category, amount, amount_format="%s"):
        # Update the 1, 5, 15 minute dt averages for a given category.
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
        p = subprocess.Popen(
            ["ps", "-o%cpu= ", str(os.getpid())], stdout=subprocess.PIPE)
        try:
            cpu_frac = float(p.communicate()[0])
        except (TypeError, OSError, IOError, ValueError) as e:
            self.log.warning("Cannot get CPU % statistics: %s" % e)
            return
        self._update_profile_info("CPU %", cpu_frac, amount_format="%.1f")

    def _get_events_conf(self, key, default=None):
        """Return a named event hooks configuration."""
        for getter in [
                self.config.cfg['cylc']['event hooks'],
                GLOBAL_CFG.get(['cylc', 'event hooks'])]:
            try:
                value = getter[key]
            except KeyError:
                pass
            else:
                if value is not None:
                    return value
        return default
