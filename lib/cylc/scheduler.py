#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

from cylc_pyro_server import pyro_server
from task_types import task, clocktriggered
from job_submission import jobfile
from suite_host import get_suite_host
from owner import user
from shutil import copy as shcopy
from copy import deepcopy
import datetime, time
import port_scan
import logging
import re, os, sys, shutil, traceback
from state_summary import state_summary
from passphrase import passphrase
from locking.lockserver import lockserver
from locking.suite_lock import suite_lock
from suite_id import identifier
from config import config, SuiteConfigError, TaskNotDefinedError
from cfgspec.site import sitecfg
from port_file import port_file, PortFileExistsError, PortFileError
from regpath import RegPath
from CylcError import TaskNotFoundError, SchedulerError
from RunEventHandler import RunHandler
from LogDiagnosis import LogSpec
from suite_state_dumping import dumper
from suite_logging import suite_log
import threading
from suite_cmd_interface import comqueue
from suite_info_interface import info_interface
from suite_log_interface import log_interface
import TaskID
from task_pool import pool
import flags
import cylc.rundb
from Queue import Queue, Empty
import subprocess
from mp_pool import mp_pool
from exceptions import SchedulerStop, SchedulerError
from wallclock import (
    now, get_current_time_string, get_seconds_as_interval_string)
from cycling import PointParsingError
from cycling.loader import get_point
import isodatetime.data
import isodatetime.parsers


class request_handler(threading.Thread):
    def __init__(self, pyro):
        threading.Thread.__init__(self)
        self.pyro = pyro
        self.quit = False
        self.log = logging.getLogger('main')
        self.log.debug("request handling thread starting")

    def run(self):
        while True:
            self.pyro.handleRequests(timeout=1)
            if self.quit:
                break
        self.log.debug("request handling thread exiting")


