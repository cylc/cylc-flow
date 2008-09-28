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

Task names must not contain underscores at the moment (the 'name'
attribute, not the class name itself, that is).
"""

import reference_time
from requisites import requisites

import os
import sys
from copy import deepcopy
from time import strftime
import Pyro.core

#----------------------------------------------------------------------
class task_base( Pyro.core.ObjBase ):
    "ecoconnect task base class"
    
    name = "task base class"

    # default host info (used to decide when to overlap the next cycle)
    runs_on_kupe = False

    def __init__( self, initial_state ):
        Pyro.core.ObjBase.__init__(self)
        self.state = "waiting"
        self.latest_message = ""
        self.abdicated = False # True => my successor has been created

        # initial states:
        #   waiting
        #   running
        #   finishd
        # (deliberate spelling error for equal word lengths: nicer for display)
        if initial_state is None: 
            pass
        elif initial_state == "finishd":  
            self.postrequisites.set_all_satisfied()
            self.state = "finishd"
        elif initial_state == "ready":
            # waiting, but ready to go
            self.prerequisites.set_all_satisfied()
        else:
            print "ERROR: unknown initial task state " + initial_state
            sys.exit(1)

        self.no_previous_instance = True

    def run_if_satisfied( self ):
        if self.state == "finishd":
            # already finished
            pass
        elif self.state == "running":
            # already running
            pass
        elif self.prerequisites.all_satisfied() and self.no_previous_instance:
            # RUN THE EXTERNAL TASK AS A SEPARATE PROCESS
            # TO DO: the subprocess module might be better than os.system?
            print strftime("%Y-%m-%d %H:%M:%S ") + self.display() + " RUN EXTERNAL TASK",
            print "[ext_task_dummy.py " + self.name + " " + self.ref_time + "]"
            os.system( "./ext_task_dummy.py " + self.name + " " + self.ref_time + "&" )
            self.state = "running"
        else:
            # still waiting
            pass

    def get_state( self ):
        return self.name + ": " + self.state

    def identity( self ):
        return self.name + "_" + self.ref_time

    def display( self ):
        return self.name + "(" + self.ref_time + ")"

    def set_finished( self ):
        # could do this automatically off the "name finished for ref_time" message
        self.state = "finishd"

    def abdicate( self ):
        if self.state == "finishd" and not self.abdicated:
            self.abdicated = True
            return True
        else:
            return False

    def get_satisfaction( self, tasks ):

        # don't bother settling prerequisites if a previous instance
        # of me hasn't finished yet NOT NEEDED UNDER NEW TASK
        # MANAGEMENT SCHEME
        self.no_previous_instance = True
        for task in tasks:
            if task.name == self.name:
                if task.state != "finishd":
                    if int( task.ref_time ) < int( self.ref_time ):
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

    def is_running( self ): 
        if self.state == "running":
            return True
        else:
            return False

    def is_finished( self ): 
        if self.state == "finishd":
            return True
        else:
            return False

    def get_postrequisite_list( self ):
        return self.postrequisites.get_list()

    def get_postrequisites( self ):
        return self.postrequisites.get_requisites()

    def get_latest_message( self ):
        return self.latest_message

    def get_valid_hours( self ):
        return self.valid_hours

    def incoming( self, message ):
        # receive all incoming pyro messages for this task 

        self.latest_message = message

        warning = " "
        if self.state != "running":
            warning = " WARNING: message received for a non-running task: "

        if self.postrequisites.requisite_exists( message ):
            if self.postrequisites.is_satisfied( message ):
                warning = " WARNING: this postrequisite is already satisfied: "

            self.postrequisites.set_satisfied( message )

        else:
            warning = " WARNING: received non-postrequisite message: "

        print strftime("%Y-%m-%d %H:%M:%S ") + self.display() + warning + message

#----------------------------------------------------------------------
all_task_names = [ 'downloader', 'nwpglobal', 'globalprep', 'globalwave',
                   'nzlam', 'nzlampost', 'nzwave', 'ricom', 'nztide', 
                   'topnet', 'mos' ]

#----------------------------------------------------------------------
class downloader( task_base ):
    "Met Office input file download task"

    """
    this task provides initial input to get things going: it starts
    running immediately and it completes when it's outputs are generated
    for use by the downstream tasks.
    """

    name = "downloader"
    ref_time_increment = 6
    valid_hours = [ "00", "06", "12", "18" ]

    def __init__( self, ref_time, initial_state ):

        self.ref_time = ref_time
        hour = ref_time[8:10]

        # no prerequisites: this is The Initial Task
        self.prerequisites = requisites([])

        # my postrequisites are files needed FOR my reference time
        # (not files downloaded at my reference time) 

        lbc_06 = reference_time.decrement( ref_time, 6 )
        lbc_12 = reference_time.decrement( ref_time, 12 )

        if hour == "00":
            self.postrequisites = requisites([ 
                    self.name + " started for " + ref_time,
                    "file obstore_" + ref_time + ".um ready",
                    "file bgerr" + ref_time + ".um ready", 
                    "file lbc_" + lbc_12 + ".um ready", 
                    "file 10mwind_" + ref_time + ".um ready",
                    "file seaice_" + ref_time + ".um ready",
                    self.name + " finished for " + ref_time
                    ])

        elif hour == "12":
            self.postrequisites = requisites([ 
                    self.name + " started for " + ref_time,
                    "file obstore_" + ref_time + ".um ready",
                    "file bgerr" + ref_time + ".um ready", 
                    "file lbc_" + lbc_12 + ".um ready",
                    self.name + " finished for " + ref_time
                    ])

        if hour == "06" or hour == "18":
            self.postrequisites = requisites([
                    self.name + " started for " + ref_time,
                    "file obstore_" + ref_time + ".um ready",
                    "file bgerr" + ref_time + ".um ready",
                    "file lbc_" + lbc_06 + ".um ready",
                    self.name + " finished for " + ref_time
                    ])

        task_base.__init__( self, initial_state )


#----------------------------------------------------------------------
class nzlam( task_base ):

    name = "nzlam"
    ref_time_increment = 6
    valid_hours = [ "00", "06", "12", "18" ]

    def __init__( self, ref_time, initial_state ):
        
        self.ref_time = ref_time
        hour = ref_time[8:10]

        lbc_06 = reference_time.decrement( ref_time, 6 )
        lbc_12 = reference_time.decrement( ref_time, 12 )

        if hour == "00" or hour == "12":
            self.prerequisites = requisites([ 
                    "file obstore_" + ref_time + ".um ready",
                    "file bgerr" + ref_time + ".um ready",
                    "file lbc_" + lbc_12 + ".um ready" ])

        if hour == "06" or hour == "18":
            self.prerequisites = requisites([ 
                    "file obstore_" + ref_time + ".um ready",
                    "file bgerr" + ref_time + ".um ready",
                    "file lbc_" + lbc_06 + ".um ready" ])

        self.postrequisites = requisites([ 
                self.name + " started for " + ref_time,
                "file tn_" + ref_time + ".um ready",
                "file sls_" + ref_time + ".um ready",   
                "file met_" + ref_time + ".um ready",
                self.name + " finished for " + ref_time
                ])
        
        task_base.__init__( self, initial_state )


#----------------------------------------------------------------------
class nzlampost( task_base ):

    name = "nzlampost"
    ref_time_increment = 6
    valid_hours = [ "00", "06", "12", "18" ]

    def __init__( self, ref_time, initial_state ):
        
        self.ref_time = ref_time

        self.prerequisites = requisites([ 
                  "file tn_" + ref_time + ".um ready",
                  "file sls_" + ref_time + ".um ready",   
                  "file met_" + ref_time + ".um ready" ])

        self.postrequisites = requisites([ 
                self.name + " started for " + ref_time,
                "file tn_" + ref_time + ".nc ready",
                "file sls_" + ref_time + ".nc ready",   
                "file met_" + ref_time + ".nc ready",
                self.name + " finished for " + ref_time
                ])
        
        task_base.__init__( self, initial_state )


#----------------------------------------------------------------------
class globalprep( task_base ):
    name = "globalprep"
    ref_time_increment = 24
    valid_hours = [ "00" ]

    def __init__( self, ref_time, initial_state ):

        self.ref_time = ref_time

        self.prerequisites = requisites([ 
                "file 10mwind_" + ref_time + ".um ready",
                "file seaice_" + ref_time + ".um ready" ])

        self.postrequisites = requisites([
                self.name + " started for " + ref_time,
                "file 10mwind_" + ref_time + ".nc ready",
                "file seaice_" + ref_time + ".nc ready",
                self.name + " finished for " + ref_time
                ])
       
        task_base.__init__( self, initial_state )
 
 
#----------------------------------------------------------------------
class globalwave( task_base ):

    name = "globalwave"
    ref_time_increment = 24
    valid_hours = [ "00" ]

    def __init__( self, ref_time, initial_state ):

        self.ref_time = ref_time

        self.prerequisites = requisites([ 
                "file 10mwind_" + ref_time + ".nc ready",
                "file seaice_" + ref_time + ".nc ready" ])

        self.postrequisites = requisites([
                self.name + " started for " + ref_time,
                "file globalwave_" + ref_time + ".nc ready",
                self.name + " finished for " + ref_time
                ])
        
        task_base.__init__( self, initial_state )
 
    
#----------------------------------------------------------------------
class nzwave( task_base ):
    
    name = "nzwave"
    ref_time_increment = 6
    valid_hours = [ "00", "06", "12", "18" ]

    def __init__( self, ref_time, initial_state ):

        self.ref_time = ref_time

        self.prerequisites = requisites([ 
                 "file sls_" + ref_time + ".nc ready" ])

        self.postrequisites = requisites([
                self.name + " started for " + ref_time,
                "file nzwave_" + ref_time + ".nc ready",
                self.name + " finished for " + ref_time
                ])
        
        task_base.__init__( self, initial_state )


#----------------------------------------------------------------------
class ricom( task_base ):
    
    name = "ricom"
    ref_time_increment = 12
    valid_hours = [ "06", "18" ]

    def __init__( self, ref_time, initial_state ):

        self.ref_time = ref_time

        self.prerequisites = requisites([ 
                 "file sls_" + ref_time + ".nc ready" ])

        self.postrequisites = requisites([
                self.name + " started for " + ref_time,
                "file ricom_" + ref_time + ".nc ready",
                self.name + " finished for " + ref_time
                ])
        
        task_base.__init__( self, initial_state )


#----------------------------------------------------------------------
class mos( task_base ):
    
    name = "mos"
    ref_time_increment = 6
    valid_hours = [ "00", "06", "12", "18" ]

    def __init__( self, ref_time, initial_state ):

        self.ref_time = ref_time

        self.prerequisites = requisites([ 
                 "file met_" + ref_time + ".nc ready" ])

        self.postrequisites = requisites([
                self.name + " started for " + ref_time,
                "file mos_" + ref_time + ".nc ready",
                self.name + " finished for " + ref_time
                ])
        
        task_base.__init__( self, initial_state )


#----------------------------------------------------------------------
class nztide( task_base ):
    
    name = "nztide"
    ref_time_increment = 12
    valid_hours = [ "06", "18" ]

    def __init__( self, ref_time, initial_state ):

        self.ref_time = ref_time

        # artificial prerequisite to stop nztide running ahead
        self.prerequisites = requisites([
                "downloader started for " + ref_time ])

        self.postrequisites = requisites([
                self.name + " started for " + ref_time,
                "file nztide_" + ref_time + ".nc ready",
                self.name + " finished for " + ref_time
                ])
        
        task_base.__init__( self, initial_state )


#----------------------------------------------------------------------
class topnet( task_base ):
 
    name = "topnet"
    ref_time_increment = 1
    valid_hours = [ "06", "18" ]   
    def __init__( self, ref_time, initial_state ):

        self.ref_time = ref_time

        self.prerequisites = requisites([ 
                "file tn_" + ref_time + ".nc ready" ])

        self.postrequisites = requisites([ 
                self.name + " started for " + ref_time,
                "file topnet_" + ref_time + ".nc ready",
                self.name + " finished for " + ref_time
                ])
        
        task_base.__init__( self, initial_state )


#----------------------------------------------------------------------
class nwpglobal( task_base ):

    name = "nwpglobal"
    ref_time_increment = 24
    valid_hours = [ "00" ]

    def __init__( self, ref_time, initial_state ):

        self.ref_time = ref_time

        self.prerequisites = requisites([ 
                 "file 10mwind_" + ref_time + ".um ready" ])

        self.postrequisites = requisites([
                self.name + " started for " + ref_time,
                "file 10mwind_" + ref_time + ".nc ready",
                self.name + " finished for " + ref_time
                ])
    
        task_base.__init__( self, initial_state )
