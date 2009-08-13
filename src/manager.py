#!/usr/bin/python

import reference_time
import pimp_my_logger
import requisites
import logging
import task
import os
import re

class manager:
    def __init__( self, config, pyro, restart, dummy_clock ):
        
        self.pyro = pyro  # pyrex (cycon Pyro helper) object
        self.log = logging.getLogger( "main" )

        self.config = config

        self.finished_task_dict = []
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
        for task in self.tasks:
            if int( task.ref_time ) < int( oldest ):
                oldest = task.ref_time
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
            task = self.get_task_instance( 'task_classes', name )( start_time, 'False', state )

            # create the task log
            log = logging.getLogger( 'main.' + name )
            pimp_my_logger.pimp_it( log, name, self.config, dummy_clock )

            # the initial task reference time can be altered during
            # creation, so we have to create the task before
            # checking if stop time has been reached.
            skip = False
            if self.config.get('stop_time'):
                if int( task.ref_time ) > int( self.config.get('stop_time') ):
                    task.log.warning( task.name + " STOPPING at " + self.config.get('stop_time') )
                    task.prepare_for_death()
                    del task
                    skip = True

            if not skip:
                task.log.debug( "new " + task.name + " connected for " + task.ref_time )
                self.pyro.connect( task, task.identity )
                self.tasks.append( task )


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
            # convert running to waiting on restart
            if state == 'running' or state == 'failed':
                state_list[0] = 'waiting'

            # instantiate the task object
            task = self.get_task_instance( 'task_classes', name )( ref_time, abdicated, *state_list )

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
                if int( task.ref_time ) > int( self.config.get('stop_time') ):
                    task.log.warning( task.name + " STOPPING at " + self.config.get('stop_time') )
                    task.prepare_for_death()
                    del task
                    skip = True

            if not skip:
                task.log.debug( "new " + task.name + " connected for " + task.ref_time )
                self.pyro.connect( task, task.identity )
                self.tasks.append( task )

    def all_finished( self ):
        # return True if all tasks have finished AND abdicated
        #--
        for task in self.tasks:
            if task.is_not_finished() or not task.has_abdicated():
                return False
        return True


    def negotiate_dependencies( self ):
        # run time dependency negotiation: tasks attempt to get their
        # prerequisites satisfied by other tasks' outputs.
        #--
    
        # O(n^2) DIRECT INTERACTION: NO LONGER USED 
        # for task in self.tasks:
        #     task.get_satisfaction( self.tasks )

        # O(n) BROKERED NEGOTIATION

        self.broker.reset()

        # each task registers its outputs
        for task in self.tasks:
            self.broker.register( task.get_fulloutputs() )

        # each task asks the broker to satisfy its prerequisites
        for task in self.tasks:
            task.prerequisites.satisfy_me( self.broker )


    def run_tasks( self, launcher ):
        # tell each task to run if it is ready
        # unless the system is on hold
        #--
        if self.system_hold:
            return

        for task in self.tasks:
                task.run_if_ready( launcher )

    def regenerate_tasks( self ):
        # create new tasks foo(T+1) if foo has not got too far ahead of
        # the slowest task, and if foo(T) abdicates
        #--

        # update oldest system reference time
        oldest_ref_time = self.get_oldest_ref_time()

        for task in self.tasks:

            tdiff = reference_time.decrement( task.ref_time, self.config.get('max_runahead_hours') )
            if int( tdiff ) > int( oldest_ref_time ):
                # too far ahead: don't abdicate this task.
                self.log.debug( task.identity + " delayed: too far ahead" )
                continue

            if task.abdicate():
                task.log.debug( "abdicating " + task.identity )

                # dynamic task object creation by task and module name
                new_task = self.get_task_instance( 'task_classes', task.name )( task.next_ref_time(), 'False', "waiting" )
                if self.config.get('stop_time') and int( new_task.ref_time ) > int( self.config.get('stop_time') ):
                    # we've reached the stop time: delete the new task 
                    new_task.log.warning( new_task.name + " STOPPING at configured stop time " + self.config.get('stop_time') )
                    new_task.prepare_for_death()
                    del new_task
                else:
                    # no stop time, or we haven't reached it yet.
                    self.pyro.connect( new_task, new_task.identity )
                    new_task.log.debug( "New " + new_task.name + " connected for " + new_task.ref_time )
                    self.tasks.append( new_task )

    def dump_state( self ):
        filename = self.config.get('state_dump_file')
        FILE = open( filename, 'w' )
        for task in self.tasks:
            task.dump_state( FILE )
        FILE.close()

    def kill_lame_tasks( self ):
        # Remove any tasks in the OLDEST BATCH whose prerequisites
        # cannot be satisfied by their co-temporal peers.  It's not
        # possible to detect lame tasks in newer batches because 
        # they may not be fully populated yet (more tasks can appear
        # as their predecessors abdicate).

        # This is needed in order to allow us to start the system
        # simply, at a single reference time, even when the configured 
        # task list includes tasks that do not all have the same list
        # of valid reference times at which they can run: some lame
        # tasks may be created initially, and these will abdicate until
        # their first non-lame descendent is generated. 

        # This function removes all lame tasks in the oldest batch
        # before returning. Any lame tasks in the next batch may not be
        # removed immediately during periods when no remote messages are
        # coming in (since that's what activates task processing,
        # including this function). 
        
        # To Do: put an outer loop in this function to repeat the
        # process in the next batch, if the first batch is entirely
        # rejected for being lame.
        #--

        batches = {}
        for task in self.tasks:
           if task.ref_time not in batches.keys():
               batches[ task.ref_time ] = [ task ]
           else:
               batches[ task.ref_time ].append( task )

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
            for task in oldest_batch:
                if task.state != 'waiting':
                    # running, finished, or failed tasks are not lame
                    continue
                # need to attempt satisfaction from all tasks in the
                # batch, not just the potentially lame ones
                if not task.will_get_satisfaction( oldest_batch ):
                    lame_tasks.append( task )
                    no_lame_found = False
    
            if no_lame_found:
                break

            for lame in lame_tasks:
                # abdicate the lame task and create its successor
                if lame.abdicate():
                    lame.log.warning( "ABDICATED A LAME TASK " + lame.identity )

                new_task = self.get_task_instance( 'task_classes', lame.name )( lame.next_ref_time(), 'False', "waiting" )
                new_task.log.debug( "new task connected for " + new_task.ref_time )
                self.pyro.connect( new_task, new_task.identity )
                self.tasks.append( new_task )

                # delete the lame task
                oldest_batch.remove( lame )
                self.tasks.remove( lame )
                self.pyro.disconnect( lame )
                lame.log.debug( "lame task disconnected for " + lame.ref_time )
                lame.prepare_for_death()
                del lame

    def update_finished_task_dict( self ):
        # compile a dict for possible use by task.get_cutoff():
        # finished_task_dict[ name ] = [ list of ref times ] 

        self.finished_task_dict = {}

        for task in self.tasks:

            if task.is_not_finished():
                continue
            if task.name not in self.finished_task_dict.keys():
                self.finished_task_dict[ task.name ] = [ task.ref_time ]
            else:
                self.finished_task_dict[ task.name ].append( task.ref_time )


    def kill_spent_tasks( self ):
        # Delete FINISHED tasks that have ABDICATED already AND:
        # (i) if quick_death is True: are older than all non-finished tasks 
        #   OR
        # (ii) if quick_death is False: are older than the system cutoff time

        # System cutoff time is the oldest task cutoff time.

        # A task's cutoff time is the reference time of the earliest
        # upstream dependency that it has.
        
        # For a waiting task with only cotemporal upstream dependencies
        # the cutoff time is its own reference time.  

        # For a running task with only cotemporal upstream dependencies
        # the cutoff time is the reference time of its immediate
        # successor, i.e. the next instance of that task type. 
        #--

        # list of candidates for deletion
        finished_and_abdicated = []
        # list of ref times of non-finished tasks
        ref_times_not_finished = []
        # list of all task cutoff times
        cutoff_times = []

        self.update_finished_task_dict()
        # compile the above lists
        for task in self.tasks:
            coft = task.get_cutoff( self.finished_task_dict ) 
            if coft:
                cutoff_times.append( coft )
            if task.state == 'waiting' or task.state == 'running':
                ref_times_not_finished.append( task.ref_time )
            if task.state == 'finished' and task.has_abdicated():
                # we don't tag 'failed' tasks for deletion
                finished_and_abdicated.append( task )

        # find reference time of the oldest non-finished task
        all_tasks_finished = True
        if len( ref_times_not_finished ) > 0:
            all_tasks_finished = False
            ref_times_not_finished.sort( key = int )
            oldest_ref_time_not_finished = ref_times_not_finished[0]
            self.log.debug( "oldest non-finished task ref time is " + oldest_ref_time_not_finished )

        # find the system cutoff reference time
        no_cutoff_times = True
        if len( cutoff_times ) > 0:
            no_cutoff_times = False
            cutoff_times.sort( key = int )
            system_cutoff = cutoff_times[0]
            self.log.debug( "task deletion cutoff is " + system_cutoff )

        # find list of tasks to delete
        spent_tasks = []

        for task in finished_and_abdicated:
            if task.quick_death: 
                # case (i) tasks to delete
                if all_tasks_finished or \
                        int( task.ref_time ) < int( oldest_ref_time_not_finished ):
                    spent_tasks.append( task )
            else:
                # case (ii) tasks to delete
                if not no_cutoff_times and \
                        int( task.ref_time ) < int( system_cutoff ):
                    spent_tasks.append( task )

        # delete spent tasks
        for task in spent_tasks:
            self.log.debug( "removing spent " + task.identity )
            self.tasks.remove( task )
            self.pyro.disconnect( task )
            task.prepare_for_death()

        del spent_tasks


    def abdicate_and_kill( self, task_id ):
        # find the task
        found = False
        for t in self.tasks:
            if t.identity == task_id:
                found = True
                task = t
                break

        if not found:
            self.log.warning( "task not found for remote kill request: " + task_id )
            return

        task.log.debug( "suicide by remote request " + task.identity )

        if task.abdicate():
            # task had not abdicated yet; need to create its successor
            task.log.debug( task.identity + " abdicated" )
            # TO DO: the following should reuse code in regenerate_tasks()?
            # dynamic task object creation by task and module name
            new_task = self.get_task_instance( 'task_classes', task.name )( task.next_ref_time(), 'False', "waiting" )
            if self.config.get('stop_time') and int( new_task.ref_time ) > int( self.config.get('stop_time') ):
                # we've reached the stop time: delete the new task 
                new_task.log.warning( new_task.name + " STOPPING at configured stop time " + self.config.get('stop_time') )
                new_task.prepare_for_death()
                del new_task
            else:
                # no stop time, or we haven't reached it yet.
                self.pyro.connect( new_task, new_task.identity )
                new_task.log.debug( "New " + new_task.name + " connected for " + new_task.ref_time )
                self.tasks.append( new_task )

        else:
            task.log.debug( task.identity + " already abdicated" )

        # now kill the task
        self.tasks.remove( task )
        self.pyro.disconnect( task )
        task.prepare_for_death()
        del task
