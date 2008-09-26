#!/usr/bin/python

"""
Class to keep record of current control system status, for Pyro access
by the external monitoring program, system_monitor.py

Current implementation: 
    system_status[ <task_identity> ] = [ <state>, <n_completed>, <n_total>, <latest>]

Where 
  <task_identity> = <task_name>_<reference_time> (uniquely identifies tasks)
  <state> = waiting, running, or finished
  <n_completed> = number of postrequisites completed so far
  <n_total> = total number of postrequisites for this task
  <latest> = message most recently received from the external task
All values are strings
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
            n_completed = 0
            for key in keys:
                if postreqs[ key ]:
                    n_completed += 1

            latest = task.get_latest_message()
            self.status[ task.identity() ] = [ task.state, str( n_completed), str( n_total ), latest ] 

    def get_status( self ):
        return self.status
