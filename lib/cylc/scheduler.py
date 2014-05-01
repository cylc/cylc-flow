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
from prerequisites.plain_prerequisites import plain_prerequisites
from suite_host import get_suite_host
from owner import user
from shutil import copy as shcopy
from copy import deepcopy
from cycle_time import ct, CycleTimeError, ctime_ge, ctime_gt, ctime_lt, ctime_le
import datetime, time
import port_scan
import logging
import re, os, sys, shutil
from state_summary import state_summary
from passphrase import passphrase
from locking.lockserver import lockserver
from locking.suite_lock import suite_lock
from suite_id import identifier
from config import config, SuiteConfigError, TaskNotDefinedError
from cfgspec.site import sitecfg
from port_file import port_file, PortFileExistsError, PortFileError
from broker import broker
from regpath import RegPath
from CylcError import TaskNotFoundError, TaskStateError
from RunEventHandler import RunHandler
from LogDiagnosis import LogSpec
from broadcast import broadcast
from suite_state_dumping import dumper
from suite_logging import suite_log
import threading
from suite_cmd_interface import comqueue
from suite_info_interface import info_interface
from suite_log_interface import log_interface
from TaskID import TaskID, TaskIDError
from task_pool import pool
import flags
import cylc.rundb
from Queue import Queue, Empty
from batch_submit import event_batcher, poll_and_kill_batcher
import subprocess
from wallclock import now


class result:
    """TODO - GET RID OF THIS - ONLY USED BY INFO COMMANDS"""
    def __init__( self, success, reason="Action succeeded", value=None ):
        self.success = success
        self.reason = reason
        self.value = value


class SchedulerError( Exception ):
    """
    Attributes:
        message - what the problem is.
        TODO - element - config element causing the problem
    """
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)


class request_handler( threading.Thread ):
    def __init__( self, pyro ):
        threading.Thread.__init__(self)
        self.pyro = pyro
        self.quit = False
        self.log = logging.getLogger( 'main' )
        self.log.info(  str(self.getName()) + " start (Request Handling)")

    def run( self ):
        while True:
            self.pyro.handleRequests(timeout=1)
            if self.quit:
                break
        self.log.info(  str(self.getName()) + " exit (Request Handling)")


