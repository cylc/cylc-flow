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
            postreqs = task.get_postrequisites()
            n_total = len( postreqs )
            n_satisfied = 0
            for key in postreqs.keys():
                if postreqs[ key ]:
                    n_satisfied += 1

            # temporary hack to show tasks that are finished but have
            # not abdicated yet (i.e. parallel tasks held back by
            # the number of instances constraint): prepend an asterisk
            # to the name of tasks that have NOT abdicated yet.

            name = task.name
            if not task.has_abdicated():
                name = '*' + name

            identity = name + '%' + task.ref_time

            self.summary[ identity ] = [ \
                    task.state, \
                    str( n_satisfied), \
                    str(n_total), \
                    task.latest_message ]


    def get_dummy_mode( self ):
        return self.config.get( 'dummy_mode' )


    def get_summary( self ):
        return self.summary
