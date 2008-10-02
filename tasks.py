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
from requisites import requisites, fuzzy_requisites
from time import sleep

import os
import re
import sys
from copy import deepcopy
from time import strftime
import Pyro.core

import logging
import logging.handlers

#-----------------------------------------------------------------------
all_tasks = [ 
        'downloader',
        'nwpglobal',
        'globalprep',
        'globalwave',
        'nzlam',
        'nzlampost',
        'nzwave',
        'ricom',
        'nztide',
        'topnet',
        'mos' 
        ]

#----------------------------------------------------------------------
class task_base( Pyro.core.ObjBase ):
    "ecoconnect task base class"
    
    name = "task base class"

    def __init__( self, ref_time, initial_state = "waiting" ):

        Pyro.core.ObjBase.__init__(self)

        # adjust ref time (needed for creation of initial task list)
        self.ref_time = self.nearest_ref_time( ref_time )

        self.log = logging.getLogger( "ecoconnect." + self.name ) 

        self.latest_message = ""
        self.abdicated = False # True => my successor has been created

        # initial states: waiting, running, finishd
        # (spelling: equal word lengths for display)
        if not initial_state:
            self.state = "waiting"
            pass
        elif initial_state == "waiting": 
            self.state = "waiting"
        elif initial_state == "finishd":  
            self.postrequisites.set_all_satisfied()
            self.state = "finishd"
        elif initial_state == "ready":
            # waiting, but ready to go
            self.prerequisites.set_all_satisfied()
        else:
            print "ERROR: unknown initial task state " + initial_state
            sys.exit(1)

    def nearest_ref_time( self, rt ):
        # return the next time >= rt for which this task is valid
        rh = int( rt[8:10])
        
        incr = None

        first_vh = self.valid_hours[ 0 ]
        extra_vh = 24 + first_vh 
        foo = self.valid_hours
        foo.append( extra_vh )

        for vh in foo:
            if rh <= vh:
                incr = vh - rh
                break
    
        nearest_rt = reference_time.increment( rt, incr )
        return nearest_rt


    def next_ref_time( self ):
        # return the next time that this task is valid at
        n_times = len( self.valid_hours )
        if n_times == 1:
            increment = 24
        else:
            i_now = self.valid_hours.index( int( self.ref_time[8:10]) )
            # list indices start at zero
            if i_now < n_times - 1 :
                increment = self.valid_hours[ i_now + 1 ] - self.valid_hours[ i_now ]
            else:
                increment = self.valid_hours[ 0 ] + 24 - self.valid_hours[ i_now ]

        return reference_time.increment( self.ref_time, increment )


    def run_if_ready( self, tasks ):

        # This function originally called run() if all prerequisites
        # were satisfied. Now we can also check non-prerequisite
        # conditions relating to other tasks, hence the list list
        # argument 

        # don't run if any previous instance not finished
        for task in tasks:
            if task.name == self.name:
                if task.state != "finishd":
                    if int( task.ref_time ) < int( self.ref_time ):
                        self.log.info( self.identity() + " blocked by " + task.identity() )
                        return

        # don't run a new downloader if too many previous finished
        # instances exist (this stops downloader running far ahead)
        old_and_finished = []
        if self.name == "downloader" and self.state == "waiting":
            for task in tasks:
               if task.name == self.name and task.state == "finishd":
                   old_and_finished.append( task.ref_time )
                            
            # TO DO: THIS LISTS ALL FINISHED DOWNLOADERS TOO
            MAX_FINISHED_DOWNLOADERS = 8
            if len( old_and_finished ) == MAX_FINISHED_DOWNLOADERS:
                self.log.info( self.identity() + " waiting, too far ahead" )
                return

        if self.state == "finishd":
            # already finished
            pass
        elif self.state == "running":
            # already running
            pass
        elif self.prerequisites.all_satisfied():
            self.run()
        else:
            # still waiting
            pass

    def run( self ):
        # RUN THE EXTERNAL TASK AS A SEPARATE PROCESS
        # TO DO: the subprocess module might be better than os.system?
        self.log.debug( "RUNNING [task_dummy.py " + self.name + " " + self.ref_time + "]" )
        os.system( "./task_dummy.py " + self.name + " " + self.ref_time + "&" )
        self.state = "running"


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

        if self.state != "running":
            self.log.warning( "NON-RUNNING TASK: " + message )

        if self.postrequisites.requisite_exists( message ):
            if self.postrequisites.is_satisfied( message ):
                self.log.warning( "ALREADY SATISFIED: " + message )

            self.postrequisites.set_satisfied( message )

        else:
            self.log.warning( "UNEXPECTED: " + message )


