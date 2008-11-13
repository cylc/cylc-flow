#!/usr/bin/python

# operational task class definitions

from task_base import task_base, simple_task, free_task
import job_submit

import reference_time
from requisites import requisites, timed_requisites, fuzzy_requisites
from time import sleep

import os, sys, re
from copy import deepcopy
from time import strftime
import Pyro.core
import logging

#----------------------------------------------------------------------
class downloader( free_task ):
    "Met Office input file download task"

    """
    This task provides initial input to get things going: it starts
    running immediately and it completes when its outputs are ready
    for use by downstream tasks.
    """

    name = "downloader"
    valid_hours = [ 0, 6, 12, 18 ]
    external_task = 'downloader.sh' 
    user_prefix = 'ecoconnect'

    def __init__( self, ref_time, initial_state ):
 
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
 
        free_task.__init__( self, ref_time, initial_state )
           
#----------------------------------------------------------------------
class nzlam( task_base ):

    name = "nzlam"
    valid_hours = [ 0, 6, 12, 18 ]
    external_task = 'nzlam.sh'
    user_prefix = 'nwp'

    def __init__( self, ref_time, initial_state ):

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
                [110, "file tn_"  + ref_time + "_utc_nzlam_12.um ready"],
                [111, "file sls_" + ref_time + "_utc_nzlam_12.um ready"],   
                [112, "file met_" + ref_time + "_utc_nzlam_12.um ready"],
                [115, self.name + " finished for " + ref_time] ])

        task_base.__init__( self, ref_time, initial_state )

#----------------------------------------------------------------------
class nzlam_post_06_18( task_base ):

    name = "nzlam_post_06_18"
    valid_hours = [ 6, 18 ]
    external_task = 'nzlam_post.sh'
    user_prefix = 'nwp'
    quick_death = False

    def __init__( self, ref_time, initial_state ):

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time

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
class nzlam_post_00_12( task_base ):

    name = "nzlam_post_00_12"
    valid_hours = [ 0, 12 ]
    external_task = 'nzlam_post.sh'
    user_prefix = 'nwp'

    def __init__( self, ref_time, initial_state ):

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time

        self.prerequisites = requisites( self.name, [ 
            "file sls_" + ref_time + "_utc_nzlam_12.um ready" ])

        self.postrequisites = timed_requisites( self.name, [
            [0, self.name + " started for " + ref_time],
            [10, "file sls_" + ref_time + "_utc_nzlam_12.nc ready"],   
            [11, self.name + " finished for " + ref_time] ])

        task_base.__init__( self, ref_time, initial_state )

#----------------------------------------------------------------------
class global_prep( task_base ):

    name = "global_prep"
    valid_hours = [ 0 ]
    external_task = 'global_prep.sh'
    user_prefix = 'wave'

    def __init__( self, ref_time, initial_state ):

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
    external_task = 'globalwave.sh'
    user_prefix = 'wave'

    def __init__( self, ref_time, initial_state ):

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
    external_task = 'nzwave.sh'
    user_prefix = 'wave'

    def __init__( self, ref_time, initial_state ):

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time
 
        hour = ref_time[8:10]

        self.prerequisites = requisites( self.name, [ 
            "file sls_" + ref_time + "_utc_nzlam_12.nc ready" ])

        self.postrequisites = timed_requisites( self.name, [
            [0, self.name + " started for " + ref_time],
            [110, "processing finished"],
            [112, self.name + " finished for " + ref_time] ])
 
        task_base.__init__( self, ref_time, initial_state )
       
#----------------------------------------------------------------------
class ricom( task_base ):

    name = "ricom"
    valid_hours = [ 6, 18 ]
    external_task = 'ricom.sh'
    user_prefix = 'sea_level'

    def __init__( self, ref_time, initial_state ):

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time
 
        self.prerequisites = requisites( self.name, [ 
            "file sls_" + ref_time + "_utc_nzlam_12.nc ready" ])

        self.postrequisites = timed_requisites( self.name, [
            [0, self.name + " started for " + ref_time],
            [30, "processing finished"],
            [31, self.name + " finished for " + ref_time] ])
 
        task_base.__init__( self, ref_time, initial_state )
       
