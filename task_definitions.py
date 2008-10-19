#!/usr/bin/python

# operational task class definitions

from task_base import *

import reference_time
from requisites import requisites, timed_requisites, fuzzy_requisites
from time import sleep

import os
import re
import sys
from copy import deepcopy
from time import strftime
import Pyro.core

import logging
import logging.handlers

#----------------------------------------------------------------------
class downloader( free_task_base ):
    "Met Office input file download task"

    """
    This task provides initial input to get things going: it starts
    running immediately and it completes when its outputs are ready
    for use by downstream tasks.
    """

    name = "downloader"
    valid_hours = [ 0, 6, 12, 18 ]

    def __init__( self, ref_time, initial_state = "waiting" ):
 
        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time
       
        hour = ref_time[8:10]

        # no prerequisites: this is The Initial Task
        self.prerequisites = requisites( self.name, [])

        lbc_06 = reference_time.decrement( ref_time, 6 )
        lbc_12 = reference_time.decrement( ref_time, 12 )

        if hour == "00":

            self.postrequisites = timed_requisites( self.name, [ 
                [0, self.name + " started for " + ref_time],
                [0.5, "file obstore_" + ref_time + ".um ready"],
                [1, "file bgerr" + ref_time + ".um ready"], 
                [106, "file lbc_" + lbc_12 + ".um ready"], 
                [122, "file 10mwind_" + ref_time + ".um ready"],
                [122.5, "file seaice_" + ref_time + ".um ready"],
                [199, "file dump_" + ref_time + ".um ready"], 
                [200, self.name + " finished for " + ref_time] ])

        elif hour == "12":

            self.postrequisites = timed_requisites( self.name, [ 
                [0, self.name + " started for " + ref_time],
                [0.5, "file obstore_" + ref_time + ".um ready"],
                [1, "file bgerr" + ref_time + ".um ready"], 
                [97, "file lbc_" + lbc_12 + ".um ready"],
                [98, self.name + " finished for " + ref_time] ])

        if hour == "06" or hour == "18":

            self.postrequisites = timed_requisites( self.name, [
                [0, self.name + " started for " + ref_time],
                [0, "file lbc_" + lbc_06 + ".um ready"],
                [0.5, "file obstore_" + ref_time + ".um ready"],
                [1, "file bgerr" + ref_time + ".um ready"],
                [2, self.name + " finished for " + ref_time] ])
 
        free_task_base.__init__( self, ref_time, initial_state )
           
#----------------------------------------------------------------------
class oper2test_topnet( free_task_base ):

    name = "oper2test_topnet"
    valid_hours = [ 6, 18 ]
    external_task = 'oper2test_topnet.sh' 
    #user_prefix = 'hydrology'
    user_prefix = 'ecoconnect'

    def __init__( self, ref_time, initial_state = "waiting" ):

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time

        hour = ref_time[8:10]

        self.prerequisites = requisites( self.name, []) 
        
        self.postrequisites = timed_requisites( self.name, [ 
                [0, self.name + " started for " + ref_time],
                [2, "file tn_" + ref_time + "_utc_nzlam_12.nc ready"],
                [3, self.name + " finished for " + ref_time] ])

        free_task_base.__init__( self, ref_time, initial_state )

#----------------------------------------------------------------------
class nzlam( task_base ):

    name = "nzlam"
    valid_hours = [ 0, 6, 12, 18 ]

    def __init__( self, ref_time, initial_state = "waiting" ):

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time
 
        hour = ref_time[8:10]

        lbc_06 = reference_time.decrement( ref_time, 6 )
        lbc_12 = reference_time.decrement( ref_time, 12 )

        if hour == "00" or hour == "12":
            self.prerequisites = requisites( self.name, [ 
                "file obstore_" + ref_time + ".um ready",
                "file bgerr" + ref_time + ".um ready",
                "file lbc_" + lbc_12 + ".um ready" ])

            self.postrequisites = timed_requisites( self.name, [ 
                [0, self.name + " started for " + ref_time],
                [30, "file sls_" + ref_time + "_utc_nzlam_12.um ready"],   
                [32, self.name + " finished for " + ref_time] ])
 
        elif hour == "06" or hour == "18":
            self.prerequisites = requisites( self.name, [ 
                "file obstore_" + ref_time + ".um ready",
                "file bgerr" + ref_time + ".um ready",
                "file lbc_" + lbc_06 + ".um ready" ])

            self.postrequisites = timed_requisites( self.name, [ 
                [0, self.name + " started for " + ref_time],
                [110, "file tn_" + ref_time + "_utc_nzlam_12.um ready"],
                [111, "file sls_" + ref_time + "_utc_nzlam_12.um ready"],   
                [112, "file met_" + ref_time + "_utc_nzlam_12.um ready"],
                [115, self.name + " finished for " + ref_time] ])

        task_base.__init__( self, ref_time, initial_state )

