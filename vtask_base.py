#!/usr/bin/python

"""
Virtual task base class for the Ecoconnect Controller.

A vtask represents a particular group of external tasks, for a single
reference time, that we want separate scheduling control over (as a
group).  Each vtask has certain prerequisites that must be satisfied
before it can launch its external task, and certain postrequisites that
are created or achieved as the task runs, and which may be prerequisites
for other vtasks.  A vtask must maintain an accurate representation of
the task's state as it follows through to the end of processing for its
reference time.  

vtasks communicate with each other in order to sort out inter-task
dependencies (i.e. match postrequisites with prerequisites).
"""

from reference_time import reference_time
from requisites import requisites

import os
import Pyro.core

class vtask( Pyro.core.ObjBase ):
    "ecoconnect vtask base class"
    
    name = "vtask base class"

    def __init__( self, ref_time ):
        Pyro.core.ObjBase.__init__(self)
        self.ref_time = ref_time
        self.running = False  # TO DO: get rid of logical status vars in favour of one string?
        self.finished = False
        self.status = "waiting"

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
        os.system( "./run_task.py " + self.name + " " + self.ref_time.to_str() + "&" )
        self.running = True
        self.status = "RUNNING"

    def set_finished( self ):
        self.running = False
        self.finished = True
        self.status = "finished"

    def set_satisfied( self, message ):
        print self.identity(), ": ", message
        self.postrequisites.set_satisfied( message )
        # TO DO: SHOULD WE CHECK THIS IS A KNOWN POSTREQUISITE?

    def get_satisfaction( self, other_tasks ):
        for other_task in other_tasks:
            self.prerequisites.satisfy_me( other_task.postrequisites )

    def is_complete( self ):
        if self.postrequisites.all_satisfied():
            return True
        else:
            return False

    def get_postrequisites( self ):
        return self.postrequisites.get_list()
