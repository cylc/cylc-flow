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
# To get it to work with Python 2.3 (note that cylc view will not work!)
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


# TASK BASE CLASS:

import sys
import task_state
import logging
import Pyro.core
from copy import deepcopy
from dynamic_instantiation import get_object

global state_changed
#state_changed = False
state_changed = True

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
        #for line in cls.description:
        #    print line


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

        try:
            # is there a task command lined up?
            self.external_task = self.external_tasks.popleft()
        except IndexError:
            # this is currently an error; scripting-only tasks
            # are given the command /bin/true by configure.
            raise
 
        self.launcher = get_object( 'job_submit_methods', self.job_submit_method ) \
                ( self.id, self.external_task, self.env_vars, self.directives, 
                        self.extra_scripting, self.logfiles, self.__class__.owner, self.__class__.remote_host )

    def log( self, priority, message ):
        # task-specific log file

        # is it better to "get" this each call as here, or to get a
        # 'self.logger' once in __init__?
        logger = logging.getLogger( "main." + self.name ) 

        # task logs are specific to task type
        try:
            ( name, tag ) = (self.id).split('%')
        except ValueError:
            pass
        else:
            message = '[' + tag + '] ' + message

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
            self.run_external_task()
            return True
        else:
            return False

    def run_external_task( self, dry_run=False ):
        self.log( 'DEBUG',  'launching external task' )
        if self.launcher.submit( dry_run ):
            self.state.set_status( 'submitted' )
            self.log( 'NORMAL', "job submitted" )
        else:
            self.state.set_status( 'failed' )
            self.log( 'CRITICAL', "job submission failed" )

    def set_all_internal_outputs_completed( self ):
        if self.reject_if_failed( 'set_all_internal_outputs_completed' ):
            return
        # used by the task wrapper 
        self.log( 'DEBUG', 'setting all internal outputs completed' )
        for message in self.outputs.satisfied.keys():
            if message != self.id + ' started' and \
                    message != self.id + ' finished' and \
                    message != self.id + ' completed':
                #self.outputs.set_satisfied( message )
                #self.latest_message = message
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
        if self.reject_if_failed( message ):
            return

        # receive all incoming pyro messages for this task 
        self.latest_message = message

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
            self.state.set_status( 'running' )

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
                        self.log( 'CRITICAL', 'finished before all outputs were completed' )
                        self.state.set_status( 'failed' )
                    else:
                        print
                        print self.id + " FINISHED"
                        self.state.set_status( 'finished' )
                        self.launcher.cleanup()
            else:
                # this output has already been satisfied
                self.log( 'WARNING', "UNEXPECTED OUTPUT (already satisfied):" )
                self.log( 'WARNING', "-> " + message )

        elif message == self.id + ' failed':
            # process task failure messages

            state_changed = True
            self.log( 'CRITICAL',  message )
            self.state.set_status( 'failed' )

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
                    self.log( 'CRITICAL',  'Retrying with next %TASK' )
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
