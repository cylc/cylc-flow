#!/usr/bin/python

"""Task class definitions for running topnet on /test off the
operational nzlam output. The initial task, with no prequisites, is now
oper2test_topnet which waits on and copies back the operational tn netcdf
when ready.  Topnet's behaviour with respect to oper2test_topnet must be
the same as it is to nzlam_post in the operational system."""

from task_base import *
from dummy_task_base import *

import reference_time
from requisites import requisites, timed_requisites, fuzzy_requisites
from time import sleep

import os
import re
import sys
from copy import deepcopy
from time import strftime
import Pyro.core

from config import dummy_mode, dummy_clock_rate

import logging
import logging.handlers

# task classes 'normal', 'free', and topnet_foo exist entirely so we can
# override run_external_dummy in this module, so I can determine the
# module's name and execute the module file to run the module-specific
# dummy tasks. There is probably a better way to do this!

#----------------------------------------------------------------------
class normal ( task_base ):
        
    def run_external_dummy( self ):
        self.log.info( "launching external dummy for " + self.ref_time )
        os.system( './' + __name__ + '.py ' + self.name + " " + self.ref_time + " &" )
        self.state = "running"

#----------------------------------------------------------------------
class free ( free_task_base ):
 
    def run_external_dummy( self ):
        self.log.info( "launching external dummy for " + self.ref_time )
        os.system( './' + __name__ + '.py ' + self.name + " " + self.ref_time + " &" )
        self.state = "running"

#----------------------------------------------------------------------
class topnet_foo ( topnet_base ):
 
    def run_external_dummy( self ):
        self.log.info( "launching external dummy for " + self.ref_time )
        os.system( './' + __name__ + '.py ' + self.name + " " + self.ref_time + " &" )
        self.state = "running"

#----------------------------------------------------------------------
class oper2test_topnet( free ):

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

        free.__init__( self, ref_time, initial_state )

#----------------------------------------------------------------------
class topnet( topnet_foo ):
    "streamflow data extraction and topnet" 

    """If no other tasks dependend on the streamflow data then it's
    easiest to make streamflow part of the topnet task, because of
    the unusual runahead behavior of topnet"""

    # topnet is not a "free" task, it has prerequisites.
 
    name = "topnet"
    valid_hours = range( 0,24 )

    # assume catchup mode and detect if we've caught up
    catchup_mode = True
    # (SHOULD THIS BE BASED ON TOPNET OR DOWNLOADER?)

    fuzzy_file_re =  re.compile( "^file (.*) ready$" )

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
            [4, "file topnet_" + ref_time + "_utc_nzlam_12.nc ready"],
            [5, self.name + " finished for " + ref_time] ])

        topnet_foo.__init__( self, ref_time, initial_state )


    def run_external_dummy( self ):
        # RUN THE EXTERNAL TASK AS A SEPARATE PROCESS
        # TO DO: the subprocess module might be better than os.system?

        # for topnet, supply name of most recent nzlam file from the
        # sharpened fuzzy prerequisite

        prereqs = self.prerequisites.get_list()
        prereq = prereqs[0]
        m = topnet.fuzzy_file_re.match( prereq )
        [ file ] = m.groups()

        self.log.info( "launching external dummy for " + self.ref_time + " (off " + file + ")" )
        os.system( './' + __name__ + '.py ' + self.name + " " + self.ref_time + " &" )
        self.state = "running"


    def incoming( self, priority, message ):

        # pass on to the base class message handling function
        topnet_foo.incoming( self, priority, message)
        
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

#----------------------------------------------------------------------
class dummy_task( dummy_task_base ):

    def delay( self ):
        if not dummy_mode:
            return

        if self.task_name == "oper2test_topnet":

            rt = reference_time._rt_to_dt( self.ref_time )
            delayed_start = rt + datetime.timedelta( 0,0,0,0,0,4.5,0 )  # 4.5 hours 
            if self.clock.get_datetime() >= delayed_start:
                self.task.incoming( 'NORMAL', 'CATCHUP: operational tn file already exists for ' + self.ref_time )
                self.fast_complete = True
            else:
                self.task.incoming( 'NORMAL', 'UPTODATE: waiting for operational tn file for ' + self.ref_time )
                while True:
                    sleep(1)
                    if self.clock.get_datetime() >= delayed_start:
                        break

        elif self.task_name == "topnet":

            rt = reference_time._rt_to_dt( self.ref_time )
            rt_p25 = rt + datetime.timedelta( 0,0,0,0,0,0.25,0 ) # 15 min past the hour
            # THE FOLLOWING MESSAGES MUST MATCH THOSE IN topnet.incoming()
            if self.clock.get_datetime() >= rt_p25:
                self.task.incoming( 'NORMAL', 'CATCHUP: streamflow data available, for ' + self.ref_time )
            else:
                self.task.incoming( 'NORMAL', 'UPTODATE: waiting for streamflow, for ' + self.ref_time ) 
                while True:
                    sleep(1)
                    if self.clock.get_datetime() >= rt_p25:
                        break

#----------------------------------------------------------------------
if __name__ == '__main__':
    [ task_name, ref_time ] = sys.argv[1:]

    dummy = dummy_task( task_name, ref_time )
    dummy.run()
