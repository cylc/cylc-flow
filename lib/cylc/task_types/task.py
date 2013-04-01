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

# This module uses the @classmethod decorator, introduced in Python 2.4.
# . @classmethod
# . def foo( bar ):
# .   pass
# Equivalent Python<2.4 form:
# . def foo( bar ):
# .   pass
# . foo = classmethod( foo )

import os, sys, re
import datetime
from copy import copy, deepcopy
from random import randrange
from collections import deque
from cylc import task_state
from cylc.strftime import strftime
from cylc.global_config import gcfg
from cylc.owner import user
from cylc.suite_host import hostname as suite_hostname
import logging
import cylc.flags as flags
from cylc.task_receiver import msgqueue
import cylc.rundb
from cylc.run_get_stdout import run_get_stdout

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
    # 
    # Currently on manual re-triggering...

    clock = None
    intercycle = False

    event_queue = None

    # set by the back door at startup:
    cylc_env = {}

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
        # the class variables here are defined in derived task classes
        if not started:
            # in case the started messaged did not get through
            return
        cls.elapsed_times.append( succeeded - started )
        elt_sec = [x.days * 86400 + x.seconds for x in cls.elapsed_times ]
        mtet_sec = sum( elt_sec ) / len( elt_sec )
        cls.mean_total_elapsed_time = datetime.timedelta( seconds=mtet_sec )

    def __init__( self, state, validate=False ):
        # Call this AFTER derived class initialisation

        # Derived class init MUST define:
        #  * self.id: unique identity (e.g. NAME.CYCLE for cycling tasks)
        #  * prerequisites and outputs
        #  * self.env_vars

        class_vars = {}
        self.state = task_state.task_state( state )
        self.trigger_now = False # used by clock-triggered tasks

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

        self.retries_configured = False

        self.try_number = 1
        self.retry_delay_timer_start = None

        self.sub_try_number = 1
        self.sub_retry_delay_timer_start = None

        self.message_queue = msgqueue()
        self.db_queue = []

        self.suite_name = os.environ['CYLC_SUITE_REG_NAME']
        self.validate = validate
        
        # sets submit num for restarts or when triggering state prior to submission
        if self.validate: # if in validate mode bypass db operations
            self.submit_num = 0
        else:
            self.db_path = os.path.join(gcfg.cfg['task hosts']['local']['run directory'], self.suite_name)
            self.db = cylc.rundb.CylcRuntimeDAO(suite_dir=self.db_path)
            submits = self.db.get_task_current_submit_num(self.name, self.c_time)
            if submits > 0:
                self.submit_num = submits
                self.record_db_update("task_states", self.name, self.c_time, status=self.state.get_status()) #is this redundant?
            else:
                self.submit_num = 0

            if not self.db.get_task_state_exists(self.name, self.c_time):
                try:
                    self.record_db_state(self.name, self.c_time, submit_num=self.submit_num, try_num=self.try_number, status=self.state.get_status()) #queued call
                except:
                    pass
            self.db.close()

        self.hostname = None
        self.owner = None
        self.submit_method = None

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
        user_at_host = ""
        if event in ["submission failed", "submission succeeded" ]:
            if self.owner is None:
                self.owner = user
            if self.hostname is None:
                self.hostname = "localhost"
            user_at_host = self.owner + "@" + self.hostname
        call = cylc.rundb.RecordEventObject(self.name, self.c_time, self.submit_num, event, message, user_at_host)
        self.db_queue.append(call)
    
    def record_db_update(self, table, name, cycle, **kwargs):
        call = cylc.rundb.UpdateObject(table, name, cycle, **kwargs)
        self.db_queue.append(call)        

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

    def get_db_ops(self):
        ops = []
        for item in self.db_queue:
            if item.to_run:
                ops.append(item)
                item.to_run = False
        return ops

    def ready_to_run( self ):
        ready = False
        if self.state.is_currently('queued') or \
            self.state.is_currently('waiting') and self.prerequisites.all_satisfied() or \
             self.state.is_currently('retrying') and self.prerequisites.all_satisfied():
                if self.retry_delay_timer_start:
                     diff = task.clock.get_datetime() - self.retry_delay_timer_start
                     foo = datetime.timedelta( 0,0,0,0,self.retry_delay,0,0 )
                     if diff >= foo:
                        ready = True
                elif self.sub_retry_delay_timer_start:
                     diff = task.clock.get_datetime() - self.sub_retry_delay_timer_start
                     foo = datetime.timedelta( 0,0,0,0,self.sub_retry_delay,0,0 )
                     if diff >= foo:
                        ready = True
                else:
                    ready = True
        return ready

    def get_resolved_dependencies( self ):
        dep = []
        satby = self.prerequisites.get_satisfied_by()
        for label in satby.keys():
            dep.append( satby[ label ] )
        return dep

      
    def unfail( self ):
        # if a task is manually reset remove any previous failed message
        # or on later success it will be seen as an incomplete output.
        failed_msg = self.id + " failed"
        if self.outputs.exists(failed_msg):
            self.outputs.remove(failed_msg)

    def turn_off_timeouts( self ):
        self.submission_timer_start = None
        self.execution_timer_start = None

    def reset_state_ready( self ):
        self.state.set_status( 'waiting' )
        self.record_db_update("task_states", self.name, self.c_time, submit_num=self.submit_num, status="waiting")
        self.record_db_event(event="reset to waiting")
        self.prerequisites.set_all_satisfied()
        self.unfail()
        self.turn_off_timeouts()
        self.outputs.set_all_incomplete()

    def reset_state_waiting( self ):
        # waiting and all prerequisites UNsatisified.
        self.state.set_status( 'waiting' )
        self.record_db_update("task_states", self.name, self.c_time, status="waiting")
        self.record_db_event(event="reset to waiting")
        self.prerequisites.set_all_unsatisfied()
        self.unfail()
        self.turn_off_timeouts()
        self.outputs.set_all_incomplete()

    def reset_state_succeeded( self, manual=True ):
        # all prerequisites satisified and all outputs complete
        self.state.set_status( 'succeeded' )
        self.record_db_update("task_states", self.name, self.c_time, status="succeeded")
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
        self.state.set_status( 'failed' )
        self.record_db_update("task_states", self.name, self.c_time, status="failed")
        self.record_db_event(event="reset to failed")
        self.prerequisites.set_all_satisfied()
        self.outputs.set_all_incomplete()
        # set a new failed output just as if a failure message came in
        self.turn_off_timeouts()
        self.outputs.add( self.id + ' failed', completed=True )

    def reset_state_held( self ):
        self.state.set_status( 'held' )
        self.record_db_update("task_states", self.name, self.c_time, status="held")
        self.turn_off_timeouts()
        self.record_db_event(event="reset to held")

    def reset_state_runahead( self ):
        self.state.set_status( 'runahead' )
        self.turn_off_timeouts()
        self.record_db_update("task_states", self.name, self.c_time, status="runahead")

    def set_state_submitting( self ):
        # called by scheduler main thread
        self.state.set_status( 'submitting' )
        self.record_db_update("task_states", self.name, self.c_time, status="submitting")

    def set_state_queued( self ):
        # called by scheduler main thread
        self.state.set_status( 'queued' )
        self.record_db_update("task_states", self.name, self.c_time, status="queued")

    def override( self, target, sparse ):
        for key,val in sparse.items():
            if isinstance( val, dict ):
                self.override( target[key], val )
            else:
                target[key] = val

    def _get_retry_delays( self, cfg, descr ):
        """Check retry delay config (execution and submission) and return
        a deque of individual delay values (multipliers expanded out)."""

        # coerce single values to list (see warning in conf/suiterc/runtime.spec)
        if not isinstance( cfg, list ):
            cfg = [ cfg ]

        values = []
        for item in cfg:
            try:
                try:
                    mult, val = item.split('*')
                except ValueError:
                    # too few values to unpack (single item)
                    values.append(float(item))
                else:
                    # mult * val
                    values += int(mult) * [float(val)]
            except ValueError, x:
                # illegal values for mult and/or val
                print >> sys.stderr, x
                print >> sys.stderr, "WARNING ignoring " + descr
                print >> sys.stderr, "(values must be FLOAT or INT*FLOAT)"
        return deque(values)

    def set_from_rtconfig( self, cfg={} ):
        """Some [runtime] config requiring consistency checking on reload, 
        and self variables requiring updating for the same."""

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
            if self.__class__.run_mode == 'live' or \
                ( self.__class__.run_mode == 'simulation' and not rtconfig['simulation mode']['disable retries'] ) or \
                ( self.__class__.run_mode == 'dummy' and not rtconfig['dummy mode']['disable retries'] ):
                # note that a *copy* of the retry delays list is needed
                # so that all instances of the same task don't pop off
                # the same deque (but copy of rtconfig above solves this).
                self.retry_delays = self._get_retry_delays( rtconfig['retry delays'], 'retry delays' )
                self.sub_retry_delays_orig = self._get_retry_delays( rtconfig['job submission']['retry delays'], '[job submission] retry delays' )
            else:
                self.retry_delays = deque()
                self.sub_retry_delays_orig = deque()
            # retain the original submission retry deque for re-use if
            # execution fails (then submission tries start over).
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

        if self.run_mode == 'live' or \
                ( self.run_mode == 'simulation' and not rtconfig['simulation mode']['disable task event hooks'] ) or \
                ( self.run_mode == 'dummy' and not rtconfig['dummy mode']['disable task event hooks'] ):
            self.event_handlers = {
                'submitted' : rtconfig['event hooks']['submitted handler'],
                'started'   : rtconfig['event hooks']['started handler'],
                'succeeded' : rtconfig['event hooks']['succeeded handler'],
                'failed'    : rtconfig['event hooks']['failed handler'],
                'warning'   : rtconfig['event hooks']['warning handler'],
                'retry'     : rtconfig['event hooks']['retry handler'],
                'submission retry'   : rtconfig['event hooks']['submission retry handler'],
                'submission failed'  : rtconfig['event hooks']['submission failed handler'],
                'submission timeout' : rtconfig['event hooks']['submission timeout handler'],
                'execution timeout'  : rtconfig['event hooks']['execution timeout handler']
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

    def submit( self, dry_run=False, debug=False, overrides={} ):
        """NOTE THIS METHOD EXECUTES IN THE JOB SUBMISSION THREAD. It
        returns the job process number if successful. Exceptions raised
        will be caught by the job submission code and will result in a
        task failed message being sent for handling by the main thread.
        Run db updates as a result of such errors will also be done by
        the main thread in response to receiving the message."""

        self.submit_num += 1
        self.record_db_update("task_states", self.name, self.c_time, submit_num=self.submit_num)
    
        # TODO: REPLACE DEEPCOPY():
        rtconfig = deepcopy( self.__class__.rtconfig )
        self.override( rtconfig, overrides )
        
        self.set_from_rtconfig( rtconfig )

        if len(self.env_vars) > 0:
            # Add in any instance-specific environment variables
            # (currently only used by async_repeating tasks)
            rtconfig['environment'].update( self.env_vars )

        self.log( 'DEBUG', 'submitting task job script' )
        # construct the job launcher here so that a new one is used if
        # the task is re-triggered by the suite operator - so it will
        # get new stdout/stderr logfiles and not overwrite the old ones.

        # dynamic instantiation - don't know job sub method till run time.
        module_name = rtconfig['job submission']['method']
        class_name  = module_name
        # NOTE: not using__import__() keyword arguments:
        #mod = __import__( module_name, fromlist=[class_name] )
        # as these were only introduced in Python 2.5.
        try:
            # try to import built-in job submission classes first
            mod = __import__( 'cylc.job_submission.' + module_name, globals(), locals(), [class_name] )
        except ImportError:
            try:
                # else try for user-defined job submission classes, in sys.path
                mod = __import__( module_name, globals(), locals(), [class_name] )
            except ImportError, x:
                self.log( 'CRITICAL', 'cannot import job submission module ' + class_name )
                raise

        launcher_class = getattr( mod, class_name )
 
        command = rtconfig['command scripting']
        manual = rtconfig['manual completion']
        if self.__class__.run_mode == 'dummy':
            # (dummy tasks don't detach)
            manual = False
            command = rtconfig['dummy mode']['command scripting']
            if rtconfig['dummy mode']['disable pre-command scripting']:
                precommand = None
            if rtconfig['dummy mode']['disable post-command scripting']:
                postcommand = None
        else:
            precommand = rtconfig['pre-command scripting'] 
            postcommand = rtconfig['post-command scripting'] 

        # Determine task host settings now, just before job submission,
        # because dynamic host selection may be used.

        # host may be None (= run task on suite host)
        host = rtconfig['remote']['host']
        
        if host:
            # 1) check for dynamic host selection command
            #   host = $( host-select-command )
            #   host =  ` host-select-command `
            m = re.match( '(`|\$\()\s*(.*)\s*(`|\))$', host )
            if m:
                # extract the command and execute it
                hs_command = m.groups()[1]
                res = run_get_stdout( hs_command ) # (T/F,[lines])
                if res[0]:
                    # host selection command succeeded
                    host = res[1][0]
                else:
                    # host selection command failed
                    raise Exception("Host selection by " + host + " failed\n  " + '\n'.join(res[1]) )

            # 2) check for dynamic host selection variable:
            #   host = ${ENV_VAR}
            #   host = $ENV_VAR

            n = re.match( '^\$\{{0,1}(\w+)\}{0,1}$', host )
            # any string quotes are stripped by configobj parsing 
            if n:
                var = n.groups()[0]
                try:
                    host = os.environ[var]
                except KeyError, x:
                    raise Exception( "Host selection by " + host + " failed:\n  Variable not defined: " + str(x) )

            self.log( "NORMAL", "Task host: " + host )
            self.hostname = host

            if host not in gcfg.cfg['task hosts']:
                self.log( 'NORMAL', "No explicit site/user config for host " + host )
                cfghost = 'local'
            else:
                # use host-specific settings
                cfghost = host
        else:
            cfghost = 'local'
            self.hostname = suite_hostname

        owner = rtconfig['remote']['owner']
        if owner is None:
            self.owner = user
        else:
            self.owner = owner

        if self.hostname is None:
            self.hostname = "localhost"
            
        user_at_host = self.owner + "@" + self.hostname
        
        self.submit_method = rtconfig['job submission']['method']
        
        # Note: this should be done in the main thread, but has been
        # cleaned up in #364:
        self.record_db_update("task_states", self.name, self.c_time, 
                              submit_method=self.submit_method, host=user_at_host)

        share_dir = gcfg.get_suite_share_dir( self.suite_name, cfghost, owner )
        work_dir  = gcfg.get_task_work_dir( self.suite_name, self.id, cfghost, owner )
        local_log_dir = gcfg.get_task_log_dir( self.suite_name ) 
        remote_log_dir = gcfg.get_task_log_dir( self.suite_name, cfghost, owner )

        jobconfig = {
                'directives'             : rtconfig['directives'],
                'initial scripting'      : rtconfig['initial scripting'],
                'environment scripting'  : rtconfig['environment scripting'],
                'runtime environment'    : rtconfig['environment'],
                'use login shell'        : gcfg.cfg['task hosts'][cfghost]['use login shell'],
                'use ssh messaging'      : gcfg.cfg['task hosts'][cfghost]['use ssh messaging'],
                'remote cylc path'       : gcfg.cfg['task hosts'][cfghost]['cylc directory'],
                'remote suite path'      : rtconfig['remote']['suite definition directory'],
                'job script shell'       : rtconfig['job submission']['shell'],
                'use manual completion'  : manual,
                'pre-command scripting'  : precommand,
                'command scripting'      : command,
                'post-command scripting' : postcommand,
                'namespace hierarchy'    : self.namespace_hierarchy,
                'submission try number'  : self.sub_try_number,
                'try number'             : self.try_number,
                'absolute submit number' : self.submit_num,
                'is cold-start'          : self.is_coldstart,
                'share path'             : share_dir, 
                'work path'              : work_dir,
                'cylc environment'       : deepcopy( task.cylc_env ),
                'directive prefix'       : None,
                'directive final'        : "# FINAL DIRECTIVE",
                'directive connector'    : " ",
                }
        xconfig = {
                'owner'                  : owner,
                'host'                   : host,
                'log path'               : local_log_dir,
                'remote shell template'  : gcfg.cfg['task hosts'][cfghost]['remote shell template'],
                'job submission command template' : rtconfig['job submission']['command template'],
                'remote log path'        : remote_log_dir,
                'extra log files'        : self.logfiles,
                }
        try:
            launcher = launcher_class( self.id, jobconfig, xconfig, str(self.submit_num) )
        except Exception, x:
            # currently a bad hostname will fail out here due to an is_remote_host() test
            raise Exception( 'Failed to create job launcher\n  ' + str(x) )

        try:
            p = launcher.submit( dry_run, debug )
        except Exception, x:
            raise Exception( 'Job submission failed\n  ' + str(x) )
        else:
            return (p,launcher)

    def check_submission_timeout( self ):
        # if no timer is set, return
        if not self.submission_timer_start:
            return
        # if no handler is specified, return
        handler = self.event_handlers['submission timeout']
        timeout = self.timeouts['submission']
        if not handler or not timeout:
            return

        # if submission completed, turn off the timer
        for state in [ 'submit-failed', 'running', 'succeeded', 'failed', 'retrying' ]: 
            if self.state.is_currently(state):
                self.submission_timer_start = None
                return

        # if timed out, queue the event handler turn off the timer
        current_time = task.clock.get_datetime()
        cutoff = self.submission_timer_start + datetime.timedelta( minutes=float(timeout) )
        if current_time > cutoff:
            msg = 'task submitted ' + timeout + ' minutes ago, but has not started'
            self.log( 'WARNING', msg )
            self.log( 'NORMAL', "Queueing submission_timeout event handler" )
            self.__class__.event_queue.put( ('submission_timeout', handler, self.id, msg) )
            self.submission_timer_start = None

    def check_execution_timeout( self ):
        # if no timer is set, return
        if not self.execution_timer_start:
            return
        # if no handler is specified, return
        handler = self.event_handlers['execution timeout']
        timeout = self.timeouts['execution']
        if not handler or not timeout:
            return
        # if execution completed, turn off the timer
        for state in [ 'succeeded', 'failed', 'retrying' ]: 
            if self.state.is_currently(state):
                self.execution_timer_start = None
                return
        # if timed out, queue the event handler turn off the timer
        current_time = task.clock.get_datetime()
        cutoff = self.execution_timer_start + datetime.timedelta( minutes=float(timeout) )
        if current_time > cutoff:
            if self.reset_timer:
                # the timer is being re-started by incoming messages
                msg = 'last message ' + timeout + ' minutes ago, but has not succeeded'
            else:
                msg = 'task started ' + timeout + ' minutes ago, but has not succeeded'
            self.log( 'WARNING', msg )
            self.log( 'NORMAL', "Queueing execution_timeout event handler" )
            self.__class__.event_queue.put( ('execution_timeout', handler, self.id, msg) )
            self.execution_timer_start = None

    def sim_time_check( self ):
        if not self.state.is_currently('running'):
            return
        timeout = self.started_time_real + \
                datetime.timedelta( seconds=self.sim_mode_run_length )
        if datetime.datetime.now() > timeout:
            if self.__class__.rtconfig['simulation mode']['simulate failure']:
                self.incoming( 'CRITICAL', self.id + ' failed' )
            else:
                self.incoming( 'NORMAL', self.id + ' succeeded' )
            flags.pflag = True

    def set_all_internal_outputs_completed( self ):
        if self.reject_if_failed( 'set_all_internal_outputs_completed' ):
            return
        self.log( 'DEBUG', 'setting all internal outputs completed' )
        for message in self.outputs.completed:
            if message != self.id + ' started' and \
                    message != self.id + ' succeeded' and \
                    message != self.id + ' completed':
                self.incoming( 'NORMAL', message )

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

    def incoming( self, priority, message ):
        # queue incoming messages for this task
        self.message_queue.incoming( priority, message )

    def process_incoming_messages( self ):
        queue = self.message_queue.get_queue() 
        while queue.qsize() > 0:
            self.process_incoming_message( queue.get() )
            queue.task_done()

    def process_incoming_message( self, (priority, message) ):

        # Log every incoming task message. Prepend '>' to distinguish
        # from other non-task message log entries.
        self.log( priority, '> ' + message )

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
        flags.iflag = True

        if self.reject_if_failed( message ):
            # Failed tasks do not send messages unless declared resurrectable
            return

        # After logging remove the remote event time from the end of task messages.
        message = re.sub( ' at \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$', '', message )

        # Remove the prepended task ID.
        content = message.replace( self.id + ' ', '' )

        # If the message matches a registered output, record it as completed.
        if self.outputs.exists( message ):
            if not self.outputs.is_completed( message ):
                flags.pflag = True
                self.outputs.set_completed( message )
                self.record_db_event(event="output completed", message=content)
            else:
                # Warn if the output has already been reported complete.
                # This is no longer treated as an error condition though.
                self.log( 'WARNING', "UNEXPECTED OUTPUT (already completed):" )
                self.log( 'WARNING', "-> " + message )

        # Handle warning events
        if priority == 'WARNING':
            handler = self.event_handlers['warning']
            if handler:
                self.log( 'NORMAL', "Queueing warning event handler" )
                self.__class__.event_queue.put( ('warning', handler, self.id, content) )

        if self.reset_timer:
            # Reset execution timer on incoming messages
            self.execution_timer_start = task.clock.get_datetime()

        if content == 'submitting now':
            # (A fake task message from the job submission thread).
            # The job submission command was about to be executed.
            # Not currently doing anything other than logging this.
            pass

        elif content == 'submission succeeded':
            # (A fake task message from the job submission thread).
            # The job submission command returned success status.

            # TODO: should we use the real event time from the message here?
            self.submitted_time = task.clock.get_datetime()

            if self.state.is_currently( 'submitting' ): 
                # It is possible that task started arrives first, so
                # only set to 'submitted' if we're still in the
                # 'submitting' state.
                self.state.set_status( 'submitted' )
                self.submission_timer_start = self.submitted_time
            else:
                # task started must have arrived first
                self.submission_timer_start = None

            self.record_db_update("task_states", self.name, self.c_time, status="submitted")
            self.record_db_event(event="submission succeeded" )
            handler = self.event_handlers['submitted']
            if handler:
                self.log( 'NORMAL', "Queueing submitted event handler" )
                self.__class__.event_queue.put( ('submitted', handler, self.id, 'task submitted') )

        elif content.startswith( 'submit_method_id='):
            # (A fake task message from the job submission thread).
            # Capture and record the submit method job ID.
            submit_method_id = content[len('submit_method_id='):]
            self.record_db_update("task_states", self.name, self.c_time,
                                  submit_method_id=submit_method_id)
                                  
        elif content == 'submission failed':
            # (a fake task message from the job submission thread)
            try:
                # Is there a retry lined up for this task?
                self.sub_retry_delay = float(self.sub_retry_delays.popleft())
            except IndexError:
                # There is no submission retry lined up: definitive failure.
                self.state.set_status( 'submit-failed' )
                self.record_db_update("task_states", self.name, self.c_time, status="submit-failed")
                self.record_db_event(event="submission failed" )
                handler = self.event_handlers['submission failed']
                if handler:
                    self.log( 'NORMAL', "Queueing submission_failed event handler" )
                    self.__class__.event_queue.put( ('submission_failed', handler, self.id,'') )
            else:
                # There is a retry lined up
                self.log( "NORMAL", "Setting submission retry delay: " + str(self.sub_retry_delay) +  " minutes" )
                self.sub_retry_delay_timer_start = task.clock.get_datetime()
                self.sub_try_number += 1
                self.state.set_status( 'retrying' )
                self.record_db_update("task_states", self.name, self.c_time, try_num=self.try_number, status="retrying")
                self.record_db_event(event="submission failed", message="retrying in " + str(self.sub_retry_delay) )
                self.prerequisites.set_all_satisfied()
                self.outputs.set_all_incomplete()
                # Handle submission retry events
                handler = self.event_handlers['submission retry']
                if handler:
                    self.log( 'NORMAL', "Queueing submission retry event handler" )
                    self.__class__.event_queue.put( ('submission_retry', handler, self.id, 'task retrying') )
 
        elif content == 'started':
            # Received a 'task started' message
            flags.pflag = True
            self.state.set_status( 'running' )
            self.record_db_update("task_states", self.name, self.c_time, status="running")
            self.record_db_event(event="started" )
            self.started_time = task.clock.get_datetime()
            self.started_time_real = datetime.datetime.now()

            # TODO: should we use the real event time extracted from the
            # message here:
            self.execution_timer_start = self.started_time

            # submission was successful so reset submission try number
            self.sub_try_number = 0
            self.sub_retry_delays = copy( self.sub_retry_delays_orig )
            handler = self.event_handlers['started']
            if handler:
                self.log( 'NORMAL', "Queueing started event handler" )
                self.__class__.event_queue.put( ('started', handler, self.id, 'task started') )

        elif content == 'succeeded':
            # Received a 'task succeeded' message
            flags.pflag = True
            self.succeeded_time = task.clock.get_datetime()
            self.__class__.update_mean_total_elapsed_time( self.started_time, self.succeeded_time )
            self.state.set_status( 'succeeded' )
            self.record_db_update("task_states", self.name, self.c_time, status="succeeded")
            self.record_db_event(event="succeeded" )
            handler = self.event_handlers['succeeded']
            if handler:
                self.log( 'NORMAL', "Queueing succeeded event handler" )
                self.__class__.event_queue.put( ('succeeded', handler, self.id, 'task succeeded') )
            if not self.outputs.all_completed():
                # This is no longer treated as an error condition.
                self.log( 'WARNING', "Succeeded before all outputs completed; completing them now" )
                self.outputs.set_all_completed()

        elif content == 'failed':
            # Received a 'task failed' message
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
                self.state.set_status( 'failed' )
                self.record_db_update("task_states", self.name, self.c_time, status="failed")
                self.record_db_event(event="failed" )
                handler = self.event_handlers['failed']
                if handler:
                    self.log( 'NORMAL', "Queueing failed event handler" )
                    self.__class__.event_queue.put( ('execution failed', handler, self.id, '') )
            else:
                # There is a retry lined up
                self.log( "NORMAL", "Setting retry delay: " + str(self.retry_delay) +  " minutes" )
                self.retry_delay_timer_start = task.clock.get_datetime()
                self.try_number += 1
                self.state.set_status( 'retrying' )
                self.record_db_update("task_states", self.name, self.c_time, try_num=self.try_number, status="retrying")
                self.record_db_event(event="execution failed", message="retrying in " + str( self.retry_delay) )
                self.prerequisites.set_all_satisfied()
                self.outputs.set_all_incomplete()
                # Handle retry events
                handler = self.event_handlers['retry']
                if handler:
                    self.log( 'NORMAL', "Queueing retry event handler" )
                    self.__class__.event_queue.put( ('retry', handler, self.id, 'task retrying') )

        elif content.startswith("Task job script received signal"):
            # capture and record signals sent to task proxy
            self.record_db_event(event="signaled", message=content)

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
        return self.__class__( self.next_tag(), state )

    def has_spawned( self ):
        # the one off task type modifier overrides this.
        return self.state.has_spawned()

    def ready_to_spawn( self ):
        # return True or False
        self.log( 'CRITICAL', 'ready_to_spawn(): OVERRIDE ME')
        sys.exit(1)

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

        n_total = self.outputs.count()
        n_satisfied = self.outputs.count_completed()

        summary = {}
        summary[ 'name' ] = self.name
        summary[ 'label' ] = self.tag
        summary[ 'state' ] = self.state.get_status()
        summary[ 'n_total_outputs' ] = n_total
        summary[ 'n_completed_outputs' ] = n_satisfied
        summary[ 'spawned' ] = self.state.has_spawned()
        summary[ 'latest_message' ] = self.latest_message
        summary[ 'latest_message_priority' ] = self.latest_message_priority

        if self.submitted_time:
            summary[ 'submitted_time' ] = strftime( self.submitted_time, "%H:%M:%S" )
        else:
            summary[ 'submitted_time' ] = '*'

        if self.started_time:
            summary[ 'started_time' ] =  strftime( self.started_time, "%H:%M:%S" )
        else:
            summary[ 'started_time' ] =  '*'

        if self.succeeded_time:
            summary[ 'succeeded_time' ] =  strftime( self.succeeded_time, "%H:%M:%S" )
        else:
            summary[ 'succeeded_time' ] =  '*'

        # str(timedelta) => "1 day, 23:59:55.903937" (for example)
        # to strip off fraction of seconds:
        # timedelta = re.sub( '\.\d*$', '', timedelta )

        # TODO: the following section could probably be streamlined a bit
        if self.__class__.mean_total_elapsed_time:
            met = self.__class__.mean_total_elapsed_time
            summary[ 'mean total elapsed time' ] =  re.sub( '\.\d*$', '', str(met) )
            if self.started_time:
                if not self.succeeded_time:
                    # started but not succeeded yet, compute ETC
                    current_time = task.clock.get_datetime()
                    run_time = current_time - self.started_time
                    self.to_go = met - run_time
                    self.etc = current_time + self.to_go
                    summary[ 'Tetc' ] = strftime( self.etc, "%H:%M:%S" ) + '(' + re.sub( '\.\d*$', '', displaytd(self.to_go) ) + ')'
                elif self.etc:
                    # the first time a task finishes self.etc is not defined
                    # task succeeded; leave final prediction
                    summary[ 'Tetc' ] = strftime( self.etc, "%H:%M:%S" ) + '(' + re.sub( '\.\d*$', '', displaytd(self.to_go) ) + ')'
                else:
                    summary[ 'Tetc' ] = '*'
            else:
                # not started yet
                summary[ 'Tetc' ] = '*'
        else:
            # first instance: no mean time computed yet
            summary[ 'mean total elapsed time' ] =  '*'
            summary[ 'Tetc' ] = '*'

        summary[ 'logfiles' ] = self.logfiles.get_paths()

        return summary

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

    def is_cycling( self ):
        return False

    def is_daemon( self ):
        return False

    def is_clock_triggered( self ):
        return False

