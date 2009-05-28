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

        # record remote system halt requests
        self.system_halt = False

        # record remote system pause requests
        self.system_pause = False

    def pause( self ):
        self.log.warning( "REMOTE: system pause requested" )
        self.system_pause = True

    def resume( self ):
        self.log.warning( "REMOTE: system resume requested" )
        self.system_pause = False 
        # ensure we resume task processing immediately
        task.state_changed = True

    def shutdown( self ):
        self.log.warning( "REMOTE: system halt requested" )
        self.system_halt = True

    def get_config( self, item ):
        self.log.warning( "REMOTE: config item " + item + " requested" )
        try:
            result = self.config.get( item )
        except:
            self.log.warning( "no such config item: " + item )
        else:
            return result

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
