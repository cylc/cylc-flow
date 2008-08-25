#!/usr/bin/python

"""
Task base class for the Ecoconnect Controller.

A "task" represents a particular group of external jobs, for a single
reference time, that we want separate scheduling control over (as a
group).  Each task has certain prerequisites that must be satisfied
before it can launch its external task, and certain postrequisites that
are created or achieved as the task runs, and which may be prerequisites
for other tasks.  A task must maintain an accurate representation of
the task's state as it follows through to the end of processing for its
reference time.  

tasks communicate with each other in order to sort out inter-task
dependencies (i.e. match postrequisites with prerequisites).
"""

from reference_time import reference_time
from requisites import requisites

import os
import sys
from copy import deepcopy
import Pyro.core

class task( Pyro.core.ObjBase ):
    "ecoconnect task base class"
    
    name = "task base class"

    def __init__( self, ref_time, initial_state ):
        Pyro.core.ObjBase.__init__(self)
        self.ref_time = ref_time
        self.running = False  # TO DO: get rid of logical status vars in favour of one string?
        self.finished = False
        self.status = "waiting"

        if initial_state is None: 
            pass
        elif initial_state == "finished":
            self.set_finished()
        elif initial_state == "ready":
            self.set_ready()
        else:
            print "ERROR: unknown initial task state " + initial_state
            sys.exit(1)

    def run_if_satisfied( self ):
        if self.finished:
            self.running = False
        elif self.running:
            pass
        elif self.prerequisites.all_satisfied():
            self.run()
        else:
            pass

    def get_status( self ):
        return self.name + ": " + self.status

    def identity( self ):
        return self.name + "_" + self.ref_time.to_str()

    def run( self ):
        # run the external task (but don't wait for it!)
        # NOTE: apparently os.system has been superseded by the
        # subprocess module.
        print self.identity() + ": RUN EXTERNAL TASK",
        print "[ext_task_dummy.py " + self.name + " " + self.ref_time.to_str() + "]"
        os.system( "./ext_task_dummy.py " + self.name + " " + self.ref_time.to_str() + "&" )
        self.running = True
        self.status = "RUNNING"

    def set_finished( self ):
        self.running = False
        self.finished = True
        self.status = "(done)"
        # the following is redundant, except when initialising 
        # in a "finished" state:
        self.postrequisites.set_all_satisfied()

    def set_ready( self ):
        self.running = False
        self.finished = False
        self.status = "waiting"
        self.prerequisites.set_all_satisfied()

    def set_satisfied( self, message ):
        print self.identity() +  ": " + message
        self.postrequisites.set_satisfied( message )
        # TO DO: SHOULD WE CHECK THIS IS A KNOWN POSTREQUISITE?

    def get_satisfaction( self, tasks ):
        for task in tasks:
            self.prerequisites.satisfy_me( task.postrequisites )

    def will_get_satisfaction( self, tasks ):
        temp_prereqs = deepcopy( self.prerequisites )
        for task in tasks:
            temp_prereqs.will_satisfy_me( task.postrequisites )

        if not temp_prereqs.all_satisfied(): 
            return False
        else:
            return True

    def is_complete( self ):
        if self.postrequisites.all_satisfied():
            return True
        else:
            return False

    def get_postrequisites( self ):
        return self.postrequisites.get_list()

    def get_valid_hours( self ):
        return self.valid_hours
