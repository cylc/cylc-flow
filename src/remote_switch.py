#!/usr/bin/python

import Pyro.core
import logging
import task
import sys

class remote_switch( Pyro.core.ObjBase ):
    "class to take remote system control requests" 
    # the task manager can take action on these when convenient.

    def __init__( self, config, tasknames ):
        self.log = logging.getLogger( "main" )
        Pyro.core.ObjBase.__init__(self)
        self.config = config
        self.tasknames = tasknames
        self.task_to_insert = None

        self.set_stop = False
        self.stop_time = None

        # record remote system halt requests
        self.system_halt_requested = False

        # record remote system hold requests
        self.system_hold_requested = False
        self.system_resume_requested = False

        # task to abdicate and kill
        self.kill = False
        self.kill_task_id = None

        # task to dump requisites
        self.requisite_dump = False
        self.dump_task_ids = {}

    def nudge( self ):
        # pretend a task has changed state in order to invoke the event
        # handling loop
        self.log.warning( "REMOTE: nudge requested" )
        task.state_changed = True

    def insert( self, taskid ):
        # insert a new task into the system
        self.task_to_insert = taskid
        self.log.warning( "REMOTE: task insertion request: " + taskid )

    def hold( self ):
        self.log.warning( "REMOTE: system hold requested" )
        self.system_hold_requested = True

    def get_hold( self ):
        if self.system_hold_requested:
            self.system_hold_requested = False
            return True
        else:
            return False

    def resume( self ):
        self.log.warning( "REMOTE: system resume requested" )
        self.system_resume_requested = True 
        self.system_hold_requested = False 
        # ensure we resume task processing immediately
        task.state_changed = True

    def get_resume( self ):
        if self.system_resume_requested:
            self.system_resume_requested = False
            return True
        else:
            return False

    def set_stop_time( self, reftime ):
        self.log.warning( "REMOTE: set stop time requested" )
        self.set_stop = True
        self.stop_time = reftime

    def shutdown( self ):
        self.log.warning( "REMOTE: system halt requested" )
        self.system_halt_requested = True

    def get_config( self, item ):
        self.log.warning( "REMOTE: config item " + item + " requested" )
        try:
            result = self.config.get( item )
        except:
            self.log.warning( "no such config item: " + item )
        else:
            return result

    def dump_task_requisites( self, task_ids ):
        self.log.warning( "REMOTE: requisite dump request for:")
        for task_id in task_ids:
            self.dump_task_ids[ task_id ] = True
            self.log.info( '-> ' + task_id )
        self.requisite_dump = True


    def abdicate_and_kill( self, task_id ):
        # main prog must reset kill after doin' the killin'
        self.log.warning( "REMOTE: abdicate and kill request for " + task_id )
        self.kill = True
        self.kill_task_id = task_id
        # ensure we resume task processing immediately
        task.state_changed = True

    def set_verbosity( self, level ):
        # change the verbosity of all the logs:
        #   debug, info, warning, error, critical
        self.log.warning( "REMOTE: verbosity change to " + level + " requested"  )
        
        if level == 'debug':
            new_level = logging.DEBUG
        elif level == 'info':
            new_level = logging.INFO
        elif level == 'warning':
            new_level = logging.WARNING
        elif level == 'error':
            new_level = logging.ERROR
        elif level == 'critical':
            new_level = logging.CRITICAL
        else:
            self.log.warning( "no such logging level: " + level )
            return

        self.config.set( 'logging_level', new_level )

        # main log
        self.log.setLevel( new_level )

        # task logs
        # If this run is a restart from state dump file, the following
        # assumes that the configured task list is the same as in the
        # state-dump file, which should be the case.

        for task in self.tasknames:
            # strip off any state string
            foo = task.split(':')
            name = 'main.' + foo[0]
            log = logging.getLogger( name )
            log.setLevel( new_level )
