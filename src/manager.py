#!/usr/bin/python

import reference_time
import pimp_my_logger
import requisites
import logging
import os
import re

class manager:
    def __init__( self, config, pyro, restart, dummy_clock ):
        
        self.pyro = pyro  # pyrex (cyclon Pyro helper) object
        self.log = logging.getLogger( "main" )

        self.config = config

        self.system_hold = False

        # initialise the dependency broker
        self.broker = requisites.broker()
        
        # instantiate the initial task list and create task logs 
        self.tasks = []
        if restart:
            self.load_from_state_dump( dummy_clock )
        else:
            self.load_from_config( dummy_clock )

    def set_system_hold( self ):
        self.log.critical( "SETTING SYSTEM HOLD: no new tasks will run")
        self.system_hold = True

    def unset_system_hold( self ):
        self.log.critical( "UNSETTING SYSTEM HOLD: new tasks will run when ready")
        self.system_hold = False

    def get_task_instance( self, module, class_name ):
        # task object instantiation by module and class name
	    mod = __import__( module )
	    return getattr( mod, class_name)

    def get_oldest_ref_time( self ):
        oldest = 9999887766
        for itask in self.tasks:
            if int( itask.ref_time ) < int( oldest ):
                oldest = itask.ref_time
        return oldest

    def load_from_config ( self, dummy_clock ):
        # load initial system state from configured tasks and start time
        #--
        print '\nCLEAN START: INITIAL STATE FROM CONFIGURED TASK LIST\n'
        self.log.info( 'Loading state from configured task list' )
        # config.task_list = [ taskname(:state), taskname(:state), ...]
        # where (:state) is optional and defaults to 'waiting'.

        start_time = self.config.get('start_time')

        for item in self.config.get('task_list'):
            state = 'waiting'
            name = item

            if re.compile( "^.*:").match( item ):
                [name, state] = item.split(':')

            # instantiate the task
            itask = self.get_task_instance( 'task_classes', name )( start_time, 'False', state )

            # create the task log
            log = logging.getLogger( 'main.' + name )
            pimp_my_logger.pimp_it( log, name, self.config, dummy_clock )

            # the initial task reference time can be altered during
            # creation, so we have to create the task before
            # checking if stop time has been reached.
            skip = False
            if self.config.get('stop_time'):
                if int( itask.ref_time ) > int( self.config.get('stop_time') ):
                    itask.log( 'WARNING', "STOPPING at " + self.config.get('stop_time') )
                    itask.prepare_for_death()
                    del itask
                    skip = True

            if not skip:
                itask.log( 'DEBUG', "connected" )
                self.pyro.connect( itask, itask.identity )
                self.tasks.append( itask )


    def load_from_state_dump( self, dummy_clock ):
        # load initial system state from the configured state dump file
        #--
        filename = self.config.get('state_dump_file')
        # state dump file format: ref_time:name:state, one per line 
        self.log.info( 'Loading previous state from ' + filename )

        FILE = open( filename, 'r' )
        lines = FILE.readlines()
        FILE.close()

        log_created = {}

        # parse each line and create the task it represents
        for line in lines:
            # strip trailing newlines
            line = line.rstrip( '\n' )
            # ref_time task_name abdicated task_state_string
            [ ref_time, name, abdicated, state_string ] = line.split()
            state_list = state_string.split( ':' )
            # main state (waiting, running, finished, failed)
            state = state_list[0]

            if state == 'running' or state == 'failed':
                # To be safe we have to assume that running and failed
                # tasks need to re-run on a restart. The fact that they
                # were running (or did run before failing) implies their
                # prerequisites were already satisfied so they can
                # restart in a 'ready' state
                state_list[0] = 'ready'

            # instantiate the task object
            itask = self.get_task_instance( 'task_classes', name )( ref_time, abdicated, *state_list )

            # create the task log
            if name not in log_created.keys():
                log = logging.getLogger( 'main.' + name )
                pimp_my_logger.pimp_it( log, name, self.config, dummy_clock )
                log_created[ name ] = True
 
            # the initial task reference time can be altered during
            # creation, so we have to create the task before
            # checking if stop time has been reached.
            skip = False
            if self.config.get('stop_time'):
                if int( itask.ref_time ) > int( self.config.get('stop_time') ):
                    itask.log( 'WARNING', " STOPPING at " + self.config.get('stop_time') )
                    itask.prepare_for_death()
                    del itask
                    skip = True

            if not skip:
                itask.log( 'DEBUG', "connected" )
                self.pyro.connect( itask, itask.identity )
                self.tasks.append( itask )

    def all_finished( self ):
        # return True if all tasks have finished AND abdicated
        #--
        for itask in self.tasks:
            if itask.is_not_finished() or not itask.has_abdicated():
                return False
        return True


    def negotiate_dependencies( self ):
        # run time dependency negotiation: tasks attempt to get their
        # prerequisites satisfied by other tasks' outputs.
        #--
    
        # Instead: O(n) BROKERED NEGOTIATION

        self.broker.reset()

        for itask in self.tasks:
            # register task outputs
            self.broker.register( itask.identity, itask.outputs )

        # for debugging;            
        #self.broker.dump()

        for itask in self.tasks:
            # get the broker to satisfy tasks prerequisites
            self.broker.negotiate( itask.prerequisites )

    def run_tasks( self, launcher ):
        # tell each task to run if it is ready
        # unless the system is on hold
        #--
        if self.system_hold:
            return

        for itask in self.tasks:
                itask.run_if_ready( launcher )

    def regenerate_tasks( self ):
        # create new tasks foo(T+1) if foo has not got too far ahead of
        # the slowest task, and if foo(T) abdicates
        #--

        # update oldest system reference time
        oldest_ref_time = self.get_oldest_ref_time()

        for itask in self.tasks:

            tdiff = reference_time.decrement( itask.ref_time, self.config.get('max_runahead_hours') )
            if int( tdiff ) > int( oldest_ref_time ):
                # too far ahead: don't abdicate this task.
                itask.log( 'DEBUG', "delaying abdication (too far ahead)" )
                continue

            if itask.abdicate():
                itask.log( 'DEBUG', 'abdicating')

                # dynamic task object creation by task and module name
                new_task = self.get_task_instance( 'task_classes', itask.name )( itask.next_ref_time(), 'False', "waiting" )
                if self.config.get('stop_time') and int( new_task.ref_time ) > int( self.config.get('stop_time') ):
                    # we've reached the stop time: delete the new task 
                    new_task.log( 'WARNING', "STOPPING at configured stop time " + self.config.get('stop_time') )
                    new_task.prepare_for_death()
                    del new_task
                else:
                    # no stop time, or we haven't reached it yet.
                    self.pyro.connect( new_task, new_task.identity )
                    new_task.log('DEBUG', "connected" )
                    self.tasks.append( new_task )

    def dump_state( self ):
        filename = self.config.get('state_dump_file')
        FILE = open( filename, 'w' )
        for itask in self.tasks:
            itask.dump_state( FILE )
        FILE.close()

    def kill_lame_tasks( self ):
        # Remove any tasks in the OLDEST BATCH whose prerequisites
        # cannot be satisfied by their co-temporal peers. It's not
        # possible to detect lame tasks in newer batches because 
        # they may not be fully populated yet (more tasks can appear
        # as their predecessors abdicate).

        # This function removes all lame tasks in the oldest batch
        # before returning. Any lame tasks in the next batch may not be
        # removed immediately during periods when no remote messages are
        # coming in (since that's what activates task processing,
        # including this function).  TO DO: use an outer loop in this
        # function to repeat the process in the next batch, if the first
        # batch is entirely rejected for being lame.

        # NOTE: if a lame task has been held up by a failed task that it
        # depends on, the whole system may be held up because lame tasks
        # will delay abdication past the runahead limit. So after
        # killing the failed task, the operator will need to 'nudge' the
        # system to get task processing going again (setting
        # task.state_changed = True in this function after deleting the 
        # lame task does not currently have the desired effect because
        # of the way task state_changed is reset in the main program. 
        #--

        batches = {}
        for itask in self.tasks:
           if itask.ref_time not in batches.keys():
               batches[ itask.ref_time ] = [ itask ]
           else:
               batches[ itask.ref_time ].append( itask )

        reftimes = batches.keys()
        if len( reftimes ) == 0:
            return

        reftimes.sort( key = int )
        oldest_batch = batches[ reftimes[0] ]

        while True:
            # repeat until no lame tasks are found in this batch,
            # because in a set of cotemporal tasks that depend on each
            # other only one can be identified as lame at a time (a task
            # that depends on the lame task will not itself appear to be
            # lame until the lame task has been deleted).
            lame_tasks = []
            no_lame_found = True
            for itask in oldest_batch:
                if itask.state != 'waiting':
                    # running, finished, or failed tasks are not lame
                    continue
                # need to attempt satisfaction from all tasks in the
                # batch, not just the potentially lame ones
                if not itask.will_get_satisfaction( oldest_batch ):
                    lame_tasks.append( itask )
                    no_lame_found = False
    
            if no_lame_found:
                break

            for lame in lame_tasks:
                if not lame.has_abdicated():
                    # forcibly abdicate the lame task and create its successor
                    lame.set_abdicated()
                    lame.log( 'WARNING', "forced abdication (lame)" )
                    new_task = self.get_task_instance( 'task_classes', lame.name )( lame.next_ref_time(), 'False', "waiting" )
                    new_task.log('DEBUG', "connected" )
                    self.pyro.connect( new_task, new_task.identity )
                    self.tasks.append( new_task )
                else:
                    # already abdicated: the successor already exists.
                    pass

                # delete the lame task
                oldest_batch.remove( lame )
                self.tasks.remove( lame )
                self.pyro.disconnect( lame )
                lame.log( 'WARNING', "disconnected (lame)" )
                lame.prepare_for_death()
                del lame


    def kill_spent_tasks( self ):
        # Delete tasks that are no longer needed to satisfy the
        # prerequisites of any other tasks, or to spawn a successor: 
        
        # i.e. done (finished AND abdicated for normal tasks; finished for
        # oneoff tasks) AND, if quick_death is False, older than system
        # cutoff time.

        # system cutoff is the oldest "most recently finished" time 
        #--

        # list of tasks that are "done"
        tasks_done = []
        
        oldest_unsat_ref_time = None
        all_tasks_satisfied = True
        cutoff = None

        for itask in self.tasks:

            if itask.done():
                tasks_done.append( itask )

            if not itask.prerequisites.all_satisfied():
                all_tasks_satisfied = False
                if not oldest_unsat_ref_time:
                    oldest_unsat_ref_time = itask.ref_time
                elif int( itask.ref_time ) < int( oldest_unsat_ref_time ):
                    oldest_unsat_ref_time = itask.ref_time

            if not cutoff:
                cutoff = itask.__class__.cutoff_time
            else:
                if int( itask.__class__.cutoff_time ) < int( cutoff) :
                    cutoff = itask.__class__.cutoff_time 

        if oldest_unsat_ref_time:
            self.log.debug( "oldest unsatisfied: " + oldest_unsat_ref_time )

        if cutoff:
            self.log.debug( "task deletion cutoff is " + cutoff )

        # list of tasks to delete
        spent_tasks = []
        for itask in tasks_done:
            if itask.quick_death: 
                # case [i] tasks to delete
                if all_tasks_satisfied or int( itask.ref_time ) < int( oldest_unsat_ref_time ):
                    spent_tasks.append( itask )
            else:
                # case [ii] tasks to delete
                if cutoff:
                    if int( itask.ref_time ) < int( cutoff ):
                        spent_tasks.append( itask )

        # delete spent tasks
        for itask in spent_tasks:
            self.tasks.remove( itask )
            self.pyro.disconnect( itask )
            itask.log( 'NORMAL', "disconnected (spent)" )
            itask.prepare_for_death()

        del spent_tasks

    def insert_task( self, task_id, dummy_clock ):
        # insert a new task in a waiting state

        [ name, ref_time ] = task_id.split( '%' )
        abdicated = False
        state_list = [ 'waiting' ]

        # instantiate the task object
        itask = self.get_task_instance( 'task_classes', name )( ref_time, abdicated, *state_list )

        if itask.instance_count == 1:
            # first task of its type, so create the log
            log = logging.getLogger( 'main.' + name )
            pimp_my_logger.pimp_it( log, name, self.config, dummy_clock )
 
        # the initial task reference time can be altered during
        # creation, so we have to create the task before
        # checking if stop time has been reached.
        skip = False
        if self.config.get('stop_time'):
            if int( itask.ref_time ) > int( self.config.get('stop_time') ):
                itask.log( 'WARNING', " STOPPING at " + self.config.get('stop_time') )
                itask.prepare_for_death()
                del itask
                skip = True

        if not skip:
            itask.log( 'DEBUG', "connected" )
            self.pyro.connect( itask, itask.identity )
            self.tasks.append( itask )


    def abdicate_and_kill( self, task_id ):
        # find the task
        found = False
        for t in self.tasks:
            if t.identity == task_id:
                found = True
                itask = t
                break

        if not found:
            self.log.warning( "task not found for remote kill request: " + task_id )
            return

        itask.log( 'DEBUG', "killing myself by remote request" )

        if not itask.has_abdicated():
            # forcibly abdicate the task and create its successor
            itask.set_abdicated()
            itask.log( 'DEBUG', 'forced abdication' )
            # TO DO: the following should reuse code in regenerate_tasks()?
            # dynamic task object creation by task and module name
            new_task = self.get_task_instance( 'task_classes', itask.name )( itask.next_ref_time(), 'False', "waiting" )
            if self.config.get('stop_time') and int( new_task.ref_time ) > int( self.config.get('stop_time') ):
                # we've reached the stop time: delete the new task 
                new_task.log( 'WARNING', 'STOPPING at configured stop time' )
                new_task.prepare_for_death()
                del new_task
            else:
                # no stop time, or we haven't reached it yet.
                self.pyro.connect( new_task, new_task.identity )
                new_task.log( 'DEBUG', 'connected' )
                self.tasks.append( new_task )

        else:
            # already abdicated: the successor already exists
            pass

        # now kill the task
        self.tasks.remove( itask )
        self.pyro.disconnect( itask )
        itask.log( 'WARNING', "disconnected (remote request)" )
        itask.prepare_for_death()
        del itask
