#!/usr/bin/python

from get_instance import *
import config
import pimp_my_logger
import pyro_ns_naming
import Pyro.core, Pyro.naming
from Pyro.errors import NamingError
import logging
import os, re

class manager ( Pyro.core.ObjBase ):
    def __init__( self, pyro_d, reload, dummy_clock ):

        self.log = logging.getLogger( "main" )
        Pyro.core.ObjBase.__init__(self)
        
        self.tasks = []

        self.pyro_daemon = pyro_d
        self.start_time = config.start_time
        self.stop_time = config.stop_time

        self.state_dump_file = config.state_dump_file
        if re.compile( "/" ).search( self.state_dump_file ):
            dir = os.path.dirname( self.state_dump_file )
            if not os.path.exists( dir ):
                os.makedirs( dir )

        task_config = {}
        if reload:
            print
            print 'Loading state from ' + config.state_dump_file
            self.log.info( 'Loading state from ' + config.state_dump_file )
            task_config = self.reload_state()

        else:
            print
            print 'Initial reference time ' + config.start_time
            self.log.info( 'initial reference time ' + config.start_time )

            # initialise from configured task name list
            ref_time = config.start_time
            for item in config.task_list:
                state = 'waiting'
                name = item
                if re.compile( "^.*:").match( item ):
                    [name, state] = item.split(':')

                if ref_time not in task_config.keys():
                    task_config[ ref_time  ] = [ [ name, state ] ]
                else:
                    task_config[ ref_time  ].append( [ name, state ] )

        if config.stop_time:
            print 'Final reference time ' + config.stop_time
            self.log.info( 'final reference time ' + config.stop_time )
       
        # task loggers that propagate messages up to the main logger
        seen = {}
        ref_times = task_config.keys()
        for ref_time in ref_times:
            for item in task_config[ ref_time ]:
                [name, state] = item
                if name not in seen.keys():
                    seen[ name ] = True
 
        for name in seen.keys():
            log = logging.getLogger( 'main.' + name )
            pimp_my_logger.pimp_it( log, name, dummy_clock )

        # create initial tasks
        ref_times.sort( key = int, reverse = True )
        seen = {}
        for ref_time in ref_times:
            for item in task_config[ ref_time ]:
                [name, state] = item
                abdicate = False
                if name not in seen.keys():
                    seen[ name ] = True
                elif state == 'finished':
                    # finished task, but already seen at a later
                    # reference time => already abdicated
                    abdicate = True
                    
                self._create_task( name, ref_time, abdicate, state )

    def dump_state( self ):
        # I considered using python 'pickle' to dump and read a state
        # object, but we need a trivially human-editable file format.

        FILE = open( self.state_dump_file, 'w' )

        task_config = {}
        for task in self.tasks:
            ref_time = task.ref_time
            item = task.name + ":" + task.state
            if ref_time in task_config.keys():
                task_config[ ref_time ].append( item )
            else:
                task_config[ ref_time ] = [ item ]

        ref_times = task_config.keys()
        ref_times.sort( key = int )
        for rt in ref_times:
            FILE.write( rt )
            for entry in task_config[ rt ]:
                FILE.write( ' ' + entry )

            FILE.write( '\n' )

        FILE.close()


    def reload_state( self ):
        FILE = open( self.state_dump_file, 'r' )
        lines = FILE.readlines()
        FILE.close()

        task_config = {}
        for line in lines:
            # ref_time task:state task:state ...
            if re.compile( '^.*\n$' ).match( line ):
                # strip trailing newlines
                line = line[:-1]

            tokens = line.split(' ')
            ref_time = tokens[0]
            for item in tokens[1:]:
                [name, state] = item.split(':')
                # convert running to waiting on restart
                if state == 'running':
                    state = 'waiting'
                if ref_time in task_config.keys():
                    task_config[ ref_time ].append( [name, state] )
                else:
                    task_config[ ref_time ] = [[name, state]] 

        return task_config


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

    def _create_task( self, task_name, ref_time, abdicate, state = "waiting" ):
        # dynamic task object creation by task and module name
        task = get_instance( 'task_definitions', task_name )( ref_time, state )
        if abdicate:
            if state == 'finished':
                task.abdicate()

        # the initial task reference time can be altered during
        # creation, so we have to create the task before checking if
        # stop time has been reached.
        if self.stop_time:
            if int( task.ref_time ) > int( self.stop_time ):
                task.log.info( task.name + " STOPPING at " + self.stop_time )
                del task
                return

        task.log.info( "New task created for " + task.ref_time )
        self.tasks.append( task )
        self.pyro_daemon.connect( task, pyro_ns_naming.name( task.identity ) )

    def create_tasks( self ):
        # create new task(T+1) if task(T) has abdicated
        for task in self.tasks:
            if task.abdicate():
                task.log.debug( "abdicating " + task.identity )
                self._create_task( task.name, task.next_ref_time(), False )

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
            self._create_task( task.name, task.next_ref_time(), False )
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