#----------------------------------------------------------------------
class downloader( task_base ):
    "Met Office input file download task"

    """
    this task provides initial input to get things going: it starts
    running immediately and it completes when it's outputs are generated
    for use by the downstream tasks.
    """

    name = "downloader"
    valid_hours = [ 0, 6, 12, 18 ]

    def __init__( self, ref_time, initial_state ):
        
        task_base.__init__( self, ref_time, initial_state )
        # note: base class init may adjust ref_time!
        ref_time = self.ref_time

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


#----------------------------------------------------------------------
class nzlam( task_base ):

    name = "nzlam"
    valid_hours = [ 0, 6, 12, 18 ]

    def __init__( self, ref_time, initial_state ):

        task_base.__init__( self, ref_time, initial_state )
        # note: base class init may adjust ref_time!
        ref_time = self.ref_time

        hour = ref_time[8:10]

        lbc_06 = reference_time.decrement( ref_time, 6 )
        lbc_12 = reference_time.decrement( ref_time, 12 )

        if hour == "00" or hour == "12":
            self.prerequisites = requisites([ 
                "file obstore_" + ref_time + ".um ready",
                "file bgerr" + ref_time + ".um ready",
                "file lbc_" + lbc_12 + ".um ready" 
                ])

            self.postrequisites = requisites([ 
                self.name + " started for " + ref_time,
                "file sls_" + ref_time + ".um ready",   
                self.name + " finished for " + ref_time
                ])
 
        elif hour == "06" or hour == "18":
            self.prerequisites = requisites([ 
                "file obstore_" + ref_time + ".um ready",
                "file bgerr" + ref_time + ".um ready",
                "file lbc_" + lbc_06 + ".um ready" 
                ])

            self.postrequisites = requisites([ 
                self.name + " started for " + ref_time,
                "file tn_" + ref_time + ".um ready",
                "file sls_" + ref_time + ".um ready",   
                "file met_" + ref_time + ".um ready",
                self.name + " finished for " + ref_time
                ])
        

#----------------------------------------------------------------------
class nzlampost( task_base ):

    name = "nzlampost"
    valid_hours = [ 0, 6, 12, 18 ]

    def __init__( self, ref_time, initial_state ):

        task_base.__init__( self, ref_time, initial_state )
        # note: base class init may adjust ref_time!
        ref_time = self.ref_time

        hour = ref_time[8:10]

        if hour == "00" or hour == "12":
            self.prerequisites = requisites([ 
                "file sls_" + ref_time + ".um ready",   
                ])

            self.postrequisites = requisites([ 
                self.name + " started for " + ref_time,
                "file sls_" + ref_time + ".nc ready",   
                self.name + " finished for " + ref_time
                ])

        elif hour == "06" or hour == "18":
            self.prerequisites = requisites([ 
                "file tn_" + ref_time + ".um ready",
                "file sls_" + ref_time + ".um ready",   
                "file met_" + ref_time + ".um ready" 
                ])

            self.postrequisites = requisites([ 
                self.name + " started for " + ref_time,
                "file tn_" + ref_time + ".nc ready",
                "file sls_" + ref_time + ".nc ready",   
                "file met_" + ref_time + ".nc ready",
                self.name + " finished for " + ref_time
                ])
        

#----------------------------------------------------------------------
class globalprep( task_base ):
    name = "globalprep"
    valid_hours = [ 0 ]

    def __init__( self, ref_time, initial_state ):

        task_base.__init__( self, ref_time, initial_state )
        # note: base class init may adjust ref_time!
        ref_time = self.ref_time


        self.prerequisites = requisites([ 
                "file 10mwind_" + ref_time + ".um ready",
                "file seaice_" + ref_time + ".um ready" ])

        self.postrequisites = requisites([
                self.name + " started for " + ref_time,
                "file 10mwind_" + ref_time + ".nc ready",
                "file seaice_" + ref_time + ".nc ready",
                self.name + " finished for " + ref_time
                ])
       
 
#----------------------------------------------------------------------
class globalwave( task_base ):

    name = "globalwave"
    valid_hours = [ 0 ]

    def __init__( self, ref_time, initial_state ):

        task_base.__init__( self, ref_time, initial_state )
        # note: base class init may adjust ref_time!
        ref_time = self.ref_time


        self.prerequisites = requisites([ 
                "file 10mwind_" + ref_time + ".nc ready",
                "file seaice_" + ref_time + ".nc ready" ])

        self.postrequisites = requisites([
                self.name + " started for " + ref_time,
                "file globalwave_" + ref_time + ".nc ready",
                self.name + " finished for " + ref_time
                ])
        
    
