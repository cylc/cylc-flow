#!/usr/bin/python

import reference_time
import pimp_my_logger
import requisites
import logging
#import pdb
import os
import re

class manager:
    def __init__( self, config, dummy_mode, pyro, restart, clock ):
        
        self.dummy_mode = dummy_mode
        self.pyro = pyro  # pyrex (cyclon Pyro helper) object
        self.log = logging.getLogger( "main" )

        self.stop_time = config.get('stop_time')
 
        self.config = config

        self.system_hold_now = False
        self.system_hold_reftime = None

        # initialise the dependency broker
        self.broker = requisites.broker()
        
        # instantiate the initial task list and create task logs 
        self.tasks = []
        if restart:
            self.load_from_state_dump( clock )
        else:
            self.load_from_config( clock )

    def set_stop_time( self, stop_time ):
        self.log.debug( "Setting new stop time: " + stop_time )
        self.stop_time = stop_time

    def set_system_hold( self, reftime = None ):
        if reftime:
            self.system_hold_reftime = reftime
            self.log.critical( "SETTING SYSTEM HOLD: no new tasks will run from " + reftime )
        else:
            self.system_hold_now = True
            self.log.critical( "SETTING SYSTEM HOLD: no new tasks will run FROM NOW")

    def unset_system_hold( self ):
        self.log.critical( "UNSETTING SYSTEM HOLD: new tasks will run when ready")
        self.system_hold_now = False
        self.system_hold_reftime = None

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

    def load_from_config ( self, clock ):
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
            pimp_my_logger.pimp_it( log, name, self.config, self.dummy_mode, clock )

            # the initial task reference time can be altered during
            # creation, so we have to create the task before
            # checking if stop time has been reached.
            skip = False
            if self.stop_time:
                if int( itask.ref_time ) > int( self.stop_time ):
                    itask.log( 'WARNING', "STOPPING at " + self.stop_time )
                    itask.prepare_for_death()
                    del itask
                    skip = True

            if not skip:
                itask.log( 'DEBUG', "connected" )
                self.pyro.connect( itask, itask.identity )
                self.tasks.append( itask )


    def load_from_state_dump( self, clock ):
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
                pimp_my_logger.pimp_it( log, name, self.config, self.dummy_mode, clock )
                log_created[ name ] = True
 
            # the initial task reference time can be altered during
            # creation, so we have to create the task before
            # checking if stop time has been reached.
            skip = False
            if self.stop_time:
                if int( itask.ref_time ) > int( self.stop_time ):
                    itask.log( 'WARNING', " STOPPING at " + self.stop_time )
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
        # self.broker.dump()

        for itask in self.tasks:
            # get the broker to satisfy tasks prerequisites
            self.broker.negotiate( itask.prerequisites )

    def run_tasks( self, launcher, clock ):
        # tell each task to run if it is ready
        # unless the system is on hold
        #--
        if self.system_hold_now:
            # general system hold
            self.log.debug( 'not asking any tasks to run (general system hold in place)' )
            return

        for itask in self.tasks:
                if self.system_hold_reftime:
                    if int( itask.ref_time ) >= int( self.system_hold_reftime ):
                        self.log.debug( 'not asking ' + itask.identity + ' to run (' + self.system_hold_reftime + ' hold in place)' )
                        continue

                itask.run_if_ready( launcher, clock )

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
                if self.stop_time and int( new_task.ref_time ) > int( self.stop_time ):
                    # we've reached the stop time: delete the new task 
                    new_task.log( 'WARNING', "STOPPING at configured stop time " + self.stop_time )
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


    def kill_spent_tasks( self ):
        # Delete tasks that are no longer needed, 
        # i.e. tasks that:
        
        # 1/ have finished and abdicated, 
        #  AND
        # 2/ are no longer needed to satisfy prerequisites.

        # Tasks with 'quick_death = True' are relatively easy. By
        # definition they have only cotemporal downstream dependents, so
        # they are no longer needed to satisfy prerequisites once all
        # their cotemporal peers have finished. The only complication is
        # that new cotemporal peers can appear, in principle, so long as
        # there are unabdicated tasks with earlier reference times.
        # Therefore, finished-and-abdicated quick death tasks can be
        # deleted IF there are no earlier unabdicated tasks AND all
        # their cotemporal peers are finished.

        # For the general case we can compute a generic 'system cutoff'
        # reference time that does not violate requirement 2 as follows:

        # No finished-and-abdicated task that is later than the earliest
        # unsatisfied task can be deleted yet because it may still be
        # needed to satisfy new tasks that may appear when earlier (but
        # currently unsatisfied) tasks abdicate. Therefore only
        # finished-and-abdicated tasks that are earlier than the
        # earliest unsatisfied task are candidates for deletion. Of
        # these, we need to keep one finished task of each type (i.e.
        # all possible "satisfiers"). TO DO: EXPLAIN WHY NO EARLIER TASK
        # COULD BE DEPENDED UPON?
        #--

        # list of candidates for deletion 
        # (done => finished and abdicated)
        done = []
        # list of tasks to actually delete 
        spent = []

        # ref time of earliest unabdicated task
        earliest_unabdicated = None

        all_satisfied = True
        # ref time of earliest unsatisfied task
        earliest_unsatisfied = None

        # done task names in ref time batches
        batch = {}

        all_abdicated = True
        for itask in self.tasks:
            # loop through all tasks

            if itask.done():
                # this task is a candidate for deletion
                done.append( itask )

                # compile batched names of done tasks
                rt = itask.ref_time
                name = itask.name
                if rt not in batch.keys():
                    batch[ rt ] = [ name ]
                else:
                    if name not in batch[ rt ]:
                        batch[ rt ].append( name )

            if not itask.abdicated:
                # is this the earliest unabdicated so far? 
                all_abdicated = False
                if not earliest_unabdicated:
                    earliest_unabdicated = itask.ref_time
                elif int( itask.ref_time ) < int( earliest_unabdicated ):
                    earliest_unabdicated = itask.ref_time

            if not itask.prerequisites.all_satisfied():
                # is this the earliest unsatisfied so far? 
                all_satisfied = False
                if not earliest_unsatisfied:
                    earliest_unsatisfied = itask.ref_time
                elif int( itask.ref_time ) < int( earliest_unsatisfied ):
                    earliest_unsatisfied = itask.ref_time

        seen = {}
        cutoff = None
        # get a descending list of done task ref times
        reftimes = batch.keys()
        reftimes.sort( key = int, reverse = True )
        
        for rt in reftimes:
            # loop through all ref times of done tasks

            if not all_satisfied:
                if int( rt ) >= int( earliest_unsatisfied ):
                    # can't delete any past the earliest unsatisfied
                    continue
            
            # now we're earlier than the earliest unsatisfied task
            # so continue until we've found a done instance of each task
            for name in batch[ rt ]:
                seen[ name ] = True
            
            seen_all = True
            for itask in self.tasks:
                # check if any task type has not been seen yet
                if itask.quick_death:
                    continue
                if itask.name not in seen.keys():
                    seen_all = False
                    break

            if seen_all:
                # here's the cutoff
                cutoff = rt
                break
             
        if cutoff:
            self.log.debug( "spent task cutoff: " + cutoff )
        else:
            self.log.debug( "no spent task cutoff" )

        if not all_satisfied:
            self.log.debug( "earliest unsatisfied: " + earliest_unsatisfied )
        else:
            self.log.debug( "all tasks satisfied" )
            
        if not all_abdicated:
            self.log.debug( "earliest unabdicated: " + earliest_unabdicated )
        else:
            self.log.debug( "all tasks abdicated")

        # now compile the list of tasks to delete
        for itask in done:
            # loop through all candidates for deletion

            if itask.quick_death: 
                # quick death tasks
                if all_abdicated or int( itask.ref_time ) < int( earliest_unabdicated ):
                    spent.append( itask )
            else:
                # general case
                if cutoff:
                    if int( itask.ref_time ) < int( cutoff ):
                        spent.append( itask )

        # now delete the spent tasks
        for itask in spent:
            self.tasks.remove( itask )
            self.pyro.disconnect( itask )
            itask.log( 'NORMAL', "disconnected (spent)" )
            itask.prepare_for_death()

        del spent

    def insert_task( self, task_id, clock ):
        # insert a new task in a waiting state

        [ name, ref_time ] = task_id.split( '%' )
        abdicated = False
        state_list = [ 'waiting' ]

        # instantiate the task object
        itask = self.get_task_instance( 'task_classes', name )( ref_time, abdicated, *state_list )

        if itask.instance_count == 1:
            # first task of its type, so create the log
            log = logging.getLogger( 'main.' + name )
            pimp_my_logger.pimp_it( log, name, self.config, clock )
 
        # the initial task reference time can be altered during
        # creation, so we have to create the task before
        # checking if stop time has been reached.
        skip = False
        if self.stop_time:
            if int( itask.ref_time ) > int( self.stop_time ):
                itask.log( 'WARNING', " STOPPING at " + self.stop_time )
                itask.prepare_for_death()
                del itask
                skip = True

        if not skip:
            itask.log( 'DEBUG', "connected" )
            self.pyro.connect( itask, itask.identity )
            self.tasks.append( itask )


    def dump_task_requisites( self, task_ids ):
        for id in task_ids.keys():
            # find the task
            found = False
            itask = None
            for t in self.tasks:
                if t.identity == id:
                    found = True
                    itask = t
                    break

            if not found:
                self.log.warning( 'task not found for remote requisite dump request: ' + id )
                return

            itask.log( 'DEBUG', 'dumping requisites to stdout, by remote request' )

            print
            print 'PREREQUISITE DUMP', itask.identity 
            itask.prerequisites.dump()
            print
            print 'OUTPUT DUMP', itask.identity 
            itask.outputs.dump()
            print
 
    def abdicate_and_kill( self, task_ids ):
        for id in task_ids.keys():
            # find the task
            found = False
            itask = None
            for t in self.tasks:
                if t.identity == id:
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
                if self.stop_time and int( new_task.ref_time ) > int( self.stop_time ):
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
