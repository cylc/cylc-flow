#!/usr/bin/python

"""
Classes for handling system state information, i.e.: 
WHAT TASKS EXIST AND WHAT STATE THEY ARE IN.  

A system state object can:
1/ initialise itself using:
   (i) a user-configured list of task names and a start time, or
  (ii) by uploading the state dump file (which may have been edited).
2/ dump its contents to the state dump file 
3/ create a list of tasks that reflect the recorded system state
   (this is only used at startup; thereafter new tasks are created by
   the task manager as old ones finish).
"""

from get_instance import *
import os, re

class state_base:
    # base class; override to provide different initialisation methods
    # content[ ref_time ] = [ [taskname, state], [task_name, state], ...]

    def __init__( self, filename, start_time, stop_time = None ):
        self.filename = filename
        self.start_time = start_time
        self.stop_time = stop_time

        if re.compile( "/" ).search( filename ):
            dir = os.path.dirname( filename )
            if not os.path.exists( dir ):
                os.makedirs( dir )

    def get_unique_taskname_list( self ):
        seen = {}
        ref_times = self.content.keys()
        for ref_time in ref_times:
            for item in self.content[ ref_time ]:
                [name, state] = item
                if name not in seen.keys():
                    seen[ name ] = True
 
        return seen.keys()


    def update( self, task_list ):
        self.content = {}
        for task in task_list:
            ref_time = task.ref_time
            item = [ task.name, task.state ]
            if ref_time in self.content.keys():
                self.content[ ref_time ].append( item )
            else:
                self.content[ ref_time ] = [ item ]

    def dump( self ):
        # I considered using python 'pickle' to dump and read a state
        # object, but we need a trivially human-editable file format.
        FILE = open( self.filename, 'w' )
        ref_times = self.content.keys()
        ref_times.sort( key = int )
        for rt in ref_times:
            FILE.write( rt )
            for entry in self.content[ rt ]:
                [ name, state ] = entry
                FILE.write( ' ' + name + ':' + state )

            FILE.write( '\n' )

        FILE.close()

    def create_tasks( self ):
        ref_times = self.content.keys()
        ref_times.sort( key = int, reverse = True )
        tasks = []
        seen = {}
        for ref_time in ref_times:
            for item in self.content[ ref_time ]:
                [name, state] = item
                # dynamic task object creation by task and module name
                task = get_instance( 'task_definitions', name )( ref_time, state )
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
                if self.stop_time:
                    if int( task.ref_time ) > int( self.stop_time ):
                        task.log.info( task.name + " STOPPING at " + self.stop_time )
                        del task
                        skip = True

                if not skip:
                    task.log.info( "New task created for " + task.ref_time )
                    tasks.append( task )
                    
        return tasks

class state_from_list ( state_base ):

    def __init__( self, filename, config_list, start_time, stop_time = None ):
        # config_list = [ taskname(:state), taskname(:state), ...]
        # where (:state) is optional and defaults to 'waiting'.

        state_base.__init__( self, filename, start_time, stop_time )

        self.content = {}

        for item in config_list:
            state = 'waiting'
            name = item
            if re.compile( "^.*:").match( item ):
                [name, state] = item.split(':')

            if start_time not in self.content.keys():
                self.content[ start_time  ] = [ [ name, state ] ]
            else:
                self.content[ start_time  ].append( [ name, state ] )

class state_from_dump ( state_base ):
    
    def __init__( self, filename, start_time, stop_time ):
        # load from file with lines like this:
        # ref_time taskname:state taskname:state

        state_base.__init__( self, filename, start_time, stop_time )

        self.content = {}

        FILE = open( self.filename, 'r' )
        lines = FILE.readlines()
        FILE.close()

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
                if ref_time in self.content.keys():
                    self.content[ ref_time ].append( [name, state] )
                else:
                    self.content[ ref_time ] = [[name, state]] 


