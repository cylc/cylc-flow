#!/usr/bin/python

"""
The task manager maintains a pool of task objects, decides when to
create and destroy tasks, and provides methods for getting them to
interact, etc.
"""

import instantiation
import system_state
import config
import pimp_my_logger
import pyro_ns_naming
import Pyro.core, Pyro.naming
from Pyro.errors import NamingError
import logging

class manager ( Pyro.core.ObjBase ):
    def __init__( self, pyro_d, reload, dummy_clock ):
        
        Pyro.core.ObjBase.__init__(self)
        self.pyro_daemon = pyro_d

        # get a reference to the main log
        self.log = logging.getLogger( "main" )
        
        # start and stop times, from config file
        self.start_time = config.start_time
        self.stop_time = config.stop_time

        # initialise the task list
        if reload:
            # reload from the state dump file
            print
            print 'Loading state from ' + config.state_dump_file
            print
            self.log.info( 'Loading state from ' + config.state_dump_file )
            self.system_state = system_state.state_from_dump( config.state_dump_file, config.start_time, config.stop_time )

        else:
            # use configured task list and start time
            print
            print 'Initial reference time ' + config.start_time
            print
            self.log.info( 'initial reference time ' + config.start_time )
            self.system_state = system_state.state_from_list( config.state_dump_file, config.task_list, config.start_time, config.stop_time )

        if config.stop_time:
            print 'Final reference time ' + config.stop_time
            self.log.info( 'final reference time ' + config.stop_time )
       
        # task loggers that propagate messages up to the main logger
        for name in self.system_state.get_unique_taskname_list():
            log = logging.getLogger( 'main.' + name )
            pimp_my_logger.pimp_it( log, name, dummy_clock )

        # initialise the task list
        self.tasks = self.system_state.create_tasks()
        for task in self.tasks:
            self.pyro_daemon.connect( task, pyro_ns_naming.name( task.identity ) )

    def all_finished( self ):
        # return True if all tasks have completed
        for task in self.tasks:
            if task.is_not_finished():
                return False
        return True

    def interact( self ):
        # each task asks the others, can you satisfy my prerequisites?
        for task in self.tasks:
            task.get_satisfaction( self.tasks )

    def run_if_ready( self ):
        # tell tasks to run if their prequisites are satisfied
        for task in self.tasks:
            task.run_if_ready( self.tasks )

    def regenerate( self ):
        # create new task(T+1) if task(T) has abdicated
        for task in self.tasks:
            if task.abdicate():
                task.log.debug( "abdicating " + task.identity )
                # dynamic task object creation by task and module name
                new_task = instantiation.get_by_name( 'task_classes', task.name )( task.next_ref_time(), "waiting" )
                if config.stop_time:
                    if int( new_task.ref_time ) <= int( config.stop_time ):
                        new_task.log.info( "New task created for " + new_task.ref_time )
                        self.pyro_daemon.connect( new_task, pyro_ns_naming.name( new_task.identity ) )
                        self.tasks.append( new_task )
                    else:
                        new_task.log.warning( new_task.name + " STOPPING at configured stop time " + config.stop_time )
                        del new_task

    def dump_state( self ):
        self.system_state.update( self.tasks )
        self.system_state.dump()

    def kill_lame_ducks( self ):
        # Remove any tasks in the OLDEST BATCH whose prerequisites
        # cannot be satisfied by their co-temporal peers.  It's not
        # possible to detect lame ducks in newer batches because 
        # they may not be fully populated yet (more tasks can appear
        # as their predecessors abdicate).

        # This is needed because, for example, if we start the system at
        # 12Z with topnet turned on, topnet is valid at every hour from 
        # 12 through 17Z, so those tasks will be created but they will 
        # never be able to run due to lack of any upstream nzlam_post
        # task until 18Z comes along.

        # Note that as lame ducks are removed in the task processing
        # loop they won't get eliminated immediately during periods when
        # no remote messages are coming in at the time (incoming task
        # messages are what activates the task processing loop).

        batches = {}
        for task in self.tasks:
            if task.ref_time not in batches.keys():
                batches[ task.ref_time ] = [ task ]
            else:
                batches[ task.ref_time ].append( task )

        reftimes = batches.keys()
        reftimes.sort( key = int )
        oldest_rt = reftimes[0]

        lame_ducks = []
        for task in batches[ oldest_rt ]:
            if not task.will_get_satisfaction( batches[ oldest_rt ] ):
                lame_ducks.append( task )
    
        for lame in lame_ducks:
            lame.log.info( "abdicating a lame duck " + task.identity )

            # dynamic task object creation by task and module name
            new_task = instantiation.get_by_name( 'task_classes', lame.name )( lame.next_ref_time(), "waiting" )
            new_task.log.info( "New task created for " + new_task.ref_time )
            self.pyro_daemon.connect( new_task, pyro_ns_naming.name( new_task.identity ) )
            self.tasks.append( new_task )

            self.tasks.remove( lame )
            self.pyro_daemon.disconnect( lame )
            del lame

    def kill_spent_tasks( self ):
        # DELETE tasks that are finished AND no longer needed to satisfy
        # the prerequisites of other waiting tasks.
        batch_finished = []
        cutoff_times = []
        for task in self.tasks:   
            if task.state != 'finished':
                cutoff_times.append( task.get_cutoff( self.tasks ))
            # which ref_time batches are all finished
            if task.ref_time not in batch_finished:
                batch_finished.append( task.ref_time )

        if len( cutoff_times ) == 0:
            # no tasks to delete (is this possible?)
            return

        cutoff_times.sort( key = int )
        cutoff = cutoff_times[0]

        self.log.debug( "task deletion cutoff is " + cutoff )

        remove_these = []
        for rt in batch_finished:
            if int( rt ) < int( cutoff ):
                self.log.debug( "REMOVING BATCH " + rt )
                for task in self.tasks:
                    if task.ref_time == rt:
                        remove_these.append( task )

        if len( remove_these ) > 0:
            for task in remove_these:
                self.log.debug( "removing spent " + task.identity )
                self.tasks.remove( task )
                self.pyro_daemon.disconnect( task )

            del remove_these


    def get_state_summary( self ):
        summary = {}
        for task in self.tasks:
            postreqs = task.get_postrequisites()
            n_total = len( postreqs )
            n_satisfied = 0
            for key in postreqs.keys():
                if postreqs[ key ]:
                    n_satisfied += 1

            summary[ task.identity ] = [ task.state, str( n_satisfied), str(n_total), task.latest_message ]

        return summary
