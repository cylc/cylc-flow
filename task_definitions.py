#!/usr/bin/python

# Task names must not contain underscores. 
# The 'name' attribute, not the class name itself(?), that is.

from task_base import task_base
import reference_time
from requisites import requisites

import os
import Pyro.core
from copy import deepcopy

all_task_names = [ 'downloader', 'nwpglobal', 'globalprep', 'globalwave',
                   'nzlam', 'nzlampost', 'nzwave', 'ricom', 'nztide', 
                   'topnet', 'mos' ]

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


class topnet( task_base ):
 
    name = "topnet"
    ref_time_increment = 12
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
