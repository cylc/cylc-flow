#!/usr/bin/python

"""
Class to keep record of current control system status, for Pyro access
by the external monitoring program, system_monitor.py
"""

import Pyro.core
from string import ljust, rjust 


class system_status( Pyro.core.ObjBase ):

    def __init__( self ):
        Pyro.core.ObjBase.__init__(self)
        self.status = {}

    def update( self, task_list ):
        self.status = {}
        for task in task_list:
            postreqs = task.get_postrequisites()
            keys = postreqs.keys()
            n_total = len( keys )
            n_done = 0
            for key in keys:
                if postreqs[ key ]:
                    n_done += 1

            prog = ""
            for k in range( 1, n_total + 1):
                if k <= n_done:
                    prog += "|"
                else:
                    prog += "-"

            frac = str( n_done ) + "/" + str( n_total )

            st = task.state
            if st == "running":
                st = "RUNNING"
            if st == "finished":
                st = "...done"
            if st == "waiting":
                st = "wait..."

            self.status[ task.identity() ] = ljust( st, 8 ) + " " + " " + rjust( frac,5 ) + " " + prog

    def get_status( self ):
        return self.status