#----------------------------------------------------------------------
class nzlam_post( task_base ):

    name = "nzlam_post"
    valid_hours = [ 0, 6, 12, 18 ]

    def __init__( self, ref_time, initial_state = "waiting" ):

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time

        hour = ref_time[8:10]

        if hour == "00" or hour == "12":
            
            self.prerequisites = requisites( self.name, [ 
                "file sls_" + ref_time + ".um ready" ])

            self.postrequisites = timed_requisites( self.name, [
                [0, self.name + " started for " + ref_time],
                [10, "file sls_" + ref_time + ".nc ready"],   
                [11, self.name + " finished for " + ref_time] ])

        elif hour == "06" or hour == "18":

            self.prerequisites = requisites( self.name, [ 
                "file tn_" + ref_time + "_utc_nzlam_12.um ready",
                "file sls_" + ref_time + "_utc_nzlam_12.um ready",   
                "file met_" + ref_time + "_utc_nzlam_12.um ready" ])

            self.postrequisites = timed_requisites( self.name, [ 
                [0, self.name + " started for " + ref_time],
                [10, "file sls_" + ref_time + "_utc_nzlam_12.nc ready"],   
                [20, "file tn_" + ref_time + "_utc_nzlam_12.nc ready"],
                [30, "file met_" + ref_time + "_utc_nzlam_12.nc ready"],
                [31, self.name + " finished for " + ref_time] ])

        task_base.__init__( self, ref_time, initial_state )

#----------------------------------------------------------------------
class globalprep( task_base ):

    name = "globalprep"
    valid_hours = [ 0 ]

    def __init__( self, ref_time, initial_state = "waiting" ):

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time

        hour = ref_time[8:10]

        self.prerequisites = requisites( self.name, [ 
            "file 10mwind_" + ref_time + ".um ready",
            "file seaice_" + ref_time + ".um ready" ])

        self.postrequisites = timed_requisites( self.name, [
            [0, self.name + " started for " + ref_time],
            [5, "file 10mwind_" + ref_time + ".nc ready"],
            [7, "file seaice_" + ref_time + ".nc ready"],
            [10, self.name + " finished for " + ref_time] ])
       
        task_base.__init__( self, ref_time, initial_state )

#----------------------------------------------------------------------
class globalwave( task_base ):

    name = "globalwave"
    valid_hours = [ 0 ]

    def __init__( self, ref_time, initial_state = "waiting" ):

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time
 
        self.prerequisites = requisites( self.name, [ 
            "file 10mwind_" + ref_time + ".nc ready",
            "file seaice_" + ref_time + ".nc ready" ])

        self.postrequisites = timed_requisites( self.name, [
            [0, self.name + " started for " + ref_time],
            [120, "file globalwave_" + ref_time + ".nc ready"],
            [121, self.name + " finished for " + ref_time] ])
 
        task_base.__init__( self, ref_time, initial_state )
       
#----------------------------------------------------------------------
class nzwave( task_base ):
    
    name = "nzwave"
    valid_hours = [ 0, 6, 12, 18 ]

    def __init__( self, ref_time, initial_state = "waiting" ):

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time
 
        hour = ref_time[8:10]

        self.prerequisites = requisites( self.name, [ 
            "file sls_" + ref_time + ".nc ready" ])

        self.postrequisites = timed_requisites( self.name, [
            [0, self.name + " started for " + ref_time],
            [110, "file nzwave_" + ref_time + ".nc ready"],
            [112, self.name + " finished for " + ref_time] ])
 
        task_base.__init__( self, ref_time, initial_state )
       
#----------------------------------------------------------------------
class ricom( task_base ):

    name = "ricom"
    valid_hours = [ 6, 18 ]

    def __init__( self, ref_time, initial_state = "waiting" ):

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time
 
        self.prerequisites = requisites( self.name, [ 
            "file sls_" + ref_time + ".nc ready" ])

        self.postrequisites = timed_requisites( self.name, [
            [0, self.name + " started for " + ref_time],
            [30, "file ricom_" + ref_time + ".nc ready"],
            [31, self.name + " finished for " + ref_time] ])
 
        task_base.__init__( self, ref_time, initial_state )
       
#----------------------------------------------------------------------
class mos( task_base ):

    name = "mos"
    valid_hours = [ 0, 6, 12, 18 ]

    def __init__( self, ref_time, initial_state = "waiting" ):

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time
 
        hour = ref_time[8:10]

        if hour == "06" or hour == "18":
            self.prerequisites = requisites( self.name, [ 
                "file met_" + ref_time + "_utc_nzlam_12.nc ready" ])
        else:
            self.prerequisites = requisites( self.name, [])

        self.postrequisites = timed_requisites( self.name, [
            [0, self.name + " started for " + ref_time],
            [5, "processing done"],
            [6, self.name + " finished for " + ref_time] ])

        task_base.__init__( self, ref_time, initial_state )

#----------------------------------------------------------------------
class nztide( free_task_base ):

    name = "nztide"
    valid_hours = [ 6, 18 ]

    def __init__( self, ref_time, initial_state = "waiting" ):

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time
 
        self.prerequisites = requisites( self.name, [])

        self.postrequisites = timed_requisites( self.name, [
            [0, self.name + " started for " + ref_time],
            [1, "file nztide_" + ref_time + ".nc ready"],
            [2, self.name + " finished for " + ref_time] ])

        free_task_base.__init__( self, ref_time, initial_state )