#----------------------------------------------------------------------
class mos( task_base ):

    name = "mos"
    valid_hours = [ 6, 18 ]
    external_task = 'mos.sh'
    user_prefix = 'nwp'

    def __init__( self, ref_time, initial_state ):

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time
 
        hour = ref_time[8:10]

        self.prerequisites = requisites( self.name, [ 
            "file met_" + ref_time + "_utc_nzlam_12.nc ready" ])

        self.postrequisites = timed_requisites( self.name, [
            [0, self.name + " started for " + ref_time],
            [5, "processing done"],
            [6, self.name + " finished for " + ref_time] ])

        task_base.__init__( self, ref_time, initial_state )

#----------------------------------------------------------------------
class nztide( free_task ):

    name = "nztide"
    valid_hours = [ 6, 18 ]
    external_task = 'nztide.sh'
    user_prefix = 'sea_level'

    def __init__( self, ref_time, initial_state ):

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time
 
        self.prerequisites = requisites( self.name, [])

        self.postrequisites = timed_requisites( self.name, [
            [0, self.name + " started for " + ref_time],
            [1, "file nztide_" + ref_time + ".nc ready"],
            [2, self.name + " finished for " + ref_time] ])

        free_task.__init__( self, ref_time, initial_state )

#----------------------------------------------------------------------
class streamflow( free_task ):

    name = "streamflow"
    valid_hours = range( 0, 24 )
    external_task = 'streamflow.sh'
    user_prefix = 'hydrology'

    # assume catchup mode and detect if we've caught up
    catchup_mode = True

    def __init__( self, ref_time, initial_state ):

        self.catchup_re = re.compile( "^CATCHUP:.*for " + ref_time )
        self.uptodate_re = re.compile( "^UPTODATE:.*for " + ref_time )

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time
 
        self.prerequisites = requisites( self.name, [])

        self.postrequisites = timed_requisites( self.name, [
            [0, self.name + " started for " + ref_time],
            [5, "got streamflow data for " + ref_time ],
            [5.1, self.name + " finished for " + ref_time] ])

        free_task.__init__( self, ref_time, initial_state )

        # NEED TO ALLOW FINISHED TASKS BACK TO THE TASK DELETION CUTOFF
        # Do this AFTER parent class init, which sets to the default
        if streamflow.catchup_mode == True:
            self.MAX_FINISHED = 13
        else:
            self.MAX_FINISHED = 25


    def incoming( self, priority, message ):

        # pass on to the base class message handling function
        task_base.incoming( self, priority, message)
        
        # but intercept messages that indicate we're in catchup mode
        if not streamflow.catchup_mode and self.catchup_re.match( message ):
            #message == "CATCHUP: " + self.ref_time:
            streamflow.catchup_mode = True
            # WARNING: SHOULDN'T GO FROM UPTODATE TO CATCHUP?
            self.log.warning( "beginning CATCHUP operation" )

        elif streamflow.catchup_mode and self.uptodate_re.match( message ):
            #message == "UPTODATE: " + self.ref_time:
            streamflow.catchup_mode = False
            self.log.info( "beginning UPTODATE operation" )

#----------------------------------------------------------------------
class oper2test_topnet( free_task ):

    name = "oper2test_topnet"
    valid_hours = [ 6, 18 ]
    external_task = 'oper2test_topnet.sh' 
    user_prefix = 'hydrology'

    def __init__( self, ref_time, initial_state ):

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time

        hour = ref_time[8:10]

        self.prerequisites = requisites( self.name, []) 
        
        self.postrequisites = timed_requisites( self.name, [ 
                [0, self.name + " started for " + ref_time],
                [2, "file tn_" + ref_time + "_utc_nzlam_12.nc ready"],
                [3, self.name + " finished for " + ref_time] ])

        free_task.__init__( self, ref_time, initial_state )