class scheduler(object):

    def __init__( self, is_restart=False ):

        # SUITE OWNER
        self.owner = user

        # SUITE HOST
        self.host= get_suite_host()

        self.lock_acquired = False

        self.is_restart = is_restart

        self.graph_warned = {}

        self.suite_env = {}
        self.suite_task_env = {}
        self.suite_contact_env = {}

        self.do_process_tasks = False
        self.do_update_state_summary = False

        # initialize some items in case of early shutdown
        # (required in the shutdown() method)
        self.suite_id = None
        self.suite_state = None
        self.command_queue = None
        self.pool = None
        self.proc_pool = None
        self.request_handler = None
        self.pyro = None
        self.state_dumper = None

        self._profile_amounts = {}
        self._profile_update_times = {}

        # provide a variable to allow persistance of reference test settings
        # across reloads
        self.reference_test_mode = False
        self.gen_reference_log = False

        self.shut_down_cleanly = False
        self.shut_down_quickly = False
        self.shut_down_now = False

        # TODO - stop task should be held by the task pool.
        self.stop_task = None

        self.stop_clock_time = None  # When not None, in Unix time
        self.stop_clock_time_description = None  # Human-readable format.

        self._start_string = None
        self._stop_string = None
        self._cli_start_string = None

        self.parser.add_option( "--until",
                help=("Shut down after all tasks have PASSED " +
                      "this cycle point."),
                metavar="CYCLE_POINT", action="store", dest="stop_string" )

        self.parser.add_option( "--hold", help="Hold (don't run tasks) "
                "immediately on starting.",
                action="store_true", default=False, dest="start_held" )

        self.parser.add_option( "--hold-after",
                help="Hold (don't run tasks) AFTER this cycle point.",
                metavar="CYCLE_POINT", action="store", dest="hold_time" )

        self.parser.add_option( "-m", "--mode",
                help="Run mode: live, simulation, or dummy; default is live.",
                metavar="STRING", action="store", default='live', dest="run_mode" )

        self.parser.add_option( "--reference-log",
                help="Generate a reference log for use in reference tests.",
                action="store_true", default=False, dest="genref" )

        self.parser.add_option( "--reference-test",
                help="Do a test run against a previously generated reference log.",
                action="store_true", default=False, dest="reftest" )

        self.parse_commandline()

    def configure( self ):
        # read-only commands to expose directly to the network
        self.info_commands = {
                'ping suite'        : self.info_ping_suite,
                'ping task'         : self.info_ping_task,
                'suite info'        : self.info_get_suite_info,
                'task list'         : self.info_get_task_list,
                'task info'         : self.info_get_task_info,
                'all families'      : self.info_get_all_families,
                'triggering families' : self.info_get_triggering_families,
                'first-parent ancestors'    : self.info_get_first_parent_ancestors,
                'first-parent descendants'  : self.info_get_first_parent_descendants,
                'do live graph movie'       : self.info_do_live_graph_movie,
                'graph raw'         : self.info_get_graph_raw,
                'task requisites'   : self.info_get_task_requisites,
                }

        # control commands to expose indirectly via a command queue
        self.control_commands = {
                'stop cleanly'          : self.command_set_stop_cleanly,
                'stop quickly'          : self.command_stop_quickly,
                'stop now'              : self.command_stop_now,
                'stop after tag'        : self.command_set_stop_after_tag,
                'stop after clock time' : self.command_set_stop_after_clock_time,
                'stop after task'       : self.command_set_stop_after_task,
                'release suite'         : self.command_release_suite,
                'release task'          : self.command_release_task,
                'remove cycle'          : self.command_remove_cycle,
                'remove task'           : self.command_remove_task,
                'hold suite now'        : self.command_hold_suite,
                'hold task now'         : self.command_hold_task,
                'set runahead'          : self.command_set_runahead,
                'set verbosity'         : self.command_set_verbosity,
                'purge tree'            : self.command_purge_tree,
                'reset task state'      : self.command_reset_task_state,
                'trigger task'          : self.command_trigger_task,
                'nudge suite'           : self.command_nudge,
                'insert task'           : self.command_insert_task,
                'reload suite'          : self.command_reload_suite,
                'add prerequisite'      : self.command_add_prerequisite,
                'poll tasks'            : self.command_poll_tasks,
                'kill tasks'            : self.command_kill_tasks,
                }

        # run dependency negotation etc. after these commands
        self.proc_cmds = [
            'release suite',
            'release task',
            'kill cycle',
            'kill task',
            'set runahead',
            'purge tree',
            'reset task state',
            'trigger task',
            'nudge suite',
            'insert task',
            'reload suite',
            'prerequisite'
            ]
        self.configure_suite()

        # REMOTELY ACCESSIBLE SUITE IDENTIFIER
        self.suite_id = identifier( self.suite, self.owner )
        self.pyro.connect( self.suite_id, 'cylcid', qualified = False )

        reqmode = self.config.cfg['cylc']['required run mode']
        if reqmode:
            if reqmode != self.run_mode:
                raise SchedulerError, 'ERROR: this suite requires the ' + reqmode + ' run mode'

        # TODO - self.config.fdir can be used instead of self.suite_dir
        self.reflogfile = os.path.join(self.config.fdir,'reference.log')

        if self.gen_reference_log or self.reference_test_mode:
            self.configure_reftest()

        # Note that the following lines must be present at the top of
        # the suite log file for use in reference test runs:
        self.log.info( 'Suite starting at ' + get_current_time_string() )
        if self.run_mode == 'live':
            self.log.info( 'Log event clock: real time' )
        else:
            self.log.info( 'Log event clock: accelerated' )
        self.log.info( 'Run mode: ' + self.run_mode )
        self.log.info( 'Start tag: ' + str(self.start_point) )
        self.log.info( 'Stop tag: ' + str(self.stop_point) )

        self.pool = pool( self.suite, self.db, self.stop_point, self.config,
                          self.pyro, self.log, self.run_mode, self.proc_pool )
        self.state_dumper.pool = self.pool
        self.request_handler = request_handler( self.pyro )
        self.request_handler.start()

        # LOAD TASK POOL ACCORDING TO STARTUP METHOD
        self.old_user_at_host_set = set()
        self.load_tasks()

        # REMOTELY ACCESSIBLE SUITE STATE SUMMARY
        self.suite_state = state_summary( self.config, self.run_mode, str(self.pool.get_min_ctime()) )
        self.pyro.connect( self.suite_state, 'state_summary')

        self.state_dumper.set_cts( self.start_point, self.stop_point )
        self.configure_suite_environment()

        # Write suite contact environment variables.
        # 1) local file (os.path.expandvars is called automatically for local)
        suite_run_dir = sitecfg.get_derived_host_item(self.suite, 'suite run directory')
        env_file_path = os.path.join(suite_run_dir, "cylc-suite-env")
        f = open(env_file_path, 'wb')
        for key, value in self.suite_contact_env.items():
            f.write("%s=%s\n" % (key, value))
        f.close()
        # 2) restart only: copy to other accounts with still-running tasks
        r_suite_run_dir = os.path.expandvars(
                sitecfg.get_derived_host_item(self.suite, 'suite run directory'))
        for user_at_host in self.old_user_at_host_set:
            # Reinstate suite contact file to each old job's user@host
            if '@' in user_at_host:
                owner, host = user_at_host.split('@', 1)
            else:
                owner, host = None, user_at_host
            if (owner, host) in [(None, 'localhost'), (user, 'localhost')]:
                continue
            r_suite_run_dir = sitecfg.get_derived_host_item(
                                self.suite,
                                'suite run directory',
                                host,
                                owner)
            r_env_file_path = '%s:%s/cylc-suite-env' % (
                                user_at_host,
                                r_suite_run_dir)
            self.log.info('Installing %s' % r_env_file_path)
            cmd1 = (['ssh'] + task.task.SUITE_CONTACT_ENV_SSH_OPTS +
                    [user_at_host, 'mkdir', '-p', r_suite_run_dir])
            cmd2 = (['scp'] + task.task.SUITE_CONTACT_ENV_SSH_OPTS +
                    [env_file_path, r_env_file_path])
            for cmd in [cmd1, cmd2]:
                subprocess.check_call(cmd)
            task.task.suite_contact_env_hosts.append( user_at_host )

        self.already_timed_out = False
        if self.config.cfg['cylc']['event hooks']['timeout']:
            self.set_suite_timer()

        self.nudge_timer_start = None
        self.nudge_timer_on = False
        self.auto_nudge_interval = 5 # seconds

    def process_command_queue( self ):
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
            cmdstr = name + '(' + ','.join( [ str(a) for a in args ]) + ')'
            try:
                self.control_commands[ name ]( *args )
            except SchedulerStop:
                self.log.info( 'Command succeeded: ' + cmdstr )
                raise
            except Exception, x:
                # don't let a bad command bring the suite down
                self.log.warning( traceback.format_exc() )
                self.log.warning( str(x) )
                self.log.warning( 'Command failed: ' +  cmdstr )
            else:
                self.log.info( 'Command succeeded: ' + cmdstr )
                self.do_update_state_summary = True
                if name in self.proc_cmds:
                    self.do_process_tasks = True
            queue.task_done()

    def _task_type_exists( self, name_or_id ):
        # does a task name or id match a known task type in this suite?
        name = name_or_id
        if TaskID.DELIM in name_or_id:
            name, tag = TaskID.split(name_or_id)
        if name in self.config.get_task_name_list():
            return True
        else:
            return False

    def info_ping_suite( self ):
        return True

    def info_ping_task( self, task_id ):
        return self.pool.ping_task( task_id )

    def info_get_suite_info( self ):
        return [ self.config.cfg['title'], user ]

    def info_get_task_list( self, logit=True ):
        return self.config.get_task_name_list()

    def info_get_task_info( self, task_names ):
        info = {}
        for name in task_names:
            if self._task_type_exists( name ):
                info[ name ] = self.config.get_task_class( name ).describe()
            else:
                info[ name ] = ['ERROR: no such task type']
        return info

    def info_get_all_families( self, exclude_root=False ):
        fams = self.config.get_first_parent_descendants().keys()
        if exclude_root:
            return fams[:-1]
        else:
            return fams

    def info_get_triggering_families( self ):
        return self.config.triggering_families

    def info_get_first_parent_descendants( self ):
        # families for single-inheritance hierarchy based on first parents
        return deepcopy(self.config.get_first_parent_descendants())

    def info_do_live_graph_movie( self ):
        return ( self.config.cfg['visualization']['enable live graph movie'], self.suite_dir )

    def info_get_first_parent_ancestors( self, pruned=False ):
        # single-inheritance hierarchy based on first parents
        return deepcopy(self.config.get_first_parent_ancestors(pruned) )

    def info_get_graph_raw( self, cto, ctn, raw, group_nodes, ungroup_nodes,
            ungroup_recursive, group_all, ungroup_all ):
        return self.config.get_graph_raw( cto, ctn, raw, group_nodes,
                ungroup_nodes, ungroup_recursive, group_all, ungroup_all), \
                        self.config.suite_polling_tasks, \
                        self.config.leaves, self.config.feet

    def info_get_task_requisites( self, in_ids ):
        ids = []
        for id in in_ids:
            if not self._task_type_exists( id ):
                continue
            ids.append( id )
        return self.pool.get_task_requisites( ids )

    def command_set_stop_cleanly(self, kill_active_tasks=False):
        """Stop job submission and set the flag for clean shutdown."""
        if kill_active_tasks:
            self.pool.kill_active_tasks()
        self.proc_pool.close()
        self.shut_down_cleanly = True

    def command_stop_quickly(self):
        """Stop job submission and set the flag for quick shutdown."""
        self.proc_pool.close()
        self.shut_down_quickly = True

    def command_stop_now(self):
        """Shutdown immediately."""
        self.proc_pool.terminate()
        raise SchedulerStop("Stopping NOW")

    def command_set_stop_after_tag( self, tag ):
        self.set_stop_ctime( tag )

    def command_set_stop_after_clock_time( self, arg ):
        # format: ISO 8601 compatible or YYYY/MM/DD-HH:mm (backwards comp.)
        parser = isodatetime.parsers.TimePointParser()
        try:
            stop_point = parser.parse(arg)
        except ValueError as exc:
            try:
                stop_point = parser.strptime("%Y/%m/%d-%H:%M")
            except ValueError:
                raise exc  # Raise the first (prob. more relevant) ValueError.
        stop_time_in_epoch_seconds = int(stop_point.get(
            "seconds_since_unix_epoch"))
        self.set_stop_clock( stop_time_in_epoch_seconds, str(stop_point) )

    def command_set_stop_after_task( self, tid ):
        if TaskID.is_valid_id(tid):
            self.set_stop_task( tid )

    def command_release_task( self, name, tag, is_family ):
        matches = self.get_matching_tasks( name, is_family )
        if not matches:
            raise TaskNotFoundError, "No matching tasks found: " + name
        task_ids = [ TaskID.get(i,tag) for i in matches ]
        self.pool.release_tasks( task_ids )

    def command_poll_tasks( self, name, tag, is_family ):
        matches = self.get_matching_tasks( name, is_family )
        if not matches:
            raise TaskNotFoundError, "No matching tasks found: " + name
        task_ids = [ TaskID.get(i,tag) for i in matches ]
        self.pool.poll_tasks( task_ids )


    def command_kill_tasks( self, name, tag, is_family ):
        matches = self.get_matching_tasks( name, is_family )
        if not matches:
            raise TaskNotFoundError, "No matching tasks found: " + name
        task_ids = [ TaskID.get(i,tag) for i in matches ]
        self.pool.kill_tasks( task_ids )

    def command_release_suite( self ):
        self.release_suite()

    def command_hold_task( self, name, tag, is_family ):
        matches = self.get_matching_tasks( name, is_family )
        if not matches:
            raise TaskNotFoundError, "No matching tasks found: " + name
        task_ids = [ TaskID.get(i,tag) for i in matches ]
        self.pool.hold_tasks( task_ids )

    def command_hold_suite( self ):
        self.hold_suite()

    def command_hold_after_tag( self, tag ):
        """TODO - not currently used, add to the cylc hold command"""
        # TODO ISO - USE VAR NAMES TO MAKE CLEAR STRING CTIME VS POINT
        self.hold_suite( tag )
        self.log.info( "The suite will pause when all tasks have passed " + tag )

    def command_set_verbosity( self, level ):
        # change logging verbosity:
        if level == 'debug':
            new_level = logging.DEBUG
        elif level == 'info':
            new_level = logging.INFO
        elif level == 'warning':
            new_level = logging.WARNING
        elif level == 'error':
            new_level = logging.ERROR
        elif level == 'critical':
            new_level = logging.CRITICAL
        else:
            self.log.warning( "Illegal logging level: " + level )
            return False, "Illegal logging level: " + level

        self.log.setLevel( new_level )

        flags.debug = ( level == 'debug' )
        return True, 'OK'

    def command_remove_cycle( self, tag, spawn ):
        self.pool.remove_entire_cycle( tag,spawn )

    def command_remove_task( self, name, tag, is_family, spawn ):
        matches = self.get_matching_tasks( name, is_family )
        if not matches:
            raise TaskNotFoundError, "No matching tasks found: " + name
        task_ids = [ TaskID.get(i,tag) for i in matches ]
        self.pool.remove_tasks( task_ids, spawn )

    def command_insert_task( self, name, tag, is_family, stop_string ):
        matches = self.get_matching_tasks( name, is_family )
        if not matches:
            raise TaskNotFoundError, "No matching tasks found: " + name
        task_ids = [ TaskID.get(i,tag) for i in matches ]

        point = get_point(tag).standardise()
        if stop_string is None:
            stop_point = None
        else:
            stop_point = get_point(stop_string).standardise()
        

        for task_id in task_ids:
            name, tag = TaskID.split( task_id )
            # TODO - insertion of start-up tasks? (startup=False is assumed here)
            new_task = self.config.get_task_proxy( name, point, 'waiting', stop_point, startup=False, submit_num=self.db.get_task_current_submit_num(name, tag), exists=self.db.get_task_state_exists(name, tag))
            if new_task:
                self.pool.add_to_runahead_pool( new_task )

    def command_nudge( self ):
        # just to cause the task processing loop to be invoked
        pass

    def command_reload_suite( self ):
        self.reconfigure()

    def command_set_runahead( self, *args  ):
        self.pool.set_runahead(*args)

    def set_suite_timer( self, reset=False ):
        self.suite_timer_timeout = time.time() + (       
            self.config.cfg['cylc']['event hooks']['timeout']
        )
        if flags.verbose:
            print "%s suite timer starts NOW: %s" % (
                get_seconds_as_interval_string(
                    self.config.cfg['cylc']['event hooks']['timeout']),
                get_current_time_string()
            )

    def reconfigure( self ):
        print "RELOADING the suite definition"
        self.configure_suite( reconfigure=True )

        self.pool.reconfigure( self.config, self.stop_point )

        self.suite_state.config = self.config
        self.configure_suite_environment()

        if self.gen_reference_log or self.reference_test_mode:
            self.configure_reftest(recon=True)

        # update state dumper state
        self.state_dumper.set_cts( self.start_point, self.stop_point )

    def parse_commandline( self ):
        self.run_mode = self.options.run_mode

        # LOGGING LEVEL
        if flags.debug:
            self.logging_level = logging.DEBUG
        else:
            self.logging_level = logging.INFO

        if self.options.reftest:
            self.reference_test_mode = self.options.reftest

        if self.options.genref:
            self.gen_reference_log = self.options.genref

    def configure_pyro( self ):
        # CONFIGURE SUITE PYRO SERVER
        self.pyro = pyro_server( self.suite, self.suite_dir,
                sitecfg.get( ['pyro','base port'] ),
                sitecfg.get( ['pyro','maximum number of ports'] ) )
        self.port = self.pyro.get_port()

        try:
            self.port_file = port_file( self.suite, self.port )
        except PortFileExistsError,x:
            print >> sys.stderr, x
            raise SchedulerError( 'Suite already running? (if not, delete the port file)' )
        except PortFileError,x:
            raise SchedulerError( str(x) )

    def configure_suite( self, reconfigure=False ):
        # LOAD SUITE CONFIG FILE

        if self.is_restart:
            self._cli_start_string = self.get_state_start_string()
            self.do_process_tasks = True

        self.config = config(
            self.suite, self.suiterc,
            self.options.templatevars,
            self.options.templatevars_file, run_mode=self.run_mode,
            cli_start_string=(self._start_string or
                              self._cli_start_string),
            is_restart=self.is_restart, is_reload=reconfigure
        )

        # Initial and final cycle times - command line takes precedence
        self.start_point = get_point(
            self._start_string or self._cli_start_string or
            self.config.cfg['scheduling']['initial cycle point']
        )
        if self.start_point is not None:
            self.start_point.standardise()

        self.stop_point = get_point(
            self.options.stop_string or
            self.config.cfg['scheduling']['final cycle point']
        )
        if self.stop_point is not None:
            self.stop_point.standardise()

        if (not self.start_point and not self.is_restart and
            self.config.cycling_tasks):
            print >> sys.stderr, 'WARNING: No initial cycle point provided - no cycling tasks will be loaded.'

        if self.run_mode != self.config.run_mode:
            self.run_mode = self.config.run_mode

        if not reconfigure:
            self.state_dumper = dumper( self.suite, self.run_mode,
                                        self.start_point, self.stop_point )

            run_dir = sitecfg.get_derived_host_item( self.suite, 'suite run directory' )
            if not self.is_restart:     # create new suite_db file (and dir) if needed
                self.db = cylc.rundb.CylcRuntimeDAO(suite_dir=run_dir, new_mode=True)
            else:
                self.db = cylc.rundb.CylcRuntimeDAO(suite_dir=run_dir)

            self.hold_suite_now = False
            self.hold_time = None
            if self.options.hold_time:
                self.hold_time = get_point( self.options.hold_time )

        # USE LOCKSERVER?
        self.use_lockserver = self.config.cfg['cylc']['lockserver']['enable']
        self.lockserver_port = None
        if self.use_lockserver:
            # check that user is running a lockserver
            # DO THIS BEFORE CONFIGURING PYRO FOR THE SUITE
            # (else scan etc. will hang on the partially started suite).
            # raises port_scan.SuiteNotFound error:
            self.lockserver_port = lockserver( self.host ).get_port()

        # ALLOW MULTIPLE SIMULTANEOUS INSTANCES?
        self.exclusive_suite_lock = not self.config.cfg['cylc']['lockserver']['simultaneous instances']

        # Running in UTC time? (else just use the system clock)
        flags.utc = self.config.cfg['cylc']['UTC mode']

        # Capture cycling mode
        flags.cycling_mode = self.config.cfg['scheduling']['cycling mode']

        if not reconfigure:
            slog = suite_log( self.suite )
            self.suite_log_dir = slog.get_dir()
            slog.pimp( self.logging_level )
            self.log = slog.get_log()
            self.logfile = slog.get_path()

            self.command_queue = comqueue( self.control_commands.keys() )
            self.pyro.connect( self.command_queue, 'command-interface' )

            self.proc_pool = mp_pool( self.config.cfg['cylc']['process pool size'])
            task.task.proc_pool = self.proc_pool

            self.info_interface = info_interface( self.info_commands )
            self.pyro.connect( self.info_interface, 'suite-info' )

            self.log_interface = log_interface( slog )
            self.pyro.connect( self.log_interface, 'log' )

            self.log.info( "port:" +  str( self.port ))

    def configure_suite_environment( self ):
        # static cylc and suite-specific variables:
        self.suite_env = {
                'CYLC_UTC'               : str(flags.utc),
                'CYLC_CYCLING_MODE'      : str(flags.cycling_mode),
                'CYLC_MODE'              : 'scheduler',
                'CYLC_DEBUG'             : str( flags.debug ),
                'CYLC_VERBOSE'           : str( flags.verbose ),
                'CYLC_USE_LOCKSERVER'    : str( self.use_lockserver ),
                'CYLC_LOCKSERVER_PORT'   : str( self.lockserver_port ), # "None" if not using lockserver
                'CYLC_DIR_ON_SUITE_HOST' : os.environ[ 'CYLC_DIR' ],
                'CYLC_SUITE_NAME'        : self.suite,
                'CYLC_SUITE_REG_NAME'    : self.suite, # DEPRECATED
                'CYLC_SUITE_HOST'        : str( self.host ),
                'CYLC_SUITE_OWNER'       : self.owner,
                'CYLC_SUITE_PORT'        :  str( self.pyro.get_port()),
                'CYLC_SUITE_REG_PATH'    : RegPath( self.suite ).get_fpath(), # DEPRECATED
                'CYLC_SUITE_DEF_PATH_ON_SUITE_HOST' : self.suite_dir,
                'CYLC_SUITE_INITIAL_CYCLE_POINT' : str( self.start_point ), # may be "None"
                'CYLC_SUITE_FINAL_CYCLE_POINT'   : str( self.stop_point ), # may be "None"
                'CYLC_SUITE_INITIAL_CYCLE_TIME' : str( self.start_point ), # may be "None"
                'CYLC_SUITE_FINAL_CYCLE_TIME'   : str( self.stop_point ), # may be "None"
                'CYLC_SUITE_LOG_DIR'     : self.suite_log_dir # needed by the test battery
                }

        # Contact details for remote tasks, written to file on task
        # hosts because the details can change on restarting a suite.
        self.suite_contact_env = {
                'CYLC_SUITE_NAME'        : self.suite_env['CYLC_SUITE_NAME' ],
                'CYLC_SUITE_HOST'        : self.suite_env['CYLC_SUITE_HOST' ],
                'CYLC_SUITE_OWNER'       : self.suite_env['CYLC_SUITE_OWNER'],
                'CYLC_SUITE_PORT'        : self.suite_env['CYLC_SUITE_PORT' ],
                }

        # Set local values of variables that are potenitally task-specific
        # due to different directory paths on different task hosts. These
        # are overridden by tasks prior to job submission, but in
        # principle they could be needed locally by event handlers:
        self.suite_task_env = {
                'CYLC_SUITE_RUN_DIR'    : sitecfg.get_derived_host_item( self.suite, 'suite run directory' ),
                'CYLC_SUITE_WORK_DIR'   : sitecfg.get_derived_host_item( self.suite, 'suite work directory' ),
                'CYLC_SUITE_SHARE_DIR'  : sitecfg.get_derived_host_item( self.suite, 'suite share directory' ),
                'CYLC_SUITE_SHARE_PATH' : '$CYLC_SUITE_SHARE_DIR', # DEPRECATED
                'CYLC_SUITE_DEF_PATH'   : self.suite_dir
                }
        # (note global config automatically expands environment variables in local paths)

        # Pass these to the job script generation code.
        jobfile.jobfile.suite_env = self.suite_env
        jobfile.jobfile.suite_task_env = self.suite_task_env
        # And pass contact env to the task module
        task.task.suite_contact_env = self.suite_contact_env

        # make suite vars available to [cylc][environment]:
        for var, val in self.suite_env.items():
            os.environ[var] = val
        for var, val in self.suite_task_env.items():
            os.environ[var] = val
        cenv = self.config.cfg['cylc']['environment']
        for var, val in cenv.items():
            cenv[var] = os.path.expandvars(val)
        # path to suite bin directory for suite and task event handlers
        cenv['PATH'] = self.suite_dir + '/bin:' + os.environ['PATH']

        # make [cylc][environment] available to task event handlers in worker processes
        task.task.event_handler_env = cenv
        # make [cylc][environment] available to suite event handlers in this process
        for var, val in cenv.items():
            os.environ[var] = val

    def configure_reftest( self, recon=False ):
        if self.gen_reference_log:
            self.config.cfg['cylc']['log resolved dependencies'] = True

        elif self.reference_test_mode:
            req = self.config.cfg['cylc']['reference test']['required run mode']
            if req and req != self.run_mode:
                raise SchedulerError, 'ERROR: this suite allows only ' + req + ' mode reference tests'
            handlers = self.config.cfg['cylc']['event hooks']['shutdown handler']
            if handlers:
                print >> sys.stderr, 'WARNING: replacing shutdown event handlers for reference test run'
            self.config.cfg['cylc']['event hooks']['shutdown handler'] = [ self.config.cfg['cylc']['reference test']['suite shutdown event handler'] ]
            self.config.cfg['cylc']['log resolved dependencies'] = True
            self.config.cfg['cylc']['event hooks']['abort if shutdown handler fails'] = True
            if not recon:
                spec = LogSpec( self.reflogfile )
                self.start_point = get_point( spec.get_start_string() )
                self.stop_point = get_point( spec.get_stop_string() )
            self.ref_test_allowed_failures = self.config.cfg['cylc']['reference test']['expected task failures']
            if not self.config.cfg['cylc']['reference test']['allow task failures'] and len( self.ref_test_allowed_failures ) == 0:
                self.config.cfg['cylc']['abort if any task fails'] = True
            self.config.cfg['cylc']['event hooks']['abort on timeout'] = True
            timeout = self.config.cfg['cylc']['reference test'][ self.run_mode + ' mode suite timeout' ]
            if not timeout:
                raise SchedulerError, 'ERROR: suite timeout not defined for ' + self.run_mode + ' mode reference test'
            self.config.cfg['cylc']['event hooks']['timeout'] = timeout
            self.config.cfg['cylc']['event hooks']['reset timer'] = False

    def run_event_handlers( self, name, fg, msg ):
        if self.run_mode != 'live' or \
                ( self.run_mode == 'simulation' and \
                        self.config.cfg['cylc']['simulation mode']['disable suite event hooks'] ) or \
                ( self.run_mode == 'dummy' and \
                        self.config.cfg['cylc']['dummy mode']['disable suite event hooks'] ):
            return
 
        handlers = self.config.cfg['cylc']['event hooks'][name + ' handler']
        if handlers:
            for handler in handlers:
                try:
                    RunHandler( name, handler, self.suite, msg=msg, fg=fg )
                except Exception, x:
                    # Note: test suites depends on this message:
                    print >> sys.stderr, '\nERROR: ' + name + ' EVENT HANDLER FAILED'
                    raise SchedulerError, x
                    if name == 'shutdown' and self.reference_test_mode:
                            sys.exit( '\nERROR: SUITE REFERENCE TEST FAILED' )
                else:
                    if name == 'shutdown' and self.reference_test_mode:
                        # TODO - this isn't true, it just means the
                        # shutdown handler run successfully:
                        print '\nSUITE REFERENCE TEST PASSED'

    def run( self ):

        if self.use_lockserver:
            # request suite access from the lock server
            if suite_lock( self.suite, self.suite_dir, self.host, self.lockserver_port, 'scheduler' ).request_suite_access( self.exclusive_suite_lock ):
               self.lock_acquired = True
            else:
               raise SchedulerError( "Failed to acquire a suite lock" )

        if self.hold_time:
            # TODO - HANDLE STOP AND PAUSE TIMES THE SAME WAY?
            self.hold_suite( self.hold_time )

        if self.options.start_held:
            self.log.info( "Held on start-up (no tasks will be submitted)")
            self.hold_suite()

        abort = self.config.cfg['cylc']['event hooks']['abort if startup handler fails']
        self.run_event_handlers( 'startup', abort, 'suite starting' )

        while True: # MAIN LOOP
            # PROCESS ALL TASKS whenever something has changed that might
            # require renegotiation of dependencies, etc.

            if self.shut_down_now:
                warned = False
                while not self.proc_pool.is_dead():
                    self.proc_pool.handle_results_async()
                    if not warned:
                        print "Waiting for the command process pool to empty for shutdown"
                        print "(you can \"stop now\" to shut down immediately if you like)."
                        warned = True
                    self.process_command_queue()
                    time.sleep(0.5)
                raise SchedulerStop("Finished")

            t0 = time.time()

            if self.pool.reconfiguring:
                # suite definition reload still in progress
                self.pool.reload_taskdefs()

            self.pool.release_runahead_tasks()

            self.proc_pool.handle_results_async()

            if self.process_tasks():
                if flags.debug:
                    self.log.debug( "BEGIN TASK PROCESSING" )
                    main_loop_start_time = time.time()

                self.pool.match_dependencies()

                ready = self.pool.process()
                self.process_resolved( ready )

                self.pool.spawn_tasks()

                self.pool.remove_spent_tasks()

                self.state_dumper.dump()

                self.do_update_state_summary = True

                self.pool.wireless.expire( self.pool.get_min_ctime() )

                if flags.debug:
                    seconds = time.time() - main_loop_start_time
                    self.log.debug( "END TASK PROCESSING (took " + str( seconds ) + " sec)" )

            self.pool.process_queued_task_messages()

            self.process_command_queue()

            if flags.iflag or self.do_update_state_summary:
                flags.iflag = False
                self.do_update_state_summary = False
                self.update_state_summary()

            if self.config.cfg['cylc']['event hooks']['timeout']:
                self.check_suite_timer()

            if self.config.cfg['cylc']['abort if any task fails']:
                if self.pool.any_task_failed():
                    raise SchedulerError( 'One or more tasks failed and "abort if any task fails" is set' )

            # the run is a reference test, and unexpected failures occured
            if self.reference_test_mode:
                if len( self.ref_test_allowed_failures ) > 0:
                    for itask in self.pool.get_failed_tasks():
                        if itask.id not in self.ref_test_allowed_failures:
                            print >> sys.stderr, itask.id
                            raise SchedulerError( 'A task failed unexpectedly: not in allowed failures list' )

            # check submission and execution timeout and polling timers
            if self.run_mode != 'simulation':
                self.pool.check_task_timers()

            if (self.stop_clock_done() or
                    self.stop_task_done() or 
                    self.pool.check_stop()):
                self.command_set_stop_cleanly()

            if ((self.shut_down_cleanly and self.pool.no_active_tasks()) or 
                    self.shut_down_quickly or self.pool.check_stop()):
                self.shut_down_now = True

            if self.options.profile_mode:
                t1 = time.time()
                self._update_profile_info("scheduler loop dt (s)", t1 - t0,
                                          amount_format="%.3f")
                self._update_cpu_usage()
                self._update_profile_info("jobqueue.qsize", float(self.pool.jobqueue.qsize()),
                                          amount_format="%.1f")

            time.sleep(1)

        # END MAIN LOOP

    def update_state_summary(self):
        self.suite_state.update(
                self.pool.get_tasks(), 
                self.pool.get_min_ctime(), self.pool.get_max_ctime(),
                self.paused(),
                self.will_pause_at(),
                (self.shut_down_cleanly or self.shut_down_quickly),
                self.will_stop_at(), self.pool.custom_runahead_limit,
                self.config.ns_defn_order)

    def process_resolved(self, tasks):
        # process resolved dependencies (what actually triggers off what
        # at run time). Note 'triggered off' means 'prerequisites
        # satisfied by', but necessarily 'started running' too.
        for itask in tasks:
            if self.config.cfg['cylc']['log resolved dependencies']:
                itask.log( 'NORMAL', 'triggered off ' + str( itask.get_resolved_dependencies()) )

    def check_suite_timer( self ):
        if self.already_timed_out:
            return
        if time.time() > self.suite_timer_timeout:
            self.already_timed_out = True
            message = 'suite timed out after %s' % (
                get_seconds_as_interval_string(
                    self.config.cfg['cylc']['event hooks']['timeout'])
            )
            self.log.warning( message )
            abort = self.config.cfg['cylc']['event hooks']['abort if timeout handler fails']
            self.run_event_handlers( 'timeout', abort, message )
            if self.config.cfg['cylc']['event hooks']['abort on timeout']:
                raise SchedulerError, 'Abort on suite timeout is set'

    def process_tasks( self ):
        # do we need to do a pass through the main task processing loop?
        process = False

        if self.do_process_tasks:
            # this flag is turned on by commands that change task state
            process = True
            self.do_process_tasks = False # reset

        if flags.pflag:
            process = True
            flags.pflag = False # reset
            # a task changing state indicates new suite activity
            # so reset the suite timer.
            if self.config.cfg['cylc']['event hooks']['timeout'] and self.config.cfg['cylc']['event hooks']['reset timer']:
                self.set_suite_timer()

        elif self.pool.waiting_tasks_ready():
            process = True

        elif self.run_mode == 'simulation':
            process = self.pool.sim_time_check()

        ##if not process:
        ##    # If we neglect to set flags.pflag on some event that
        ##    # makes re-negotiation of dependencies necessary then if
        ##    # that event ever happens in isolation the suite could stall
        ##    # unless manually nudged ("cylc nudge SUITE").  If this
        ##    # happens turn on debug logging to see what happens
        ##    # immediately before the stall, then set flags.pflag = True in
        ##    # the corresponding code section. Alternatively,
        ##    # for an undiagnosed stall you can uncomment this section to
        ##    # stimulate task processing every few seconds even during
        ##    # lulls in activity.  THIS SHOULD NOT BE NECESSARY, HOWEVER.
        ##    if not self.nudge_timer_on:
        ##        self.nudge_timer_start = now()
        ##        self.nudge_timer_on = True
        ##    else:
        ##        timeout = self.nudge_timer_start + \
        ##              datetime.timedelta( seconds=self.auto_nudge_interval )
        ##      if now() > timeout:
        ##          process = True
        ##          self.nudge_timer_on = False

        return process

    def shutdown( self, reason='' ):
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
            shcopy( self.logfile, self.reflogfile)

        if self.proc_pool:
            if not self.proc_pool.is_dead():
                # e.g. KeyboardInterrupt
                self.proc_pool.terminate()
            self.proc_pool.join()
            self.proc_pool.handle_results_async()

        if self.pool:
            self.pool.shutdown()
            if self.state_dumper:
                try:
                    self.state_dumper.dump()
                except (OSError, IOError) as exc:
                    # (see comments in the state dumping module)
                    # ignore errors here in order to shut down cleanly
                    self.log.warning( 'Final state dump failed: ' + str(exc) )
                    pass

        if self.request_handler:
            self.request_handler.quit = True
            self.request_handler.join()

        for i in [ self.command_queue, self.suite_id, self.suite_state ]:
            if i:
                self.pyro.disconnect( i )

        if self.pyro:
            self.pyro.shutdown()

        if getattr(self, "use_lockserver", None):
            if self.lock_acquired:
                lock = suite_lock( self.suite, self.suite_dir, self.host, self.lockserver_port, 'scheduler' )
                try:
                    if not lock.release_suite_access():
                        print >> sys.stderr, 'WARNING failed to release suite lock!'
                except port_scan.SuiteIdentificationError, x:
                    print >> sys.stderr, x
                    print >> sys.stderr, 'WARNING failed to release suite lock!'

        try:
            self.port_file.unlink()
        except PortFileError, x:
            # port file may have been deleted
            print >> sys.stderr, x

        # disconnect from suite-db, stop db queue
        if getattr(self, "db", None) is not None:
            self.db.close()

        if getattr(self, "config", None) is not None:
            # run shutdown handlers
            abort = self.config.cfg['cylc']['event hooks']['abort if shutdown handler fails']
            self.run_event_handlers( 'shutdown', abort, reason )

        print "DONE" # main thread exit

    def set_stop_ctime( self, stop_string ):
        self.stop_point = get_point(stop_string)
        try:
            self.stop_point.standardise()
        except PointParsingError as exc:
            self.log.critical(
                "Cannot set stop cycle point: %s: %s" % (stop_string, exc))
            return
        self.log.info( "Setting stop cycle point: %s" % stop_string )
        self.pool.set_stop_point(self.stop_point)

    def set_stop_clock( self, unix_time, date_time_string ):
        self.log.info( "Setting stop clock time: %s (unix time: %s)" % (
                           date_time_string, unix_time))
        self.stop_clock_time = unix_time
        self.stop_clock_time_string = date_time_string

    def set_stop_task(self, taskid):
        name, tag = TaskID.split(taskid)
        if name in self.config.get_task_name_list():
            self.log.info("Setting stop task: " + taskid)
            self.stop_task = taskid
        else:
            self.log.warning("Requested stop task name does not exist: " + name)

    def stop_task_done(self):
        """Return True if stop task has succeeded."""
        id = self.stop_task
        if (id is None or not self.pool.task_succeeded(id)):
            return False
        self.log.info("Stop task " + id + " finished")
        return True

    def hold_suite( self, ctime = None ):
        if ctime:
            self.log.info( "Setting suite hold cycle point: " + ctime )
            self.hold_time = ctime
        else:
            self.hold_suite_now = True
            self.pool.hold_all_tasks()

    def release_suite( self ):
        if self.hold_suite_now:
            self.log.info( "RELEASE: new tasks will be queued when ready")
            self.hold_suite_now = False
            self.hold_time = None
        self.pool.release_all_tasks()

    def will_stop_at( self ):
        if self.stop_point:
            return str(self.stop_point)
        elif self.stop_clock_time is not None:
            return self.stop_clock_time_description
        elif self.stop_task:
            return self.stop_task
        else:
            return None

    def clear_stop_times( self ):
        self.stop_point = None
        self.stop_clock_time = None
        self.stop_clock_time_description = None
        self.stop_task = None

    def paused( self ):
        return self.hold_suite_now

    def stopping( self ):
        if self.stop_point is not None or self.stop_clock_time is not None:
            return True
        else:
            return False

    def will_pause_at( self ):
        return self.hold_time

    def command_trigger_task( self, name, tag, is_family ):
        matches = self.get_matching_tasks( name, is_family )
        if not matches:
            raise TaskNotFoundError, "No matching tasks found: " + name
        task_ids = [ TaskID.get(i,tag) for i in matches ]
        self.pool.trigger_tasks( task_ids )

    def get_matching_tasks( self, name, is_family=False ):
        """name can be a task or family name, or a regex to match
        multiple tasks or families."""

        matches = []
        tasks = self.config.get_task_name_list()

        if is_family:
            families = self.config.runtime['first-parent descendants']
            try:
                # exact
                f_matches = families[name]
            except KeyError:
                # regex match
                for fam, mems in families.items():
                    if re.match( name, fam ):
                        f_matches += mems
            matches = []
            for m in f_matches:
                if m in tasks:
                    matches.append(m)

        else:
            if name in tasks:
                # exact
                matches.append(name)
            else:
                # regex match
                for task in tasks:
                    if re.match( name, task ):
                        matches.append(task)
        return matches

    def command_reset_task_state( self, name, tag, state, is_family ):
        matches = self.get_matching_tasks( name, is_family )
        if not matches:
            raise TaskNotFoundError, "No matching tasks found: " + name
        task_ids = [ TaskID.get(i,tag) for i in matches ]
        self.pool.reset_task_states( task_ids, state )

    def command_add_prerequisite( self, task_id, message ):
        self.pool.add_prereq_to_task( task_id, message )

    def command_purge_tree( self, id, stop ):
        self.pool.purge_tree( id, get_point(stop) )

    def filter_initial_task_list( self, inlist ):
        included_by_rc  = self.config.cfg['scheduling']['special tasks']['include at start-up']
        excluded_by_rc  = self.config.cfg['scheduling']['special tasks']['exclude at start-up']
        outlist = []
        for name in inlist:
            if name in excluded_by_rc:
                continue
            if len( included_by_rc ) > 0:
                if name not in included_by_rc:
                    continue
            outlist.append( name )
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
        self.log.info( output_text )

    def _update_cpu_usage(self):
        p = subprocess.Popen(["ps", "-o%cpu= ", str(os.getpid())], stdout=subprocess.PIPE)
        try:
            cpu_frac = float(p.communicate()[0])
        except (TypeError, OSError, IOError, ValueError) as e:
            self.log.warning( "Cannot get CPU % statistics: %s" % e )
            return
        self._update_profile_info("CPU %", cpu_frac, amount_format="%.1f")

