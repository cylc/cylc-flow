#!/usr/bin/python

import Pyro.core
import logging
import sys

class state_summary( Pyro.core.ObjBase ):
    "class to supply system state summary to external monitoring programs"

    def __init__( self, config ):
        Pyro.core.ObjBase.__init__(self)
        summary = {}
        self.config = config
 
    def update( self, tasks ):
        self.summary = {}
        for task in tasks:
            self.summary[ task.identity ] = task.get_state_summary()
           
        self.get_summary()

    def get_dummy_mode( self ):
        return self.config.get( 'dummy_mode' )

    def get_state_summary( self ):
        return self.summary

    def get_summary( self ):
        # DEPRECATED. Remove when Bernard's monitor has been updated
        # to use get_state_summary()

        old_style_summary = {}

        for task_id in self.summary.keys():
            old_style_summary[ task_id ] = [ \
                         self.summary[ task_id ][ 'state' ], \
                    str( self.summary[ task_id ][ 'n_completed_postrequisites' ] ), \
                    str( self.summary[ task_id ][ 'n_total_postrequisites' ] ), \
                         self.summary[ task_id ]['latest_message' ] ]

        return old_style_summary
