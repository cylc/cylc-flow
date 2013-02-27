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

# TASK PROXY BASE CLASS:

import os, sys, re
import datetime
from copy import deepcopy
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
        cls.elapsed_times.append( succeeded - started )
        elt_sec = [x.days * 86400 + x.seconds for x in cls.elapsed_times ]
        mtet_sec = sum( elt_sec ) / len( elt_sec )
        cls.mean_total_elapsed_time = datetime.timedelta( seconds=mtet_sec )

    def __init__( self, state ):
        # Call this AFTER derived class initialisation

        # Derived class init MUST define:
        #  * self.id: unique identity (e.g. NAME.CYCLE for cycling tasks)
        #  * prerequisites and outputs
        #  * self.env_vars

        class_vars = {}
        self.state = task_state.task_state( state )
        self.trigger_now = False

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
        self.try_number = 1
        self.retry_delay_timer_start = None

        self.message_queue = msgqueue()
        self.db_queue = []

        self.suite_name = os.environ['CYLC_SUITE_REG_NAME']
        self.db_path = os.path.join(gcfg.cfg['task hosts']['local']['run directory'], self.suite_name)
        self.db = cylc.rundb.CylcRuntimeDAO(suite_dir=self.db_path)
        
        # sets submit num for restarts or when triggering state prior to submission
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
                else:
                        ready = True
        return ready

    def get_resolved_dependencies( self ):
        dep = []
        satby = self.prerequisites.get_satisfied_by()
        for label in satby.keys():
            dep.append( satby[ label ] )
        return dep

    def set_submitted( self ):
        self.state.set_status( 'submitted' )
        self.record_db_event(event="submitted", message="task submitted")
        self.record_db_update("task_states", self.name, self.c_time, status="submitted")
        self.log( 'NORMAL', "job submitted" )
        self.submitted_time = task.clock.get_datetime()
        self.submission_timer_start = self.submitted_time
        handler = self.event_handlers['submitted']
        if handler:
            self.log( 'NORMAL', "Queuing submitted event handler" )
            self.__class__.event_queue.put( ('submitted', handler, self.id, 'task submitted') )
        
    def set_running( self ):
        self.state.set_status( 'running' )
        self.record_db_event(event="started", message="task started")
        self.record_db_update("task_states", self.name, self.c_time, status="running")
        self.started_time = task.clock.get_datetime()
        self.started_time_real = datetime.datetime.now()
        self.execution_timer_start = self.started_time
        handler = self.event_handlers['started']
        if handler:
            self.log( 'NORMAL', "Queuing started event handler" )
            self.__class__.event_queue.put( ('started', handler, self.id, 'task started') )

    def set_succeeded( self ):
        self.outputs.set_all_completed()
        self.state.set_status( 'succeeded' )
        self.record_db_update("task_states", self.name, self.c_time, status="succeeded")
        self.record_db_event(event="succeeded", message="task succeeded")
        self.succeeded_time = task.clock.get_datetime()
        # don't update mean total elapsed time if set_succeeded() was called

    def set_succeeded_handler( self ):
        # (set_succeeded() is used by remote switch)
        self.record_db_event(event="succeeded", message="task succeeded")
        self.state.set_status( 'succeeded' )
        self.record_db_update("task_states", self.name, self.c_time, status="succeeded")
        handler = self.event_handlers['succeeded']
        if handler:
            self.log( 'NORMAL', "Queuing succeeded event handler" )
            self.__class__.event_queue.put( ('succeeded', handler, self.id, 'task succeeded') )
        
    def set_failed( self, reason='task failed' ):
        self.state.set_status( 'failed' )
        self.record_db_update("task_states", self.name, self.c_time, status="failed")
        self.record_db_event(event="failed", message=reason)
        self.log( 'CRITICAL', reason )
        handler = self.event_handlers['failed']
        if handler:
            self.log( 'NORMAL', "Queuing failed event handler" )
            self.__class__.event_queue.put( ('failed', handler, self.id, reason) )

    def set_submit_failed( self, reason='job submission failed' ):
        self.state.set_status( 'failed' )
        self.record_db_update("task_states", self.name, self.c_time, status="failed")
        self.record_db_event(event="failed", message=reason)
        self.log( 'CRITICAL', reason )
        handler = self.event_handlers['submission failed']
        if handler:
            self.log( 'NORMAL', "Queuing submission_failed event handler" )
            self.__class__.event_queue.put( ('submission_failed', handler, self.id, reason) )

    def unfail( self ):
        # if a task is manually reset remove any previous failed message
        # or on later success it will be seen as an incomplete output.
        failed_msg = self.id + " failed"
        if self.outputs.exists(failed_msg):
            self.outputs.remove(failed_msg)

    def reset_state_ready( self ):
        self.state.set_status( 'waiting' )
        self.record_db_update("task_states", self.name, self.c_time, submit_num=self.submit_num, status="waiting")
        self.prerequisites.set_all_satisfied()
        self.unfail()
        self.outputs.set_all_incomplete()

    def reset_state_waiting( self ):
        # waiting and all prerequisites UNsatisified.
        self.state.set_status( 'waiting' )
        self.record_db_update("task_states", self.name, self.c_time, status="waiting")
        self.prerequisites.set_all_unsatisfied()
        self.unfail()
        self.outputs.set_all_incomplete()

    def reset_state_succeeded( self ):
        # all prerequisites satisified and all outputs complete
        self.state.set_status( 'succeeded' )
        self.record_db_update("task_states", self.name, self.c_time, status="succeeded")
        self.record_db_event(event="succeeded", message="task succeeded")
        self.prerequisites.set_all_satisfied()
        self.unfail()
        self.outputs.set_all_completed()

    def reset_state_failed( self ):
        # all prerequisites satisified and no outputs complete
        self.state.set_status( 'failed' )
        self.record_db_update("task_states", self.name, self.c_time, status="failed")
        self.record_db_event(event="failed", message="task failed")
        self.prerequisites.set_all_satisfied()
        self.outputs.set_all_incomplete()
        # set a new failed output just as if a failure message came in
        self.outputs.add( self.id + ' failed', completed=True )

    def reset_state_held( self ):
        self.state.set_status( 'held' )
        self.record_db_update("task_states", self.name, self.c_time, status="held")

    def reset_state_runahead( self ):
        self.state.set_status( 'runahead' )
        self.record_db_update("task_states", self.name, self.c_time, status="runahead")

    def reset_state_submitting( self ):
        self.state.set_status( 'submitting' )
        self.record_db_update("task_states", self.name, self.c_time, status="submitting")

    def reset_state_queued( self ):
        self.state.set_status( 'queued' )
        self.record_db_update("task_states", self.name, self.c_time, status="queued")

    def override( self, target, sparse ):
        for key,val in sparse.items():
            if isinstance( val, dict ):
                self.override( target[key], val )
            else:
                target[key] = val

    def set_from_rtconfig( self, cfg={} ):
        # [runtime] settings that are not involved in job submission may
        # also be overridden by a broadcast:
        if cfg:
            rtconfig = cfg
        else:
            rtconfig = self.__class__.rtconfig

        # note: we currently only access the class variable with describe():
        self.title = rtconfig['title']
        self.description = rtconfig['description']

        if self.try_number == 1:
            # configure retry delays before the first try
            if self.__class__.run_mode == 'live' or \
                ( self.__class__.run_mode == 'simulation' and not rtconfig['simulation mode']['disable retries'] ) or \
                ( self.__class__.run_mode == 'dummy' and not rtconfig['dummy mode']['disable retries'] ):

                # note that a *copy* of the retry delays list is needed
                # so that all instances of the same task don't pop off
                # the same deque (copy of rtconfig above solves this).

                # expand out 'n*d' list items

                rd = rtconfig['retry delays']
                # coerce single values to list (see warning in conf/suiterc/runtime.spec)
                if not isinstance( rd, list ):
                    rd = [ rd ]

                dlist = []
                for item in rd:
                    try:
                        try:
                            mult, val = item.split('*')
                        except ValueError:
                            dlist.append(float(item))
                        else:
                            dlist += int(mult) * [float(val)]
                    except ValueError, x:
                        print >> sys.stderr, x
                        raise SystemExit( "ERROR, retry delay values must be INT or INT*FLOAT" )

                self.retry_delays = deque( dlist )
            else:
                self.retry_delays = deque()

        rrange = rtconfig['simulation mode']['run time range']
        ok = True
        if len(rrange) != 2:
            ok = False
        try:
            res = [ int( rrange[0] ), int( rrange[1] ) ]
        except:
            ok = False
        if not ok:
            raise SystemExit, "ERROR, " + self.name + ": simulation mode run time range must be 'int, int'" 
        try:
            self.sim_mode_run_length = randrange( res[0], res[1] )
        except Exception, x:
            print >> sys.stderr, x
            raise SystemExit, "ERROR: simulation mode task run time range must be [MIN,MAX)" 

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

        self.submit_num += 1
        self.record_db_update("task_states", self.name, self.c_time, submit_num=self.submit_num)
    
        # TO DO: REPLACE DEEPCOPY():
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
                print >> sys.stderr, x
                raise SystemExit( 'ERROR importing job submission method: ' + class_name )

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
            # dynamic host section:
            #   host = $( host-select-command )
            #   host =  ` host-select-command `
            m = re.match( '(`|\$\()\s*(.*)\s*(`|\))$', host )
            if m:
                # extract the command and execute it
                hs_command = m.groups()[1]
                res = run_get_stdout( hs_command ) # (T/F,[lines])
                if res[0]:
                    # host selection command succeeded
                    host = res[1]
                    self.log( "NORMAL", "Host selected for " + self.id + ": " + host )
                    self.hostname = host
                else:
                    # host selection command failed
                    self.log( 'CRITICAL', "Dynamic host selection failed for task " + self.id )
                    self.incoming( 'CRITICAL', self.id + " failed" )
                    return

            if host not in gcfg.cfg['task hosts']:
                # there's no specific config for this host
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
                'try number'             : self.try_number,
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

        launcher = launcher_class( self.id, jobconfig, xconfig, str(self.submit_num) )

        try:
            p = launcher.submit( dry_run, debug )
        except Exception, x:
            # a bug was activated in cylc job submission code
            print >> sys.stderr, 'ERROR: cylc job submission bug?'
            raise
        else:
            return (p, launcher)

    def check_submission_timeout( self ):
        handler = self.event_handlers['submission timeout']
        timeout = self.timeouts['submission']
        if not handler or not timeout:
            return
        if not self.state.is_currently('submitted') and not self.state.is_currently('running'):
            # nothing to time out yet
            return
        current_time = task.clock.get_datetime()
        if self.submission_timer_start != None and not self.state.is_currently('running'):
            cutoff = self.submission_timer_start + datetime.timedelta( minutes=float(timeout) )
            if current_time > cutoff:
                msg = 'task submitted ' + timeout + ' minutes ago, but has not started'
                self.log( 'WARNING', msg )
                self.log( 'NORMAL', "Queuing submission_timeout event handler" )
                self.__class__.event_queue.put( ('submission_timeout', handler, self.id, msg) )
                self.submission_timer_start = None

    def check_execution_timeout( self ):
        handler = self.event_handlers['execution timeout']
        timeout = self.timeouts['execution']
        if not handler or not timeout:
            return
        if not self.state.is_currently('submitted') and not self.state.is_currently('running'):
            # nothing to time out yet
            return
        current_time = task.clock.get_datetime()
        if self.execution_timer_start != None and self.state.is_currently('running'):
            cutoff = self.execution_timer_start + datetime.timedelta( minutes=float(timeout) )
            if current_time > cutoff:
                if self.reset_timer:
                    msg = 'last message ' + timeout + ' minutes ago, but has not succeeded'
                else:
                    msg = 'task started ' + timeout + ' minutes ago, but has not succeeded'
                self.log( 'WARNING', msg )
                self.log( 'NORMAL', "Queuing execution_timeout event handler" )
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

        # always update the suite state summary for latest message
        flags.iflag = True

        if self.reject_if_failed( message ):
            # Failed tasks do not send messages unless declared resurrectable
            return

        self.latest_message = message
        self.latest_message_priority = priority

        # Handle warning events
        handler = self.event_handlers['warning']
        if priority == 'WARNING' and handler:
            self.log( 'NORMAL', "Queuing warning event handler" )
            self.__class__.event_queue.put( ('warning', handler, self.id, message) )

        if self.reset_timer:
            # Reset execution timer on incoming messages
            self.execution_timer_start = task.clock.get_datetime()

        if message == self.id + ' started':
            # Received a 'task started' message
            flags.pflag = True
            self.set_running()

        elif message == self.id + ' submitted':
            # (a faked task message from the job submission thread)
            self.set_submitted()

        elif message.startswith(self.id + ' submit_method_id='):
            submit_method_id = message[len(self.id + ' submit_method_id='):]
            self.record_db_update("task_states", self.name, self.c_time,
                                  submit_method_id=submit_method_id)

        if message == self.id + ' failed':
            # (note not 'elif' here as started messages must go through
            # the elif block below)
            # Received a 'task failed' message
            flags.pflag = True
            self.succeeded_time = task.clock.get_datetime()
            try:
                # Is there a retry lined up for this task?
                self.retry_delay = float(self.retry_delays.popleft())
            except IndexError:
                # There is no retry lined up: definitive failure.
                # Add the failed message as a task output so that other tasks can
                # trigger off the failure event (failure outputs are not added in
                # advance - they are not completed outputs in case of success):
                self.outputs.add( message )
                self.outputs.set_completed( message )
                # (this also calls the task failure handler):
                self.set_failed( message )
            else:
                # There is a retry lined up
                self.log( "NORMAL", "Setting retry delay: " + str(self.retry_delay) +  " minutes" )
                self.retry_delay_timer_start = task.clock.get_datetime()
                self.try_number += 1
                self.state.set_status( 'retrying' )
                self.record_db_update("task_states", self.name, self.c_time, try_num=self.try_number, status="retrying")
                self.prerequisites.set_all_satisfied()
                self.outputs.set_all_incomplete()
                # Handle retry events
                handler = self.event_handlers['retry']
                if handler:
                    self.log( 'NORMAL', "Queuing retry event handler" )
                    self.__class__.event_queue.put( ('retry', handler, self.id, 'task retrying') )

        elif self.outputs.exists( message ):
            # Received a registered internal output message
            # (this includes 'task succeeded')
            if not self.outputs.is_completed( message ):
                flags.pflag = True
                self.log( priority,  message )
                self.outputs.set_completed( message )
                if message == self.id + ' succeeded':
                    # Task has succeeded
                    self.succeeded_time = task.clock.get_datetime()
                    self.__class__.update_mean_total_elapsed_time( self.started_time, self.succeeded_time )
                    if not self.outputs.all_completed():
                        # Reported success before all registered outputs were completed.
                        # Currently this is treated as an error condition.
                        self.set_failed( 'succeeded before all outputs were completed' )
                    else:
                        # Set state to 'succeeded' and handle succeeded events
                        self.set_succeeded_handler()
            else:
                # This output has already been reported complete.
                # Currently this is treated as an error condition
                self.log( 'WARNING', "UNEXPECTED OUTPUT (already completed):" )
                self.log( 'WARNING', "-> " + message )
        else:
            # A general unregistered progress message: log with a '*' prefix
            message = '*' + message
            self.log( priority, message )

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

        # TO DO: the following section could probably be streamlined a bit
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

