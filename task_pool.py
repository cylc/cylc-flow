#!/usr/bin/python

import config
from get_instance import *
from pyro_ns_naming import *
import Pyro.core, Pyro.naming
from Pyro.errors import NamingError
import logging
import os, re

class task_pool ( Pyro.core.ObjBase ):
    
    def __init__( self, task_names, pyrod ):

        self.log = logging.getLogger( "main" )
        self.log.debug( "Initialising Task Pool" )
        Pyro.core.ObjBase.__init__(self)

        self.task_names = task_names
        self.tasks = []

        self.pyro_daemon = pyrod

        self.state_dump_dir = 'STATE'
        if not os.path.exists( self.state_dump_dir ):
            os.makedirs( self.state_dump_dir )

        # create initial set of tasks
        for task_name in self.task_names:
            state = None
            if re.compile( "^.*:").match( task_name ):
                [task_name, state] = task_name.split(':')

            self._create_task( task_name, config.start_time, state )

    def all_finished( self ):
        # return True if all tasks have completed
        for task in self.tasks:
            if task.is_running():
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

    def _create_task( self, task_name, ref_time, state = "waiting" ):
        # dynamic task object creation by task and module name
        task = get_instance( 'task_definitions', task_name )( ref_time, state )

        # the initial task reference time can be altered during
        # creation, so we have to create the task before checking if
        # stop time has been reached.
        if config.stop_time:
            if int( task.ref_time ) > int( config.stop_time ):
                task.log.info( task.name + " STOPPING at " + config.stop_time )
                del task
                return

        task.log.info( "New task created for " + task.ref_time )
        self.tasks.append( task )
        self.pyro_daemon.connect( task, pyro_ns_name( task.identity ) )

    def spawn_new_tasks( self ):
        # create new task(T+1) if task(T) has abdicated
        for task in self.tasks:
            if task.abdicate():
                task.log.debug( "abdicating " + task.identity )
                self._create_task( task.name, task.next_ref_time() )

    def kill_lame_ducks( self ):
        # Remove any tasks in the OLDEST BATCH whose prerequisites
        # cannot be satisfied by their co-temporal peers.  It's not
        # possible to detect lame ducks in newer batches because 
        # the batch may not be fully populated yet(more tasks may appear
        # as their predecessors abdicate).

        # This is needed because, for example, if we start the system at
        # 12Z with topnet turned on, topnet is valid at every hour from 
        # 12 through 17Z, so those tasks will be created but they will 
        # never be able to run due to lack of any upstream nzlam_post
        # task until 18Z comes along.

        # LAME DUCKS ARE REMOVED IN THE TASK PROCESSING LOOP SO THEY 
        # WON'T GET ELIMINATED IMMEDIATELY IF NO REMOTE MESSAGES ARE
        # COMING IN ... when a new message does come in for any task 
        # it will cause the pyro request handling loop to return and
        # and thereby allow another round of task processing.

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
    
        for task in lame_ducks:
            task.log.info( "abdicating a lame duck " + task.identity )
            self._create_task( task.name, task.next_ref_time() )
            self.tasks.remove( task )
            self.pyro_daemon.disconnect( task )

            del task

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

    def dump_state( self ):
        # TO DO: implement restart from dumped state capability 
        # Also, consider:
        #  (i) using 'pickle' to dump and read state, or
        #  (ii) writing a python source file similar to current startup config

        config = {}
        for task in self.tasks:
            ref_time = task.ref_time
            state = task.name + ":" + task.state
            if ref_time in config.keys():
                config[ ref_time ].append( state )
            else:
                config[ ref_time ] = [ state ]

        FILE = open( self.state_dump_dir + '/state', 'w' )

        ref_times = config.keys()
        ref_times.sort( key = int )
        for rt in ref_times:
            FILE.write( rt + ' ' )
            for entry in config[ rt ]:
                FILE.write( entry + ' ' )

            FILE.write( '\n' )

        FILE.close()

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


