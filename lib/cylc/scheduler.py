#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
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
from suite_host import suite_host
from owner import user
from shutil import copy as shcopy
from copy import deepcopy
from cycle_time import ct, CycleTimeError
import datetime, time
import port_scan
import accelerated_clock 
import logging
import re, os, sys, shutil
from state_summary import state_summary
from passphrase import passphrase
from locking.lockserver import lockserver
from locking.suite_lock import suite_lock
from suite_id import identifier
from config import config, SuiteConfigError, TaskNotDefinedError
from global_config import gcfg
from port_file import port_file, PortFileExistsError, PortFileError
from broker import broker
from Pyro.errors import NamingError, ProtocolError
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
from TaskID import TaskID, TaskIDError
from task_pool import pool
import flags
import cylc.rundb
from Queue import Queue
from batch_submit import event_batcher
import subprocess


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
        TO DO: element - config element causing the problem
    """
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)


class request_handler( threading.Thread ):
    def __init__( self, pyro, verbose ):
        threading.Thread.__init__(self)
        self.pyro = pyro
        self.quit = False
        self.log = logging.getLogger( 'main' )
        self.log.info(  "Starting request handler thread" )

    def run( self ):
        while True:
            self.pyro.handleRequests(timeout=1)
            if self.quit:
                break
        self.log.info(  "Exiting request handler thread" )

class scheduler(object):

    def __init__( self, is_restart=False ):

        # SUITE OWNER
        self.owner = user

        # SUITE HOST
        self.host= suite_host

        # DEPENDENCY BROKER
        self.broker = broker()

        self.lock_acquired = False

        self.is_restart = is_restart

        self.graph_warned = {}

        self.suite_env = {}
        self.suite_task_env = {}

        self.do_process_tasks = False

        # initialize some items in case of early shutdown
        # (required in the shutdown() method)
        self.clock = None
        self.wireless = None
        self.suite_state = None
        self.command_queue = None
        self.pool = None
        self.evworker = None
        self.request_handler = None
        self.pyro = None
        self.state_dumper = None

        # COMMANDLINE OPTIONS

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

        gcfg.print_deprecation_warnings()

    def configure( self ):
        # read-only commands to expose directly to the network
        self.info_commands = {
                'ping suite'        : self.info_ping,
                'ping task'         : self.info_ping_task,
                'suite info'        : self.info_get_suite_info,
                'task list'         : self.info_get_task_list,
                'task info'         : self.info_get_task_info,
                'family nodes'      : self.info_get_family_nodes,
                'graphed family nodes' : self.info_get_graphed_family_nodes,
                'vis families'      : self.info_get_vis_families,
                'first-parent ancestors'    : self.info_get_first_parent_ancestors,
                'first-parent descendants'  : self.info_get_first_parent_descendants,
                'do live graph movie'       : self.info_do_live_graph_movie,
                'graph raw'         : self.info_get_graph_raw,
                'task requisites'   : self.info_get_task_requisites,
                }
 
        # control commands to expose indirectly via a command queue
        self.control_commands = {
                'stop cleanly'          : self.command_stop_cleanly,
                'stop now'              : self.command_stop_now,
                'stop after tag'        : self.command_stop_after_tag,
                'stop after clock time' : self.command_stop_after_clock_time,
                'stop after task'       : self.command_stop_after_task,
                'release suite'         : self.command_release_suite,
                'release task'          : self.command_release_task,
                'kill cycle'            : self.command_kill_cycle,
                'kill task'             : self.command_kill_task,
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
                }

        self.configure_suite()

        # REMOTELY ACCESSIBLE SUITE IDENTIFIER
        self.suite_id = identifier( self.suite, self.owner )
        self.pyro.connect( self.suite_id, 'cylcid', qualified = False )

        reqmode = self.config['cylc']['required run mode']
        if reqmode:
            if reqmode != self.run_mode:
                raise SchedulerError, 'ERROR: this suite requires the ' + reqmode + ' run mode'
        
        self.reflogfile = os.path.join(self.config.dir,'reference.log')

        if self.options.genref:
            self.config['cylc']['log resolved dependencies'] = True

        elif self.options.reftest:
            req = self.config['cylc']['reference test']['required run mode']
            if req and req != self.run_mode:
                raise SchedulerError, 'ERROR: this suite allows only ' + req + ' mode reference tests'
            handler = self.config.event_handlers['shutdown']
            if handler: 
                print >> sys.stderr, 'WARNING: replacing shutdown event handler for reference test run'
            self.config.event_handlers['shutdown'] = self.config['cylc']['reference test']['suite shutdown event handler']
            self.config['cylc']['log resolved dependencies'] = True
            self.config.abort_if_shutdown_handler_fails = True
            spec = LogSpec( self.reflogfile )
            self.start_tag = spec.get_start_tag()
            self.stop_tag = spec.get_stop_tag()
            self.ref_test_allowed_failures = self.config['cylc']['reference test']['expected task failures']
            if not self.config['cylc']['reference test']['allow task failures'] and len( self.ref_test_allowed_failures ) == 0:
                self.config['cylc']['abort if any task fails'] = True
            self.config.abort_on_timeout = True
            timeout = self.config['cylc']['reference test'][ self.run_mode + ' mode suite timeout' ]
            if not timeout:
                raise SchedulerError, 'ERROR: suite timeout not defined for ' + self.run_mode + ' mode reference test'
            self.config.suite_timeout = timeout
            self.config.reset_timer = False

        # Note that the following lines must be present at the top of
        # the suite log file for use in reference test runs:
        self.log.critical( 'Suite starting at ' + str( datetime.datetime.now()) )
        if self.run_mode == 'live':
            self.log.info( 'Log event clock: real time' )
        else:
            self.log.info( 'Log event clock: accelerated' )
        self.log.info( 'Run mode: ' + self.run_mode )
        self.log.info( 'Start tag: ' + str(self.start_tag) )
        self.log.info( 'Stop tag: ' + str(self.stop_tag) )

        if self.start_tag:
            self.start_tag = self.ctexpand( self.start_tag)
        if self.stop_tag:
            self.stop_tag = self.ctexpand( self.stop_tag)

        self.runahead_limit = self.config.get_runahead_limit()
        self.asynchronous_task_list = self.config.get_asynchronous_task_name_list()

        # RECEIVER FOR BROADCAST VARIABLES
        self.wireless = broadcast( self.config.get_linearized_ancestors() )
        self.pyro.connect( self.wireless, 'broadcast_receiver')

        self.pool = pool( self.suite, self.config, self.wireless, self.pyro, self.log, self.run_mode, self.verbose, self.options.debug )
        self.request_handler = request_handler( self.pyro, self.verbose )
        self.request_handler.start()

        # LOAD TASK POOL ACCORDING TO STARTUP METHOD
        self.old_user_at_host_set = set()
        self.load_tasks()
        self.initial_oldest_ctime = self.get_oldest_c_time()

        # REMOTELY ACCESSIBLE SUITE STATE SUMMARY
        self.suite_state = state_summary( self.config, self.run_mode, self.initial_oldest_ctime )
        self.pyro.connect( self.suite_state, 'state_summary')

        # initial cycle time
        if self.is_restart:
            self.ict = None
        else:
            if self.options.warm:
                if self.options.set_ict:
                    self.ict = self.start_tag
                else:
                    self.ict = None
            elif self.options.raw:
                self.ict = None
            else:
                self.ict = self.start_tag

        self.configure_suite_environment()

        suite_run_dir = os.path.expandvars(
                gcfg.get_derived_host_item(self.suite, 'suite run directory'))
        env_file_path = os.path.join(suite_run_dir, "cylc-suite-env")
        f = open(env_file_path, 'wb')
        for key, value in task.task.cylc_env.items():
            f.write("%s=%s\n" % (key, value))
        f.close()
        r_suite_run_dir = os.path.expandvars(
                gcfg.get_derived_host_item(self.suite, 'suite run directory'))
        for user_at_host in self.old_user_at_host_set:
            if '@' in user_at_host:
                user, host = user_at_host.split('@', 1)
            else:
                user, host = None, user_at_host
            # this handles defaulting to localhost:
            r_suite_run_dir = gcfg.get_derived_host_item(
                    self.suite, 'suite run directory', host, user)
            r_env_file_path = '%s:%s/cylc-suite-env' % (
                    user_at_host, r_suite_run_dir)
            cmd = ['scp', '-oBatchMode=yes', env_file_path, r_env_file_path]
            if subprocess.call(cmd): # return non-zero
                raise Exception("ERROR: " + str(cmd))

        self.already_timed_out = False
        if self.config.suite_timeout:
            self.set_suite_timer()

        self.runtime_graph_on = False
        if self.config['visualization']['runtime graph']['enable']:
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

        self.suite_halt = False
        self.suite_halt_now = False

    def process_command_queue( self ):
        queue = self.command_queue.get_queue()
        n = queue.qsize()
        if n > 0:
            print 'Actioning', n, 'queued commands'
        else:
            return
        while queue.qsize() > 0:
            name, args = queue.get()
            try:
                self.control_commands[ name ]( *args )
            except Exception, x:
                # don't let a bad command bring the suite down
                print >> sys.stderr, x
                self.log.warning( 'Queued command failed: ' + name + '(' + ','.join( [ str(a) for a in args ]) + ')' )
            else:
                self.log.info( 'Actioned queued command: ' + name + '(' + ','.join( [str(a) for a in args ]) + ')' )
            queue.task_done()
            # each command stimulates a state summary update if necessary

    def _task_type_exists( self, name_or_id ):
        # does a task name or id match a known task type in this suite?
        name = name_or_id
        if TaskID.DELIM in name_or_id:
            name, tag = name.split(TaskID.DELIM)
        if name in self.config.get_task_name_list():
            return True
        else:
            return False

    def _name_from_id( self, task_id ):
        if TaskID.DELIM in task_id:
            name, tag = task_id.split(TaskID.DELIM)
        else:
            name = task_id
        return name

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
        return [ self.config['title'], user ]

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

    def info_get_family_nodes( self ):
        return self.config.get_first_parent_descendants().keys()

    def info_get_graphed_family_nodes( self ):
        return self.config.families_used_in_graph

    def info_get_vis_families( self ):
        return self.config.vis_families

    def info_get_first_parent_descendants( self ):
        # families for single-inheritance hierarchy based on first parents
        return deepcopy(self.config.get_first_parent_descendants())

    def info_do_live_graph_movie( self ):
        return ( self.config['visualization']['enable live graph movie'],
                 self.config['visualization']['runtime graph']['directory'] ) 

    def info_get_first_parent_ancestors( self ):
        # single-inheritance hierarchy based on first parents
        return deepcopy(self.config.get_first_parent_ancestors() )

    def info_get_graph_raw( self, cto, ctn, raw, group_nodes, ungroup_nodes,
            ungroup_recursive, group_all, ungroup_all ):
        # TO DO: CAN WE OMIT THE MIDDLE MAN HERE?
        return self.config.get_graph_raw( cto, ctn, raw, group_nodes,
                ungroup_nodes, ungroup_recursive, group_all, ungroup_all)

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
                # extra info for catchup_clocktriggered tasks
                try:
                    extra_info[ itask.__class__.name + ' caught up' ] = itask.__class__.get_class_var( 'caughtup' )
                except:
                    # not a catchup_clocktriggered task
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
    # TO DO: LOG OR PRINT ERRORS AND CARRY ON FROM CONTROL COMMANDS
    # WHICH ARE NOW EXECUTED ASYNCHRONOUSLY.
    # AND DO A SUITE SUMMARY UPDATE AFTER EACH COMMAND?

    def command_stop_cleanly( self ):
        self.hold_suite()
        self.suite_halt = True

    def command_stop_now( self ):
        self.hold_suite()
        self.suite_halt_now = True

    def command_stop_after_tag( self, tag ):
        self.set_stop_ctime( tag )

    def command_stop_after_clock_time( self, arg ):
        #try:
        date, time = arg.split('-')
        yyyy, mm, dd = date.split('/')
        HH,MM = time.split(':')
        dtime = datetime( int(yyyy), int(mm), int(dd), int(HH), int(MM) )
        #except:
        return result( False, "Bad datetime (YYYY/MM/DD-HH:mm): " + arg )
        self.set_stop_clock( dtime )

    def command_stop_after_task( self, tid ):
        #try:
        tid = TaskID( tid )
        #except TaskIDError,x:
        #    return result( False, "Invalid stop task ID: " + arg )
        #else:
        arg = tid.getstr()
        self.set_stop_task( arg )

    def command_release_task( self, task_id ):
        if not self._task_type_exists( task_id ):
            print >> sys.stderr, "task not found: " + self._name_from_id( task_id )

        found = False
        for itask in self.pool.get_tasks():
            if itask.id == task_id:
                itask.reset_state_waiting()
                found = True
                break
        if found:
            self.do_process_tasks = True
        else:
            print >> sys.stderr, "Task not found" 

    def command_release_suite( self ):
        self.release_suite()
        # TO DO: process, to update state summary
        self.suite_halt = False
        print "Tasks will be submitted when they are ready to run" 

    def command_hold_task( self, task_id ):
        if not self._task_type_exists( task_id ):
            print >> sys.stderr, "COMMAND ERROR, task not found:", self._name_from_id( task_id )

        found = False
        was_waiting = False
        for itask in self.pool.get_tasks():
            if itask.id == task_id:
                found = True
                if itask.state.is_currently('waiting') or itask.state.is_currently('queued') or \
                        itask.state.is_currently('retrying'):
                    was_waiting = True
                    itask.reset_state_held()
                break
        if found:
            if was_waiting:
                self.do_process_tasks = True # to update monitor
                ##return result( True, "OK" )
            else:
                pass
                ##TO DO: return result( False, "Task was not waiting or queued" )
        else:
            pass
            ## TO DO: return result( False, "Task not found" )

    def command_hold_suite( self ):
        if self.paused():
            print >> sys.stderr, "COMMAND WARNING: the suite is already paused"

        self.hold_suite()
        # TO DO: process, to update state summary
        self.do_process_tasks = True

        ##return result( True, "Tasks that are ready to run will not be submitted" )

    def command_hold_after_tag( self, tag ):
        """To Do: not currently used - add to the cylc hold command"""
        self.hold_suite( tag )
        # TO DO: process, to update state summary
        self.do_process_tasks = True
        print "COMMAND result: The suite will pause when all tasks have passed " + tag 

    def command_set_runahead( self, hours=None ):
        if hours:
            self.log.info( "setting runahead limit to " + str(hours) )
            self.runahead_limit = int(hours)
        else:
            # No limit
            self.log.warning( "setting NO runahead limit" )
            self.runahead_limit = None

        self.do_process_tasks = True
        ##return result( True, "Action succeeded" )

    def command_set_verbosity( self, level ):
        # change the verbosity of all the logs:
        #   debug, info, warning, error, critical
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
        return result(True, 'OK')

    def command_kill_cycle( self, force_spawn, tag ):
        if not force_spawn:
            self.kill_cycle( tag )
        else:
            self.spawn_and_die_cycle( tag )

    def command_kill_task( self, force_spawn, task_id ):
        if not self._task_type_exists( task_id ):
            pass
            ## To Do:
            ## return result(False, "there is no task " + self._name_from_id( task_id ) + " in the suite graph." )
        if not force_spawn:
            self.kill( [ task_id ] )
        else:
            self.spawn_and_die( [ task_id ] )

    def command_purge_tree( self, task_id, stop ):
        # TO DO: REMOVE MIDDLE-MAN COMMANDS (E.G. THIS ONE) WHERE POSSIBLE
        if not self._task_type_exists( task_id ):
            pass
            ## To Do:
            ## return result( False, "there is no task " + self._name_from_id( task_id ) + " in the suite graph." )
        self.purge( task_id, stop )

    def command_reset_task_state( self, task_id, state ):
        # TO DO: HANDLE EXCEPTIONS FOR THE NEW WAY
        try:
            self.reset_task_state( task_id, state )
        except TaskStateError, x:
            self.log.warning( 'Refused remote reset: task state error' )
        except TaskNotFoundError, x:
            self.log.warning( 'Refused remote reset: task not found' )
        except Exception, x:
            # do not let a remote request bring the suite down for any reason
            self.log.warning( 'Remote reset failed: ' + x.__str__() )
        else:
            # To Do: report success
            self.do_process_tasks = True

    def command_trigger_task( self, task_id ):
        # TO DO: HANDLE EXCEPTIONS FOR THE NEW WAY
        try:
            self.trigger_task( task_id )
        except TaskNotFoundError, x:
            self.log.warning( 'Refused remote trigger, task not found: ' + task_id )
        except Exception, x:
            # do not let a remote request bring the suite down for any reason
            self.log.warning( 'Remote reset failed: ' + x.__str__() )
        else:
            # To Do: report success
            self.do_process_tasks = True

    def command_add_prerequisite( self, task_id, message ):
        try:
            self.add_prerequisite( task_id, message )
        except TaskNotFoundError, x:
            self.log.warning( 'Refused remote reset: task not found' )
        except Exception, x:
            # do not let a remote request bring the suite down for any reason
            self.log.warning( 'Remote reset failed: ' + x.__str__() )
        else:
            # report success
            # TO DO
            pass

    def command_insert_task( self, ins_id, stop_c_time=None ):
        ins_name = self._name_from_id( ins_id )
        if not self._task_type_exists( ins_name ):
            # TASK INSERTION GROUPS TEMPORARILY DISABLED
            #and ins_name not in self.config[ 'task insertion groups' ]:
            #return result( False, "No such task or group: " + ins_name )
            print >> sys.stderr, "Task not found: " + ins_name
        ins = ins_id
        # insert a new task or task group into the suite
        try:
            inserted, rejected = self.insertion( ins, stop_c_time )
        except Exception, x:
            self.log.warning( 'Remote insert failed: ' + x.__str__() )
        n_inserted = len(inserted)
        n_rejected = len(rejected)
        if n_inserted == 0:
            msg = "No tasks inserted"
            if n_rejected != 0:
                msg += '\nRejected tasks:'
                for t in rejected:
                    msg += '\n  ' + t
        elif n_rejected != 0:
            msg = 'Inserted tasks:' 
            for t in inserted:
                msg += '\n  ' + t
            msg += '\nRejected tasks:'
            for t in rejected:
                msg += '\n  ' + t
        elif n_rejected == 0:
            msg = 'Inserted tasks:' 
            for t in inserted:
                msg += '\n  ' + t


    def command_nudge( self ):
        # cause the task processing loop to be invoked
        # just set the "process tasks" indicator
        self.do_process_tasks = True

    def command_reload_suite( self ):
        try:
            self.reconfigure()
        except Exception, x:
            pass
            # TO DO: return result( False, str(x) )
        else:
            pass
            # TO DO: return result( True, 'OK' )


    #___________________________________________________________________

    def set_suite_timer( self, reset=False ):
        now = datetime.datetime.now()
        self.suite_timer_start = now
        print str(self.config.suite_timeout) + " minute suite timer starts NOW:", str(now)

    def ctexpand( self, tag ):
        # expand truncated cycle times (2012 => 2012010100)
        try:
            # cycle time
            tag = ct(tag).get()
        except CycleTimeError,x:
            try:
                # async integer tag
                int( tag )
            except ValueError:
                raise SystemExit( "ERROR:, invalid task tag : " + tag )
            else:
                pass
        else:
            pass
        return tag

    def reconfigure( self ):
        # reload the suite definition while the suite runs
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
        self.pool.qconfig = self.config['scheduling']['queues']
        self.pool.verbose = self.verbose
        self.pool.assign( reload=True )
        self.suite_state.config = self.config
        self.configure_suite_environment()
        self.reconfiguring = True
        for itask in self.pool.get_tasks():
            itask.reconfigure_me = True

    def reload_taskdefs( self ):
        found = False
        for itask in self.pool.get_tasks():
            if itask.state.is_currently('running'):
                # do not reload running tasks as some internal state
                # (e.g. timers) not easily cloneable at the moment,
                # and it is possible to make changes to the task config
                # that would be incompatible with the running task.
                if itask.reconfigure_me:
                    found = True
                continue
            if itask.reconfigure_me:
                itask.reconfigure_me = False
                if itask.name in self.orphans:
                    # orphaned task
                    if itask.state.is_currently('waiting') or itask.state.is_currently('queued') or \
                            itask.state.is_currently('retrying'):
                        # if not started running yet, remove it.
                        self.pool.remove( itask, '(task orphaned by suite reload)' )
                    else:
                        # set spawned already so it won't carry on into the future
                        itask.state.set_spawned()
                        self.log.warning( 'orphaned task will not continue: ' + itask.id  )
                else:
                    self.log.warning( 'RELOADING TASK DEFINITION FOR ' + itask.id  )
                    new_task = self.config.get_task_proxy( itask.name, itask.tag, itask.state.get_status(), None, False )
                    if itask.state.has_spawned():
                        new_task.state.set_spawned()
                    # succeeded tasks need their outputs set completed:
                    if itask.state.is_currently('succeeded'):
                        new_task.reset_state_succeeded(manual=False)
                    self.pool.remove( itask, '(suite definition reload)' )
                    self.pool.add( new_task )
        self.reconfiguring = found

    def parse_commandline( self ):
        self.run_mode = self.options.run_mode

        # LOGGING LEVEL
        if self.options.debug:
            self.logging_level = logging.DEBUG
        else:
            self.logging_level = logging.INFO

    def configure_pyro( self ):
        # CONFIGURE SUITE PYRO SERVER
        self.pyro = pyro_server( self.suite, self.suite_dir, 
                gcfg.cfg['pyro']['base port'],
                gcfg.cfg['pyro']['maximum number of ports'] )
        self.port = self.pyro.get_port()

        try:
            self.port_file = port_file( self.suite, self.port, self.verbose )
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
                verbose=self.verbose )

        if not reconfigure:
            run_dir = gcfg.get_derived_host_item( self.suite, 'suite run directory' )
            if not self.is_restart:     # create new suite_db file (and dir) if needed
                self.db = cylc.rundb.CylcRuntimeDAO(suite_dir=run_dir, new_mode=True)
            else:
                self.db = cylc.rundb.CylcRuntimeDAO(suite_dir=run_dir)

        self.stop_task = None

        # START and STOP CYCLE TIMES
        self.stop_tag = None
        self.stop_clock_time = None

        # (self.start_tag is set already if provided on the command line).
        if not self.start_tag:
            # No initial cycle time on the command line
            if self.config['scheduling']['initial cycle time']:
                # Use suite.rc initial cycle time
                self.start_tag = str(self.config['scheduling']['initial cycle time'])

        if self.options.stop_tag:
            # A final cycle time was provided on the command line.
            self.stop_tag = self.options.stop_tag
        elif self.config['scheduling']['final cycle time']:
            # Use suite.rc final cycle time
            self.stop_tag = str(self.config['scheduling']['final cycle time'])

        # could be async tags:
        ##if self.stop_tag:
        ##    self.stop_tag = ct( self.stop_tag ).get()
        ##if self.start_tag:
        ##    self.start_tag = ct( self.start_tag ).get()

        if not self.start_tag and not self.is_restart:
            print >> sys.stderr, 'WARNING: No initial cycle time provided - no cycling tasks will be loaded.'

        # PAUSE TIME?
        self.hold_suite_now = False
        self.hold_time = None
        if self.options.hold_time:
            # raises CycleTimeError:
            self.hold_time = ct( self.options.hold_time ).get()
            #    self.parser.error( "invalid cycle time: " + self.hold_time )

        # USE LOCKSERVER?
        self.use_lockserver = self.config['cylc']['lockserver']['enable']
        self.lockserver_port = None
        if self.use_lockserver:
            # check that user is running a lockserver
            # DO THIS BEFORE CONFIGURING PYRO FOR THE SUITE
            # (else scan etc. will hang on the partially started suite).
            # raises port_scan.SuiteNotFound error:
            self.lockserver_port = lockserver( self.host ).get_port()


        # USE QUICK TASK ELIMINATION?
        self.use_quick = self.config['development']['use quick task elimination']

        # ALLOW MULTIPLE SIMULTANEOUS INSTANCES?
        self.exclusive_suite_lock = not self.config['cylc']['lockserver']['simultaneous instances']

        # Running in UTC time? (else just use the system clock)
        self.utc = self.config['cylc']['UTC mode']

        # ACCELERATED CLOCK for simulation and dummy run modes
        rate = self.config['cylc']['accelerated clock']['rate']
        offset = self.config['cylc']['accelerated clock']['offset']
        disable = self.config['cylc']['accelerated clock']['disable']
        if self.run_mode == 'live':
            disable = True
        if not reconfigure:
            self.clock = accelerated_clock.clock( int(rate), int(offset), self.utc, disable ) 
            task.task.clock = self.clock
            clocktriggered.clocktriggered.clock = self.clock
            self.pyro.connect( self.clock, 'clock' )

        self.state_dumper = dumper( self.suite, self.run_mode, self.clock, self.start_tag, self.stop_tag )
        self.state_dump_dir = self.state_dumper.get_dir()
        self.state_dump_filename = self.state_dumper.get_path()

        if not reconfigure:
            slog = suite_log( self.suite )
            self.suite_log_dir = slog.get_dir()
            slog.pimp( self.logging_level, self.clock )
            self.log = slog.get_log()
            self.logfile = slog.get_path()

            self.command_queue = comqueue( self.control_commands.keys() )
            self.pyro.connect( self.command_queue, 'command-interface' )

            self.event_queue = Queue()
            task.task.event_queue = self.event_queue
            self.evworker = event_batcher( 
                    'Event Handler Submission', self.event_queue, 
                    self.config['cylc']['event handler execution']['batch size'],
                    self.config['cylc']['event handler execution']['delay between batches'],
                    self.suite,
                    self.verbose )
            self.evworker.start()

            self.info_interface = info_interface( self.info_commands )
            self.pyro.connect( self.info_interface, 'suite-info' )

            self.log.info( "port:" +  str( self.port ))

    def configure_suite_environment( self ):

        # static cylc and suite-specific variables:
        self.suite_env = {
                'CYLC_UTC'               : str(self.utc),
                'CYLC_MODE'              : 'scheduler',
                'CYLC_DEBUG'             : str( self.options.debug ),
                'CYLC_VERBOSE'           : str(self.verbose),
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
                'CYLC_SUITE_INITIAL_CYCLE_TIME' : str( self.ict ), # may be "None"
                'CYLC_SUITE_FINAL_CYCLE_TIME'   : str( self.stop_tag ), # may be "None"
                'CYLC_SUITE_LOG_DIR'     : self.suite_log_dir # needed by the test battery
                }

        # Set local values of variables that are potenitally task-specific
        # due to different directory paths on different task hosts. These 
        # are overridden by tasks prior to job submission, but in
        # principle they could be needed locally by event handlers:
        self.suite_task_env = {
                'CYLC_SUITE_RUN_DIR'    : gcfg.get_derived_host_item( self.suite, 'suite run directory' ),
                'CYLC_SUITE_WORK_DIR'   : gcfg.get_derived_host_item( self.suite, 'suite work directory' ),
                'CYLC_SUITE_SHARE_DIR'  : gcfg.get_derived_host_item( self.suite, 'suite share directory' ),
                'CYLC_SUITE_SHARE_PATH' : '$CYLC_SUITE_SHARE_DIR', # DEPRECATED
                'CYLC_SUITE_DEF_PATH'   : self.suite_dir
                }
        # (note gcfg automatically expands environment variables in local paths)

        # Add to the scheduler environment for possible use by event handlers
        for var,val in self.suite_env.items():
            os.environ[var] = val
        for var,val in self.suite_task_env.items():
            os.environ[var] = val

        # Pass these to the jobfile generation module.
        # TODO - find a better, less back-door, way of doing this!
        jobfile.jobfile.suite_env = self.suite_env
        jobfile.jobfile.suite_task_env = self.suite_task_env

        # Suite bin directory for event handlers executed by the scheduler. 
        os.environ['PATH'] = self.suite_dir + '/bin:' + os.environ['PATH'] 

        # User defined local variables that may be required by event handlers
        cenv = self.config['cylc']['environment']
        for var in cenv:
            os.environ[var] = os.path.expandvars(cenv[var])

    def run( self ):

        if self.use_lockserver:
            # request suite access from the lock server
            if suite_lock( self.suite, self.suite_dir, self.host, self.lockserver_port, 'scheduler' ).request_suite_access( self.exclusive_suite_lock ):
               self.lock_acquired = True
            else:
               raise SchedulerError( "Failed to acquire a suite lock" )

        if self.hold_time:
            # TO DO: HANDLE STOP AND PAUSE TIMES THE SAME WAY?
            self.hold_suite( self.hold_time )

        if self.options.start_held:
            self.log.warning( "Held on start-up (no tasks will be submitted)")
            self.hold_suite()

        handler = self.config.event_handlers['startup']
        if handler:
            if self.config.abort_if_startup_handler_fails:
                foreground = True
            else:
                foreground = False
            try:
                RunHandler( 'startup', handler, self.suite, msg='suite starting', fg=foreground )
            except Exception, x:
                # Note: test suites depends on this message:
                print >> sys.stderr, '\nERROR: startup EVENT HANDLER FAILED'
                raise SchedulerError, x

        while True: # MAIN LOOP
            # PROCESS ALL TASKS whenever something has changed that might
            # require renegotiation of dependencies, etc.

            if self.reconfiguring:
                # user has requested a suite definition reload
                self.reload_taskdefs()

            if self.run_mode == 'simulation':
                for itask in self.pool.get_tasks():
                    # set sim-mode tasks to "succeeded" after their
                    # alotted run time (and then set flags.pflag to
                    # stimulate task processing).
                    itask.sim_time_check()

            if self.process_tasks():
                self.log.debug( "BEGIN TASK PROCESSING" )
                # loop timing: use real clock even in sim mode
                main_loop_start_time = datetime.datetime.now()

                self.negotiate()

                submitted = self.pool.process()
                self.process_resolved( submitted )

                if not self.config['development']['disable task elimination']:
                    self.cleanup()
                self.spawn()
                self.state_dumper.dump( self.pool.get_tasks(), self.wireless )

                self.update_state_summary()

                # expire old broadcast variables
                self.wireless.expire( self.get_oldest_c_time() )

                delta = datetime.datetime.now() - main_loop_start_time
                seconds = delta.seconds + float(delta.microseconds)/10**6
                self.log.debug( "END TASK PROCESSING (took " + str( seconds ) + " sec)" )

            time.sleep(1)

            # process queued task messages
            for itask in self.pool.get_tasks():
                itask.process_incoming_messages()

            # process queued database operations
            for itask in self.pool.get_tasks():
                db_ops = itask.get_db_ops()
                for d in db_ops:
                    self.db.run_db_op(d)
            
            # record any broadcast settings to be dumped out
            if self.wireless:
                if self.wireless.new_settings:
                    db_ops = self.wireless.get_db_ops()
                    for d in db_ops:
                        self.db.run_db_op(d)
                
            # process queued commands
            self.process_command_queue()

            #print '<Pyro'
            if flags.iflag:
                flags.iflag = False
                self.update_state_summary()

            if self.config.suite_timeout:
                self.check_suite_timer()

            # initiate normal suite shutdown?
            if self.check_suite_shutdown():
                break

            # hard abort? (To Do: will a normal shutdown suffice here?)
            # 1) "abort if any task fails" is set, and one or more tasks failed
            if self.config['cylc']['abort if any task fails']:
                if self.any_task_failed():
                    raise SchedulerError( 'One or more tasks failed and "abort if any task fails" is set' )

            # 4) the run is a reference test, and any disallowed failures occured
            if self.options.reftest:
                if len( self.ref_test_allowed_failures ) > 0:
                    for itask in self.get_failed_tasks():
                        if itask.id not in self.ref_test_allowed_failures:
                            print >> sys.stderr, itask.id
                            raise SchedulerError( 'A task failed unexpectedly: not in allowed failures list' )

            self.check_timeouts()
            self.release_runahead()

        # END MAIN LOOP
        self.log.critical( "Suite shutting down at " + str(datetime.datetime.now()) )

        if self.options.genref:
            print '\nCOPYING REFERENCE LOG to suite definition directory'
            shcopy( self.logfile, self.reflogfile)

    def update_state_summary( self ):
        self.log.debug( "UPDATING STATE SUMMARY" )
        self.suite_state.update( self.pool.get_tasks(), self.clock,
                self.get_oldest_c_time(), self.get_newest_c_time(), self.paused(),
                self.will_pause_at(), self.suite_halt,
                self.will_stop_at(), self.runahead_limit )

    def process_resolved( self, tasks ):
        # process resolved dependencies (what actually triggers off what at run time).
        for itask in tasks:
            if self.runtime_graph_on:
                self.runtime_graph.update( itask, self.get_oldest_c_time(), self.get_oldest_async_tag() )
            if self.config['cylc']['log resolved dependencies']:
                itask.log( 'NORMAL', 'triggered off ' + str( itask.get_resolved_dependencies()) )

    def check_suite_timer( self ):
        if self.already_timed_out:
            return
        now = datetime.datetime.now()
        timeout = self.suite_timer_start + datetime.timedelta( minutes=self.config.suite_timeout )
        handler = self.config.event_handlers['timeout']
        if now > timeout:
            message = 'suite timed out after ' + str( self.config.suite_timeout) + ' minutes' 
            self.log.warning( message )
            if handler:
                # a handler is defined
                self.already_timed_out = True
                if self.config.abort_if_timeout_handler_fails:
                    foreground = True
                else:
                    foreground = False
                try:
                    RunHandler( 'timeout', handler, self.suite, msg=message, fg=foreground )
                except Exception, x:
                    # Note: tests suites depend on the following message:
                    print >> sys.stderr, '\nERROR: timeout EVENT HANDLER FAILED'
                    raise SchedulerError, x

            if self.config.abort_on_timeout:
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
            if self.config.suite_timeout and self.config.reset_timer:
                self.set_suite_timer()

        elif self.waiting_clocktriggered_task_ready():
            # This actually returns True if ANY task is ready to run,
            # not just clock-triggered tasks (but this should not matter).
            # For a clock-triggered task, this means its time offset is
            # up AND its prerequisites are satisfied; it won't result
            # in multiple passes through the main loop.
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
        ##        self.nudge_timer_start = datetime.datetime.now()
        ##        self.nudge_timer_on = True
        ##    else:
        ##        timeout = self.nudge_timer_start + \
        ##              datetime.timedelta( seconds=self.auto_nudge_interval )
        ##      if datetime.datetime.now() > timeout:
        ##          process = True
        ##          self.nudge_timer_on = False

        return process

    def shutdown( self, reason='' ):
        print "\nMain thread shutting down ",
        if reason != '':
            print '(' + reason + ')'
        else:
            print


        if self.pool:
            print " * telling job submission thread to terminate"
            self.pool.worker.quit = True
            self.pool.worker.join()
            # disconnect task message queues
            for itask in self.pool.get_tasks():
                if itask.message_queue:
                    self.pyro.disconnect( itask.message_queue )
            if self.state_dumper:
                self.state_dumper.dump( self.pool.get_tasks(), self.wireless )

        if self.evworker:
            print " * telling event handler thread to terminate"
            self.evworker.quit = True
            self.evworker.join()

        if self.request_handler:
            print " * telling request handling thread to terminate"
            self.request_handler.quit = True
            self.request_handler.join()
        if self.command_queue:
            self.pyro.disconnect( self.command_queue )
        if self.clock:
            self.pyro.disconnect( self.clock )
        if self.wireless:
            self.pyro.disconnect( self.wireless )
        if self.suite_id:
            self.pyro.disconnect( self.suite_id )
        if self.suite_state:
            self.pyro.disconnect( self.suite_state )

        if self.pyro:
            print " * terminating the suite Pyro daemon"
            self.pyro.shutdown()

        if self.use_lockserver:
            # do this last
            if self.lock_acquired:
                print " * releasing suite lock"
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

        #disconnect from suite-db/stop db queue
        self.db.close()
        print " * disconnecting from suite database"

        # shutdown handler
        handler = self.config.event_handlers['shutdown']
        if handler:
            if self.config.abort_if_shutdown_handler_fails:
                foreground = True
            else:
                foreground = False
            try:
                RunHandler( 'shutdown', handler, self.suite, msg=reason, fg=foreground )
            except Exception, x:
                if self.options.reftest:
                    sys.exit( '\nERROR: SUITE REFERENCE TEST FAILED' )
                else:
                    # Note: tests suites depend on the following message:
                    sys.exit( '\nERROR: shutdown EVENT HANDLER FAILED' )
            else:
                print '\nSUITE REFERENCE TEST PASSED'

        print "Main thread DONE"

    def set_stop_ctime( self, stop_tag ):
        self.log.warning( "Setting stop cycle time: " + stop_tag )
        self.stop_tag = stop_tag

    def set_stop_clock( self, dtime ):
        self.log.warning( "Setting stop clock time: " + dtime.isoformat() )
        self.stop_clock_time = dtime

    def set_stop_task( self, taskid ):
        self.log.warning( "Setting stop task: " + taskid )
        self.stop_task = taskid

    def hold_suite( self, ctime = None ):
        if ctime:
            self.log.warning( "Setting suite hold cycle time: " + ctime )
            self.hold_time = ctime
        else:
            self.hold_suite_now = True
            self.log.warning( "Holding all waiting or queued tasks now")
            for itask in self.pool.get_tasks():
                if itask.state.is_currently('queued') or itask.state.is_currently('waiting') or \
                        itask.state.is_currently('retrying'):
                    # (not runahead: we don't want these converted to
                    # held or they'll be released immediately on restart)
                    itask.reset_state_held()

    def release_suite( self ):
        if self.hold_suite_now:
            self.log.warning( "RELEASE: new tasks will be queued when ready")
            self.hold_suite_now = False
            self.hold_time = None
        for itask in self.pool.get_tasks():
            if itask.state.is_currently('held'):
                if self.stop_tag and int( itask.c_time ) > int( self.stop_tag ):
                    # this task has passed the suite stop time
                    itask.log( 'NORMAL', "Not releasing (beyond suite stop cycle) " + self.stop_tag )
                elif itask.stop_c_time and int( itask.c_time ) > int( itask.stop_c_time ):
                    # this task has passed its own stop time
                    itask.log( 'NORMAL', "Not releasing (beyond task stop cycle) " + itask.stop_c_time )
                else:
                    # release this task
                    itask.reset_state_waiting()
 
        # TO DO: write a separate method for cancelling a stop time:
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
        oldest = '99991228235959'
        for itask in self.pool.get_tasks():
            if not itask.is_cycling():
                continue
            if itask.state.is_currently('failed') or itask.state.is_currently('succeeded'):
                continue
            #if itask.is_daemon():
            #    # avoid daemon tasks
            #    continue
            if int( itask.c_time ) < int( oldest ):
                oldest = itask.c_time
        return oldest

    def get_oldest_async_tag( self ):
        # return the tag of the oldest non-daemon task
        oldest = 99999999999999
        for itask in self.pool.get_tasks():
            if itask.is_cycling():
                continue
            #if itask.state.is_currently('failed'):  # uncomment for earliest NON-FAILED 
            #    continue
            if itask.is_daemon():
                continue
            if int( itask.tag ) < oldest:
                oldest = int(itask.tag)
        return oldest

    def get_oldest_c_time( self ):
        # return the cycle time of the oldest task
        oldest = '99991228230000'
        for itask in self.pool.get_tasks():
            if not itask.is_cycling():
                continue
            #if itask.state.is_currently('failed'):  # uncomment for earliest NON-FAILED 
            #    continue
            #if itask.is_daemon():
            #    # avoid daemon tasks
            #    continue
            if int( itask.c_time ) < int( oldest ):
                oldest = itask.c_time
        return oldest

    def get_newest_c_time( self ):
        # return the cycle time of the newest task
        newest = ct('1000010101').get()
        for itask in self.pool.get_tasks():
            if not itask.is_cycling():
                continue
            # avoid daemon tasks
            #if itask.is_daemon():
            #    continue
            if int( itask.c_time ) > int( newest ):
                newest = itask.c_time
        return newest

    def no_tasks_submitted_or_running( self ):
        for itask in self.pool.get_tasks():
            if itask.state.is_currently('running') or itask.state.is_currently('submitted'):
                return False
        return True

    def get_failed_tasks( self ):
        failed = []
        for itask in self.pool.get_tasks():
            if itask.state.is_currently('failed'):
                failed.append( itask )
        return failed

    def any_task_failed( self ):
        for itask in self.pool.get_tasks():
            if itask.state.is_currently('failed'):
                return True
        return False

    def negotiate( self ):
        # run time dependency negotiation: tasks attempt to get their
        # prerequisites satisfied by other tasks' outputs.
        # BROKERED NEGOTIATION is O(n) in number of tasks.

        self.broker.reset()

        for itask in self.pool.get_tasks():
            # register task outputs
            self.broker.register( itask )

        for itask in self.pool.get_tasks():
            # try to satisfy me (itask) if I'm not already satisfied.
            if itask.not_fully_satisfied():
                self.broker.negotiate( itask )

        for itask in self.pool.get_tasks():
            # (To Do: only used by repeating async tasks now)
            if not itask.not_fully_satisfied():
                itask.check_requisites()

    def release_runahead( self ):
        if self.runahead_limit:
            ouct = self.get_runahead_base() 
            for itask in self.pool.get_tasks():
                if not itask.is_cycling():
                    # TO DO: this test is not needed?
                    continue
                if itask.state.is_currently('runahead'):
                    foo = ct( itask.c_time )
                    foo.decrement( hours=self.runahead_limit )
                    if int( foo.get() ) < int( ouct ):
                        if self.hold_suite_now:
                            itask.log( 'DEBUG', "Releasing runahead (to held)" )
                            itask.reset_state_held()
                        else:
                            itask.log( 'DEBUG', "Releasing runahead (to waiting)" )
                            itask.reset_state_waiting()

    def check_hold_spawned_task( self, old_task, new_task ):
        if self.hold_suite_now:
            new_task.log( 'NORMAL', "HOLDING (general suite hold) " )
            new_task.reset_state_held()
        elif self.stop_tag and int( new_task.c_time ) > int( self.stop_tag ):
            # we've reached the suite stop time
            new_task.log( 'NORMAL', "HOLDING (beyond suite stop cycle) " + self.stop_tag )
            new_task.reset_state_held()
        elif self.hold_time and int( new_task.c_time ) > int( self.hold_time ):
            # we've reached the suite hold time
            new_task.log( 'NORMAL', "HOLDING (beyond suite hold cycle) " + self.hold_time )
            new_task.reset_state_held()
        elif old_task.stop_c_time and int( new_task.c_time ) > int( old_task.stop_c_time ):
            # this task has a stop time configured, and we've reached it
            new_task.log( 'NORMAL', "HOLDING (beyond task stop cycle) " + old_task.stop_c_time )
            new_task.reset_state_held()
        elif self.runahead_limit:
            ouct = self.get_runahead_base()
            foo = ct( new_task.c_time )
            foo.decrement( hours=self.runahead_limit )
            if int( foo.get() ) >= int( ouct ):
                # beyond the runahead limit
                new_task.log( "NORMAL", "HOLDING (runahead limit)" )
                new_task.reset_state_runahead()

    def spawn( self ):
        # create new tasks foo(T+1) if foo has not got too far ahead of
        # the slowest task, and if foo(T) spawns
        for itask in self.pool.get_tasks():
            if itask.ready_to_spawn():
                itask.log( 'DEBUG', 'spawning')
                new_task = itask.spawn( 'waiting' )
                if itask.is_cycling():
                    self.check_hold_spawned_task( itask, new_task )
                    # perpetuate the task stop time, if there is one
                    new_task.stop_c_time = itask.stop_c_time
                self.pool.add( new_task )

    def force_spawn( self, itask ):
        if itask.state.has_spawned():
            return None
        else:
            itask.state.set_spawned()
            itask.log( 'DEBUG', 'forced spawning')
            # dynamic task object creation by task and module name
            new_task = itask.spawn( 'waiting' )
            self.check_hold_spawned_task( itask, new_task )
            # perpetuate the task stop time, if there is one
            new_task.stop_c_time = itask.stop_c_time
            self.pool.add( new_task )
            return new_task

    def earliest_unspawned( self ):
        all_spawned = True
        earliest_unspawned = '99998877665544'
        for itask in self.pool.get_tasks():
            if not itask.is_cycling():
                continue
            if not itask.state.has_spawned():
                all_spawned = False
                if not earliest_unspawned:
                    earliest_unspawned = itask.c_time
                elif int( itask.c_time ) < int( earliest_unspawned ):
                    earliest_unspawned = itask.c_time

        return [ all_spawned, earliest_unspawned ]

    def earliest_unsatisfied( self ):
        # find the earliest unsatisfied task
        all_satisfied = True
        earliest_unsatisfied = '99998877665544'
        for itask in self.pool.get_tasks():
            if not itask.is_cycling():
                continue
            if not itask.prerequisites.all_satisfied():
                all_satisfied = False
                if not earliest_unsatisfied:
                    earliest_unsatisfied = itask.c_time
                elif int( itask.c_time ) < int( earliest_unsatisfied ):
                    earliest_unsatisfied = itask.c_time

        return [ all_satisfied, earliest_unsatisfied ]

    def earliest_unsucceeded( self ):
        # find the earliest unsucceeded task
        # EXCLUDING FAILED TASKS
        all_succeeded = True
        earliest_unsucceeded = '99998877665544'
        for itask in self.pool.get_tasks():
            if not itask.is_cycling():
                continue
            if itask.state.is_currently('failed'):
                # EXCLUDING FAILED TASKS
                continue
            #if itask.is_daemon():
            #   avoid daemon tasks
            #   continue

            if not itask.state.is_currently('succeeded'):
                all_succeeded = False
                if not earliest_unsucceeded:
                    earliest_unsucceeded = itask.c_time
                elif int( itask.c_time ) < int( earliest_unsucceeded ):
                    earliest_unsucceeded = itask.c_time

        return [ all_succeeded, earliest_unsucceeded ]

    def cleanup( self ):
        # Delete tasks that are no longer needed, i.e. those that
        # spawned, succeeded, AND are no longer needed to satisfy
        # the prerequisites of other tasks.

        # times of any failed tasks. 
        failed_rt = {}
        for itask in self.pool.get_tasks():
            if not itask.is_cycling():
                continue
            if itask.state.is_currently('failed'):
                failed_rt[ itask.c_time ] = True

        # suicide
        for itask in self.pool.get_tasks():
            if itask.suicide_prerequisites.count() != 0:
                if itask.suicide_prerequisites.all_satisfied():
                    self.spawn_and_die( [itask.id], dump_state=False, reason='suicide' )

        if self.use_quick:
            self.cleanup_non_intercycle( failed_rt )

        self.cleanup_generic( failed_rt )

        self.cleanup_async()

    def async_cutoff(self):
        cutoff = 0
        for itask in self.pool.get_tasks():
            if itask.is_cycling():
                continue
            if itask.is_daemon():
                # avoid daemon tasks
                continue
            if not itask.done():
                if itask.tag > cutoff:
                    cutoff = itask.tag
        return cutoff
 
    def cleanup_async( self ):
        cutoff = self.async_cutoff()
        spent = []
        for itask in self.pool.get_tasks():
            if itask.is_cycling():
                continue
            if itask.done() and itask.tag < cutoff:
                spent.append( itask )
        for itask in spent:
            self.pool.remove( itask, 'async spent' )

    def cleanup_non_intercycle( self, failed_rt ):
        # A/ Non INTERCYCLE tasks by definition have ONLY COTEMPORAL
        # DOWNSTREAM DEPENDANTS). i.e. they are no longer needed once
        # their cotemporal peers have succeeded AND there are no
        # unspawned tasks with earlier cycle times. So:
        #
        # (i) FREE TASKS are spent if they are:
        #    spawned, succeeded, no earlier unspawned tasks.
        #
        # (ii) TIED TASKS are spent if they are:
        #    spawned, succeeded, no earlier unspawned tasks, AND there is
        #    at least one subsequent instance that is SUCCEEDED
        #    ('satisfied' would do but that allows elimination of a tied
        #    task whose successor could subsequently fail, thus
        #    requiring manual task reset after a restart).
        #  ALTERNATIVE TO (ii): DO NOT ALLOW non-INTERCYCLE tied tasks

        # time of the earliest unspawned task
        [all_spawned, earliest_unspawned] = self.earliest_unspawned()
        if all_spawned:
            self.log.debug( "all tasks spawned")
        else:
            self.log.debug( "earliest unspawned task at: " + earliest_unspawned )

        # find the spent quick death tasks
        spent = []
        for itask in self.pool.get_tasks():
            if not itask.is_cycling():
                continue
            if itask.intercycle: 
                # task not up for consideration here
                continue
            if not itask.has_spawned():
                # task has not spawned yet, or will never spawn (one off tasks)
                continue
            if not itask.done():
                # task has not succeeded yet
                continue

            #if itask.c_time in failed_rt.keys():
            #    # task is cotemporal with a failed task
            #    # THIS IS NOT NECESSARY AS WE RESTART FAILED
            #    # TASKS IN THE READY STATE?
            #    continue

            if all_spawned:
                # (happens prior to shutting down at stop top time)
                # (=> earliest_unspawned is undefined)
                continue

            if int( itask.c_time ) >= int( earliest_unspawned ):
                # An EARLIER unspawned task may still spawn a successor
                # that may need me to satisfy its prerequisites.
                # The '=' here catches cotemporal unsatisfied tasks
                # (because an unsatisfied task cannot have spawned).
                continue

            if hasattr( itask, 'is_pid' ):
                # Is there a later succeeded instance of the same task?
                # It must be SUCCEEDED in case the current task fails and
                # cannot be fixed => the task's manually inserted
                # post-gap successor will need to be satisfied by said
                # succeeded task. 
                there_is = False
                for t in self.pool.get_tasks():
                    if not t.is_cycling():
                        continue
                    if t.name == itask.name and \
                            int( t.c_time ) > int( itask.c_time ) and \
                            t.state.is_currently('succeeded'):
                                there_is = True
                                break
                if not there_is:
                    continue

            # and, by a process of elimination
            spent.append( itask )
 
        # delete the spent quick death tasks
        for itask in spent:
            self.pool.remove( itask, 'quick' )

    def cleanup_generic( self, failed_rt ):
        # B/ THE GENERAL CASE
        # No succeeded-and-spawned task that is later than the *EARLIEST
        # UNSATISFIED* task can be deleted yet because it may still be
        # needed to satisfy new tasks that may appear when earlier (but
        # currently unsatisfied) tasks spawn. Therefore only
        # succeeded-and-spawned tasks that are earlier than the
        # earliest unsatisfied task are candidates for deletion. Of
        # these, we can delete a task only IF another spent instance of
        # it exists at a later time (but still earlier than the earliest
        # unsatisfied task) 

        # BUT while the above paragraph is correct, the method can fail
        # at restart: just before shutdown, when all running tasks have
        # finished, we briefly have 'all tasks satisfied', which allows 
        # deletion without the 'earliest unsatisfied' limit, and can
        # result in deletion of succeeded tasks that are still required
        # to satisfy others after a restart.

        # THEREFORE the correct deletion cutoff is the earlier of:
        # *EARLIEST UNSUCCEEDED*  OR *EARLIEST UNSPAWNED*, the latter
        # being required to account for sequential (and potentially
        # tied) tasks that can spawn only after finishing - thus there
        # may be tasks in the system that have succeeded but have not yet
        # spawned a successor that could still depend on the deletion
        # candidate.  The only way to use 'earliest unsatisfied'
        # over a suite restart would be to record the state of all
        # prerequisites for each task in the state dump (which may be a
        # good thing to do, eventually!)

        [ all_succeeded, earliest_unsucceeded ] = self.earliest_unsucceeded()
        if all_succeeded:
            self.log.debug( "all tasks succeeded" )
        else:
            self.log.debug( "earliest unsucceeded: " + earliest_unsucceeded )

        # time of the earliest unspawned task
        [all_spawned, earliest_unspawned] = self.earliest_unspawned()
        if all_spawned:
            self.log.debug( "all tasks spawned")
        else:
            self.log.debug( "earliest unspawned task at: " + earliest_unspawned )

        cutoff = int( earliest_unsucceeded )
        if int( earliest_unspawned ) < cutoff:
            cutoff = int( earliest_unspawned )
        self.log.debug( "cleanup cutoff: " + str(cutoff) )

        # find candidates for deletion
        candidates = {}
        for itask in self.pool.get_tasks():
            if not itask.is_cycling():
                continue
            if not itask.done():
                continue
            #if itask.c_time in failed_rt.keys():
            #    continue
            if int( itask.c_time ) >= cutoff:
                continue
            
            if itask.c_time in candidates.keys():
                candidates[ itask.c_time ].append( itask )
            else:
                candidates[ itask.c_time ] = [ itask ]

        # searching from newest tasks to oldest, after the earliest
        # unsatisfied task, find any done task types that appear more
        # than once - the second or later occurrences can be deleted.
        ctimes = candidates.keys()
        ctimes.sort( key = int, reverse = True )
        seen = {}
        spent = []
        for rt in ctimes:
            if int( rt ) >= cutoff:
                continue
            
            for itask in candidates[ rt ]:
                if hasattr( itask, 'is_oneoff' ):
                    # one off candidates that do not nominate a follow-on can
                    # be assumed to have no non-cotemporal dependants
                    # and can thus be eliminated.
                    try:
                        name = itask.oneoff_follow_on
                    except AttributeError:
                        spent.append( itask )
                        continue
                else:
                    name = itask.name

                if name in seen.keys():
                    # already seen this guy, so he's spent
                    spent.append( itask )
                else:
                    # first occurence
                    seen[ name ] = True
            
        # now delete the spent tasks
        for itask in spent:
            self.pool.remove( itask, 'general' )

    def trigger_task( self, task_id ):
        # Set a task to the 'waiting' with all prerequisites satisfied,
        # and tell clock-triggered tasks to trigger regardless of their
        # designated trigger time.
        found = False
        for itask in self.pool.get_tasks():
            # Find the task to trigger.
            if itask.id == task_id:
                found = True
                break
        if not found:
            raise TaskNotFoundError, "Task not present in suite: " + task_id
        if itask.state.is_currently( 'submitting' ):
            # (manual reset of 'submitting' tasks disabled pending
            # some deep thought about concurrency with the job
            # submission thread.
            raise TaskStateError, "ERROR: cannot reset a submitting task: " + task_id

        # dump state
        self.log.warning( 'pre-trigger state dump: ' + self.state_dumper.dump( self.pool.get_tasks(), self.wireless, new_file=True ))
        itask.log( "NORMAL", "triggering now" )
        itask.reset_state_ready()
        if itask.is_clock_triggered():
            itask.set_trigger_now(True)

    def reset_task_state( self, task_id, state ):
        # we only allow resetting to a subset of available task states
        if state not in [ 'ready', 'waiting', 'succeeded', 'failed', 'held', 'spawn' ]:
            raise TaskStateError, 'Illegal reset state: ' + state
        found = False
        for itask in self.pool.get_tasks():
            # Find the task to reset.
            if itask.id == task_id:
                found = True
                break
        if not found:
            raise TaskNotFoundError, "Task not present in suite: " + task_id
        if itask.state.is_currently( 'submitting' ):
            # Currently can't reset a 'submitting' task in the job submission thread!
            raise TaskStateError, "ERROR: cannot reset a submitting task: " + task_id

        itask.log( "NORMAL", "resetting to " + state + " state" )

        self.log.warning( 'pre-reset state dump: ' + self.state_dumper.dump( self.pool.get_tasks(), self.wireless, new_file=True ))

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

    def add_prerequisite( self, task_id, message ):
        # find the task to reset
        found = False
        for itask in self.pool.get_tasks():
            if itask.id == task_id:
                found = True
                break
        if not found:
            raise TaskNotFoundError, "Task not present in suite: " + task_id

        pp = plain_prerequisites( task_id ) 
        pp.add( message )

        itask.prerequisites.add_requisites(pp)

    def insertion( self, ins_id, stop_c_time=None ):
        # TO DO: UPDATE FOR ASYCHRONOUS TASKS

        # for remote insertion of a new task, or task group
        ( ins_name, ins_ctime ) = ins_id.split( TaskID.DELIM )

        #### TASK INSERTION GROUPS TEMPORARILY DISABLED
        ###if ins_name in ( self.config[ 'task insertion groups' ] ):
        ###    ids = []
        ###    for name in self.config[ 'task insertion groups' ][ins_name]:
        ###        ids.append( name + TaskID.DELIM + ins_ctime )
        ###else:
        ids = [ ins_id ]

        rejected = []
        inserted = []
        to_insert = []
        for task_id in ids:
            [ name, c_time ] = task_id.split( TaskID.DELIM )
            # Instantiate the task proxy object
            gotit = False
            try:
                itask = self.config.get_task_proxy( name, c_time, 'waiting', stop_c_time, startup=False )
            except KeyError, x:
                try:
                    itask = self.config.get_task_proxy_raw( name, c_time, 'waiting', stop_c_time, startup=False )
                except SuiteConfigError,x:
                    self.log.warning( str(x) )
                    rejected.append( name + TaskID.DELIM + c_time )
                else:
                    gotit = True
            else: 
                gotit = True

            if gotit:
                # The task cycle time can be altered during task initialization
                # so we have to create the task before checking if the task
                # already exists in the system or the stop time has been reached.
                rject = False
                for jtask in self.pool.get_tasks():
                    if not jtask.is_cycling():
                        continue
                    if itask.id == jtask.id:
                        # task already in the suite
                        rject = True
                        break
                if rject:
                    rejected.append( itask.id )
                    itask.prepare_for_death()
                    del itask
                else: 
                    if self.stop_tag and int( itask.tag ) > int( self.stop_tag ):
                        itask.log( "NORMAL", "HOLDING at configured suite stop time " + self.stop_tag )
                        itask.reset_state_held()
                    if itask.stop_c_time and int( itask.tag ) > int( itask.stop_c_time ):
                        # this task has a stop time configured, and we've reached it
                        itask.log( "NORMAL", "HOLDING at configured task stop time " + itask.stop_c_time )
                        itask.reset_state_held()
                    inserted.append( itask.id )
                    to_insert.append(itask)

        if len( to_insert ) > 0:
            self.log.warning( 'pre-insertion state dump: ' + self.state_dumper.dump( self.pool.get_tasks(), self.wireless, new_file=True ))
            for jtask in to_insert:
                self.pool.add( jtask )
        return ( inserted, rejected )

    def purge( self, id, stop ):
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
        # TO DO: THINK ABOUT WHETHER THIS CAN APPLY TO TASKS THAT
        # ALREADY EXISTED PRE-PURGE, NOT ONLY THE JUST-SPAWNED ONES. If
        # so we should explicitly record the tasks that get satisfied
        # during the purge.

        self.log.warning( 'pre-purge state dump: ' + self.state_dumper.dump( self.pool.get_tasks(), self.wireless, new_file=True ))

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
                die.append( id )
                break

        print 'VIRTUAL TRIGGERING'
        # trace out the tree of dependent tasks
        something_triggered = True
        while something_triggered:
            self.negotiate()
            something_triggered = False
            for itask in self.pool.get_tasks():
                if int( itask.tag ) > int( stop ):
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
                    # kill these later (their outputs may still be needed)
                    die.append( itask.id )
                elif itask.suicide_prerequisites.count() > 0:
                    if itask.suicide_prerequisites.all_satisfied():
                        print '  Spawning virtually activated suicide task', itask.id
                        self.force_spawn( itask )
                        # kill these now (not setting succeeded; outputs not needed)
                        print '  Suiciding', itask.id, 'now'
                        self.kill( [itask.id], dump_state=False )

        # reset any prerequisites "virtually" satisfied during the purge
        print 'RESETTING spawned tasks to unsatisified:'
        for itask in spawn:
            print '  ', itask.id
            itask.prerequisites.set_all_unsatisfied()

        # finally, purge all tasks marked as depending on the target
        print 'REMOVING PURGED TASKS:'
        for id in die:
            print '  ', id
        self.kill( die, dump_state=False )

        print 'PURGE DONE'

    def check_timeouts( self ):
        for itask in self.pool.get_tasks():
            itask.check_submission_timeout()
            itask.check_execution_timeout()

    def waiting_clocktriggered_task_ready( self ):
        # This method actually returns True if ANY task is ready to run,
        # not just clocktriggered tasks. However, this should not be a problem.
        result = False
        for itask in self.pool.get_tasks():
            #print itask.id
            if itask.ready_to_run():
                result = True
                break
        return result

    def kill_cycle( self, tag ):
        # kill all tasks currently with given tag
        task_ids = []
        for itask in self.pool.get_tasks():
            if itask.tag == tag:
                task_ids.append( itask.id )
        self.kill( task_ids )

    def spawn_and_die_cycle( self, tag ):
        # spawn and kill all tasks currently with given tag
        task_ids = {}
        for itask in self.pool.get_tasks():
            if itask.tag == tag:
                task_ids[ itask.id ] = True
        self.spawn_and_die( task_ids )

    def spawn_and_die( self, task_ids, dump_state=True, reason='remote request' ):
        # Spawn and kill all tasks in task_ids. Works for dict or list input.
        # TO DO: clean up use of spawn_and_die (the keyword args are clumsy)

        if dump_state:
            self.log.warning( 'pre-spawn-and-die state dump: ' + self.state_dumper.dump( self.pool.get_tasks(), self.wireless, new_file=True ))

        for id in task_ids:
            # find the task
            found = False
            itask = None
            for t in self.pool.get_tasks():
                if t.id == id:
                    found = True
                    itask = t
                    break

            if not found:
                self.log.warning( "task to kill not found: " + id )
                return

            itask.log( 'DEBUG', reason )

            if not itask.state.has_spawned():
                # forcibly spawn the task and create its successor
                itask.state.set_spawned()
                itask.log( 'DEBUG', 'forced spawning' )

                new_task = itask.spawn( 'waiting' )
 
                if self.stop_tag and int( new_task.tag ) > int( self.stop_tag ):
                    # we've reached the stop time
                    new_task.log( "NORMAL", 'HOLDING at configured suite stop time' )
                    new_task.reset_state_held()
                # perpetuate the task stop time, if there is one
                new_task.stop_c_time = itask.stop_c_time
                self.pool.add( new_task )
            else:
                # already spawned: the successor already exists
                pass

            # now kill the task
            self.pool.remove( itask, reason )

    def kill( self, task_ids, dump_state=True ):
        # kill without spawning all tasks in task_ids
        if dump_state:
            self.log.warning( 'pre-kill state dump: ' + self.state_dumper.dump( self.pool.get_tasks(), self.wireless, new_file=True ))
        for id in task_ids:
            # find the task
            found = False
            itask = None
            for t in self.pool.get_tasks():
                if t.id == id:
                    found = True
                    itask = t
                    break
            if not found:
                self.log.warning( "task to kill not found: " + id )
                return
            self.pool.remove( itask, 'by request' )

    def filter_initial_task_list( self, inlist ):
        included_by_rc  = self.config['scheduling']['special tasks']['include at start-up']
        excluded_by_rc  = self.config['scheduling']['special tasks']['exclude at start-up']
        outlist = []
        for name in inlist:
            if name in excluded_by_rc:
                continue
            if len( included_by_rc ) > 0:
                if name not in included_by_rc:
                    continue
            outlist.append( name ) 
        return outlist

    def check_suite_shutdown( self ):

        # 1) shutdown requested NOW
        if self.suite_halt_now:
            if not self.no_tasks_submitted_or_running():
                self.log.warning( "STOPPING NOW: some running tasks will be orphaned" )
            return True

        # 2) normal shutdown requested and no tasks  submitted or running
        if self.suite_halt and self.no_tasks_submitted_or_running():
            self.log.info( "Stopping now: all current tasks completed" )
            return True

        # 3) if a suite stop time (wall clock) is set and has gone by,
        # get 2) above to finish when current tasks have completed.
        if self.stop_clock_time:
            now = self.clock.get_datetime()
            if now > self.stop_clock_time:
                self.log.info( "Wall clock stop time reached: " + self.stop_clock_time.isoformat() )
                if self.no_tasks_submitted_or_running():
                    return True
                else:
                    # reset self.stop_clock_time and delegate to 2) above
                    # To Do: rationalize use of hold_suite and suite_halt?
                    self.log.info( "The suite will shutdown when all running tasks have finished" )
                    self.hold_suite()
                    self.suite_halt = True
                    self.stop_clock_time = None

        # 4) if a suite stop task is set and has completed, 
        # get 2) above to finish when current tasks have completed.
        if self.stop_task:
            name, tag = self.stop_task.split(TaskID.DELIM)
            stop = True
            for itask in self.pool.get_tasks():
                if itask.name == name:
                    # To Do: the task must still be present in the pool
                    # (this should be OK; but the potential loophole
                    # will be closed by the upcoming task event databse).
                    if not itask.state.is_currently('succeeded'):
                        iname, itag = itask.id.split(TaskID.DELIM)
                        if int(itag) <= int(tag):
                            stop = False
                            break
            if stop:
                self.log.warning( "Stop task " + name + TaskID.DELIM + tag + " finished" )
                if self.no_tasks_submitted_or_running():
                    return True
                else:
                    # reset self.stop_task and delegate to 2) above
                    self.log.info( "The suite will shutdown when all running tasks have finished" )
                    self.hold_suite()
                    self.suite_halt = True
                    self.stop_task = None

        # 5) (i) all cycling tasks are held past the suite stop cycle, 
        # and (ii) all async tasks have succeeded (failed). The suite should
        # not shut down if any failed tasks exist, but there's no need
        # to check for that if (i) and (ii) are satisfied.
        stop = True
        
        i_cyc = False
        i_asy = False
        for itask in self.pool.get_tasks():
            if itask.is_cycling():
                i_cyc = True
                # don't stop if a cycling task has not passed the stop cycle
                if self.stop_tag:
                    if int( itask.c_time ) <= int( self.stop_tag ):
                        if itask.state.is_currently('succeeded') and itask.has_spawned():
                            # a succeeded task that is earlier than the
                            # stop cycle can be ignored if it has
                            # spawned, in which case the successor matters.
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
            if i_cyc:
                self.log.info( "All cycling tasks have spawned past the final cycle " + self.stop_tag )
            if i_asy:
                self.log.info( "All non-cycling tasks have succeeded" )
            return True
        else:
            return False

