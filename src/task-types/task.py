#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|

# This module uses the @classmethod decorator, introduced in Python 2.4.
# To get it to work with Python 2.3 (note that cylc gui will not work!),
# replace:
# 
# @classmethod
# def foo( bar ):
#   pass
# 
# with:
#
# def foo( bar ):
#   pass
# foo = classmethod( foo )


# TASK PROXY BASE CLASS:

import sys
import datetime
import task_state
import logging
import Pyro.core
import subprocess
from copy import deepcopy
from dynamic_instantiation import get_object
from collections import deque

# TO DO: IS GLOBAL NECESSARY HERE?
global state_changed
state_changed = True

task_started_hook = None
task_finished_hook = None
task_failed_hook = None
task_warning_hook = None
task_submitted_hook = None
task_submission_failed_hook = None
task_timeout_hook = None
task_submission_timeout_minutes = None

# NOTE ON TASK STATE INFORMATION---------------------------------------

# task attributes required for a system cold start are:
#  state ('waiting', 'submitted', 'running', and 'finished' or 'failed')

# The 'state' variable is initialised by the base class, and written to
# the state dump file by the base class dump_state() method.

# For a restart from previous state some tasks may require additional
# state information to be stored in the state dump file.

# To handle this difference in initial state information (between normal
# start and restart) task initialisation must use a default value of
# 'None' for the additional variables, and for a restart the task
# manager must instantiate each task with a flattened list of all the
# state values found in the state dump file.

