#!/usr/bin/python

import Pyro.core
import logging

class state_summary( Pyro.core.ObjBase ):
    "class to supply system state summary to external monitoring programs"

    def __init__( self, config, dummy_mode ):
        Pyro.core.ObjBase.__init__(self)
        self.task_summary = {}
        self.global_summary = {}
        # external monitors should access config via methods in this
        # class, in case config items are ever updated dynamically by
        # remote control
        self.config = config
        self.dummy_mode = dummy_mode
 
    def update( self, tasks, clock ):
        self.task_summary = {}
        self.global_summary = {}

        for task in tasks:
            self.task_summary[ task.get_identity() ] = task.get_state_summary()

        self.global_summary[ 'last_updated' ] = clock.get_datetime()
        self.global_summary[ 'dummy_mode' ] = self.dummy_mode
        self.global_summary[ 'dummy_clock_rate' ] = clock.get_rate()
           
        # update deprecated old-style summary (DELETE WHEN NO LONGER NEEDED)
        self.get_summary()


    def get_state_summary( self ):
        return [ self.global_summary, self.task_summary ]

    def get_summary( self ):
        # DEPRECATED. Remove when Bernard's monitor has been updated
        # to use get_state_summary()

        old_style_summary = {}

        for task_id in self.task_summary.keys():
            old_style_summary[ task_id ] = [ \
                         self.task_summary[ task_id ][ 'state' ], \
                    str( self.task_summary[ task_id ][ 'n_completed_outputs' ] ), \
                    str( self.task_summary[ task_id ][ 'n_total_outputs' ] ), \
                         self.task_summary[ task_id ]['latest_message' ] ]

        return old_style_summary
