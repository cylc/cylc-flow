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
from time import strftime
import Pyro.core


class task_base( Pyro.core.ObjBase ):
    "ecoconnect task base class"
    
    name = "task base class"

    def __init__( self, ref_time, initial_state ):
        Pyro.core.ObjBase.__init__(self)
        # don't just keep a reference to input reference time object
        self.ref_time = deepcopy( ref_time )
        self.state = "waiting"

        if initial_state is None: 
            pass
        elif initial_state == "finished":
            self.postrequisites.set_all_satisfied()
            self.state = "finished"
        elif initial_state == "ready":
            # waiting, but ready to go
            self.prerequisites.set_all_satisfied()
        else:
            print "ERROR: unknown initial task state " + initial_state
            sys.exit(1)

        self.no_previous_instance = True

    def run_if_satisfied( self ):
        if self.state == "finished":
            # already finished
            pass
        elif self.state == "running":
            # already running
            pass
        elif self.prerequisites.all_satisfied() and self.no_previous_instance:
            # RUN THE EXTERNAL TASK AS A SEPARATE PROCESS
            # TO DO: the subprocess module might be better than os.system?
            print strftime("%Y-%m-%d %H:%M:%S ") + self.display() + " RUN EXTERNAL TASK",
            print "[ext_task_dummy.py " + self.name + " " + self.ref_time.to_str() + "]"
            os.system( "./ext_task_dummy.py " + self.name + " " + self.ref_time.to_str() + "&" )
            self.state = "running"
        else:
            # still waiting
            pass

    def get_state( self ):
        return self.name + ": " + self.state

    def identity( self ):
        return self.name + "_" + self.ref_time.to_str()

    def display( self ):
        return self.name + "(" + self.ref_time.to_str() + ")"

    def set_finished( self ):
        self.state = "finished"

    def set_satisfied( self, message ):
        print  strftime("%Y-%m-%d %H:%M:%S ") + self.display() + " " + message
        self.postrequisites.set_satisfied( message )
        # TO DO: SHOULD WE CHECK THIS IS A KNOWN POSTREQUISITE?

    def get_satisfaction( self, tasks ):

        # don't bother settling prerequisites if a previous instance
        # of me hasn't finished yet 
        self.no_previous_instance = True
        for task in tasks:
            if task.name == self.name:
                if task.state != "finished":
                    if task.ref_time.is_lessthan( self.ref_time ):
                        self.no_previous_instance = False
                        #print self.identity() + " blocked by " + task.identity()
                        return

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

    def is_complete( self ):  # not needed?
        if self.postrequisites.all_satisfied():
            return True
        else:
            return False

    def is_finished( self ): 
        if self.state == "finished":
            return True
        else:
            return False

    def get_postrequisite_list( self ):
        return self.postrequisites.get_list()

    def get_postrequisites( self ):
        return self.postrequisites.get_requisites()

    def get_valid_hours( self ):
        return self.valid_hours
