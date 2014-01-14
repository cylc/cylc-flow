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

import os, sys, re
import datetime
import subprocess
from copy import copy
from random import randrange
from collections import deque
from cylc import task_state
from cylc.strftime import strftime
from cylc.global_config import get_global_cfg
from cylc.owner import user
import logging
import cylc.flags as flags
from cylc.task_receiver import msgqueue
import cylc.rundb
from cylc.run_get_stdout import run_get_stdout
from cylc.command_env import cv_scripting_sl
from parsec.util import pdeepcopy, poverride

def displaytd( td ):
    # Display a python timedelta sensibly.
    # Default for str(td) of -5 sec is '-1 day, 23:59:55' !
    d, s, m = td.days, td.seconds, td.microseconds
    secs = d * 24 * 3600 + s + m / 10**6
    if secs < 0:
        res = '-' + str( datetime.timedelta( 0, - secs, 0 ))
    else:
        res = str(td)
    return res

class PollTimer( object ):

    def __init__( self, intervals, defaults, name, log ):
        self.intervals = copy( deque(intervals) )
        self.default_intervals = deque( defaults )
        self.name = name
        self.log = log
        self.current_interval = None
        self.timer_start = None
        self.gcfg = get_global_cfg()

    def set_host( self, host, set_timer=False ):
        # the polling comms method is host-specific
        if self.gcfg.get_host_item( 'task communication method', host ) == "poll":
            if not self.intervals:
                self.intervals = copy(self.default_intervals)
                self.log( 'WARNING', '(polling comms) using default ' + self.name + ' polling intervals' )
            if set_timer:
                self.set_timer()

    def set_timer( self ):
        try:
            self.current_interval = self.intervals.popleft() * 60.0 # seconds
        except IndexError:
            # no more intervals, keep the last one
            pass
        
        if self.current_interval:
            self.log( 'NORMAL', 'setting ' + self.name + ' poll timer for ' + str(self.current_interval) + ' seconds' )
            self.timer_start = datetime.datetime.now()
        else:
            self.timer_start = None

    def get( self ):
        if not self.timer_start:
            return False
        timeout = self.timer_start + datetime.timedelta( seconds=self.current_interval )
        if datetime.datetime.now() > timeout:
            return True