class task( Pyro.core.ObjBase ):
    
    intercycle = False

    @classmethod
    def describe( cls ):
        return cls.description 

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

    def __init__( self, state ):
        # Call this AFTER derived class initialisation

        # Derived class init MUST define:
        #  * unique identity (NAME%CYCLE for cycling tasks)
        #  * prerequisites and outputs
        #  * self.env_vars 

        class_vars = {}
        self.state = task_state.task_state( state )

        # count instances of each top level object derived from task
        # top level derived classes must define:
        #   <class>.instance_count = 0
        self.__class__.instance_count += 1

        Pyro.core.ObjBase.__init__(self)

        # set state_changed True if any task's state changes 
        # as a result of a remote method call
        global state_changed 
        state_changed = True

        self.latest_message = ""
        self.latest_message_priority = "NORMAL"

        try:
            # is there a task command lined up?
            self.external_task = self.external_tasks.popleft()
        except IndexError:
            # this is currently an error; scripting-only tasks
            # default to the command /bin/true.
            raise

        self.submission_start_time = None
        self.execution_start_time = None

        self.set_execution_timer = False

        self.launcher = get_object( 'job_submit_methods', self.job_submit_method ) \
                ( self.id, self.external_task, self.env_vars, self.directives, 
                        self.extra_scripting, self.logfiles, self.__class__.owner, self.__class__.remote_host )

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
        # The task manager MUST call this immediately before deleting a
        # task object. It decrements the instance count of top level
        # objects derived from task base. It would be nice to use Python's
        # __del__() function for this, but that is only called when a
        # deleted object is about to be garbage collected (which is not
        # guaranteed to be right away). This was once used for
        # constraining the number of instances of each task type. 
        self.__class__.instance_count -= 1

    def ready_to_run( self, current_time ):
        # ready if 'waiting' AND all prequisites satisfied
        ready = False
        if self.state.is_waiting() and self.prerequisites.all_satisfied(): 
            ready = True
        return ready

    def get_resolved_dependencies( self ):
        dep = []
        for label in self.prerequisites.satisfied_by.keys():
            print ' o "' + self.prerequisites.messages[ label ] + '" <--- ' + self.prerequisites.satisfied_by[ label ]
            dep.append( self.prerequisites.satisfied_by[ label ] )
        return dep

    def run_if_ready( self, current_time ):
        if self.ready_to_run( current_time ):
            print
            print self.id, ' READY TO RUN'
            self.run_external_task( current_time )
            return True
        else:
            return False

    def call_warning_hook( self, message ):
        self.log( 'WARNING', 'calling task warning hook' )
        command = ' '.join( [task_warning_hook, 'warning', self.name, self.c_time, "'" + message + "'"] )
        subprocess.call( command, shell=True )

    def set_submitted( self ):
        self.state.set_status( 'submitted' )
        self.log( 'NORMAL', "job submitted" )
        if task_submitted_hook:
            self.log( 'NORMAL', 'calling task submitted hook' )
            command = ' '.join( [task_submitted_hook, 'submitted', self.name, self.c_time, "'(task submitted)'"] )
            subprocess.call( command, shell=True )

    def set_running( self ):
        self.state.set_status( 'running' )
        if task_started_hook:
            self.log( 'NORMAL', 'calling task started hook' )
            command = ' '.join( [task_started_hook, 'started', self.name, self.c_time, "'(task running)'"] )
            subprocess.call( command, shell=True )

    def set_finished( self ):
        self.outputs.set_all_complete()
        self.state.set_status( 'finished' )

    def set_finished_hook( self ):
        # (set_finished() is used by remote switch)
        print '\n' + self.id + " FINISHED"
        self.state.set_status( 'finished' )
        if task_finished_hook:
            self.log( 'NORMAL', 'calling task finished hook' )
            command = ' '.join( [task_finished_hook, 'finished', self.name, self.c_time, "'(task finished)'"] )
            subprocess.call( command, shell=True )

    def set_failed( self, reason ):
        self.state.set_status( 'failed' )
        self.log( 'CRITICAL', reason )
        if task_failed_hook:
            self.log( 'WARNING', 'calling task failed hook' )
            command = ' '.join( [task_failed_hook, 'failed', self.name, self.c_time, "'" + reason + "'"] )
            subprocess.call( command, shell=True )

    def set_submit_failed( self ):
        reason = 'job submission failed'
        self.state.set_status( 'failed' )
        self.log( 'CRITICAL', reason )
        if task_submission_failed_hook:
            self.log( 'WARNING', 'calling task submission failed hook' )
            command = ' '.join( [task_submission_failed_hook, 'submit_failed', self.name, self.c_time, "'" + reason + "'"] )
            subprocess.call( command, shell=True )

    def run_external_task( self, current_time, dry_run=False ):
        self.log( 'DEBUG',  'submitting task script' )
        if self.launcher.submit( dry_run ):
            self.set_submitted()
            self.submission_start_time = current_time
        else:
            self.set_submit_failed()

    def check_timeout( self, current_time ):
        if not task_timeout_hook:
            # no script defined (in suite.rc) to process timeouts
            return
        if not self.state.is_submitted() and not self.state.is_running():
            # task submission and execution timeouts only
            return
        if self.set_execution_timer:
            # this indicates that the task has started and we need to 
            # start the execution timer now (current_time is not
            # available in the incoming message receiver as this 
            # is the accelerated clock if in dummy mode ... we need a
            # way to make the accelerated clock available anywhere).
            self.execution_start_time = current_time
            self.set_execution_timer = False
            # cancel job submission timer
            self.submission_start_time = None
            return

        if task_submission_timeout_minutes and self.submission_start_time:
            timeout = self.submission_start_time + datetime.timedelta( minutes=task_submission_timeout_minutes )
            if current_time > timeout:
                msg = 'submitted ' + str( task_submission_timeout_minutes ) + ' minutes ago but has not started'
                self.log( 'WARNING', msg )
                command = ' '.join( [ task_timeout_hook, 'submission', self.name, self.c_time, "'" + msg + "'" ] )
                subprocess.call( command, shell=True )
                self.submission_start_time = None

        if self.execution_timeout_minutes and self.execution_start_time:
            timeout = self.execution_start_time + datetime.timedelta( minutes=self.execution_timeout_minutes )
            if current_time > timeout:
                if self.reset_execution_timeout_on_incoming_messages:
                    msg = 'last message ' + str( self.execution_timeout_minutes ) + ' minutes ago, not finished'
                else:
                    msg = 'started ' + str( self.execution_timeout_minutes ) + ' minutes ago, not finished'
                self.log( 'WARNING', msg )
                command = ' '.join( [ task_timeout_hook, 'execution', self.name, self.c_time, "'" + msg + "'" ] )
                subprocess.call( command, shell=True )
                self.execution_start_time = None

    def set_all_internal_outputs_completed( self ):
        if self.reject_if_failed( 'set_all_internal_outputs_completed' ):
            return
        # used by the task wrapper 
        self.log( 'DEBUG', 'setting all internal outputs completed' )
        for message in self.outputs.satisfied.keys():
            if message != self.id + ' started' and \
                    message != self.id + ' finished' and \
                    message != self.id + ' completed':
                self.incoming( 'NORMAL', message )

    def is_complete( self ):  # not needed?
        if self.outputs.all_satisfied():
            return True
        else:
            return False

    def get_ordered_outputs( self ):
        return self.outputs.get_ordered()

    def reject_if_failed( self, message ):
        if self.state.is_failed():
            self.log( 'WARNING', 'rejecting the following message as I am in the failed state:' )
            self.log( 'WARNING', '  ' + message )
            return True
        else:
            return False

    def incoming( self, priority, message ):
        if task_warning_hook and priority == 'WARNING':
            self.call_warning_hook( message )

        if self.reject_if_failed( message ):
            return

        if self.reset_execution_timeout_on_incoming_messages:
            self.set_execution_timer = True

        # receive all incoming pyro messages for this task 
        self.latest_message = message
        self.latest_message_priority = priority

        # setting state_change results in task processing loop
        # invocation. We should really only do this when the
        # incoming message results in a state change that matters to
        # scheduling ... but system monitor may need latest message, and
        # we don't yet have a separate state-summary-update invocation
        # flag. 
        
        # new round of dependency renegotiations)
        global state_changed
        state_changed = True

        if message == self.id + ' started':
            self.set_execution_timer = True
            self.set_running()

        if not self.state.is_running():
            # my external task should not be running!
            self.log( 'WARNING', "UNEXPECTED MESSAGE (task should not be running)" )
            self.log( 'WARNING', '-> ' + message )

        if self.outputs.exists( message ):
            # registered output messages

            if not self.outputs.is_satisfied( message ):
                # message indicates completion of a registered output.
                self.log( priority,  message )
                self.outputs.set_satisfied( message )

                if message == self.id + ' finished':
                    # TASK HAS FINISHED
                    if not self.outputs.all_satisfied():
                        self.set_failed( 'finished before all outputs were completed' )
                    else:
                        self.set_finished_hook()
                        self.launcher.cleanup()
            else:
                # this output has already been satisfied
                self.log( 'WARNING', "UNEXPECTED OUTPUT (already satisfied):" )
                self.log( 'WARNING', "-> " + message )

        elif message == self.id + ' failed':
            # process task failure messages

            state_changed = True

            self.set_failed( message )

            try:
                # is there another task lined up for a retry?
                self.external_task = self.external_tasks.popleft()
            except IndexError:
                # no, can't retry.
                self.outputs.add( message )
                self.outputs.set_satisfied( message )
            else:
                # yes, do retry.
                if not self.launcher.dummy_mode:
                    self.log( 'CRITICAL',  'Retrying with next command' )
                    self.launcher.task = self.external_task
                    self.state.set_status( 'waiting' )
                    self.prerequisites.set_all_satisfied()
                    self.outputs.set_all_incomplete()

        else:
            # log other (non-failed) unregistered messages with a '*' prefix
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
        # this exists because the oneoff modifier needs to override it.
        return self.state.has_spawned()

    def ready_to_spawn( self ):
        # return True or False
        self.log( 'CRITICAL', 'ready_to_spawn(): OVERRIDE ME')
        sys.exit(1)

    def done( self ):
        # return True if task has finished and spawned
        if self.state.is_finished() and self.state.has_spawned():
            return True
        else:
            return False

    def check_requisites( self ):
        # overridden by asynchronous tasks and task families
        pass

    def get_state_summary( self ):
        # derived classes can call this method and then 
        # add more information to the summary if necessary.

        n_total = self.outputs.count()
        n_satisfied = self.outputs.count_satisfied()

        summary = {}
        summary[ 'name' ] = self.name
        summary[ 'label' ] = self.tag
        try:
            summary[ 'short_name' ] = self.short_name
        except AttributeError:
            # task has no short name
            pass
        summary[ 'state' ] = self.state.get_status()
        summary[ 'n_total_outputs' ] = n_total
        summary[ 'n_completed_outputs' ] = n_satisfied
        summary[ 'spawned' ] = self.state.has_spawned()
        summary[ 'latest_message' ] = self.latest_message
        summary[ 'latest_message_priority' ] = self.latest_message_priority


        summary[ 'logfiles' ] = self.logfiles.get_paths()
 
        return summary

    def not_fully_satisfied( self ):
        if not self.prerequisites.all_satisfied():
            return True
        if not self.suicide_prerequisites.all_satisfied():
            return True
        return False

    def satisfy_me( self, task ):
        self.prerequisites.satisfy_me( task )
        self.suicide_prerequisites.satisfy_me( task )

    def next_tag( self ):
        raise SystemExit( "OVERRIDE ME" )

    def my_successor_still_needs_me( self, tasks ):
        # overridden in mod_pid
        return False
