#!/usr/bin/python

import Pyro.core
import logging
import sys

class switch( Pyro.core.ObjBase ):
    "class to take remote system control requests" 
    # the task manager can take action on these when convenient.

    def __init__( self ):
        self.log = logging.getLogger( "main" )
        Pyro.core.ObjBase.__init__(self)

        # record remote system halt requests
        self.system_halt = False

        # record remote system pause requests
        self.system_pause = False

    def pause( self ):
        self.log.warning( "system pause requested" )
        self.system_pause = True

    def resume( self ):
        self.log.warning( "system resume requested" )
        self.system_pause = False 

    def shutdown( self ):
        self.log.warning( "system halt requested" )
        self.system_halt = True


class state_summary( Pyro.core.ObjBase ):
    "class to supply system state summary to external monitoring programs"

    def __init__( self ):
        Pyro.core.ObjBase.__init__(self)
        summary = {}
 
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

    def get_summary( self ):
        return self.summary
