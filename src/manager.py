#!/usr/bin/python

"""
The task manager maintains a pool of task objects, decides when to
create and destroy tasks, and provides methods for getting them to
interact, etc.
"""

from instantiate import get_instance
import pimp_my_logger
import datetime
import logging
import shutil
import broker
import re

class manager:
    def __init__( self, config, pyro, restart, dummy_clock ):
        
        self.pyro = pyro  # pyrex (sequenz Pyro helper) object
        self.log = logging.getLogger( "main" )

        if config.get('use_broker'):
            self.broker = broker.broker()
        
        self.tasks = []

        # state_list = [ref_time:name:state, ...]
        if restart:
            state_list = self.states_from_dump( config )
        else:
            state_list = self.states_from_config( config )

        self.create_task_logs( state_list, config, dummy_clock)
        self.create_initial_tasks( state_list, config )


    def create_task_logs( self, state_list, config, dummy_clock ):
        # task loggers that propagate messages up to the main logger
        #--
        print "CREATING TASK LOGS......"
        unique_task_names = {}
        for item in state_list:
            [ref_time, name, state] = item.split(':')
            unique_task_names[ name ] = True
    
        for task_name in unique_task_names.keys():
            log = logging.getLogger( 'main.' + task_name )
            pimp_my_logger.pimp_it( log, task_name, config, dummy_clock )
 

    def states_from_config ( self, config ):
        # use configured task list and start time
        #--
        print '\nCLEAN START: INITIAL STATE FROM CONFIGURED TASK LIST\n'
        self.log.info( 'Loading state from configured task list' )
        # config.task_list = [ taskname(:state), taskname(:state), ...]
        # where (:state) is optional and defaults to 'waiting'.

        state_list = []
        for item in config.get('task_list'):
            state = 'waiting'
            name = item
            if re.compile( "^.*:").match( item ):
                [name, state] = item.split(':')

            state_list.append( config.get('start_time') + ':' + name + ':' + state )

        return state_list


    def states_from_dump( self, config ):
        # restart from the state dump file
        #--
        filename = config.get('state_dump_file')
        backup = filename + '.' + datetime.datetime.now().isoformat()
        print '\nRESTART: INITIAL STATE FROM STATE DUMP: ' + filename
        print ' backing up the initial state dump file to ' + backup
        shutil.copyfile( filename, backup )

        self.log.info( 'Loading previous state from ' + filename )
        # file format: ref_time:name:state, one per line 

        FILE = open( filename, 'r' )
        lines = FILE.readlines()
        FILE.close()

        state_list = []

        for line in lines:
            # ref_time task:state task:state ...
            if re.compile( '^.*\n$' ).match( line ):
                # strip trailing newlines
                line = line[:-1]

            [ref_time, name, state] = line.split(':')
            # convert running to waiting on restart
            if state == 'running' or state == 'failed':
                state = 'waiting'

            state_list.append( ref_time + ':' + name + ':' + state )

        return state_list


    def create_initial_tasks( self, state_list, config ):

        state_by_reftime = {}

        for item in state_list:
            [ref_time, name, state] = item.split(':')
            if ref_time not in state_by_reftime.keys():
                state_by_reftime[ ref_time ] = [item]
            else:
                state_by_reftime[ ref_time ].append( item )
 
        # reverse sorted list of reference times
        ref_times = state_by_reftime.keys()
        ref_times.sort( key = int, reverse = True )

        self.tasks = []
        seen = {}
        for ref_time in ref_times:
            for item in state_by_reftime[ ref_time ]:
                # Create each task in reverse sorted reference time
                # order. Abdicate all but the last task of each type.
                # This correctly handles waiting and running tasks that
                # have not abdicated AND finished tasks that have not 
                # abdicated yet (parallel tasks that have been delayed
                # by the number-of-instances restriction).
                [ref_time, name, state] = item.split(':')
                task = get_instance( 'task_classes', name )( ref_time, state )
                if name not in seen.keys():
                    seen[ name ] = True
                else:
                    # an instance of this task was already seen at a
                    # later reference time, therefore it has abdicated
                    task.set_abdicated()

                # the initial task reference time can be altered during
                # creation, so we have to create the task before
                # checking if stop time has been reached.
                skip = False
                if config.get('stop_time'):
                    if int( task.ref_time ) > int( self.stop_time ):
                        task.log.info( task.name + " STOPPING at " + self.stop_time )
                        task.prepare_for_death()
                        del task
                        skip = True

                if not skip:
                    task.log.debug( "new " + task.name + " connected for " + task.ref_time )
                    self.pyro.connect( task, task.identity )
                    self.tasks.append( task )

    def all_finished( self ):
        # return True if all tasks have completed
        #--
        for task in self.tasks:
            if task.is_not_finished():
                return False
        return True


    def negotiate_dependencies( self, config ):
        # run time dependency negotiation: tasks attempt to get their
        # prerequisites satisfied by other tasks' postrequisites.
        #--
        if config.get('use_broker'):
            self.negotiate_via_broker()
        else:
            self.direct_interaction()


    def direct_interaction( self ):
        # each task asks the others to satisfy its prerequisites
        #--
        for task in self.tasks:
            task.get_satisfaction( self.tasks )

    def negotiate_via_broker( self ):
        # each task registers its postrequisites with the broker
        #--
        for task in self.tasks:
            self.broker.register( task.get_fullpostrequisites() )

        # each task asks the broker to satisfy its prerequisites
        for task in self.tasks:
            task.prerequisites.satisfy_me( self.broker.get_requisites() )

    def run_tasks( self, launcher ):
        for task in self.tasks:
                task.run_if_ready( launcher )

    def regenerate_tasks( self, config ):
        # create new task(T+1) if task(T) has abdicated
        #--
        for task in self.tasks:
            if task.abdicate():
                task.log.debug( "abdicating " + task.identity )
                # dynamic task object creation by task and module name
                new_task = get_instance( 'task_classes', task.name )( task.next_ref_time(), "waiting" )
                if config.get('stop_time') and int( new_task.ref_time ) > int( config.get('stop_time') ):
                    # we've reached the stop time: delete the new task 
                    new_task.log.info( new_task.name + " STOPPING at configured stop time " + config.get('stop_time') )
                    new_task.prepare_for_death()
                    del new_task
                else:
                    # no stop time, or we haven't reached it yet.
                    self.pyro.connect( new_task, new_task.identity )
                    new_task.log.debug( "New " + new_task.name + " connected for " + new_task.ref_time )
                    self.tasks.append( new_task )

    def dump_state( self, config ):
        dir( config )
        filename = config.get('state_dump_file')
        FILE = open( filename, 'w' )
        for task in self.tasks:
            task.dump_state( FILE )
        FILE.close()

    def kill_lame_tasks( self, config ):
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
                lame.log.warning( "ABDICATING A LAME TASK " + lame.identity )
                new_task = get_instance( 'task_classes', lame.name )( lame.next_ref_time(), "waiting" )
                new_task.log.debug( "new task connected for " + new_task.ref_time )
                self.pyro.connect( new_task, new_task.identity )
                self.tasks.append( new_task )

                # delete the lame task
                oldest_batch.remove( lame )
                self.tasks.remove( lame )
                self.pyro.disconnect( lame )
                lame.log.debug( "lame task disconnected for " + lame.ref_time )
                if config.get('use_broker'):
                    self.broker.unregister( lame.get_fullpostrequisites() )
                lame.prepare_for_death()
                del lame


    def kill_spent_tasks( self, config ):
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
        # compile the above lists
        for task in self.tasks:
            cutoff_times.append( task.get_cutoff() )
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
            if config.get('use_broker'):
                self.broker.unregister( task.get_fullpostrequisites() )
            task.prepare_for_death()

        del spent_tasks