#----------------------------------------------------------------------
class nzwave( task_base ):
    
    name = "nzwave"
    valid_hours = [ 0, 6, 12, 18 ]

    def __init__( self, ref_time, initial_state ):

        task_base.__init__( self, ref_time, initial_state )
        # note: base class init may adjust ref_time!
        ref_time = self.ref_time

        self.prerequisites = requisites([ 
                 "file sls_" + ref_time + ".nc ready" ])

        self.postrequisites = requisites([
                self.name + " started for " + ref_time,
                "file nzwave_" + ref_time + ".nc ready",
                self.name + " finished for " + ref_time
                ])
        

#----------------------------------------------------------------------
class ricom( task_base ):
    
    name = "ricom"
    valid_hours = [ 6, 18 ]

    def __init__( self, ref_time, initial_state ):

        task_base.__init__( self, ref_time, initial_state )
        # note: base class init may adjust ref_time!
        ref_time = self.ref_time

        self.prerequisites = requisites([ 
                 "file sls_" + ref_time + ".nc ready" ])

        self.postrequisites = requisites([
                self.name + " started for " + ref_time,
                "file ricom_" + ref_time + ".nc ready",
                self.name + " finished for " + ref_time
                ])
        

#----------------------------------------------------------------------
class mos( task_base ):
    
    name = "mos"
    valid_hours = [ 0, 6, 12, 18 ]

    def __init__( self, ref_time, initial_state ):

        task_base.__init__( self, ref_time, initial_state )
        # note: base class init may adjust ref_time!
        ref_time = self.ref_time

        hour = ref_time[8:10]

        if hour == "06" or hour == "18":
            self.prerequisites = requisites([ 
                "file met_" + ref_time + ".nc ready"
                ])
        else:
            self.prerequisites = requisites([])

        self.postrequisites = requisites([
                self.name + " started for " + ref_time,
                "file mos_" + ref_time + ".nc ready",
                self.name + " finished for " + ref_time
                ])
        

#----------------------------------------------------------------------
class nztide( task_base ):
    
    name = "nztide"
    valid_hours = [ 6, 18 ]

    def __init__( self, ref_time, initial_state ):

        task_base.__init__( self, ref_time, initial_state )
        # note: base class init may adjust ref_time!
        ref_time = self.ref_time

        # artificial prerequisite to stop nztide running ahead
        self.prerequisites = requisites([
                "downloader started for " + ref_time ])

        self.postrequisites = requisites([
                self.name + " started for " + ref_time,
                "file nztide_" + ref_time + ".nc ready",
                self.name + " finished for " + ref_time
                ])
        

#----------------------------------------------------------------------
class topnet( task_base ):
 
    name = "topnet"
    valid_hours = range( 0,24 )

    def __init__( self, ref_time, initial_state ):

        task_base.__init__( self, ref_time, initial_state )
        # note: base class init may adjust ref_time!
        ref_time = self.ref_time

        nzlam_cutoff = reference_time.decrement( ref_time, 24 )
 
        # fuzzy prequisites: nzlam 24 hours old or less
        self.prerequisites = fuzzy_requisites([ 
                "file tn_" + nzlam_cutoff + ".nc ready" ])

        self.postrequisites = requisites([ 
                self.name + " started for " + ref_time,
                "file topnet_" + ref_time + ".nc ready",
                self.name + " finished for " + ref_time
                ])

    def run( self ):
        # RUN THE EXTERNAL TASK AS A SEPARATE PROCESS
        # TO DO: the subprocess module might be better than os.system?

        # for topnet, supply name of most recent nzlam file from the
        # sharpened fuzzy prerequisite

        prereqs = self.prerequisites.get_list()
        prereq = prereqs[0]
        m = re.compile( "^file (.*) ready$" ).match( prereq )
        [ file ] = m.groups()

        self.log.debug( "RUNNING [task_dummy.py " + self.name + " " + self.ref_time + " " + file + "]" )
        os.system( "./task_dummy.py " + self.name + " " + self.ref_time + "&" )
        self.state = "running"


#----------------------------------------------------------------------
class nwpglobal( task_base ):

    name = "nwpglobal"
    valid_hours = [ 0 ]

    def __init__( self, ref_time, initial_state ):

        task_base.__init__( self, ref_time, initial_state )
        # note: base class init may adjust ref_time!
        ref_time = self.ref_time

        self.prerequisites = requisites([ 
                 "file 10mwind_" + ref_time + ".um ready" ])

        self.postrequisites = requisites([
                self.name + " started for " + ref_time,
                "file 10mwind_" + ref_time + ".nc ready",
                self.name + " finished for " + ref_time
                ])