#----------------------------------------------------------------------
class topnet( task_base ):
    "run hourly topnet off most recent nzlam input" 

    # topnet is not a "free_task task" -- it has prerequisites.
 
    name = "topnet"
    valid_hours = range( 0,24 )
    external_task = 'topnet_run.sh'
    user_prefix = 'hydrology'

    fuzzy_file_re =  re.compile( "^file (.*) ready$" )
    reftime_re = re.compile( "\d{10}")

    def __init__( self, ref_time, initial_state ):

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time
 
        if streamflow.catchup_mode:
            #print "CUTOFF 11 for " + self.name + "%" + ref_time
            nzlam_cutoff = reference_time.decrement( ref_time, 11 )
        else:
            #print "CUTOFF 23 for " + self.name + "%" + ref_time
            nzlam_cutoff = reference_time.decrement( ref_time, 23 )

        # min:max
        fuzzy_limits = nzlam_cutoff + ':' + ref_time
 
        self.prerequisites = fuzzy_requisites( self.name, [ 
            "got streamflow data for " + ref_time + ':' + ref_time, 
            "file tn_" + fuzzy_limits + "_utc_nzlam_12.nc ready" ])

        self.postrequisites = timed_requisites( self.name, [ 
            [3, self.name + " started for " + ref_time],
            [6, self.name + " finished for " + ref_time] ])

        task_base.__init__( self, ref_time, initial_state )


    def run_external_task( self ):
        # topnet needs to be given the time of the netcdf file that
        # satisfied satisified the topnet fuzzy prerequisite

        # assumes the nzlam prereq is the second one
        # (TO DO: search for 'nzlam' in the list of prereqs)
        prereqs = self.prerequisites.get_list()
        prereq = prereqs[1]
        m = topnet.fuzzy_file_re.match( prereq )
        [ file ] = m.groups()
        m = topnet.reftime_re.search( file )
        nzlam_time = m.group()

        extra_vars = [ ['NZLAM_TIME', nzlam_time ] ]
        task_base.run_external_task( self, extra_vars )


    def get_cutoff( self, all_tasks ):

        # keep the most recent *finished* nzlam_post_06_18 or
        # oper2test_topnet task that is OLDER THAN ME, because the next
        # hourly topnet may also need the output from that same
        # 12-hourly task.

        # note that this could be down without searching for actual
        # 'nzlam_post_06_18' or 'oper2test_topnet' tasks because we know how 
        # far ahead topnet is allowed to get, depending on catchup.

        found = False
        times = []

        result = self.ref_time # default

        for task in all_tasks:
            if task.name == 'nzlam_post_06_18' or task.name == 'oper2test_topnet':
                if task.state == 'finished':
                    found = True
                    times.append( task.ref_time )
        if not found: 
            # This could mean the task is lame, in which case it will
            # be eliminated by lame task deletion in the main program.

            # Or, more likely, at start up, the first nzlam_post_06_18
            # just hasn't finished yet.

            pass

        else:
            times.sort( key = int, reverse = True )
            for time in times:
                if int( time ) < int( self.ref_time ):
                    self.log.debug( self.identity + ' cutoff: ' + time )
                    result = time
                    break

        return result

#----------------------------------------------------------------------
class topnet_vis( simple_task ):

    name = "topnet_vis"
    valid_hours = range( 0,24 )
    external_task = 'topnet_vis.sh'
    user_prefix = 'hydrology'

    def __init__( self, ref_time, initial_state ):

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time

        self.prerequisites = requisites( self.name, [ 
            "topnet finished for " + ref_time  ])

        simple_task.__init__( self, ref_time, initial_state, est_run_time = 3 )

#----------------------------------------------------------------------
class topnet_products( simple_task ):

    name = "topnet_products"
    valid_hours = range( 0,24 )
    external_task = 'product_gen.sh'
    user_prefix = 'hydrology'
    env_vars = [ ['MODEL_NAME', 'topnet' ] ]  # needed by external task

    def __init__( self, ref_time, initial_state ):

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time

        self.prerequisites = requisites( self.name, [ 
            "topnet_vis finished for " + ref_time  ])

        simple_task.__init__( self, ref_time, initial_state, est_run_time = 2 )

    def run_external_task( self ):
        task_base.run_external_task( self, topnet_products.env_vars )

#----------------------------------------------------------------------
class nwp_global( task_base ):

    name = "nwp_global"
    valid_hours = [ 0 ]
    external_task = 'nwp_global.sh'
    user_prefix = 'nwp'

    def __init__( self, ref_time, initial_state ):

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

