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

import Queue
import os, sys, re, time
import datetime
import subprocess
from copy import copy
from random import randrange
from collections import deque
from cylc import task_state
from cylc.cfgspec.site import sitecfg
from cylc.owner import user
import logging
import cylc.flags as flags
from cylc.wallclock import (
    get_current_time_string, get_time_string_from_unix_time,
    RE_DATE_TIME_FORMAT_EXTENDED, get_seconds_as_interval_string
)
from cylc.task_receiver import msgqueue
import cylc.rundb
from cylc.command_env import cv_scripting_sl
from cylc.host_select import get_task_host
from parsec.util import pdeepcopy, poverride
from cylc.mp_pool import command_types

cylc_mode = 'scheduler'
poll_suffix_re = re.compile(
    ' at (' + RE_DATE_TIME_FORMAT_EXTENDED + '|unknown-time)$')

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
        self.timeout = None

    def set_host( self, host, set_timer=False ):
        # the polling comms method is host-specific
        if sitecfg.get_host_item( 'task communication method', host ) == "poll":
            if not self.intervals:
                self.intervals = copy(self.default_intervals)
                self.log( 'WARNING', '(polling comms) using default ' + self.name + ' polling intervals' )
            if set_timer:
                self.set_timer()

    def set_timer( self ):
        try:
            self.current_interval = self.intervals.popleft() # seconds
        except IndexError:
            # no more intervals, keep the last one
            pass

        if self.current_interval:
            self.log( 'NORMAL', 'setting ' + self.name + ' poll timer for ' + str(self.current_interval) + ' seconds' )
            self.timeout = time.time() + self.current_interval
        else:
            self.timeout = None

    def get( self ):
        if not self.timeout:
            return False
        return (time.time() > self.timeout)


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

    intercycle = False
    is_clock_triggered = False

    proc_pool = None

    suite_contact_env_hosts = []
    suite_contact_env = {}
    event_handler_env = {}
    SUITE_CONTACT_ENV_SSH_OPTS = ['-oBatchMode=yes', '-oConnectTimeout=10']

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
        mtet_sec = sum( cls.elapsed_times ) / len( cls.elapsed_times )
        cls.mean_total_elapsed_time = mtet_sec

    def __init__( self, state, validate=False ):
        # Call this AFTER derived class initialisation

        class_vars = {}
        self.state = task_state.task_state( state )
        self.manual_trigger = False

        self.stop_point = None

        self.latest_message = ""
        self.latest_message_priority = "NORMAL"

        self.submission_timer_timeout = None
        self.execution_timer_timeout = None

        self.submitted_time = None
        self.started_time = None
        self.succeeded_time = None
        self.etc = None
        self.summary = { 'latest_message': self.latest_message,
                         'latest_message_priority': self.latest_message_priority,
                         'started_time': None,
                         'started_time_string': '*',
                         'submitted_time': None,
                         'submitted_time_string': '*',
                         'succeeded_time': None,
                         'succeeded_time_string': '*',
                         'name': self.name,
                         'description': self.description,
                         'title': self.title,
                         'label': str(self.tag),
                         'logfiles': self.logfiles.get_paths()}

        self.retries_configured = False

        self.try_number = 1
        self.retry_delay = None
        self.retry_delay_timer_timeout = None

        self.sub_try_number = 1
        self.sub_retry_delay = None
        self.sub_retry_delay_timer_timeout = None

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
        self.job_sub_method_name = None
        self.job_sub_method = None
        self.job_vacated = False

        self.submission_poll_timer = None
        self.execution_poll_timer = None

        if self.validate: # if in validate mode bypass db operations
            self.submit_num = 0
        else:
            if not self.exists:
                self.record_db_state(
                    self.name, self.c_time,
                    time_created_string=get_current_time_string(),
                    submit_num=self.submit_num, try_num=self.try_number,
                    status=self.state.get_status()
                )
            if self.submit_num > 0:
                self.record_db_update("task_states", self.name, self.c_time,
                                      status=self.state.get_status())

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

    def record_db_event(self, event="", message=""):
        call = cylc.rundb.RecordEventObject(self.name, str(self.c_time), self.submit_num, event, message, self.user_at_host)
        self.db_queue.append(call)
        self.db_items = True

    def record_db_update(self, table, name, cycle, **kwargs):
        call = cylc.rundb.UpdateObject(table, name, str(cycle), **kwargs)
        self.db_queue.append(call)
        self.db_items = True

    def record_db_state(self, name, cycle, time_created_string=None,
                        time_updated_string=None, submit_num=None,
                        is_manual_submit=None, try_num=None, host=None,
                        submit_method=None, submit_method_id=None,
                        status=None):
        call = cylc.rundb.RecordStateObject(name, str(cycle),
                     time_created_string=time_created_string,
                     time_updated_string=time_updated_string,
                     submit_num=submit_num,
                     is_manual_submit=is_manual_submit, try_num=try_num,
                     host=host, submit_method=submit_method,
                     submit_method_id=submit_method_id, status=status)
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
        now_time = time.time()
        if self.retry_delay_timer_timeout:
            if now_time > self.retry_delay_timer_timeout:
                done = True
        elif self.sub_retry_delay_timer_timeout:
            if now_time > self.sub_retry_delay_timer_timeout:
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
        self.submission_timer_timeout = None
        self.execution_timer_timeout = None

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

    def set_state_ready( self ):
        self.set_status( 'ready' )

    def set_state_queued( self ):
        self.set_status( 'queued' )

    def submission_command_callback( self, result ):
        out, err = result['OUT'], result['ERR']
        if result['EXIT'] != 0:
            self.job_submission_failed( out, err )
        else:
            self.submit_method_id = self.job_sub_method.get_id( out, err )
            if self.submit_method_id:
                self.log( 'NORMAL', 'submit_method_id=' + self.submit_method_id )
                self.record_db_update("task_states", self.name, self.c_time, submit_method_id=self.submit_method_id)
            out, err = self.job_sub_method.filter_output( out, err )
            self.job_submission_succeeded( out, err )

    def poll_command_callback( self, result ):
        rcode = result['EXIT']
        out   = result['OUT'].strip()
        err   = result['ERR'].strip()
        # TODO - CHECK FOR FAILED POLL HERE
        if not self.state.is_currently( 'submitted', 'running' ):
            # Poll results can come in after a task finishes
            self.log( "WARNING", "Ignoring late poll result: task is not active" ) 
            return
        # poll results emulate task messages
        self.process_incoming_message( ('NORMAL', out) )

    def kill_command_callback( self, result ):
        rcode = result['EXIT']
        out   = result['OUT'].strip()
        err   = result['ERR'].strip()
        if rcode:
            self.log ('WARNING', 'job kill failed' )
        else:
            if self.state.is_currently('submitted'):
                self.log( 'NORMAL', 'job killed' )
                self.job_submission_failed()
            elif self.state.is_currently( 'running' ):
                self.log( 'NORMAL', 'job killed' )
                self.job_execution_failed()
            else:
                # should not happen
                self.log( 'WARNING', 'job kill error? task state ' + self.state.get_status() )


    def event_handler_callback( self, result ):
        command = result['COMMAND']
        rcode = result['EXIT']
        out   = result['OUT'].strip()
        err   = result['ERR'].strip()
        if rcode:
            self.log ('WARNING', 'event handler failed:\n' + command )
            if err:
                self.log('WARNING', err)
        elif out:
            self.log( 'NORMAL', out )

    def handle_event( self, event, descr=None, db_update=True, db_event=None, db_msg=None ):
        # extra args for inconsistent use between events, logging, and db updates
        db_event = db_event or event
        if db_update:
            self.record_db_event(event=db_event, message=db_msg )

        if self.__class__.run_mode != 'live' or \
                ( self.__class__.run_mode == 'simulation' and \
                        rtconfig['simulation mode']['disable task event hooks'] ) or \
                ( self.__class__.run_mode == 'dummy' and \
                        rtconfig['dummy mode']['disable task event hooks'] ):
            return
 
        handlers = self.event_hooks[ event + ' handler' ]
        if handlers:
            self.log( 'DEBUG', "Queueing " + event + " event handler(s)" )
            for handler in handlers:
                self.log( 'DEBUG', "Queueing " + event + " event handler" )
                cmd = ""
                for var, val in self.__class__.event_handler_env.items():
                    cmd += var + '=' + val + ' '
                cmd += " ".join( [handler, "'" + event + "'", self.suite_name, self.id, "'" + descr + "'"] )
                cmd_spec = ( command_types.EVENT_HANDLER, cmd )
                self.__class__.proc_pool.put_command( cmd_spec, self.event_handler_callback )

    def job_submission_failed( self, out=None, err=None ):
        if out:
            self.log( 'NORMAL', out )
        if err:
            self.log( 'WARNING', err )
        self.log( 'CRITICAL', 'submission failed' )

        self.submit_method_id = None
        try:
            sub_retry_delay = self.sub_retry_delays.popleft()
        except IndexError:
            # No submission retry lined up: definitive failure.
            flags.pflag = True
            outp = self.id + " submit-failed" # hack: see github #476
            self.outputs.add( outp )
            self.outputs.set_completed( outp )
            self.set_status( 'submit-failed' )
            self.handle_event( 'submission failed', 'job submission failed' )
        else:
            # There is a submission retry lined up.
            delay_msg = "submit-retrying in %s" % (
                get_seconds_as_interval_string(sub_retry_delay))
            msg = "job submission failed, " + delay_msg
            self.log( "NORMAL", msg )

            self.sub_retry_delay_timer_timeout = (
                time.time() + sub_retry_delay)
            self.sub_try_number += 1
            self.set_status( 'submit-retrying' )
            self.record_db_event(event="submission failed",
                                 message=delay_msg)
            self.prerequisites.set_all_satisfied()
            self.outputs.set_all_incomplete()
            self.queue_event_handlers( 'submission retry', msg )

            # TODO - is this record is redundant with that in handle_event?
            self.record_db_event(
                    event="submission failed",
                    message="submit-retrying in " + str(self.sub_retry_delay))
            self.handle_event( 'submission retry', msg )

    def job_submission_succeeded( self, out, err ):
        self.log( 'NORMAL', 'submission succeeded' )
        if self.__class__.run_mode == 'simulation':
            self.started_time = time.time()
            self.summary[ 'started_time' ] = self.started_time
            self.summary[ 'started_time_string' ] = (
                get_time_string_from_unix_time(
                    self.started_time, no_display_time_zone=True
                )
            )
            self.outputs.set_completed( self.id + " started" )
            self.set_status( 'running' )
            return

        outp = self.id + ' submitted'
        if not self.outputs.is_completed( outp ):
            # Allow submitted tasks to spawn even if nothing else is happening.
            flags.pflag = True
            self.outputs.set_completed( outp )
        else:
            self.log( "WARNING", "already submitted" )

        # allow submitted tasks to spawn even if nothing else is happening
        flags.pflag = True

        # TODO - should we use the real event time from the message here?
        self.submitted_time = time.time()
        self.summary[ 'submitted_time' ] = self.submitted_time
        self.summary[ 'submitted_time_string' ] = (
            get_time_string_from_unix_time(
                self.submitted_time, no_display_time_zone=True
            )
        )
        self.handle_event( 'submitted', 'job submitted', db_event='submission succeeded' )

        if self.state.is_currently( 'ready' ):
            # The 'started' message can arrive before this.
            # TODO - is this still true under mp_pool?
            self.set_status( 'submitted' )
            submit_timeout = self.event_hooks['submission timeout']
            if submit_timeout:
                self.submission_timer_timeout = (
                    self.submitted_time + submit_timeout
                )
            else:
                self.submission_timer_timeout = None
            self.submission_poll_timer.set_timer()

    def job_execution_failed( self ):

        self.execution_timer_timeout = None
        try:
            retry_delay = self.retry_delays.popleft()
        except IndexError:
            # No retry lined up: definitive failure.
            # Note the 'failed' output is only added if needed.
            flags.pflag = True
            msg = self.id + ' failed'
            self.outputs.add( msg )
            self.outputs.set_completed( msg )
            self.set_status( 'failed' )
            self.handle_event( 'failed', 'job failed' )

        else:
            # There is a retry lined up
            delay_msg = "retrying in %s" % (
                get_seconds_as_interval_string(retry_delay))
            msg = "job failed, " + delay_msg
            self.log( "NORMAL", msg )
            self.retry_delay_timer_timeout = (
                time.time() + self.retry_delay)
            self.try_number += 1
            self.set_status('retrying')
            self.prerequisites.set_all_satisfied()
            self.outputs.set_all_incomplete()
            self.handle_event( 'retry', msg, db_msg= "retrying in " + str( self.retry_delay) )

    def reset_manual_trigger( self ):
        # call immediately after manual trigger flag used
        self.manual_trigger = False
        # unset any retry delay timers
        self.retry_delay_timer_timeout = None
        self.sub_retry_delay_timer_timeout = None

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
            res = [rrange[0],rrange[1]]
        except:
            ok = False
        if not ok:
            raise Exception, ("ERROR, " + self.name + ": simulation mode " +
                              "run time range should be ISO 8601-compatible")
        try:
            self.sim_mode_run_length = randrange( res[0], res[1] )
        except Exception, x:
            print >> sys.stderr, x
            raise Exception, "ERROR: simulation mode task run time range must be [MIN,MAX)"

        self.event_hooks = rtconfig['event hooks']

        self.submission_poll_timer = PollTimer( \
                    copy( rtconfig['submission polling intervals']), 
                    copy( sitecfg.get( ['submission polling intervals'] )),
                    'submission', self.log )

        self.execution_poll_timer = PollTimer( \
                    copy( rtconfig['execution polling intervals']), 
                    copy( sitecfg.get( ['execution polling intervals'] )),
                   'execution', self.log )

    def get_command( self, dry_run=False, overrides={} ):

        self.log( 'NORMAL', "submitting now" )
        self.record_db_event(event="submitting now")

        self.submit_num += 1
        self.record_db_update("task_states", self.name, self.c_time, submit_num=self.submit_num)

        rtconfig = pdeepcopy( self.__class__.rtconfig )
        poverride( rtconfig, overrides )

        self.set_from_rtconfig( rtconfig )

        if len(self.env_vars) > 0:
            # Add in any instance-specific environment variables
            # (not currently used?)
            rtconfig['environment'].update( self.env_vars )

        # construct the job_sub_method here so that a new one is used if
        # the task is re-triggered by the suite operator - so it will
        # get new stdout/stderr logfiles and not overwrite the old ones.

        # dynamic instantiation - don't know job sub method till run time.
        module_name = rtconfig['job submission']['method']
        self.job_sub_method_name = module_name

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

        job_sub_method_class = getattr( mod, class_name )

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
            comstr = "cylc suite-state " + \
                     " --task=" + self.suite_polling_cfg['task'] + \
                     " --cycle=" + str(self.c_time) + \
                     " --status=" + self.suite_polling_cfg['status']
            if rtconfig['suite state polling']['user']:
                comstr += " --user=" + rtconfig['suite state polling']['user']
            if rtconfig['suite state polling']['host']:
                comstr += " --host=" + rtconfig['suite state polling']['host']
            if rtconfig['suite state polling']['interval']:
                comstr += " --interval=" + str(int(
                    rtconfig['suite state polling']['interval']))
            if rtconfig['suite state polling']['max-polls']:
                comstr += " --max-polls=" + str(rtconfig['suite state polling']['max-polls'])
            if rtconfig['suite state polling']['run-dir']:
                comstr += " --run-dir=" + str(rtconfig['suite state polling']['run-dir'])
            comstr += " " + self.suite_polling_cfg['suite']
            command = "echo " + comstr + "\n" + comstr

        # Determine task host settings now, just before job submission,
        # because dynamic host selection may be used.

        # host may be None (= run task on suite host)
        self.task_host = get_task_host( rtconfig['remote']['host'] )
        if self.task_host != "localhost":
            self.log( "NORMAL", "Task host: " + self.task_host )

        self.task_owner = rtconfig['remote']['owner']

        if self.task_owner:
            self.user_at_host = self.task_owner + "@" + self.task_host
        else:
            self.user_at_host = self.task_host
        self.submission_poll_timer.set_host( self.task_host )
        self.execution_poll_timer.set_host( self.task_host )

        if self.task_host not in self.__class__.suite_contact_env_hosts and \
                self.user_at_host != 'localhost' and cylc_mode == 'scheduler':
            # If the suite contact file has not been copied to user@host
            # host yet, do so.
            suite_run_dir = sitecfg.get_derived_host_item(
                                self.suite_name,
                                'suite run directory')
            env_file_path = os.path.join(suite_run_dir, 'cylc-suite-env')
            r_suite_run_dir = sitecfg.get_derived_host_item(
                                self.suite_name,
                                'suite run directory',
                                self.task_host,
                                self.task_owner)
            r_env_file_path = '%s:%s/cylc-suite-env' % (
                                self.user_at_host,
                                r_suite_run_dir)
            self.log('NORMAL', 'Installing %s' % r_env_file_path)
            cmd1 = (['ssh'] + self.SUITE_CONTACT_ENV_SSH_OPTS +
                    [self.user_at_host, 'mkdir', '-p', r_suite_run_dir])
            cmd2 = (['scp'] + self.SUITE_CONTACT_ENV_SSH_OPTS +
                    [env_file_path, r_env_file_path])
            for cmd in [cmd1, cmd2]:
                subprocess.check_call(cmd)
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
            self.job_sub_method = job_sub_method_class( self.id, self.suite_name, jobconfig, str(self.submit_num) )
        except Exception, x:
            # currently a bad hostname will fail out here due to an is_remote_host() test
            raise  # TODO - check best way of alerting the user here
            #raise Exception( 'Failed to create job_sub_method\n  ' + str(x) )

        self.job_sub_method.write_jobscript()
        return self.job_sub_method.get_job_submission_command( dry_run )

    def presubmit( self, owner, host, subnum ):
        """A cut down version of submit, without the job submission,
        just to provide access to the job_sub_method-specific job poll
        commands before the task is submitted (polling in submitted
        state or on suite restart)."""
        # TODO - refactor to get easier access to polling commands!

        rtconfig = pdeepcopy( self.__class__.rtconfig )

        # dynamic instantiation - don't know job sub method till run time.
        module_name = rtconfig['job submission']['method']
        self.job_sub_method_name = module_name

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

        job_sub_method_class = getattr( mod, class_name )

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
            job_sub_method = job_sub_method_class( self.id, self.suite_name, jobconfig, str(subnum) )
        except Exception, x:
            raise
            # currently a bad hostname will fail out here due to an is_remote_host() test
            raise Exception( 'Failed to create job_sub_method\n  ' + str(x) )
        return job_sub_method

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
        if self.submission_timer_timeout is None:
            # (explicit None in case of a zero timeout!)
            # no timer set
            return

        # if timed out, log warning, poll, queue event handler, and turn off the timer
        if time.time() > self.submission_timer_timeout:
            msg = 'job submitted %s ago, but has not started' % (
                get_seconds_as_interval_string(
                    self.event_hooks['submission timeout'])
            )
            self.log( 'WARNING', msg )
            self.poll()
            self.handle_event( 'submission timeout', msg )
            self.submission_timer_timeout = None

    def check_execution_timeout( self ):
        # only called if in the 'running' state
        if self.execution_timer_timeout is None:
            # (explicit None in case of a zero timeout!)
            # no timer set
            return

        # if timed out: log warning, poll, queue event handler, and turn off the timer
        if time.time() > self.execution_timer_timeout:
            if self.event_hooks['reset timer']:
                # the timer is being re-started by put messages
                msg = 'last message %s ago, but job not finished'
            else:
                msg = 'job started %s ago, but has not finished'
            msg = msg % get_seconds_as_interval_string(
                self.event_hooks['execution timeout'])
            self.log( 'WARNING', msg )
            self.poll()
            self.handle_event( 'execution timeout', msg )
            self.execution_timer_timeout = None

    def sim_time_check( self ):
        timeout = self.started_time + self.sim_mode_run_length
        if time.time() > timeout:
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
            try:
                self.process_incoming_message( queue.get(block=False) )
            except Queue.Empty:
                break
            queue.task_done()

    def process_incoming_message( self, (priority, message) ):
        """
        Parse incoming task messages and update task state - unless the
        current message is late (out of order) and would set the state
        backward in the natural order of events.
        """
        # TODO - formalize state ordering, for: 'if new_state < old_state'

        # Log incoming messages with '>' to distinguish non-message log entries.
        self.log( priority, '(current:' + self.state.get_status() + ')> ' + message )

        # always update the suite state summary for latest message
        self.latest_message = message
        self.latest_message_priority = priority
        self.summary[ 'latest_message' ] = (
            self.latest_message.replace(self.id, "", 1).strip())
        self.summary[ 'latest_message_priority' ] = self.latest_message_priority
        flags.iflag = True

        if self.reject_if_failed( message ):
            # Failed tasks do not send messages unless declared resurrectable
            return

        msg_was_polled = False
        if message.startswith( 'polled ' ):
            if not self.state.is_currently( 'submitted', 'running' ):
                # Polling can take a few seconds or more, so it is
                # possible for a poll result to come in after a task
                # finishes normally (success or failure) - in which case
                # we should ignore the poll result.
                self.log( "WARNING", "Ignoring late poll result: task is not active" ) 
                return
            # remove polling prefix and treat as a normal task message
            msg_was_polled = True
            message = message[7:]

        # remove the remote event time (or "unknown-time" from polling) from the end:
        message = poll_suffix_re.sub( '', message )

        # Remove the prepended task ID.
        content = message.replace( self.id + ' ', '' )

        # If the message matches a registered output, record it as completed.
        if self.outputs.exists( message ):
            if not self.outputs.is_completed( message ):
                flags.pflag = True
                self.outputs.set_completed( message )
                self.record_db_event(event="output completed", message=content)
            elif content == 'started' and self.job_vacated:
                self.job_vacated = False
                self.log( "WARNING", "Vacated job restarted: " + message )
            elif not msg_was_polled:
                # This output has already been reported complete.
                # Not an error condition - maybe the network was down for a bit.
                # Ok for polling as multiple polls *should* produce the same result.
                self.log( "WARNING", "Unexpected output (already completed):\n  " + message )

        if priority == 'WARNING':
            self.handle_event( 'warning', content, db_update=False )

        if self.event_hooks['reset timer']:
            # Reset execution timer on incoming messages
            execution_timeout = self.event_hooks['execution timeout']
            if execution_timeout:
                self.execution_timer_timeout = (
                    time.time() + execution_timeout
                )

        elif content == 'started' and self.state.is_currently( 'ready','submitted','submit-failed' ):
            # Received a 'task started' message

            flags.pflag = True
            self.set_status( 'running' )

            self.started_time = time.time()
            self.summary[ 'started_time' ] = self.started_time
            self.summary[ 'started_time_string' ] = (
                get_time_string_from_unix_time(
                    self.started_time, no_display_time_zone=True
                )
            )

            # TODO - should we use the real event time extracted from the message here:
            execution_timeout = self.event_hooks['execution timeout']
            if execution_timeout:
                self.execution_timer_timeout = (
                    self.started_time + execution_timeout
                )
            else:
                self.execution_timer_timeout = None

            # submission was successful so reset submission try number
            self.sub_try_number = 1
            self.sub_retry_delays = copy( self.sub_retry_delays_orig )
            self.handle_event( 'started', 'job started' )
            self.execution_poll_timer.set_timer()

        elif content == 'succeeded' and self.state.is_currently('ready','submitted','submit-failed','running','failed'):
            # Received a 'task succeeded' message
            # (submit* states in case of very fast submission and execution)
            self.execution_timer_timeout = None
            flags.pflag = True
            self.succeeded_time = time.time()
            self.summary[ 'succeeded_time' ] = self.succeeded_time
            self.summary[ 'succeeded_time_string' ] = (
                get_time_string_from_unix_time(
                    self.succeeded_time, no_display_time_zone=True
                )
            )
            self.__class__.update_mean_total_elapsed_time( self.started_time, self.succeeded_time )
            self.set_status( 'succeeded' )
            self.handle_event( "succeeded", "job succeeded" )
            if not self.outputs.all_completed():
                # This is no longer treated as an error condition.
                err = "Assuming non-reported outputs were completed:"
                for key in self.outputs.not_completed:
                    err += "\n" + key
                self.log( 'WARNING', err )
                self.outputs.set_all_completed()

        elif content == 'failed' and self.state.is_currently('ready','submitted','submit-failed','running'):
            # (submit- states in case of very fast submission and execution).
            self.job_execution_failed()

        elif content.startswith("Task job script received signal"):
            # capture and record signals sent to task proxy
            self.record_db_event(event="signaled", message=content)
 
        elif content.startswith("Task job script vacated by signal"):
            flags.pflag = True
            self.set_status('submitted')
            self.record_db_event(event="vacated", message=content)
            self.execution_timer_timeout = None
            self.summary['started_time'] = '*'
            self.sub_try_number = 0
            self.sub_retry_delays = copy(self.sub_retry_delays_orig)
            self.execution_poll_timer.timer_start = None
            self.job_vacated = True

        else:
            # Unhandled messages. These include:
            #  * general non-output/progress messages
            #  * poll messages that repeat previous results
            # Note that all messages are logged already at the top.
            self.log('DEBUG', '(current:' + self.state.get_status() + ') unhandled: ' + content )

    def set_status( self, status ):
        if status != self.state.get_status():
            flags.iflag = True
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
        next = self.next_tag()
        if next:
            successor = self.__class__( next, state )
            # propagate task stop time
            successor.stop_c_time = self.stop_c_time
            return successor
        else:
            # next instance is out of the sequence bounds
            return None

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

    def get_state_summary( self ):
        # derived classes can call this method and then
        # add more information to the summary if necessary.

        self.summary[ 'state' ] = self.state.get_status()
        self.summary[ 'spawned' ] = self.state.has_spawned()

        met = self.__class__.mean_total_elapsed_time
        if not met:
            met = "*"
        self.summary[ 'mean total elapsed time' ] =  met

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
        # derived classes override this to compute next valid cycle point.
        return None

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

        job_sub_method = self.job_sub_method
        if not job_sub_method:
            if self.user_at_host:
                if "@" in self.user_at_host:
                    self.task_owner, self.task_host = self.user_at_host.split('@', 1)
                else:
                    self.task_host = self.user_at_host
            job_sub_method = self.presubmit( self.task_owner, self.task_host, self.submit_num )

        if not hasattr( job_sub_method, 'poll' ):
            # (for job submission methods that do not handle polling yet)
            self.log( 'WARNING', "'" + self.job_sub_method_name + "' job submission does not support polling" )
            return

        cmd = ("cylc get-job-status %(status_file)s %(job_sys)s %(job_id)s" % {
                    "status_file": job_sub_method.jobfile_path + ".status",
                    "job_sys": job_sub_method.__class__.__name__,
                    "job_id": self.submit_method_id})
        if self.user_at_host not in [user + '@localhost', 'localhost']:
            cmd = cv_scripting_sl + "; " + cmd
            cmd = 'ssh -oBatchMode=yes ' + self.user_at_host + " '" + cmd + "'"

        self.log( 'NORMAL', 'polling now' )
        cmd_spec = ( command_types.POLL_OR_KILL, cmd )
        self.__class__.proc_pool.put_command( cmd_spec, self.poll_command_callback )

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

        job_sub_method = self.job_sub_method
        if not job_sub_method:
            if self.user_at_host:
                if "@" in self.user_at_host:
                    self.task_owner, self.task_host = self.user_at_host.split('@', 1)
                else:
                    self.task_host = self.user_at_host
            job_sub_method = self.presubmit( self.task_owner, self.task_host, self.submit_num )

        if not hasattr( job_sub_method, 'kill' ):
            # (for job submission methods that do not handle polling yet)
            self.log( 'WARNING', "'" + self.job_sub_method_name + "' job submission does not support killing" )
            return

        cmd = ("cylc job-kill %(status_file)s %(job_sys)s %(job_id)s" % {
                    "status_file": job_sub_method.jobfile_path + ".status",
                    "job_sys": job_sub_method.__class__.__name__,
                    "job_id": self.submit_method_id})
        if self.user_at_host != user + '@localhost':
            cmd = cv_scripting_sl + "; " + cmd
            cmd = 'ssh -oBatchMode=yes ' + self.user_at_host + " '" + cmd + "'"
        # TODO - just pass self.message_queue.put rather than whole self?
        self.log( 'CRITICAL', "Killing job" )
        cmd_spec = ( command_types.POLL_OR_KILL, cmd )
        self.__class__.proc_pool.put_command( cmd_spec, self.kill_command_callback )