#----------------------------------------------------------------------
class topnet( task_base ):
    "streamflow data extraction and topnet" 

    """If no other tasks dependend on the streamflow data then it's
    easiest to make streamflow part of the topnet task, because of
    the unusual runahead behavior of topnet"""

    # topnet is not a "free_task_base task" -- it has prerequisites.
 
    name = "topnet"
    valid_hours = range( 0,24 )

    # assume catchup mode and detect if we've caught up
    catchup_mode = True
    # (SHOULD THIS BE BASED ON TOPNET OR DOWNLOADER?)

    fuzzy_file_re =  re.compile( "^file (.*) ready$" )

    #    def run_external_task( self ):
    #        print "TEMPORARILY DUMMYING OUT THE REAL TOPNET"
    #        self.run_external_dummy()

    def __init__( self, ref_time, initial_state = "waiting" ):

        self.catchup_re = re.compile( "^CATCHUP:.*for " + ref_time )
        self.uptodate_re = re.compile( "^UPTODATE:.*for " + ref_time )

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time
 
        if topnet.catchup_mode:
            #print "CUTOFF 11 for " + self.identity
            nzlam_cutoff = reference_time.decrement( ref_time, 11 )
        else:
            #print "CUTOFF 23 for " + self.identity
            nzlam_cutoff = reference_time.decrement( ref_time, 23 )

        # min:max
        fuzzy_limits = nzlam_cutoff + ':' + ref_time
 
        self.prerequisites = fuzzy_requisites( self.name, [ 
            "file tn_" + fuzzy_limits + "_utc_nzlam_12.nc ready" ])

        self.postrequisites = timed_requisites( self.name, [ 
            [0, "streamflow extraction started for " + ref_time],
            [2, "got streamflow data for " + ref_time],
            [2.1, "streamflow extraction finished for " + ref_time],
            [3, self.name + " started for " + ref_time],
            [4, "catchment forecasts finished"],
            [5, self.name + " finished for " + ref_time] ])

        task_base.__init__( self, ref_time, initial_state )


    def run_external_dummy( self ):
        # RUN THE EXTERNAL TASK AS A SEPARATE PROCESS
        # topnet (external) needs to be given the name of the netcdf
        # file that satisfied satisified the topnet fuzzy prerequisite

        prereqs = self.prerequisites.get_list()
        prereq = prereqs[0]
        m = topnet.fuzzy_file_re.match( prereq )
        [ file ] = m.groups()

        self.log.info( "launching external dummy for " + self.ref_time + " (off " + file + ")" )
        os.system( './dummy_task.py ' + self.name + " " + self.ref_time + " &" )
        self.state = "running"


    def incoming( self, priority, message ):

        # pass on to the base class message handling function
        task_base.incoming( self, priority, message)
        
        # but intercept catchup mode messages
        if not topnet.catchup_mode and self.catchup_re.match( message ):
            #message == "CATCHUP: " + self.ref_time:
            topnet.catchup_mode = True
            # WARNING: SHOULDN'T GO FROM UPTODATE TO CATCHUP?
            self.log.warning( "beginning CATCHUP operation" )

        elif topnet.catchup_mode and self.uptodate_re.match( message ):
            #message == "UPTODATE: " + self.ref_time:
            topnet.catchup_mode = False
            self.log.info( "beginning UPTODATE operation" )


    def oldest_to_keep( self, all_tasks ):

        if self.state == 'finished':
            return None

        # keep the most recent non-waiting 06 or 18Z nzlam_post or
        # oper2test_topnet task, because the next hourly topnet may 
        # also need the output from that same 12-hourly task.

        # note that this could be down without searching for actual
        # 'nzlam_post' or 'oper2test_topnet' tasks because we know how 
        # for ahead topnet is allowed to get, depending on catchup.

        found = False
        times = []
        result = None
        for task in all_tasks:
            if task.name == 'nzlam_post' or task.name == 'oper2test_topnet':
                if task.state != 'waiting':
                    hour = task.ref_time[8:10]
                    if hour == '06' or hour == '18':
                        found = True
                        times.append( task.ref_time )
        if not found: 
            #self.log.debug( 'no upstream task found: I am a dead soldier' )
            pass
            # will be eliminated by the main program dead soldier check

        else:
            times.sort( key = int, reverse = True )
            for time in times:
                if int( time ) < int( self.ref_time ):
                    self.log.debug( 'most recent non-waiting upstream task: ' + time )
                    result = time
                    break

        return result

#----------------------------------------------------------------------
class nwpglobal( task_base ):

    name = "nwpglobal"
    valid_hours = [ 0 ]

    def __init__( self, ref_time, initial_state = "waiting" ):

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time
 
        self.prerequisites = requisites( self.name, [ 
            "file 10mwind_" + ref_time + ".um ready" ])

        self.postrequisites = timed_requisites( self.name, [
            [0, self.name + " started for " + ref_time],
            [120, "file 10mwind_" + ref_time + ".nc ready"],
            [121, self.name + " finished for " + ref_time] ])

        task_base.__init__( self, ref_time, initial_state )


