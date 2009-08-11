#!/usr/bin/python

import Pyro.core
import logging
import sys

class state_summary( Pyro.core.ObjBase ):
    "class to supply system state summary to external monitoring programs"

    def __init__( self, config ):
        Pyro.core.ObjBase.__init__(self)
        summary = {}
        # external monitors should access config via methods in this
        # class, in case config items are ever updated dynamically by
        # remote control
        self.config = config
 
    def update( self, tasks ):
        self.summary = {}
        self.name_list = []
        self.ref_time_list = []
        seen_name = {}
        seen_time = {}
        for task in tasks:
            if task.ref_time not in seen_time.keys():
                seen_time[ task.ref_time ] = True
                self.ref_time_list.append( task.ref_time )

            if task.name not in seen_name.keys():
                seen_name[ task.name ] = True
                self.name_list.append( task.name )

            self.summary[ task.identity ] = task.get_state_summary()
           
        # update deprecated old-style summary
        # (delete when no longer needed)
        self.get_summary()

    def get_dummy_mode( self ):
        return self.config.get( 'dummy_mode' )

    def get_dummy_clock_rate( self ):
        return self.config.get( 'dummy_clock_rate' )


    def get_state_summary( self ):
        return self.summary

    def get_ref_time_list( self ):
        return self.ref_time_list

    def get_name_list( self ):
        return self.name_list

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
