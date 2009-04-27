#!/usr/bin/python

"""
The task manager maintains a pool of task objects, decides when to
create and destroy tasks, and provides methods for getting them to
interact, etc.
"""

import instantiation
import job_submit
import pimp_my_logger
import pyro_ns_naming
import Pyro.core, Pyro.naming
from Pyro.errors import NamingError
import logging
import broker
import re

class manager ( Pyro.core.ObjBase ):
    def __init__( self, config, pyro_d, reload, dummy_clock ):
        
        Pyro.core.ObjBase.__init__(self)
        self.pyro_daemon = pyro_d

        self.launcher = job_submit.job_submit( config )

        # get a reference to the main log
        self.log = logging.getLogger( "main" )

        self.config = config
        self.dummy_clock = dummy_clock

        if config.get('use_broker'):
            self.broker = broker.broker()
        
        # initialise the list of tasks
        # state_list = [ref_time:name:state, ...]
        if reload:
            # reload from the state dump file
            print
            print 'Loading state from ' + config.get('state_dump_file')
            print
            self.log.info( 'Loading state from ' + config.get('state_dump_file') )
            state_list = self.load_from_dump( config.get('state_dump_file') )

        else:
            # use configured task list and start time
            print
            print 'Loading configured task list'
            print
            self.log.info( 'Loading configured task list' )
            state_list = self.load_from_config( config )

        self.create_task_logs( state_list )

        self.tasks = self.create_tasks( state_list )
        for task in self.tasks:
            self.pyro_daemon.connect( task, pyro_ns_naming.name( task.identity, config.get('pyro_ns_group') ) )


    def create_task_logs( self, state_list ):
        # task loggers that propagate messages up to the main logger
        unique_task_names = {}
        for item in state_list:
            [ref_time, name, state] = item.split(':')
            unique_task_names[ name ] = True
    
        for task_name in unique_task_names.keys():
            log = logging.getLogger( 'main.' + task_name )
            pimp_my_logger.pimp_it( log, task_name, self.config, self.dummy_clock )
 

    def load_from_config ( self, config ):
        # config.task_list = [ taskname(:state), taskname(:state), ...]
        # where (:state) is optional and defaults to 'waiting'.

        state_list = []
        for item in config.get('task_list'):
            state = 'waiting'
            name = item
            if re.compile( "^.*:").match( item ):
                [name, state] = item.split(':')

            state_list.append( self.config.get('start_time') + ':' + name + ':' + state )

        return state_list


    def load_from_dump( self, filename ):
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


    def create_tasks( self, state_list ):

        state_by_reftime = {}

        for item in state_list:
            [ref_time, name, state] = item.split(':')
            if ref_time not in state_by_reftime.keys():
                state_by_reftime[ ref_time ] = [item]
            else:
                state_by_reftime[ ref_time ].append( item )
 
        ref_times = state_by_reftime.keys()
        ref_times.sort( key = int, reverse = True )

        tasks = []
        seen = {}
        for ref_time in ref_times:
            for item in state_by_reftime[ ref_time ]:
                [ref_time, name, state] = item.split(':')
                # dynamic task object creation by task and module name
                task = instantiation.get_by_name( 'task_classes', name )( ref_time, state, self.launcher )
                if name not in seen.keys():
                    seen[ name ] = True
                elif state == 'finished':
                    # finished but already seen at a later
                    # reference time => already abdicated
                    task.abdicate()

                # the initial task reference time can be altered during
                # creation, so we have to create the task before
                # checking if stop time has been reached.
                skip = False
                if self.config.get('stop_time'):
                    if int( task.ref_time ) > int( self.stop_time ):
                        task.log.info( task.name + " STOPPING at " + self.stop_time )
                        del task
                        skip = True

                if not skip:
                    task.log.debug( "New task connected for " + task.ref_time )
                    tasks.append( task )
                    
        return tasks


    def all_finished( self ):
        # return True if all tasks have completed
        for task in self.tasks:
            if task.is_not_finished():
                return False
        return True

    def interact( self ):
        # get each task to ask all the others if 
        # they can satisfy its prerequisites
        #--
        for task in self.tasks:
            task.get_satisfaction( self.tasks )

    def negotiate( self ):
        # each task registers its postrequisites with the broker
        for task in self.tasks:
            self.broker.register( task.get_fullpostrequisites() )

        # each task asks the broker to satisfy its prerequisites
        for task in self.tasks:
            task.prerequisites.satisfy_me( self.broker.get_requisites() )

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
                new_task = instantiation.get_by_name( 'task_classes', task.name )( task.next_ref_time(), "waiting", self.launcher )
                if self.config.get('stop_time') and int( new_task.ref_time ) > int( self.config.get('stop_time') ):
                    # we've reached the stop time: delete the new task 
                    new_task.log.info( new_task.name + " STOPPING at configured stop time " + self.config.get('stop_time') )
                    del new_task
                else:
                    # no stop time, or we haven't reached it yet.
                    self.pyro_daemon.connect( new_task, pyro_ns_naming.name( new_task.identity, self.config.get('pyro_ns_group') ) )
                    new_task.log.debug( "New " + new_task.name + " connected for " + new_task.ref_time )
                    self.tasks.append( new_task )

    def dump_state( self ):
        filename = self.config.get( 'state_dump_file' )
        FILE = open( filename, 'w' )
        for task in self.tasks:
            task.dump_state( FILE )

        FILE.close()

    def kill_lame_ducks( self ):
        # Remove any tasks in the OLDEST BATCH whose prerequisites
        # cannot be satisfied by their co-temporal peers.  It's not
        # possible to detect lame ducks in newer batches because 
        # they may not be fully populated yet (more tasks can appear
        # as their predecessors abdicate).

        # This is needed because, for example, if we start the system at
        # 12Z with topnet turned on, topnet is valid at every hour from 
        # 12 through 17Z, so those tasks will be created but they will 
        # never be able to run due to lack of any upstream
        # nzlam_06_18_post until 18Z comes along.

        # Note that lame ducks won't be eliminated immediately during
        # periods when no remote messages are coming in (since that's
        # what activates task processing, including this function). If
        # this is ever a problem though, we could decide to kill lame
        # ducks on temporary handleRequests() timeouts as well, OR set
        # task_base.state_changed in this function, whenever any lame
        # ducks are detected.

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
            lame.log.warning( "ABDICATING A LAME TASK " + lame.identity )

            # dynamic task object creation by task and module name
            new_task = instantiation.get_by_name( 'task_classes', lame.name )( lame.next_ref_time(), "waiting", self.launcher )
            new_task.log.debug( "New task connected for " + new_task.ref_time )
            self.pyro_daemon.connect( new_task, pyro_ns_naming.name( new_task.identity, self.config.get('pyro_ns_group') ) )
            self.tasks.append( new_task )

            self.tasks.remove( lame )
            self.pyro_daemon.disconnect( lame )
            lame.log.debug( "lame task disconnected for " + lame.ref_time )
            if self.config.get('use_broker'):
                self.broker.unregister( lame.get_fullpostrequisites() )

            del lame

    def kill_spent_tasks( self ):
        # delete FINISHED tasks that are:

        # (i) older than the oldest non-finished task 
        # (this applies to most tasks, with quick_death = True)
        #   OR
        # (ii) older than the oldest cutoff time
        # cutoff time is the oldest time still needed to satisfy the
        # prerequisites of a waiting task or a running task's immediate
        # successor. This only matters rarely, e.g. nzlam_06_18_post
        # which has to hang around longer to satisfy many subsequent
        # hourly topnets.
         
        not_finished = []
        cutoff_times = []

        for task in self.tasks:   
            if task.state != 'finished':
                cutoff_times.append( task.get_cutoff( self.tasks ))
                not_finished.append( task.ref_time )
        
        not_finished.sort( key = int )
        death_list = []
        if len( not_finished ) != 0:

            oldest_not_finished = not_finished[0]
            for task in self.tasks:
                if task.quick_death and int( task.ref_time ) < int( oldest_not_finished ):
                    death_list.append( task )
                     
        for task in death_list:
            self.log.debug( "removing spent " + task.identity )
            self.tasks.remove( task )
            self.pyro_daemon.disconnect( task )
            if self.config.get('use_broker'):
                self.broker.unregister( task.get_fullpostrequisites() )

        del death_list

        if len( cutoff_times ) != 0:

            cutoff_times.sort( key = int )
            cutoff = cutoff_times[0]

            self.log.debug( "task deletion cutoff is " + cutoff )

            death_list = []
            for task in self.tasks:
                if task.is_finished() and int( task.ref_time ) < int( cutoff ):
                    death_list.append( task )

            for task in death_list:
                self.log.debug( "removing spent " + task.identity )
                self.tasks.remove( task )
                self.pyro_daemon.disconnect( task )
                if self.config.get('use_broker'):
                    self.broker.unregister( task.get_fullpostrequisites() )

            del death_list


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


    def process_tasks( self ):

            self.regenerate()

            if self.config.get('use_broker'):
                self.negotiate()
            else:
                self.interact()

            self.run_if_ready()

            self.kill_spent_tasks()

            self.kill_lame_ducks()