class scheduler(object):

    def __init__( self, is_restart=False ):

        # SUITE OWNER
        self.owner = user

        # SUITE HOST
        self.host= get_suite_host()

        # DEPENDENCY BROKER
        self.broker = broker()

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
        self.wireless = None
        self.suite_state = None
        self.command_queue = None
        self.pool = None
        self.eventq_worker = None
        self.pollkq_worker = None
        self.request_handler = None
        self.pyro = None
        self.state_dumper = None
        self.runtime_graph_on = None

        self._profile_amounts = {}
        self._profile_update_times = {}

        self.held_future_tasks = []

        # provide a variable to allow persistance of reference test settings
        # across reloads
        self.reference_test_mode = False
        self.gen_reference_log = False

        self.do_shutdown = None
        self.threads_stopped = False

        self.stop_task = None
        self.stop_clock_time = None

        self.start_tag = None
        self.stop_tag = None
        self.cli_start_tag = None

        self.parser.add_option( "--until",
                help="Shut down after all tasks have PASSED this cycle time.",
                metavar="CYCLE", action="store", dest="stop_tag" )

        self.parser.add_option( "--hold", help="Hold (don't run tasks) "
                "immediately on starting.",
                action="store_true", default=False, dest="start_held" )

        self.parser.add_option( "--hold-after",
                help="Hold (don't run tasks) AFTER this cycle time.",
                metavar="CYCLE", action="store", dest="hold_time" )

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
                'ping suite'        : self.info_ping,
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
                'stop cleanly'          : self.command_stop_cleanly,
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
        self.log.info( 'Suite starting at ' + str( now()) )
        if self.run_mode == 'live':
            self.log.info( 'Log event clock: real time' )
        else:
            self.log.info( 'Log event clock: accelerated' )
        self.log.info( 'Run mode: ' + self.run_mode )
        self.log.info( 'Start tag: ' + str(self.start_tag) )
        self.log.info( 'Stop tag: ' + str(self.stop_tag) )

        self.runahead_limit = self.config.get_runahead_limit()
        self.asynchronous_task_list = self.config.get_asynchronous_task_name_list()

        # RECEIVER FOR BROADCAST VARIABLES
        self.wireless = broadcast( self.config.get_linearized_ancestors() )
        self.state_dumper.wireless = self.wireless
        self.pyro.connect( self.wireless, 'broadcast_receiver')

        self.pool = pool( self.suite, self.config, self.wireless, self.pyro, self.log, self.run_mode )
        self.state_dumper.pool = self.pool
        self.request_handler = request_handler( self.pyro )
        self.request_handler.start()

        # LOAD TASK POOL ACCORDING TO STARTUP METHOD
        self.old_user_at_host_set = set()
        self.load_tasks()
        self.initial_oldest_ctime = self.get_oldest_c_time()

        # REMOTELY ACCESSIBLE SUITE STATE SUMMARY
        self.suite_state = state_summary( self.config, self.run_mode, self.initial_oldest_ctime )
        self.pyro.connect( self.suite_state, 'state_summary')

        self.state_dumper.set_cts( self.start_tag, self.stop_tag )
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

        self.runtime_graph_on = False
        if self.config.cfg['visualization']['runtime graph']['enable']:
            try:
                from RuntimeGraph import rGraph
            except ImportError, x:
                # this imports pygraphviz via cylc.graphing
                print >> sys.stderr, str(x)
                print >> sys.stderr, "WARNING: runtime graphing disabled, please install pygraphviz."
            else:
                self.runtime_graph_on = True
                self.runtime_graph = rGraph( self.suite, self.config, self.initial_oldest_ctime, self.start_tag )

        self.orphans = []
        self.reconfiguring = False

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
            except Exception, x:
                # don't let a bad command bring the suite down
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
            name, tag = name.split(TaskID.DELIM)
        if name in self.config.get_task_name_list():
            return True
        else:
            return False

    #_________INFO_COMMANDS_____________________________________________

    def info_ping( self ):
        return result( True )

    def info_ping_task( self, task_id ):
        # is this task running at the moment
        found = False
        running = False
        for itask in self.pool.get_tasks():
            if itask.id == task_id:
                found = True
                if itask.state.is_currently('running'):
                    running = True
                break
        if not found:
            return result( False, "Task not found: " + task_id )
        elif not running:
            return result( False, task_id + " is not currently running" )
        else:
            return result( True, task_id + " is currently running" )

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
        return ( self.config.cfg['visualization']['enable live graph movie'],
                 self.config.cfg['visualization']['runtime graph']['directory'] )

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
        in_ids_real = {}
        in_ids_back = {}
        for in_id in in_ids:
            if not self._task_type_exists( in_id ):
                continue
            real_id = in_id
            in_ids_real[ in_id ] = real_id
            in_ids_back[ real_id ] = in_id

        dump = {}
        found = False
        for itask in self.pool.get_tasks():
            # loop through the suite task list
            task_id = itask.id
            if task_id in in_ids_back:
                found = True
                extra_info = {}
                # extra info for clocktriggered tasks
                try:
                    extra_info[ 'Delayed start time reached' ] = itask.start_time_reached()
                    extra_info[ 'Triggers at' ] = 'T+' + str(itask.real_time_delay) + ' hours'
                except AttributeError:
                    # not a clocktriggered task
                    pass
                # extra info for cycling tasks
                try:
                    extra_info[ 'Valid cycles' ] = itask.valid_hours
                except AttributeError:
                    # not a cycling task
                    pass

                dump[ in_ids_back[ task_id ] ] = [ itask.prerequisites.dump(), itask.outputs.dump(), extra_info ]
        if not found:
            self.log.warning( 'task state info request: tasks not found' )
        else:
            return dump

     # CONTROL_COMMANDS__________________________________________________

    def command_stop_cleanly( self, kill_first=False ):
        self.pool.worker.request_stop( empty_before_exit=False )
        if kill_first:
            for itask in self.pool.get_tasks():
                if itask.state.is_currently( 'submitted', 'running' ):
                    itask.kill()
        self.do_shutdown = 'clean'
        self.threads_stopped = False

    def command_stop_quickly( self ):
        self.pool.worker.request_stop( empty_before_exit=False )
        self.do_shutdown = 'quick'
        self.threads_stopped = False

    def command_stop_now( self ):
        self.pool.worker.request_stop( empty_before_exit=False )
        self.do_shutdown = 'now'
        self.threads_stopped = False

    def command_set_stop_after_tag( self, tag ):
        self.set_stop_ctime( tag )

    def command_set_stop_after_clock_time( self, arg ):
        # format: YYYY/MM/DD-HH:mm
        sdate, stime = arg.split('-')
        yyyy, mm, dd = sdate.split('/')
        HH,MM = stime.split(':')
        dtime = datetime.datetime( int(yyyy), int(mm), int(dd), int(HH), int(MM) )
        self.set_stop_clock( dtime )

    def command_set_stop_after_task( self, tid ):
        tid = TaskID( tid )
        arg = tid.getstr()
        self.set_stop_task( arg )

    def command_release_task( self, name, tag, is_family ):
        matches = self.get_matching_tasks( name, is_family )
        if not matches:
            raise TaskNotFoundError, "No matching tasks found: " + name
        task_ids = [ i + TaskID.DELIM + tag for i in matches ]

        for itask in self.pool.get_tasks():
            if itask.id in task_ids:
                if itask.state.is_currently('held'):
                    itask.reset_state_waiting()

    def command_poll_tasks( self, name, tag, is_family ):
        matches = self.get_matching_tasks( name, is_family )
        if not matches:
            raise TaskNotFoundError, "No matching tasks found: " + name
        task_ids = [ i + TaskID.DELIM + tag for i in matches ]

        for itask in self.pool.get_tasks():
            if itask.id in task_ids:
                # (state check done in task module)
                itask.poll()

    def command_kill_tasks( self, name, tag, is_family ):
        matches = self.get_matching_tasks( name, is_family )
        if not matches:
            raise TaskNotFoundError, "No matching tasks found: " + name
        task_ids = [ i + TaskID.DELIM + tag for i in matches ]

        for itask in self.pool.get_tasks():
            if itask.id in task_ids:
                # (state check done in task module)
                itask.kill()

    def command_release_suite( self ):
        self.release_suite()

    def command_hold_task( self, name, tag, is_family ):
        matches = self.get_matching_tasks( name, is_family )
        if not matches:
            raise TaskNotFoundError, "No matching tasks found: " + name
        task_ids = [ i + TaskID.DELIM + tag for i in matches ]

        for itask in self.pool.get_tasks():
            if itask.id in task_ids:
                if itask.state.is_currently('waiting', 'queued', 'submit-retrying', 'retrying' ):
                    itask.reset_state_held()

    def command_hold_suite( self ):
        self.hold_suite()

    def command_hold_after_tag( self, tag ):
        """TODO - not currently used, add to the cylc hold command"""
        self.hold_suite( tag )
        self.log.info( "The suite will pause when all tasks have passed " + tag )

    def command_set_runahead( self, hours=None ):
        if hours:
            self.log.info( "setting runahead limit to " + str(hours) )
            self.runahead_limit = int(hours)
        else:
            # No limit
            self.log.warning( "setting NO runahead limit" )
            self.runahead_limit = None

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
            return result( False, "Illegal logging level: " + level)

        self.log.setLevel( new_level )

        flags.debug = ( level == 'debug' )
        return result(True, 'OK')

    def command_remove_cycle( self, tag, spawn ):
        for itask in self.pool.get_tasks():
            if itask.tag == tag:
                if spawn:
                    self.force_spawn( itask )
                self.pool.remove( itask, 'by request' )

    def command_remove_task( self, name, tag, is_family, spawn ):
        matches = self.get_matching_tasks( name, is_family )
        if not matches:
            raise TaskNotFoundError, "No matching tasks found: " + name
        task_ids = [ i + TaskID.DELIM + tag for i in matches ]
        for itask in self.pool.get_tasks():
            if itask.id in task_ids:
                if spawn:
                    self.force_spawn( itask )
                self.pool.remove( itask, 'by request' )

    def command_insert_task( self, name, tag, is_family, stop_tag ):
        matches = self.get_matching_tasks( name, is_family )
        if not matches:
            raise TaskNotFoundError, "No matching tasks found: " + name
        task_ids = [ i + TaskID.DELIM + tag for i in matches ]

        for task_id in task_ids:
            name, tag = task_id.split( TaskID.DELIM )
            # TODO - insertion of start-up tasks? (startup=False is assumed here)
            new_task = self.config.get_task_proxy( name, tag, 'waiting', stop_tag, startup=False, submit_num=self.db.get_task_current_submit_num(name, tag), exists=self.db.get_task_state_exists(name, tag))
            self.add_new_task_proxy( new_task )

    def command_nudge( self ):
        # just to cause the task processing loop to be invoked
        pass

    def command_reload_suite( self ):
        self.reconfigure()

    #___________________________________________________________________

    def set_suite_timer( self, reset=False ):
        ts = now()
        self.suite_timer_start = ts
        print str(self.config.cfg['cylc']['event hooks']['timeout']) + " minute suite timer starts NOW:", str(ts)

    def reconfigure( self ):
        print "RELOADING the suite definition"
        old_task_list = self.config.get_task_name_list()
        self.configure_suite( reconfigure=True )
        new_task_list = self.config.get_task_name_list()

        # find any old tasks that have been removed from the suite
        self.orphans = []
        for name in old_task_list:
            if name not in new_task_list:
                self.orphans.append(name)
        # adjust the new suite config to handle the orphans
        self.config.adopt_orphans( self.orphans )

        self.runahead_limit = self.config.get_runahead_limit()
        self.asynchronous_task_list = self.config.get_asynchronous_task_name_list()
        self.pool.qconfig = self.config.cfg['scheduling']['queues']
        self.pool.assign( reload=True )
        self.suite_state.config = self.config
        self.configure_suite_environment()
        self.reconfiguring = True
        for itask in self.pool.get_tasks():
            itask.reconfigure_me = True

        if self.gen_reference_log or self.reference_test_mode:
            self.configure_reftest(recon=True)

        # update state dumper state
        self.state_dumper.set_cts( self.start_tag, self.stop_tag )

    def reload_taskdefs( self ):
        found = False
        for itask in self.pool.get_tasks():
            if itask.state.is_currently('submitted','running'):
                # do not reload active tasks as it would be possible to
                # get a task proxy incompatible with the running task
                if itask.reconfigure_me:
                    found = True
                continue
            if itask.reconfigure_me:
                itask.reconfigure_me = False
                if itask.name in self.orphans:
                    # orphaned task
                    if itask.state.is_currently('waiting', 'queued', 'submit-retrying', 'retrying'):
                        # if not started running yet, remove it.
                        self.pool.remove( itask, '(task orphaned by suite reload)' )
                    else:
                        # set spawned already so it won't carry on into the future
                        itask.state.set_spawned()
                        self.log.warning( 'orphaned task will not continue: ' + itask.id  )
                else:
                    self.log.info( 'RELOADING TASK DEFINITION FOR ' + itask.id  )
                    new_task = self.config.get_task_proxy( itask.name, itask.tag, itask.state.get_status(), None, itask.startup, submit_num=self.db.get_task_current_submit_num(itask.name, itask.tag), exists=self.db.get_task_state_exists(itask.name, itask.tag) )
                    # set reloaded task's spawn status
                    if itask.state.has_spawned():
                        new_task.state.set_spawned()
                    else:
                        new_task.state.set_unspawned()
                    # succeeded tasks need their outputs set completed:
                    if itask.state.is_currently('succeeded'):
                        new_task.reset_state_succeeded(manual=False)

                    # carry some task proxy state over to the new instance
                    new_task.summary = itask.summary
                    new_task.started_time = itask.started_time
                    new_task.submitted_time = itask.submitted_time
                    new_task.succeeded_time = itask.succeeded_time
                    new_task.etc = itask.etc

                    # if currently retrying, retain the old retry delay
                    # list, to avoid extra retries (the next instance
                    # of the task will still be as newly configured)
                    if itask.state.is_currently( 'retrying' ):
                        new_task.retry_delay = itask.retry_delay
                        new_task.retry_delays = itask.retry_delays
                        new_task.retry_delay_timer_start = itask.retry_delay_timer_start
                    elif itask.state.is_currently( 'submit-retrying' ):
                        new_task.sub_retry_delay = itask.sub_retry_delay
                        new_task.sub_retry_delays = itask.sub_retry_delays
                        new_task.sub_retry_delays_orig = itask.sub_retry_delays_orig
                        new_task.sub_retry_delay_timer_start = itask.sub_retry_delay_timer_start

                    new_task.try_number = itask.try_number
                    new_task.sub_try_number = itask.sub_try_number
                    new_task.submit_num = itask.submit_num

                    self.pool.remove( itask, '(suite definition reload)' )
                    self.add_new_task_proxy( new_task )

        self.reconfiguring = found

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

        self.config = config( self.suite, self.suiterc,
                self.options.templatevars,
                self.options.templatevars_file, run_mode=self.run_mode,
                cli_start_tag=self.cli_start_tag,
                is_restart=self.is_restart, is_reload=reconfigure)

        # Initial and final cycle times - command line takes precedence
        self.start_tag = self.cli_start_tag or self.config.cfg['scheduling']['initial cycle time']
        self.stop_tag = self.options.stop_tag or self.config.cfg['scheduling']['final cycle time']
        if self.start_tag:
            self.start_tag = ct(self.start_tag).get()
        if self.stop_tag:
            self.stop_tag = ct(self.stop_tag).get()

        if (not self.start_tag and not self.is_restart and
            self.config.cycling_tasks):
            print >> sys.stderr, 'WARNING: No initial cycle time provided - no cycling tasks will be loaded.'

        if self.run_mode != self.config.run_mode:
            self.run_mode = self.config.run_mode

        if not reconfigure:
            self.state_dumper = dumper( self.suite, self.run_mode, self.start_tag, self.stop_tag )

            run_dir = sitecfg.get_derived_host_item( self.suite, 'suite run directory' )
            if not self.is_restart:     # create new suite_db file (and dir) if needed
                self.db = cylc.rundb.CylcRuntimeDAO(suite_dir=run_dir, new_mode=True)
            else:
                self.db = cylc.rundb.CylcRuntimeDAO(suite_dir=run_dir)

            self.hold_suite_now = False
            self.hold_time = None
            if self.options.hold_time:
                # raises CycleTimeError:
                self.hold_time = ct( self.options.hold_time ).get()
                #    self.parser.error( "invalid cycle time: " + self.hold_time )

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
        if flags.utc:
            os.environ['TZ'] = 'UTC'

        if not reconfigure:
            slog = suite_log( self.suite )
            self.suite_log_dir = slog.get_dir()
            slog.pimp( self.logging_level )
            self.log = slog.get_log()
            self.logfile = slog.get_path()

            self.command_queue = comqueue( self.control_commands.keys() )
            self.pyro.connect( self.command_queue, 'command-interface' )

            self.event_queue = Queue()
            task.task.event_queue = self.event_queue
            self.eventq_worker = event_batcher(
                    'Event Handlers', self.event_queue,
                    self.config.cfg['cylc']['event handler submission']['batch size'],
                    self.config.cfg['cylc']['event handler submission']['delay between batches'],
                    self.suite )
            self.eventq_worker.start()

            self.poll_and_kill_queue = Queue()
            task.task.poll_and_kill_queue = self.poll_and_kill_queue
            self.pollkq_worker = poll_and_kill_batcher(
                    'Poll & Kill Commands', self.poll_and_kill_queue,
                    self.config.cfg['cylc']['poll and kill command submission']['batch size'],
                    self.config.cfg['cylc']['poll and kill command submission']['delay between batches'],
                    self.suite )
            self.pollkq_worker.start()

            self.info_interface = info_interface( self.info_commands )
            self.pyro.connect( self.info_interface, 'suite-info' )

            self.log_interface = log_interface( slog )
            self.pyro.connect( self.log_interface, 'log' )

            self.log.info( "port:" +  str( self.port ))

    def configure_suite_environment( self ):

        # static cylc and suite-specific variables:
        self.suite_env = {
                'CYLC_UTC'               : str(flags.utc),
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
                'CYLC_SUITE_INITIAL_CYCLE_TIME' : str( self.start_tag ), # may be "None"
                'CYLC_SUITE_FINAL_CYCLE_TIME'   : str( self.stop_tag ), # may be "None"
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

        # Add to the scheduler environment for possible use by event handlers
        for var,val in self.suite_env.items():
            os.environ[var] = val
        for var,val in self.suite_task_env.items():
            os.environ[var] = val

        # Pass these to the jobfile generation module.
        # TODO - find a better, less back-door, way of doing this!
        jobfile.jobfile.suite_env = self.suite_env
        jobfile.jobfile.suite_task_env = self.suite_task_env
        # And pass contact env to the task module
        task.task.suite_contact_env = self.suite_contact_env

        # Suite bin directory for event handlers executed by the scheduler.
        os.environ['PATH'] = self.suite_dir + '/bin:' + os.environ['PATH']

        # User defined local variables that may be required by event handlers
        cenv = self.config.cfg['cylc']['environment']
        for var in cenv:
            os.environ[var] = os.path.expandvars(cenv[var])

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
                self.start_tag = spec.get_start_tag()
                self.stop_tag = spec.get_stop_tag()
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

            t0 = time.time()

            if self.reconfiguring:
                # user has requested a suite definition reload
                self.reload_taskdefs()

            if self.process_tasks():
                if flags.debug:
                    self.log.debug( "BEGIN TASK PROCESSING" )
                    main_loop_start_time = now()

                self.negotiate()

                ready = self.pool.process()
                self.process_resolved( ready )

                self.spawn()

                if not self.config.cfg['development']['disable task elimination']:
                    self.remove_spent_tasks()

                self.state_dumper.dump()

                self.do_update_state_summary = True

                # expire old broadcast variables
                self.wireless.expire( self.get_oldest_c_time() )

                if flags.debug:
                    delta = now() - main_loop_start_time
                    seconds = delta.seconds + float(delta.microseconds)/10**6
                    self.log.debug( "END TASK PROCESSING (took " + str( seconds ) + " sec)" )

            state_recorders = []
            state_updaters = []
            event_recorders = []
            other = []

            # process queued task messages
            for itask in self.pool.get_tasks():
                itask.process_incoming_messages()
                # if incoming messages have resulted in new database operations grab them
                if itask.db_items:
                    opers = itask.get_db_ops()
                    for oper in opers:
                        if isinstance(oper, cylc.rundb.UpdateObject):
                            state_updaters += [oper]
                        elif isinstance(oper, cylc.rundb.RecordStateObject):
                            state_recorders += [oper]
                        elif isinstance(oper, cylc.rundb.RecordEventObject):
                            event_recorders += [oper]
                        else:
                            other += [oper]

            #precedence is record states > update_states > record_events > anything_else
            db_ops = state_recorders + state_updaters + event_recorders + other
            # compact the set of operations
            if len(db_ops) > 1:
                db_opers = [db_ops[0]]
                for i in range(1,len(db_ops)):
                    if db_opers[-1].s_fmt == db_ops[i].s_fmt:
                        if isinstance(db_opers[-1], cylc.rundb.BulkDBOperObject):
                            db_opers[-1].add_oper(db_ops[i])
                        else:
                            new_oper = cylc.rundb.BulkDBOperObject(db_opers[-1])
                            new_oper.add_oper(db_ops[i])
                            db_opers.pop(-1)
                            db_opers += [new_oper]
                    else:
                        db_opers += [db_ops[i]]
            else:
                db_opers = db_ops

            # record any broadcast settings to be dumped out
            if self.wireless:
                if self.wireless.new_settings:
                    db_ops = self.wireless.get_db_ops()
                    for d in db_ops:
                        db_opers += [d]

            for d in db_opers:
                if self.db.c.is_alive():
                    self.db.run_db_op(d)
                elif self.db.c.exception:
                    raise self.db.c.exception
                else:
                    raise SchedulerError( 'An unexpected error occurred while writing to the database' )

            # process queued commands
            self.process_command_queue()

            # Hold waiting tasks if beyond stop cycle etc:
            # (a) newly spawned beyond existing stop cycle
            # (b) new stop cycle set by command
            runahead_base = self.get_runahead_base()
            for itask in self.pool.get_tasks():
                self.check_hold_waiting_tasks( itask, runahead_base=runahead_base )

            #print '<Pyro'
            if flags.iflag or self.do_update_state_summary:
                flags.iflag = False
                self.do_update_state_summary = False
                self.update_state_summary()

            if self.config.cfg['cylc']['event hooks']['timeout']:
                self.check_suite_timer()

            # hard abort? (TODO - will a normal shutdown suffice here?)
            # 1) "abort if any task fails" is set, and one or more tasks failed
            if self.config.cfg['cylc']['abort if any task fails']:
                if self.any_task_failed():
                    raise SchedulerError( 'One or more tasks failed and "abort if any task fails" is set' )

            # 4) the run is a reference test, and any disallowed failures occured
            if self.reference_test_mode:
                if len( self.ref_test_allowed_failures ) > 0:
                    for itask in self.get_failed_tasks():
                        if itask.id not in self.ref_test_allowed_failures:
                            print >> sys.stderr, itask.id
                            raise SchedulerError( 'A task failed unexpectedly: not in allowed failures list' )

            # check submission and execution timeout and polling timers
            if self.run_mode != 'simulation':
                for itask in self.pool.get_tasks():
                    itask.check_timers()

            self.release_runahead( runahead_base=runahead_base )

            if not self.do_shutdown:
                # check if the suite should shut down automatically now
                if self.check_clean_stop_conditions():
                    self.command_stop_cleanly()

            if self.do_shutdown:
                # Tell the non job-submission command threads to stop
                # now or when their queues are empty, according to the
                # type of shutdown. The job submission thread has been
                # stopped already by the stop commands. Note that the
                # threads_stopped flag is reset by the stop commands so
                # that 'stop --now' can override other stops in progress.
                if not self.threads_stopped and self.do_shutdown == 'now':
                    self.threads_stopped = True
                    self.eventq_worker.request_stop( empty_before_exit=False )
                    self.pollkq_worker.request_stop( empty_before_exit=False )
                elif not self.threads_stopped and \
                        ( self.do_shutdown == 'quick' or \
                        self.do_shutdown == 'clean' and self.no_active_tasks() ):
                    self.threads_stopped = True
                    # In a clean shutdown we don't stop the threads
                    # while there are still active tasks, because they
                    # could exit early if their queues temporarily empty
                    # while the final tasks are running.
                    self.eventq_worker.request_stop( empty_before_exit=True )
                    self.pollkq_worker.request_stop( empty_before_exit=True )

            if self.do_shutdown and \
                    not self.pool.worker.is_alive() and \
                    not self.eventq_worker.is_alive() and \
                    not self.pollkq_worker.is_alive():
                break

            if self.options.profile_mode:
                t1 = time.time()
                self._update_profile_info("scheduler loop dt (s)", t1 - t0,
                                          amount_format="%.3f")
                self._update_cpu_usage()
                self._update_profile_info("jobqueue.qsize", float(self.pool.jobqueue.qsize()),
                                          amount_format="%.1f")

            time.sleep(1)

        # END MAIN LOOP

        if self.gen_reference_log:
            print '\nCOPYING REFERENCE LOG to suite definition directory'
            shcopy( self.logfile, self.reflogfile)

    def update_state_summary( self ):
        self.suite_state.update( self.pool.get_tasks(), 
                self.get_oldest_c_time(), self.get_newest_c_time(),
                self.get_newest_c_time(True), self.paused(),
                self.will_pause_at(), self.do_shutdown is not None,
                self.will_stop_at(), self.runahead_limit,
                self.config.ns_defn_order )

    def process_resolved( self, tasks ):
        # process resolved dependencies (what actually triggers off what
        # at run time). Note 'triggered off' means 'prerequisites
        # satisfied by', but necessarily 'started running' too.
        for itask in tasks:
            if self.runtime_graph_on:
                self.runtime_graph.update( itask, self.get_oldest_c_time(), self.get_oldest_async_tag() )
            if self.config.cfg['cylc']['log resolved dependencies']:
                itask.log( 'NORMAL', 'triggered off ' + str( itask.get_resolved_dependencies()) )

    def check_suite_timer( self ):
        if self.already_timed_out:
            return
        timeout = self.suite_timer_start + datetime.timedelta( minutes=self.config.cfg['cylc']['event hooks']['timeout'] )
        if now() > timeout:
            self.already_timed_out = True
            message = 'suite timed out after ' + str( self.config.cfg['cylc']['event hooks']['timeout']) + ' minutes'
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

        elif self.waiting_tasks_ready():
            process = True

        if self.run_mode == 'simulation':
            for itask in self.pool.get_tasks():
                if itask.state.is_currently('running'):
                    # set sim-mode tasks to "succeeded" after their
                    # alotted run time
                    if itask.sim_time_check():
                        process = True

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
        msg = "Suite shutting down at " + str(now())

        # The getattr() calls below are used in case the suite is not
        # fully configured before the shutdown is called.

        if reason:
            msg += ' (' + reason + ')'
        print msg
        if getattr(self, "log", None) is not None:
            self.log.info( msg )
            if not self.no_active_tasks():
                self.log.warning( "some active tasks will be orphaned" )

        if self.pool:
            self.pool.worker.quit = True # (should be done already)
            self.pool.worker.join()
            # disconnect task message queues
            for itask in self.pool.get_tasks():
                if itask.message_queue:
                    self.pyro.disconnect( itask.message_queue )
            if self.state_dumper:
                try:
                    self.state_dumper.dump()
                except (OSError, IOError) as exc:
                    # (see comments in the state dumping module)
                    # ignore errors here in order to shut down cleanly
                    self.log.warning( 'Final state dump failed: ' + str(exc) )
                    pass

        for q in [ self.eventq_worker, self.pollkq_worker, self.request_handler ]:
            if q:
                q.quit = True # (should be done already)
                q.join()

        for i in [ self.command_queue, self.wireless,
                self.suite_id, self.suite_state ]:
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

        if self.runtime_graph_on:
            self.runtime_graph.finalize()

        # disconnect from suite-db, stop db queue
        if getattr(self, "db", None) is not None:
            self.db.close()

        if getattr(self, "config", None) is not None:
            # run shutdown handlers
            abort = self.config.cfg['cylc']['event hooks']['abort if shutdown handler fails']
            self.run_event_handlers( 'shutdown', abort, reason )

        print "DONE" # main thread exit

    def set_stop_ctime( self, stop_tag ):
        self.log.info( "Setting stop cycle time: " + stop_tag )
        self.stop_tag = stop_tag

    def set_stop_clock( self, dtime ):
        self.log.info( "Setting stop clock time: " + dtime.isoformat() )
        self.stop_clock_time = dtime

    def set_stop_task( self, taskid ):
        name, tag = taskid.split(TaskID.DELIM)
        if name in self.config.get_task_name_list():
            self.log.info( "Setting stop task: " + taskid )
            self.stop_task = taskid
        else:
            self.log.warning( "Requested stop task name does not exist: " + name )

    def hold_suite( self, ctime = None ):
        if ctime:
            self.log.info( "Setting suite hold cycle time: " + ctime )
            self.hold_time = ctime
        else:
            self.hold_suite_now = True
            self.log.info( "Holding all waiting or queued tasks now")
            for itask in self.pool.get_tasks():
                if itask.state.is_currently('queued','waiting','submit-retrying', 'retrying'):
                    # (not runahead: we don't want these converted to
                    # held or they'll be released immediately on restart)
                    itask.reset_state_held()

    def release_suite( self ):
        if self.hold_suite_now:
            self.log.info( "RELEASE: new tasks will be queued when ready")
            self.hold_suite_now = False
            self.hold_time = None
        for itask in self.pool.get_tasks():
            if itask.state.is_currently('held'):
                if self.stop_tag and ctime_gt(itask.c_time, self.stop_tag):
                    # this task has passed the suite stop time
                    itask.log( 'NORMAL', "Not releasing (beyond suite stop cycle) " + self.stop_tag )
                elif itask.stop_c_time and ctime_gt(itask.c_time, itask.stop_c_time):
                    # this task has passed its own stop time
                    itask.log( 'NORMAL', "Not releasing (beyond task stop cycle) " + itask.stop_c_time )
                else:
                    # release this task
                    itask.reset_state_waiting()

        # TODO - write a separate method for cancelling a stop time:
        #if self.stop_tag:
        #    self.log.warning( "UNSTOP: unsetting suite stop time")
        #    self.stop_tag = None

    def will_stop_at( self ):
        if self.stop_tag:
            return self.stop_tag
        elif self.stop_clock_time:
            return self.stop_clock_time.isoformat()
        elif self.stop_task:
            return self.stop_task
        else:
            return None

    def clear_stop_times( self ):
        self.stop_tag = None
        self.stop_clock_time = None
        self.stop_task = None

    def paused( self ):
        return self.hold_suite_now

    def stopping( self ):
        if self.stop_tag or self.stop_clock_time:
            return True
        else:
            return False

    def will_pause_at( self ):
        return self.hold_time

    def get_runahead_base( self ):
        # Return the cycle time from which to compute the runahead
        # limit: take the oldest task not succeeded or failed (note this
        # excludes finished tasks and it includes runahead-limited tasks
        # - consequently "too low" a limit cannot actually stall a suite.
        oldest_c_time = '99991228235959'
        for itask in self.pool.get_tasks():
            if not itask.is_cycling:
                continue
            #if itask.is_daemon:
            #    # avoid daemon tasks
            #    continue
            if ctime_lt(itask.c_time, oldest_c_time):
                if itask.state.is_currently('failed', 'succeeded'):
                    continue
                oldest_c_time = itask.c_time

        return oldest_c_time

    def get_oldest_async_tag( self ):
        # return the tag of the oldest non-daemon task
        oldest = 99999999999999
        for itask in self.pool.get_tasks():
            if itask.is_cycling:
                continue
            #if itask.state.is_currently('failed'):  # uncomment for earliest NON-FAILED
            #    continue
            if itask.is_daemon:
                continue
            if int( itask.tag ) < oldest:
                oldest = int(itask.tag)
        return oldest

    def get_oldest_c_time( self ):
        # return the cycle time of the oldest task
        oldest_c_time = '99991228230000'
        for itask in self.pool.get_tasks():
            if not itask.is_cycling:
                continue
            #if itask.state.is_currently('failed'):  # uncomment for earliest NON-FAILED
            #    continue
            #if itask.is_daemon:
            #    # avoid daemon tasks
            #    continue
            if ctime_lt( itask.c_time, oldest_c_time):
                oldest_c_time = itask.c_time
        return oldest_c_time

    def get_newest_c_time( self, nonrunahead=False ):
        # return the cycle time of the newest task
        newest_c_time = ct('1000010101').get()
        for itask in self.pool.get_tasks():
            if not itask.is_cycling:
                continue
            if nonrunahead:
                if itask.state.is_currently( 'runahead' ) or \
                    ( self.stop_tag and ctime_gt( itask.c_time, self.stop_tag )):
                        continue
            # avoid daemon tasks
            #if itask.is_daemon:
            #    continue
            if ctime_gt(itask.c_time, newest_c_time):
                newest_c_time = itask.c_time
        return newest_c_time

    def no_active_tasks( self ):
        for itask in self.pool.get_tasks():
            if itask.state.is_currently('running', 'submitted'):
                return False
        return True

    def get_failed_tasks( self ):
        failed = []
        for itask in self.pool.get_tasks():
            if itask.state.is_currently('failed', 'submit-failed' ):
                failed.append( itask )
        return failed

    def any_task_failed( self ):
        for itask in self.pool.get_tasks():
            if itask.state.is_currently('failed', 'submit-failed' ):
                return True
        return False

    def negotiate( self ):
        # run time dependency negotiation: tasks attempt to get their
        # prerequisites satisfied by other tasks' outputs.
        # BROKERED NEGOTIATION is O(n) in number of tasks.

        self.broker.reset()

        self.broker.register( self.pool.get_tasks() )

        for itask in self.pool.get_tasks():
            # try to satisfy me (itask) if I'm not already satisfied.
            if itask.not_fully_satisfied():
                self.broker.negotiate( itask )

        for itask in self.pool.get_tasks():
            # (TODO - only used by repeating async tasks now)
            if not itask.not_fully_satisfied():
                itask.check_requisites()

    def release_runahead( self, runahead_base=None ):
        if self.runahead_limit:
            if runahead_base is None:
                runahead_base = self.get_runahead_base()
            runahead_base_int = int(runahead_base)
            for itask in self.pool.get_tasks():
                if itask.state.is_currently('runahead'):
                    if self.stop_tag and ctime_gt(itask.c_time, self.stop_tag):
                        # beyond the final cycle time
                        itask.log( 'DEBUG', "holding (beyond suite final cycle)" )
                        itask.reset_state_held()
                        continue
                    foo = ct( itask.c_time )
                    foo.decrement( hours=self.runahead_limit )
                    if int( foo.get() ) < runahead_base_int:
                        if self.hold_suite_now:
                            itask.log( 'DEBUG', "holding (suite stopping now)" )
                            itask.reset_state_held()
                        else:
                            itask.log( 'DEBUG', "releasing (runahead limit moved on)" )
                            itask.reset_state_waiting()

    def check_hold_waiting_tasks( self, new_task, is_newly_added=False,
                                  runahead_base=None ):
        if not new_task.state.is_currently('waiting'):
            return

        if is_newly_added and self.hold_suite_now:
            new_task.log( 'DEBUG', "HOLDING (general suite hold) " )
            new_task.reset_state_held()
            return

        # further checks only apply to cycling tasks
        if not new_task.is_cycling:
            return

        # check cycle stop or hold conditions
        if self.stop_tag and ctime_gt( new_task.c_time, self.stop_tag ):
            new_task.log( 'DEBUG', "HOLDING (beyond suite stop cycle) " + self.stop_tag )
            new_task.reset_state_held()
            return
        if self.hold_time and ctime_gt( new_task.c_time , self.hold_time ):
            new_task.log( 'DEBUG', "HOLDING (beyond suite hold cycle) " + self.hold_time )
            new_task.reset_state_held()
            return

        # tasks beyond the runahead limit
        if is_newly_added and self.runahead_limit:
            if runahead_base is None:
                ouct = self.get_runahead_base()
            else:
                ouct = runahead_base
            foo = ct( new_task.c_time )
            foo.decrement( hours=self.runahead_limit )
            foo_str = foo.get()
            if ctime_ge( foo_str, ouct ):
                new_task.log( "DEBUG", "HOLDING (beyond runahead limit)" )
                new_task.reset_state_runahead()
                return

        # hold tasks with future triggers beyond the final cycle time
        if self.task_has_future_trigger_overrun( new_task ):
            new_task.log( "NORMAL", "HOLDING (future trigger beyond stop cycle)" )
            self.held_future_tasks.append( new_task.id )
            new_task.reset_state_held()
            return

    def task_has_future_trigger_overrun( self, itask ):
        # check for future triggers extending beyond the final cycle
        if not self.stop_tag:
            return False
        for pct in set(itask.prerequisites.get_target_tags()):
            try:
                if ctime_gt( pct, self.stop_tag ):
                    # pct > self.stop_tag
                    return True
            except:
                # pct invalid cycle time => is an asynch trigger
                pass
        return False

    def add_new_task_proxy( self, new_task ):
        """Add a given new task proxy to the pool, or destroy it."""
        self.check_hold_waiting_tasks( new_task, is_newly_added=True )
        if self.pool.add( new_task ):
            return True
        else:
            new_task.prepare_for_death()
            del new_task
            return False

    def force_spawn( self, itask ):
        if itask.state.has_spawned():
            return None
        itask.state.set_spawned()
        itask.log( 'DEBUG', 'forced spawning')
        new_task = itask.spawn( 'waiting' )
        if self.add_new_task_proxy( new_task ):
            return new_task
        else:
            return None

    def spawn( self ):
        # create new tasks foo(T+1) if foo has not got too far ahead of
        # the slowest task, and if foo(T) spawns
        for itask in self.pool.get_tasks():
            if itask.ready_to_spawn():
                self.force_spawn( itask )

    def remove_spent_tasks( self ):
        """Remove tasks no longer needed to satisfy others' prerequisites."""
        self.remove_suiciding_tasks()
        self.remove_spent_cycling_tasks()
        self.remove_spent_async_tasks()


    def remove_suiciding_tasks( self ):
        """Remove any tasks that have suicide-triggered."""
        for itask in self.pool.get_tasks():
            if itask.suicide_prerequisites.count() != 0:
                if itask.suicide_prerequisites.all_satisfied():
                    if itask.state.is_currently('ready', 'submitted', 'running'):
                        itask.log( 'WARNING', 'suiciding while active' )
                    else:
                        itask.log( 'NORMAL', 'suiciding' )
                    self.force_spawn( itask )
                    self.pool.remove( itask, 'suicide' )


    def remove_spent_cycling_tasks( self ):
        """
        Remove cycling tasks no longer needed to satisfy others' prerequisites.
        Each task proxy knows its "cleanup cutoff" from the graph. For example:
          graph = 'foo[T-6]=>bar \n foo[T-12]=>baz'
        implies foo's cutoff is T+12: if foo has succeeded and spawned,
        it can be removed if no unsatisfied task proxy exists with
        T<=T+12. Note this only uses information about the cycle time of
        downstream dependents - if we used specific IDs instead spent
        tasks could be identified and removed even earlier).
        """

        # first find the cycle time of the earliest unsatisfied task
        cutoff = None
        for itask in self.pool.get_tasks():
            if not itask.is_cycling:
                continue
            if itask.state.is_currently('waiting', 'runahead', 'held' ):
                if not cutoff or ctime_lt(itask.c_time, cutoff):
                    cutoff = itask.c_time
            elif not itask.has_spawned():
                nxt = itask.next_tag()
                if not cutoff or ctime_lt(nxt, cutoff):
                    cutoff = nxt

        # now check each succeeded task against the cutoff
        spent = []
        for itask in self.pool.get_tasks():
            if not itask.state.is_currently('succeeded') or \
                    not itask.is_cycling or \
                    not itask.state.has_spawned():
                continue
            if cutoff and cutoff > itask.cleanup_cutoff:
                spent.append(itask)
        for itask in spent:
            self.pool.remove( itask )


    def remove_spent_async_tasks( self ):
        cutoff = 0
        for itask in self.pool.get_tasks():
            if itask.is_cycling:
                continue
            if itask.is_daemon:
                # avoid daemon tasks
                continue
            if not itask.done():
                if itask.tag > cutoff:
                    cutoff = itask.tag
        spent = []
        for itask in self.pool.get_tasks():
            if itask.is_cycling:
                continue
            if itask.done() and itask.tag < cutoff:
                spent.append( itask )
        for itask in spent:
            self.pool.remove( itask )

    def command_trigger_task( self, name, tag, is_family ):
        matches = self.get_matching_tasks( name, is_family )
        if not matches:
            raise TaskNotFoundError, "No matching tasks found: " + name
        task_ids = [ i + TaskID.DELIM + tag for i in matches ]

        for itask in self.pool.get_tasks():
            if itask.id in task_ids:
                itask.manual_trigger = True
                itask.reset_state_ready()

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
        # we only allow resetting to a subset of available task states
        if state not in [ 'ready', 'waiting', 'succeeded', 'failed', 'held', 'spawn' ]:
            raise TaskStateError, 'Illegal reset state: ' + state

        matches = self.get_matching_tasks( name, is_family )
        if not matches:
            raise TaskNotFoundError, "No matching tasks found: " + name
        task_ids = [ i + TaskID.DELIM + tag for i in matches ]

        tasks = []
        for itask in self.pool.get_tasks():
            if itask.id in task_ids:
                tasks.append( itask )

        for itask in tasks:
            if itask.state.is_currently( 'ready' ):
                # Currently can't reset a 'ready' task in the job submission thread!
                self.log.warning( "A 'ready' task cannot be reset: " + itask.id )
            itask.log( "NORMAL", "resetting to " + state + " state" )
            if state == 'ready':
                itask.reset_state_ready()
            elif state == 'waiting':
                itask.reset_state_waiting()
            elif state == 'succeeded':
                itask.reset_state_succeeded()
            elif state == 'failed':
                itask.reset_state_failed()
            elif state == 'held':
                itask.reset_state_held()
            elif state == 'spawn':
                self.force_spawn(itask)

    def command_add_prerequisite( self, task_id, message ):
        # find the task to reset
        for itask in self.pool.get_tasks():
            if itask.id == task_id:
                break
        else:
            raise TaskNotFoundError, "Task not present in suite: " + task_id

        pp = plain_prerequisites( task_id )
        pp.add( message )

        itask.prerequisites.add_requisites(pp)

    def command_purge_tree( self, id, stop ):
        # Remove an entire dependancy tree rooted on the target task,
        # through to the given stop time (inclusive). In general this
        # involves tasks that do not even exist yet within the pool.

        # Method: trigger the target task *virtually* (i.e. without
        # running the real task) by: setting it to the succeeded state,
        # setting all of its outputs completed, and forcing it to spawn.
        # (this is equivalent to instantaneous successful completion as
        # far as cylc is concerned). Then enter the normal dependency
        # negotation process to trace the downstream effects of this,
        # also triggering subsequent tasks virtually. Each time a task
        # triggers mark it as a dependency of the target task for later
        # deletion (but not immmediate deletion because other downstream
        # tasks may still trigger off its outputs).  Downstream tasks
        # (freshly spawned or not) are not triggered if they have passed
        # the stop time, and the process is stopped is soon as a
        # dependency negotation round results in no new tasks
        # triggering.

        # Finally, reset the prerequisites of all tasks spawned during
        # the purge to unsatisfied, since they may have been satisfied
        # by the purged tasks in the "virtual" dependency negotiations.
        # TODO - THINK ABOUT WHETHER THIS CAN APPLY TO TASKS THAT
        # ALREADY EXISTED PRE-PURGE, NOT ONLY THE JUST-SPAWNED ONES. If
        # so we should explicitly record the tasks that get satisfied
        # during the purge.


        # Purge is an infrequently used power tool, so print
        # comprehensive information on what it does to stdout.
        print
        print "PURGE ALGORITHM RESULTS:"

        die = []
        spawn = []

        print 'ROOT TASK:'
        for itask in self.pool.get_tasks():
            # Find the target task
            if itask.id == id:
                # set it succeeded
                print '  Setting', itask.id, 'succeeded'
                itask.reset_state_succeeded(manual=False)
                # force it to spawn
                print '  Spawning', itask.id
                foo = self.force_spawn( itask )
                if foo:
                    spawn.append( foo )
                # mark it for later removal
                print '  Marking', itask.id, 'for deletion'
                die.append( itask )
                break

        print 'VIRTUAL TRIGGERING'
        # trace out the tree of dependent tasks
        something_triggered = True
        while something_triggered:
            self.negotiate()
            something_triggered = False
            for itask in self.pool.get_tasks():
                if ctime_gt( itask.tag, stop ):
                    continue
                if itask.ready_to_run():
                    something_triggered = True
                    print '  Triggering', itask.id
                    itask.reset_state_succeeded(manual=False)
                    print '  Spawning', itask.id
                    foo = self.force_spawn( itask )
                    if foo:
                        spawn.append( foo )
                    print '  Marking', itask.id, 'for deletion'
                    # remove these later (their outputs may still be needed)
                    die.append( itask )
                elif itask.suicide_prerequisites.count() > 0:
                    if itask.suicide_prerequisites.all_satisfied():
                        print '  Spawning virtually activated suicide task', itask.id
                        self.force_spawn( itask )
                        # remove these now (not setting succeeded; outputs not needed)
                        print '  Suiciding', itask.id, 'now'
                        self.pool.remove( itask, 'purge' )

        # reset any prerequisites "virtually" satisfied during the purge
        print 'RESETTING spawned tasks to unsatisified:'
        for itask in spawn:
            print '  ', itask.id
            itask.prerequisites.set_all_unsatisfied()

        # finally, purge all tasks marked as depending on the target
        print 'REMOVING PURGED TASKS:'
        for itask in die:
            print '  ', itask.id
            self.pool.remove( itask, 'purge' )

        print 'PURGE DONE'

    def waiting_tasks_ready( self ):
        # waiting tasks can become ready for internal reasons:
        # namely clock-triggers or retry-delay timers
        result = False
        for itask in self.pool.get_tasks():
            if itask.ready_to_run():
                result = True
                break
        return result

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

    def check_clean_stop_conditions( self ):
        stop = False

        if self.stop_clock_time:
            if now() > self.stop_clock_time:
                self.log.info( "Wall clock stop time reached: " + self.stop_clock_time.isoformat() )
                self.stop_clock_time = None
                stop = True

        elif self.stop_task:
            name, tag = self.stop_task.split(TaskID.DELIM)
            for itask in self.pool.get_tasks():
                iname, itag = itask.id.split(TaskID.DELIM)
                if itask.name == name and int(itag) == int(tag):
                    # found the stop task
                    if itask.state.is_currently('succeeded'):
                        self.log.info( "Stop task " + self.stop_task + " finished" )
                        stop = True
                    break

        else:
            # all cycling tasks are held past the suite stop cycle and
            # all async tasks have succeeded.
            stop = True

            i_cyc = False
            i_asy = False
            i_fut = False
            for itask in self.pool.get_tasks():
                if itask.is_cycling:
                    i_cyc = True
                    # don't stop if a cycling task has not passed the stop cycle
                    if self.stop_tag:
                        if ctime_le( itask.c_time, self.stop_tag ):
                            if itask.state.is_currently('succeeded') and itask.has_spawned():
                                # ignore spawned succeeded tasks - their successors matter
                                pass
                            elif itask.id in self.held_future_tasks:
                                # unless held because a future trigger reaches beyond the stop cycle
                                i_fut = True
                                pass
                            else:
                                stop = False
                                break
                    else:
                        # don't stop if there are cycling tasks and no stop cycle set
                        stop = False
                        break
                else:
                    i_asy = True
                    # don't stop if an async task has not succeeded yet
                    if not itask.state.is_currently('succeeded'):
                        stop = False
                        break
            if stop:
                msg = "Stopping: "
                if i_fut:
                    msg += "\n  + all future-triggered tasks have run as far as possible toward " + self.stop_tag
                if i_cyc:
                    msg += "\n  + all cycling tasks have spawned past the final cycle " + self.stop_tag
                if i_asy:
                    msg += "\n  + all non-cycling tasks have succeeded"
                print msg
                self.log.info( msg )

        return stop

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