class task( object ):
    """The cylc task proxy base class"""

    # RETRY LOGIC:
    #  1) ABSOLUTE SUBMIT NUMBER increments every time a task is
    #  submitted, manually or automatically by (submission or execution)
    # retries; whether or not the task actually begins executing, and is
    # appended to the task log root filename.
    #  2) SUBMISSION TRY NUMBER increments when task job submission
    # fails, if submission retries are configured, but resets to 1 if
    # the task begins executing; and is used for accounting purposes.
    #  3) EXECUTION TRY NUMBER increments only when task execution fails,
    # if execution retries are configured; and is passed to task
    # environments to allow changed behaviour after previous failures.

    clock = None
    intercycle = False
    is_cycling = False
    is_daemon = False
    is_clock_triggered = False

    event_queue = None
    poll_and_kill_queue = None

    suite_contact_env_hosts = []
    suite_contact_env = {}

    @classmethod
    def describe( cls ):
        return cls.title + '\n' + cls.description

    @classmethod
    def set_class_var( cls, item, value ):
        # set the value of a class variable
        # that will be written to the state dump file
        try:
            cls.class_vars[ item ] = value
        except AttributeError:
            cls.class_vars = {}
            cls.class_vars[ item ] = value

    @classmethod
    def get_class_var( cls, item ):
        # get the value of a class variable that is
        # written to the state dump file
        try:
            return cls.class_vars[ item ]
        except:
            raise AttributeError

    @classmethod
    def dump_class_vars( cls, FILE ):
        # dump special class variables to the state dump file
        try:
            result = ''
            for key in cls.class_vars:
                result += key + '=' + str( cls.class_vars[ key ] ) + ', '
            result = result.rstrip( ', ' )
            FILE.write( 'class ' + cls.__name__ + ' : ' + result + '\n')
        except AttributeError:
            # class has no class_vars defined
            pass

    @classmethod
    def update_mean_total_elapsed_time( cls, started, succeeded ):
        if not started:
            # TODO on suite restart we don't currently retain task started time
            return
        # the class variables here are defined in derived task classes
        if not started:
            # in case the started messaged did not get through
            return
        cls.elapsed_times.append( succeeded - started )
        elt_sec = [x.days * 86400 + x.seconds for x in cls.elapsed_times ]
        mtet_sec = sum( elt_sec ) / len( elt_sec )
        cls.mean_total_elapsed_time = mtet_sec

    def __init__( self, state, validate=False ):
        # Call this AFTER derived class initialisation

        # Derived class init MUST define:
        #  * self.id: unique identity (e.g. NAME.CYCLE for cycling tasks)
        #  * prerequisites and outputs
        #  * self.env_vars

        class_vars = {}
        self.state = task_state.task_state( state )
        self.manual_trigger = False
        
        self.stop_tag = None

        # Count instances of each top level object derived from task.
        # Top level derived classes must define:
        #   <class>.instance_count = 0
        # NOTE: top level derived classes are now defined dynamically
        # (so this is initialised in src/taskdef.py).
        self.__class__.instance_count += 1
        self.__class__.upward_instance_count += 1

        self.latest_message = ""
        self.latest_message_priority = "NORMAL"

        self.submission_timer_start = None
        self.execution_timer_start = None

        self.submitted_time = None
        self.started_time = None
        self.succeeded_time = None
        self.etc = None
        self.to_go = None
        self.summary = { 'latest_message': self.latest_message,
                         'latest_message_priority': self.latest_message_priority,
                         'started_time': '*',
                         'submitted_time': '*',
                         'succeeded_time': '*' }

        self.retries_configured = False

        self.try_number = 1
        self.retry_delay_timer_start = None

        self.sub_try_number = 1
        self.sub_retry_delay_timer_start = None

        self.message_queue = msgqueue()
        self.db_queue = []
        self.db_items = False

        self.suite_name = os.environ['CYLC_SUITE_NAME']
        self.validate = validate

        # In case task owner and host are needed by record_db_event()
        # for pre-submission events, set their initial values as if
        # local (we can't know the correct host prior to this because 
        # dynamic host selection could be used).
        self.task_host = 'localhost'
        self.task_owner = None 
        self.user_at_host = self.task_host

        self.submit_method_id = None
        self.job_sub_method = None
        self.launcher = None

        self.submission_poll_timer = None
        self.execution_poll_timer = None

        self.gcfg = get_global_cfg()

        if self.validate: # if in validate mode bypass db operations
            self.submit_num = 0
        else:
            if not self.exists:
                self.record_db_state(self.name, self.c_time, submit_num=self.submit_num, try_num=self.try_number, status=self.state.get_status())
            if self.submit_num > 0:
                self.record_db_update("task_states", self.name, self.c_time, status=self.state.get_status())

    def log( self, priority, message ):
        logger = logging.getLogger( "main" )
        message = '[' + self.id + '] -' + message
        if priority == "WARNING":
            logger.warning( message )
        elif priority == "NORMAL":
            logger.info( message )
        elif priority == "DEBUG":
            logger.debug( message )
        elif priority == "CRITICAL":
            logger.critical( message )
        else:
            logger.warning( 'UNKNOWN PRIORITY: ' + priority )
            logger.warning( '-> ' + message )

    def prepare_for_death( self ):
        # Decrement the instance count of objects derived from task
        # base. Was once used for constraining the number of instances
        # of each task type. Python's __del__() function cannot be used
        # for this as it is only called when a deleted object is about
        # to be garbage collected (not guaranteed to be right away). 
        self.__class__.instance_count -= 1

    def record_db_event(self, event="", message=""):
        call = cylc.rundb.RecordEventObject(self.name, self.c_time, self.submit_num, event, message, self.user_at_host)
        self.db_queue.append(call)
        self.db_items = True
    
    def record_db_update(self, table, name, cycle, **kwargs):
        call = cylc.rundb.UpdateObject(table, name, cycle, **kwargs)
        self.db_queue.append(call)
        self.db_items = True

    def record_db_state(self, name, cycle, time_created=datetime.datetime.now(), time_updated=None,
                     submit_num=None, is_manual_submit=None, try_num=None,
                     host=None, submit_method=None, submit_method_id=None,
                     status=None):
        call = cylc.rundb.RecordStateObject(name, cycle, 
                     time_created=time_created, time_updated=time_updated,
                     submit_num=submit_num, is_manual_submit=is_manual_submit, try_num=try_num,
                     host=host, submit_method=submit_method, submit_method_id=submit_method_id,
                     status=status)
        self.db_queue.append(call)
        self.db_items = True

    def get_db_ops(self):
        ops = []
        self.db_items = False
        for item in self.db_queue:
            if item.to_run:
                ops.append(item)
                item.to_run = False
        return ops

    def retry_delay_done( self ):
        done = False
        if self.retry_delay_timer_start:
            diff = task.clock.get_datetime() - self.retry_delay_timer_start
            foo = datetime.timedelta( 0,0,0,0,self.retry_delay,0,0 )
            if diff >= foo:
                done = True
        elif self.sub_retry_delay_timer_start:
            diff = task.clock.get_datetime() - self.sub_retry_delay_timer_start
            foo = datetime.timedelta( 0,0,0,0,self.sub_retry_delay,0,0 )
            if diff >= foo:
                done = True
        return done

    def ready_to_run( self ):
        if self.state.is_currently('queued'): # ready by definition
            return True
        elif self.state.is_currently('waiting') and self.prerequisites.all_satisfied():
            return True
        elif self.state.is_currently( 'submit-retrying', 'retrying') and self.retry_delay_done():
            return True
        else:
            return False

    def get_resolved_dependencies( self ):
        """report who I triggered off"""
        # Used by the test-battery log comparator
        dep = []
        satby = self.prerequisites.get_satisfied_by()
        for label in satby.keys():
            dep.append( satby[ label ] )
        # order does not matter here; sort to allow comparison with
        # reference run task with lots of near-simultaneous triggers.
        dep.sort()
        return dep

      
    def unfail( self ):
        # if a task is manually reset remove any previous failed message
        # or on later success it will be seen as an incomplete output.
        failed_msg = self.id + " failed"
        if self.outputs.exists(failed_msg):
            self.outputs.remove(failed_msg)
        failed_msg = self.id + "submit-failed"
        if self.outputs.exists(failed_msg):
            self.outputs.remove(failed_msg)

    def turn_off_timeouts( self ):
        self.submission_timer_start = None
        self.execution_timer_start = None

    def reset_state_ready( self ):
        self.set_status( 'waiting' )
        self.record_db_event(event="reset to ready")
        self.prerequisites.set_all_satisfied()
        self.unfail()
        self.turn_off_timeouts()
        self.outputs.set_all_incomplete()

    def reset_state_waiting( self ):
        # waiting and all prerequisites UNsatisified.
        self.set_status( 'waiting' )
        self.record_db_event(event="reset to waiting")
        self.prerequisites.set_all_unsatisfied()
        self.unfail()
        self.turn_off_timeouts()
        self.outputs.set_all_incomplete()

    def reset_state_succeeded( self, manual=True ):
        # all prerequisites satisified and all outputs complete
        self.set_status( 'succeeded' )
        if manual:
            self.record_db_event(event="reset to succeeded")
        else:
            # Artificially set to succeeded but not by the user. E.g. by
            # the purge algorithm and when reloading task definitions.
            self.record_db_event(event="set to succeeded")
        self.prerequisites.set_all_satisfied()
        self.unfail()
        self.turn_off_timeouts()
        self.outputs.set_all_completed()

    def reset_state_failed( self ):
        # all prerequisites satisified and no outputs complete
        self.set_status( 'failed' )
        self.record_db_event(event="reset to failed")
        self.prerequisites.set_all_satisfied()
        self.outputs.set_all_incomplete()
        # set a new failed output just as if a failure message came in
        self.turn_off_timeouts()
        self.outputs.add( self.id + ' failed', completed=True )

    def reset_state_held( self ):
        self.set_status( 'held' )
        self.turn_off_timeouts()
        self.record_db_event(event="reset to held")

    def reset_state_runahead( self ):
        self.set_status( 'runahead' )
        self.turn_off_timeouts()

    def set_state_ready( self ):
        # called by scheduler main thread
        self.set_status( 'ready' )

    def set_state_queued( self ):
        # called by scheduler main thread
        self.set_status( 'queued' )

    def reset_manual_trigger( self ):
        # call immediately after manual trigger flag used
        self.manual_trigger = False
        # unset any retry delay timers
        self.retry_delay_timer_start = None
        self.sub_retry_delay_timer_start = None

    def set_from_rtconfig( self, cfg={} ):
        """Some [runtime] config requiring consistency checking on reload, 
        and self variables requiring updating for the same."""
        # this is first called from class init (see taskdef.py)

        if cfg:
            rtconfig = cfg
        else:
            rtconfig = self.__class__.rtconfig

        # note: we currently only access the class variable with describe():
        self.title = rtconfig['title']
        self.description = rtconfig['description']

        if not self.retries_configured:
            # configure retry delays before the first try
            self.retries_configured = True
            # TODO - saving the retry delay lists here is not necessary
            # (it can be handled like the polling interval lists).
            if self.__class__.run_mode == 'live' or \
                ( self.__class__.run_mode == 'simulation' and not rtconfig['simulation mode']['disable retries'] ) or \
                ( self.__class__.run_mode == 'dummy' and not rtconfig['dummy mode']['disable retries'] ):
                # note that a *copy* of the retry delays list is needed
                # so that all instances of the same task don't pop off
                # the same deque (but copy of rtconfig above solves this).
                self.retry_delays = deque( rtconfig['retry delays'] )
                self.sub_retry_delays_orig = deque( rtconfig['job submission']['retry delays'])
            else:
                self.retry_delays = deque()
                self.sub_retry_delays_orig = deque()

            # retain the original submission retry deque for re-use in
            # case execution fails and submission tries start over.
            self.sub_retry_delays = copy( self.sub_retry_delays_orig )

        rrange = rtconfig['simulation mode']['run time range']
        ok = True
        if len(rrange) != 2:
            ok = False
        try:
            res = [ int( rrange[0] ), int( rrange[1] ) ]
        except:
            ok = False
        if not ok:
            raise Exception, "ERROR, " + self.name + ": simulation mode run time range must be 'int, int'" 
        try:
            self.sim_mode_run_length = randrange( res[0], res[1] )
        except Exception, x:
            print >> sys.stderr, x
            raise Exception, "ERROR: simulation mode task run time range must be [MIN,MAX)" 

        if self.__class__.run_mode == 'live' or \
                ( self.__class__.run_mode == 'simulation' and not rtconfig['simulation mode']['disable task event hooks'] ) or \
                ( self.__class__.run_mode == 'dummy' and not rtconfig['dummy mode']['disable task event hooks'] ):
            self.event_handlers = {
                'started'   : rtconfig['event hooks']['started handler'],
                'succeeded' : rtconfig['event hooks']['succeeded handler'],
                'failed'    : rtconfig['event hooks']['failed handler'],
                'warning'   : rtconfig['event hooks']['warning handler'],
                'retry'     : rtconfig['event hooks']['retry handler'],
                'execution timeout'  : rtconfig['event hooks']['execution timeout handler'],
                'submitted' : rtconfig['event hooks']['submitted handler'],
                'submission retry'   : rtconfig['event hooks']['submission retry handler'],
                'submission failed'  : rtconfig['event hooks']['submission failed handler'],
                'submission timeout' : rtconfig['event hooks']['submission timeout handler'],
                }
            self.timeouts = {
                'submission' : rtconfig['event hooks']['submission timeout'],
                'execution'  : rtconfig['event hooks']['execution timeout']
                }
            self.reset_timer = rtconfig['event hooks']['reset timer']
        else:
            self.event_handlers = {
                'submitted' : None,
                'started'   : None,
                'succeeded' : None,
                'failed'    : None,
                'warning'   : None,
                'retry'     : None,
                'submission retry'   : None,
                'submission failed'  : None,
                'submission timeout' : None,
                'execution timeout'  : None
                }
            self.timeouts = {
                'submission' : None,
                'execution'  : None
                }
            self.reset_timer = False

        self.submission_poll_timer = PollTimer( \
                    copy( rtconfig['submission polling intervals']), 
                    copy( self.gcfg.cfg['submission polling intervals']),
                    'submission', self.log )

        self.execution_poll_timer = PollTimer( \
                    copy( rtconfig['execution polling intervals']), 
                    copy( self.gcfg.cfg['execution polling intervals']),
                    'execution', self.log )
 
    def submit( self, dry_run=False, debug=False, overrides={} ):
        """NOTE THIS METHOD EXECUTES IN THE JOB SUBMISSION THREAD. It
        returns the job process number if successful. Exceptions raised
        will be caught by the job submission code and will result in a
        task failed message being sent for handling by the main thread.
        Run db updates as a result of such errors will also be done by
        the main thread in response to receiving the message."""

        if self.__class__.run_mode == 'simulation':
            self.started_time = task.clock.get_datetime()
            self.summary[ 'started_time' ] = self.started_time.isoformat()
            self.started_time_real = datetime.datetime.now()
            self.outputs.set_completed( self.id + " started" )
            self.set_status( 'running' )
            return (None,None)

        self.message_queue.put( 'NORMAL', self.id + " submitting now" )

        self.submit_num += 1
        self.record_db_update("task_states", self.name, self.c_time, submit_num=self.submit_num)

        rtconfig = pdeepcopy( self.__class__.rtconfig )
        poverride( rtconfig, overrides )
        
        self.set_from_rtconfig( rtconfig )

        if len(self.env_vars) > 0:
            # Add in any instance-specific environment variables
            # (currently only used by async_repeating tasks)
            rtconfig['environment'].update( self.env_vars )

        # construct the job launcher here so that a new one is used if
        # the task is re-triggered by the suite operator - so it will
        # get new stdout/stderr logfiles and not overwrite the old ones.

        # dynamic instantiation - don't know job sub method till run time.
        module_name = rtconfig['job submission']['method']
        self.job_sub_method = module_name

        class_name  = module_name
        try:
            # try to import built-in job submission classes first
            mod = __import__( 'cylc.job_submission.' + module_name, fromlist=[class_name] )
        except ImportError:
            try:
                # else try for user-defined job submission classes, in sys.path
                mod = __import__( module_name, fromlist=[class_name] )
            except ImportError, x:
                self.log( 'CRITICAL', 'cannot import job submission module ' + class_name )
                raise

        launcher_class = getattr( mod, class_name )

        command = rtconfig['command scripting']
        use_manual = rtconfig['manual completion']
        if self.__class__.run_mode == 'dummy':
            # (dummy tasks don't detach)
            use_manual = False
            command = rtconfig['dummy mode']['command scripting']
            if rtconfig['dummy mode']['disable pre-command scripting']:
                precommand = None
            if rtconfig['dummy mode']['disable post-command scripting']:
                postcommand = None
        else:
            precommand = rtconfig['pre-command scripting'] 
            postcommand = rtconfig['post-command scripting'] 

        if self.suite_polling_cfg:
            # generate automatic suite state polling command scripting
            #____
            # for an additional cycle time offset for --cycle:
            #offset =  rtconfig['suite state polling']['offset']
            #if offset:
            #    foo = ct( self.c_time )
            #    foo.decrement( hours=offset )
            #    cycle = foo.get()
            #else:
            #    cycle = self.c_time
            #____
            comstr = "cylc suite-state " + \
                     " --task=" + self.suite_polling_cfg['task'] + \
                     " --cycle=" + self.c_time + \
                     " --status=" + self.suite_polling_cfg['status']
            if rtconfig['suite state polling']['user']:
                comstr += " --user=" + rtconfig['suite state polling']['user']
            if rtconfig['suite state polling']['host']:
                comstr += " --host=" + rtconfig['suite state polling']['host']
            if rtconfig['suite state polling']['interval']:
                comstr += " --interval=" + str(rtconfig['suite state polling']['interval'])
            if rtconfig['suite state polling']['max-polls']:
                comstr += " --max-polls=" + str(rtconfig['suite state polling']['max-polls'])
            if rtconfig['suite state polling']['run-dir']:
                comstr += " --run-dir=" + str(rtconfig['suite state polling']['run-dir'])
            comstr += " " + self.suite_polling_cfg['suite']
            command = "echo " + comstr + "\n" + comstr

        # Determine task host settings now, just before job submission,
        # because dynamic host selection may be used.

        # host may be None (= run task on suite host)
        self.task_host = rtconfig['remote']['host']
        
        if self.task_host:
            # 1) check for dynamic host selection command
            #   host = $( host-select-command )
            #   host =  ` host-select-command `
            m = re.match( '(`|\$\()\s*(.*)\s*(`|\))$', self.task_host )
            if m:
                # extract the command and execute it
                hs_command = m.groups()[1]
                res = run_get_stdout( hs_command ) # (T/F,[lines])
                if res[0]:
                    # host selection command succeeded
                    self.task_host = res[1][0]
                else:
                    # host selection command failed
                    raise Exception("Host selection by " + self.task_host + " failed\n  " + '\n'.join(res[1]) )

            # 2) check for dynamic host selection variable:
            #   host = ${ENV_VAR}
            #   host = $ENV_VAR

            n = re.match( '^\$\{{0,1}(\w+)\}{0,1}$', self.task_host )
            # any string quotes are stripped by file parsing 
            if n:
                var = n.groups()[0]
                try:
                    self.task_host = os.environ[var]
                except KeyError, x:
                    raise Exception( "Host selection by " + self.task_host + " failed:\n  Variable not defined: " + str(x) )

            self.log( "NORMAL", "Task host: " + self.task_host )
        else:
            self.task_host = "localhost"

        self.task_owner = rtconfig['remote']['owner']

        if self.task_owner:
            self.user_at_host = self.task_owner + "@" + self.task_host
        else:
            self.user_at_host = self.task_host
        self.submission_poll_timer.set_host( self.task_host )
        self.execution_poll_timer.set_host( self.task_host )

        if self.task_host not in self.__class__.suite_contact_env_hosts and \
                self.task_host != 'localhost':
            # If the suite contact file has not been copied to user@host
            # host yet, do so. This will happen for the first task on
            # this remote account inside the job-submission thread just
            # prior to job submission.
            self.log( 'NORMAL', 'Copying suite contact file to ' + self.user_at_host )
            suite_run_dir = self.gcfg.get_derived_host_item(self.suite_name, 'suite run directory')
            env_file_path = os.path.join(suite_run_dir, "cylc-suite-env")
            r_suite_run_dir = self.gcfg.get_derived_host_item(
                    self.suite_name, 'suite run directory', self.task_host, self.task_owner)
            r_env_file_path = '%s:%s/cylc-suite-env' % ( self.user_at_host, r_suite_run_dir)
            cmd1 = ['ssh', '-oBatchMode=yes', self.user_at_host, 'mkdir', '-p', r_suite_run_dir]
            cmd2 = ['scp', '-oBatchMode=yes', env_file_path, r_env_file_path]
            for cmd in [cmd1,cmd2]:
                if subprocess.call(cmd): # return non-zero
                    raise Exception("ERROR: " + str(cmd))
            self.__class__.suite_contact_env_hosts.append( self.task_host )
        
        self.record_db_update("task_states", self.name, self.c_time, submit_method=module_name, host=self.user_at_host)

        jobconfig = {
                'directives'             : rtconfig['directives'],
                'initial scripting'      : rtconfig['initial scripting'],
                'environment scripting'  : rtconfig['environment scripting'],
                'runtime environment'    : rtconfig['environment'],
                'remote suite path'      : rtconfig['remote']['suite definition directory'],
                'job script shell'       : rtconfig['job submission']['shell'],
                'command template'       : rtconfig['job submission']['command template'],
                'work sub-directory'     : rtconfig['work sub-directory'],
                'use manual completion'  : use_manual,
                'pre-command scripting'  : precommand,
                'command scripting'      : command,
                'post-command scripting' : postcommand,
                'namespace hierarchy'    : self.namespace_hierarchy,
                'submission try number'  : self.sub_try_number,
                'try number'             : self.try_number,
                'absolute submit number' : self.submit_num,
                'is cold-start'          : self.is_coldstart,
                'task owner'             : self.task_owner,
                'task host'              : self.task_host,
                'log files'              : self.logfiles,
                }
        try:
            self.launcher = launcher_class( self.id, self.suite_name, jobconfig, str(self.submit_num) )
        except Exception, x:
            # currently a bad hostname will fail out here due to an is_remote_host() test
            raise  # TODO - check best way of alerting the user here
            #raise Exception( 'Failed to create job launcher\n  ' + str(x) )

        try:
            p = self.launcher.submit( dry_run, debug )
        except Exception, x:
            raise  # TODO - check best way of alerting the user here
            #raise Exception( 'Job submission failed\n  ' + str(x) )
        else:
            return (p,self.launcher)

    def presubmit( self, owner, host, subnum ):
        """A cut down version of submit, without the job submission,
        just to provide access to the launcher-specific job poll
        commands before the task is submitted (polling in submitted
        state or on suite restart)."""
        # TODO - refactor to get easier access to polling commands!

        rtconfig = pdeepcopy( self.__class__.rtconfig )

        # dynamic instantiation - don't know job sub method till run time.
        module_name = rtconfig['job submission']['method']
        self.job_sub_method = module_name

        class_name  = module_name
        try:
            # try to import built-in job submission classes first
            mod = __import__( 'cylc.job_submission.' + module_name, fromlist=[class_name] )
        except ImportError:
            try:
                # else try for user-defined job submission classes, in sys.path
                mod = __import__( module_name, fromlist=[class_name] )
            except ImportError, x:
                self.log( 'CRITICAL', 'cannot import job submission module ' + class_name )
                raise

        launcher_class = getattr( mod, class_name )

        jobconfig = {
                'directives'             : rtconfig['directives'],
                'initial scripting'      : rtconfig['initial scripting'],
                'environment scripting'  : rtconfig['environment scripting'],
                'runtime environment'    : rtconfig['environment'],
                'remote suite path'      : rtconfig['remote']['suite definition directory'],
                'job script shell'       : rtconfig['job submission']['shell'],
                'command template'       : rtconfig['job submission']['command template'],
                'work sub-directory'     : rtconfig['work sub-directory'],
                'use manual completion'  : False,
                'pre-command scripting'  : '',
                'command scripting'      : '',
                'post-command scripting' : '',
                'namespace hierarchy'    : '',
                'submission try number'  : 1,
                'try number'             : 1,
                'absolute submit number' : subnum,
                'is cold-start'          : False,
                'task owner'             : owner,
                'task host'              : host,
                'log files'              : self.logfiles,
                }
        try:
            launcher = launcher_class( self.id, self.suite_name, jobconfig, str(subnum) )
        except Exception, x:
            raise
            # currently a bad hostname will fail out here due to an is_remote_host() test
            raise Exception( 'Failed to create job launcher\n  ' + str(x) )
        return launcher

    def check_timers( self ):
        # not called in simulation mode
        if self.state.is_currently( 'submitted' ):
            self.check_submission_timeout()
            if self.submission_poll_timer:
                if self.submission_poll_timer.get():
                    self.poll()
                    self.submission_poll_timer.set_timer()
        elif self.state.is_currently( 'running' ):
            self.check_execution_timeout()
            if self.execution_poll_timer:
                if self.execution_poll_timer.get():
                    self.poll()
                    self.execution_poll_timer.set_timer()

    def check_submission_timeout( self ):
        # only called if in the 'submitted' state
        timeout = self.timeouts['submission']
        if not self.submission_timer_start or timeout is None:
            # (explicit None in case of a zero timeout!)
            # no timer set
            return

        # if timed out, log warning, poll, queue event handler, and turn off the timer
        current_time = task.clock.get_datetime()
        cutoff = self.submission_timer_start + datetime.timedelta( minutes=timeout )
        if current_time > cutoff:
            msg = 'job submitted ' + str(timeout) + ' minutes ago, but has not started'
            self.log( 'WARNING', msg )

            self.poll()
        
            handler = self.event_handlers['submission timeout']
            if handler:
                self.log( 'DEBUG', "Queueing submission timeout event handler" )
                self.__class__.event_queue.put( ('submission timeout', handler, self.id, msg) )

            self.submission_timer_start = None

    def check_execution_timeout( self ):
        # only called if in the 'running' state
        timeout = self.timeouts['execution']
        if not self.execution_timer_start or timeout is None:
            # (explicit None in case of a zero timeout!)
            # no timer set
            return

        # if timed out: log warning, poll, queue event handler, and turn off the timer
        current_time = task.clock.get_datetime()
        cutoff = self.execution_timer_start + datetime.timedelta( minutes=timeout )
        if current_time > cutoff:
            if self.reset_timer:
                # the timer is being re-started by put messages
                msg = 'last message ' + str(timeout) + ' minutes ago, but job not finished'
            else:
                msg = 'job started ' + str(timeout) + ' minutes ago, but has not finished'
            self.log( 'WARNING', msg )

            self.poll()
 
            # if no handler is specified, return
            handler = self.event_handlers['execution timeout']
            if handler:
                self.log( 'DEBUG', "Queueing execution timeout event handler" )
                self.__class__.event_queue.put( ('execution timeout', handler, self.id, msg) )

            self.execution_timer_start = None

    def sim_time_check( self ):
        timeout = self.started_time_real + \
                datetime.timedelta( seconds=self.sim_mode_run_length )
        if datetime.datetime.now() > timeout:
            if self.__class__.rtconfig['simulation mode']['simulate failure']:
                self.message_queue.put( 'NORMAL', self.id + ' submitted' )
                self.message_queue.put( 'CRITICAL', self.id + ' failed' )
            else:
                self.message_queue.put( 'NORMAL', self.id + ' submitted' )
                self.message_queue.put( 'NORMAL', self.id + ' succeeded' )
            return True
        else:
            return False

    def set_all_internal_outputs_completed( self ):
        if self.reject_if_failed( 'set_all_internal_outputs_completed' ):
            return
        self.log( 'DEBUG', 'setting all internal outputs completed' )
        for message in self.outputs.completed:
            if message != self.id + ' started' and \
                    message != self.id + ' succeeded' and \
                    message != self.id + ' completed':
                self.message_queue.put( 'NORMAL', message )

    def is_complete( self ):  # not needed?
        if self.outputs.all_completed():
            return True
        else:
            return False

    def reject_if_failed( self, message ):
        if self.state.is_currently('failed'):
            if self.__class__.rtconfig['enable resurrection']:
                self.log( 'WARNING', 'message receive while failed: I am returning from the dead!' )
                return False
            else:
                self.log( 'WARNING', 'rejecting a message received while in the failed state:' )
                self.log( 'WARNING', '  ' + message )
            return True
        else:
            return False

    def process_incoming_messages( self ):
        queue = self.message_queue.get_queue() 
        while queue.qsize() > 0:
            self.process_incoming_message( queue.get() )
            queue.task_done()

    def process_incoming_message( self, (priority, message) ):
        """
        Parse incoming messages and update task state accordingly.
        The latest message is assumed to reflect the true state of the
        task *unless* it would set the state backward in the natural
        order of events (a poll can take a couple of seconds to execute,
        during which time it is possible for a pyro message to come in
        reflecting a state change that occurred just *after* the poll
        executed, in which case the poll result, if actioned, would
        erroneously set the task state backwards.

        TODO - formalize state ordering, for: 'if new_state < old_state'
        """

        # print incoming messages to stdout
     #   print '  *', message
        # Log every incoming task message. Prepend '>' to distinguish
        # from other non-task message log entries.
        self.log( priority, '(current:' + self.state.get_status() + ')> ' + message )

        # We have decided not to record every incoming message as an event.
        #prefix = "message received "
        #if priority == 'CRITICAL':
        #    self.record_db_event(event=prefix+'(CRITICAL)', message=message)
        #elif priority == 'WARNING':
        #    self.record_db_event(event=prefix+'(WARNING)', message=message)
        #else:
        #    self.record_db_event(event=prefix+'(NORMAL)', message=message)

        # always update the suite state summary for latest message
        self.latest_message = message
        self.latest_message_priority = priority
        self.summary[ 'latest_message' ] = self.latest_message
        self.summary[ 'latest_message_priority' ] = self.latest_message_priority
        flags.iflag = True

        if self.reject_if_failed( message ):
            # Failed tasks do not send messages unless declared resurrectable
            return

        msg_was_polled = False
        if message.startswith( 'polled ' ):
            msg_was_polled = True
            message = message[7:]

        # remove the remote event time (or "unknown-time") from the end:
        message = re.sub( ' at \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$', '', message )

        # Remove the prepended task ID.
        content = message.replace( self.id + ' ', '' )

        # If the message matches a registered output, record it as completed.
        if self.outputs.exists( message ):
            if not self.outputs.is_completed( message ):
                flags.pflag = True
                self.outputs.set_completed( message )
                self.record_db_event(event="output completed", message=content)
            elif not msg_was_polled:
                # This output has already been reported complete.
                # Not an error condition - maybe the network was down for a bit.
                # Ok for polling as multiple polls *should* produce the same result.
                self.log( "WARNING", "Unexpected output (already completed):\n  " + message )

        # Handle warning events
        if priority == 'WARNING':
            handler = self.event_handlers['warning']
            if handler:
                self.log( 'DEBUG', "Queueing warning event handler" )
                self.__class__.event_queue.put( ('warning', handler, self.id, content) )

        if self.reset_timer:
            # Reset execution timer on incoming messages
            self.execution_timer_start = task.clock.get_datetime()

        if content == 'submitting now':
            # (A fake task message from the job submission thread).
            # The job submission command was about to be executed.
            self.record_db_event(event="submitting now")

        elif content == 'submission succeeded':
            # The job submission command returned success status.
            # (A fake task message from the job submission thread).
            # (note it is possible for 'task started' to arrive first).
            
            # flag another round through the task processing loop to
            # allow submitted tasks to spawn even if nothing else is
            # happening
            flags.pflag = True
 
            # TODO - should we use the real event time from the message here?
            self.submitted_time = task.clock.get_datetime()
            self.summary[ 'submitted_time' ] = self.submitted_time.isoformat()

            outp = self.id + " submitted" # hack: see github #476
            self.outputs.set_completed( outp )
            self.record_db_event(event="submission succeeded" )
            handler = self.event_handlers['submitted']
            if handler:
                self.log( 'DEBUG', "Queueing submitted event handler" )
                self.__class__.event_queue.put( ('submitted', handler, self.id, 'job submitted') )

            if self.state.is_currently( 'ready' ):
                # The 'started' message can arrive before 'submitted' if
                # the task starts executing very quickly. So only set
                # to 'submitted' and set the job submission timer if
                # currently still in the 'ready' state.
                self.set_status( 'submitted' )
                self.submission_timer_start = self.submitted_time
                self.submission_poll_timer.set_timer()

        elif content.startswith( 'submit_method_id='):
            # (A fake task message from the job submission thread).
            # Capture and record the submit method job ID.
            self.submit_method_id = content[len('submit_method_id='):]
            self.record_db_update("task_states", self.name, self.c_time, submit_method_id=self.submit_method_id)
                                  
        elif ( content == 'submission failed' or content == 'kill command succeeded' ) and \
                self.state.is_currently('ready','submitted'):

            # (a fake task message from the job submission thread)
            self.submit_method_id = None
            try:
                # Is there a retry lined up for this task?
                self.sub_retry_delay = float(self.sub_retry_delays.popleft())
            except IndexError:
                # There is no submission retry lined up: definitive failure.
                flags.pflag = True
                outp = self.id + " submit-failed" # hack: see github #476
                self.outputs.add( outp )
                self.outputs.set_completed( outp )
                self.set_status( 'submit-failed' )
                self.record_db_event(event="submission failed" )
                handler = self.event_handlers['submission failed']
                if handler:
                    self.log( 'DEBUG', "Queueing submission failed event handler" )
                    self.__class__.event_queue.put( ('submission failed', handler, self.id,'job submission failed') )
            else:
                # There is a retry lined up
                msg = "job submission failed, retrying in " + str(self.sub_retry_delay) +  " minutes"
                self.log( "NORMAL", msg )
                self.sub_retry_delay_timer_start = task.clock.get_datetime()
                self.sub_try_number += 1
                self.set_status( 'submit-retrying' )
                self.record_db_event(event="submission failed", message="submit-retrying in " + str(self.sub_retry_delay) )
                self.prerequisites.set_all_satisfied()
                self.outputs.set_all_incomplete()
                # Handle submission retry events
                handler = self.event_handlers['submission retry']
                if handler:
                    self.log( 'DEBUG', "Queueing submission retry event handler" )
                    self.__class__.event_queue.put( ('submission retry', handler, self.id, msg))
 
        elif content == 'started' and self.state.is_currently( 'ready','submitted','submit-failed' ):
            # Received a 'task started' message

            flags.pflag = True
            self.set_status( 'running' )
            self.record_db_event(event="started" )
            self.started_time = task.clock.get_datetime()
            self.summary[ 'started_time' ] = self.started_time.isoformat()
            self.started_time_real = datetime.datetime.now()

            # TODO - should we use the real event time extracted from the message here:
            self.execution_timer_start = self.started_time

            # submission was successful so reset submission try number
            self.sub_try_number = 0
            self.sub_retry_delays = copy( self.sub_retry_delays_orig )
            handler = self.event_handlers['started']
            if handler:
                self.log( 'DEBUG', "Queueing started event handler" )
                self.__class__.event_queue.put( ('started', handler, self.id, 'job started') )

            self.execution_poll_timer.set_timer()

        elif content == 'succeeded' and self.state.is_currently('ready','submitted','submit-failed','running','failed'):
            # Received a 'task succeeded' message
            # (submit* states in case of very fast submission and execution)
            self.execution_timer_start = None
            flags.pflag = True
            self.succeeded_time = task.clock.get_datetime()
            self.summary[ 'succeeded_time' ] = self.succeeded_time.isoformat()
            self.__class__.update_mean_total_elapsed_time( self.started_time, self.succeeded_time )
            self.set_status( 'succeeded' )
            self.record_db_event(event="succeeded" )
            handler = self.event_handlers['succeeded']
            if handler:
                self.log( 'DEBUG', "Queueing succeeded event handler" )
                self.__class__.event_queue.put( ('succeeded', handler, self.id, 'job succeeded') )
            if not self.outputs.all_completed():
                # This is no longer treated as an error condition.
                err = "Assuming non-reported outputs were completed:"
                for key in self.outputs.not_completed:
                    err += "\n" + key
                self.log( 'WARNING', err )
                self.outputs.set_all_completed()

        elif ( content == 'failed' or content == 'kill command succeeded' ) and \
                self.state.is_currently('ready','submitted','submit-failed','running','succeeded'):
            # (submit* states in case of very fast submission and
            # execution; and the fact that polling tasks 1-2 secs)

            # Received a 'task failed' message, or killed, or polling failed
            self.execution_timer_start = None
            try:
                # Is there a retry lined up for this task?
                self.retry_delay = float(self.retry_delays.popleft())
            except IndexError:
                # There is no retry lined up: definitive failure.
                # Add the failed message as a task output so that other tasks can
                # trigger off the failure event (failure outputs are not added in
                # advance - they are not completed outputs in case of success):
                flags.pflag = True
                self.outputs.add( message )
                self.outputs.set_completed( message )
                self.set_status( 'failed' )
                self.record_db_event(event="failed" )
                handler = self.event_handlers['failed']
                if handler:
                    self.log( 'DEBUG', "Queueing failed event handler" )
                    self.__class__.event_queue.put( ('failed', handler, self.id, 'job failed') )
            else:
                # There is a retry lined up
                msg = "job failed, retrying in " + str(self.retry_delay) + " minutes" 
                self.log( "NORMAL", msg )
                self.retry_delay_timer_start = task.clock.get_datetime()
                self.try_number += 1
                self.set_status( 'retrying' )
                self.record_db_event(event="failed", message="retrying in " + str( self.retry_delay) )
                self.prerequisites.set_all_satisfied()
                self.outputs.set_all_incomplete()
                # Handle retry events
                handler = self.event_handlers['retry']
                if handler:
                    self.log( 'DEBUG', "Queueing retry event handler" )
                    self.__class__.event_queue.put( ('retry', handler, self.id, msg  ))

        elif content.startswith("Task job script received signal"):
            # capture and record signals sent to task proxy
            self.record_db_event(event="signaled", message=content)

        else:
            # Unhandled messages. These include:
            #  * general non-output/progress messages
            #  * poll messages that repeat previous results
            # Note that all messages are logged already at the top.
            self.log('DEBUG', '(current:' + self.state.get_status() + ') unhandled: ' + content )

    def set_status( self, status ):
        if status != self.state.get_status():
            self.log( 'DEBUG', '(setting:' + status + ')' )
            self.state.set_status( status )
            self.record_db_update("task_states", self.name, self.c_time, 
                                  submit_num=self.submit_num, try_num=self.try_number, 
                                  status=status)

    def update( self, reqs ):
        for req in reqs.get_list():
            if req in self.prerequisites.get_list():
                # req is one of my prerequisites
                if reqs.is_satisfied(req):
                    self.prerequisites.set_satisfied( req )

    def dump_state( self, FILE ):
        # Write state information to the state dump file
        # This must be compatible with __init__() on reload
        FILE.write( self.id + ' : ' + self.state.dump() + '\n' )

    def spawn( self, state ):
        self.state.set_spawned()
        successor = self.__class__( self.next_tag(), state )
        # propagate task stop time
        successor.stop_c_time = self.stop_c_time
        return successor

    def has_spawned( self ):
        # the one off task type modifier overrides this.
        return self.state.has_spawned()

    def ready_to_spawn( self ):
        """Spawn on submission - prevents uncontrolled spawning but
        allows successive instances to run in parallel.
            A task can only fail after first being submitted, therefore
        a failed task should spawn if it hasn't already. Resetting a
        waiting task to failed will result in it spawning."""
        if self.has_spawned():
            # (note that oneoff tasks pretend to have spawned already)
            return False
        return self.state.is_currently('submitted', 'running', 'succeeded', 'failed', 'retrying')

    def done( self ):
        # return True if task has succeeded and spawned
        if self.state.is_currently('succeeded') and self.state.has_spawned():
            return True
        else:
            return False

    def check_requisites( self ):
        # overridden by repeating asynchronous tasks
        pass

    def get_state_summary( self ):
        # derived classes can call this method and then
        # add more information to the summary if necessary.

        self.summary.setdefault( 'name', self.name )
        self.summary.setdefault( 'description', self.description )
        self.summary.setdefault( 'title', self.title )
        self.summary.setdefault( 'label', self.tag )
        self.summary[ 'state' ] = self.state.get_status()
        self.summary[ 'spawned' ] = self.state.has_spawned()

        # str(timedelta) => "1 day, 23:59:55.903937" (for example)
        # to strip off fraction of seconds:
        # timedelta = re.sub( '\.\d*$', '', timedelta )

        if self.__class__.mean_total_elapsed_time:
            met = self.__class__.mean_total_elapsed_time
            self.summary[ 'mean total elapsed time' ] =  met
        else:
            # first instance: no mean time computed yet
            self.summary[ 'mean total elapsed time' ] =  '*'

        self.summary[ 'logfiles' ] = self.logfiles.get_paths()

        return self.summary

    def not_fully_satisfied( self ):
        if not self.prerequisites.all_satisfied():
            return True
        if not self.suicide_prerequisites.all_satisfied():
            return True
        return False

    def satisfy_me( self, outputs ):
        self.prerequisites.satisfy_me( outputs )
        if self.suicide_prerequisites.count() > 0:
            self.suicide_prerequisites.satisfy_me( outputs )

    def adjust_tag( self, tag ):
        # Override to modify initial tag if necessary.
        return tag

    def next_tag( self ):
        # Asynchronous tasks: increment the tag by one.
        # Cycling tasks override this to compute their next valid cycle time.
        return str( int( self.tag ) + 1 )

    def poll( self ):
        """Poll my live task job and update status accordingly."""
        if self.__class__.run_mode == 'simulation':
            # No real task to poll
            return
        if not self.submit_method_id:
            self.log( 'WARNING', 'No job submit ID to poll!' )
            return
        if self.__class__.rtconfig['manual completion']:
            self.log( 'WARNING', 'Detaching tasks cannot be polled (the real job ID is unknown)' )
            return

        launcher = self.launcher
        if not launcher:
            if self.user_at_host:
                if "@" in self.user_at_host:
                    self.task_owner, self.task_host = self.user_at_host.split('@', 1)
                else:
                    self.task_host = self.user_at_host
            launcher = self.presubmit( self.task_owner, self.task_host, self.submit_num )

        if not hasattr( launcher, 'poll' ):
            # (for job submission methods that do not handle polling yet)
            self.log( 'WARNING', "'" + self.job_sub_method + "' job submission does not support polling" )
            return

        cmd = ("cylc get-job-status %(status_file)s %(job_sys)s %(job_id)s" % {
                    "status_file": launcher.jobfile_path + ".status",
                    "job_sys": launcher.__class__.__name__,
                    "job_id": self.submit_method_id})
        if self.user_at_host not in [user + '@localhost', 'localhost']:
            cmd = cv_scripting_sl + "; " + cmd
            cmd = 'ssh -oBatchMode=yes ' + self.user_at_host + " '" + cmd + "'"

        # TODO - can we just pass self.message_queue.put rather than whole self?
        self.log( 'NORMAL', 'polling now' )
        self.__class__.poll_and_kill_queue.put( (cmd, self, 'poll') )

    def kill( self ):
        if self.__class__.run_mode == 'simulation':
            # No real task to kill
            return
        if not self.state.is_currently('running', 'submitted' ):
            self.log( 'WARNING', 'Only submitted or running tasks can be killed.' )
            return
        if not self.submit_method_id:
            # should not happen
            self.log( 'CRITICAL', 'No submit method ID' )
            return
        if self.__class__.rtconfig['manual completion']:
            self.log( 'WARNING', 'Detaching tasks cannot be killed (the real job ID is unknown)' )
            return

        launcher = self.launcher
        if not launcher:
            if self.user_at_host:
                if "@" in self.user_at_host:
                    self.task_owner, self.task_host = self.user_at_host.split('@', 1)
                else:
                    self.task_host = self.user_at_host
            launcher = self.presubmit( self.task_owner, self.task_host, self.submit_num )

        if not hasattr( launcher, 'kill' ):
            # (for job submission methods that do not handle polling yet)
            self.log( 'WARNING', "'" + self.job_sub_method + "' job submission does not support killing" )
            return

        cmd = ("cylc job-kill %(status_file)s %(job_sys)s %(job_id)s" % {
                    "status_file": launcher.jobfile_path + ".status",
                    "job_sys": launcher.__class__.__name__,
                    "job_id": self.submit_method_id})
        if self.user_at_host != user + '@localhost':
            cmd = cv_scripting_sl + "; " + cmd
            cmd = 'ssh -oBatchMode=yes ' + self.user_at_host + " '" + cmd + "'"
        # TODO - just pass self.message_queue.put rather than whole self?
        self.log( 'CRITICAL', "Killing job" )
        self.__class__.poll_and_kill_queue.put( (cmd, self, 'kill') )
