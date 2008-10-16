#!/usr/bin/python

"""operational task class definitions"""

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

# task classes 'normal' and 'free' exist entirely so we can override
# run_external_dummy in this module, so I can determine the module's
# name and execute the module file to run the module-specific dummy
# tasks. There is probably a better way to do this!

#----------------------------------------------------------------------
class normal ( task_base ):

    def __init__( self, ref_time, initial_state = 'waiting' ):
        task_base.__init__( self, ref_time, initial_state = 'waiting' )
        
    def run_external_dummy( self, dummy_clock_rate ):
        # RUN THE EXTERNAL TASK AS A SEPARATE PROCESS
        self.log.info( "launching external dummy for " + self.ref_time )
        os.system( './' + __name__ + '.py ' + self.name + " " + self.ref_time + " " + str(dummy_clock_rate) + " &" )
        self.state = "running"

#----------------------------------------------------------------------
class free ( free_task_base ):

    def __init__( self, ref_time, initial_state = 'waiting' ):
        free_task_base.__init__( self, ref_time, initial_state = 'waiting' )
 
    def run_external_dummy( self, dummy_clock_rate ):
        # RUN THE EXTERNAL TASK AS A SEPARATE PROCESS
        self.log.info( "launching external dummy for " + self.ref_time )
        os.system( './' + __name__ + '.py ' + self.name + " " + self.ref_time + " " + str(dummy_clock_rate) + " &" )
        self.state = "running"

#----------------------------------------------------------------------
class downloader( free ):
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
 
        free.__init__( self, ref_time, initial_state )
           
#----------------------------------------------------------------------
class nzlam( normal ):

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
                [30, "file sls_" + ref_time + ".um ready"],   
                [32, self.name + " finished for " + ref_time] ])
 
        elif hour == "06" or hour == "18":
            self.prerequisites = requisites( self.name, [ 
                "file obstore_" + ref_time + ".um ready",
                "file bgerr" + ref_time + ".um ready",
                "file lbc_" + lbc_06 + ".um ready" ])

            self.postrequisites = timed_requisites( self.name, [ 
                [0, self.name + " started for " + ref_time],
                [110, "file tn_" + ref_time + ".um ready"],
                [111, "file sls_" + ref_time + ".um ready"],   
                [112, "file met_" + ref_time + ".um ready"],
                [115, self.name + " finished for " + ref_time] ])

        normal.__init__( self, ref_time, initial_state )

#----------------------------------------------------------------------
class nzlam_post( normal ):

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
                "file tn_" + ref_time + ".um ready",
                "file sls_" + ref_time + ".um ready",   
                "file met_" + ref_time + ".um ready" ])

            self.postrequisites = timed_requisites( self.name, [ 
                [0, self.name + " started for " + ref_time],
                [10, "file sls_" + ref_time + ".nc ready"],   
                [20, "file tn_" + ref_time + ".nc ready"],
                [30, "file met_" + ref_time + ".nc ready"],
                [31, self.name + " finished for " + ref_time] ])

        normal.__init__( self, ref_time, initial_state )

#----------------------------------------------------------------------
class globalprep( normal ):

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
       
        normal.__init__( self, ref_time, initial_state )

#----------------------------------------------------------------------
class globalwave( normal ):

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
 
        normal.__init__( self, ref_time, initial_state )
       
#----------------------------------------------------------------------
class nzwave( normal ):
    
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
 
        normal.__init__( self, ref_time, initial_state )
       
#----------------------------------------------------------------------
class ricom( normal ):

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
 
        normal.__init__( self, ref_time, initial_state )
       
#----------------------------------------------------------------------
class mos( normal ):

    name = "mos"
    valid_hours = [ 0, 6, 12, 18 ]

    def __init__( self, ref_time, initial_state = "waiting" ):

        # adjust reference time to next valid for this task
        self.ref_time = self.nearest_ref_time( ref_time )
        ref_time = self.ref_time
 
        hour = ref_time[8:10]

        if hour == "06" or hour == "18":
            self.prerequisites = requisites( self.name, [ 
                "file met_" + ref_time + ".nc ready" ])
        else:
            self.prerequisites = requisites( self.name, [])

        self.postrequisites = timed_requisites( self.name, [
            [0, self.name + " started for " + ref_time],
            [5, "file mos_" + ref_time + ".nc ready"],
            [6, self.name + " finished for " + ref_time] ])

        normal.__init__( self, ref_time, initial_state )

#----------------------------------------------------------------------
class nztide( free ):

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

        free.__init__( self, ref_time, initial_state )

#----------------------------------------------------------------------
class topnet( normal ):
    "streamflow data extraction and topnet" 

    """If no other tasks dependend on the streamflow data then it's
    easiest to make streamflow part of the topnet task, because of
    the unusual runahead behavior of topnet"""

    # topnet is not a "free task" -- it has prerequisites.
 
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
            #print "CUTOFF 11 for " + self.identity()
            nzlam_cutoff = reference_time.decrement( ref_time, 11 )
        else:
            #print "CUTOFF 23 for " + self.identity()
            nzlam_cutoff = reference_time.decrement( ref_time, 23 )

        # min:max
        fuzzy_limits = nzlam_cutoff + ':' + ref_time
 
        self.prerequisites = fuzzy_requisites( self.name, [ 
            "file tn_" + fuzzy_limits + ".nc ready" ])

        self.postrequisites = timed_requisites( self.name, [ 
            [0, "streamflow extraction started for " + ref_time],
            [2, "got streamflow data for " + ref_time],
            [2.1, "streamflow extraction finished for " + ref_time],
            [3, self.name + " started for " + ref_time],
            [4, "file topnet_" + ref_time + ".nc ready"],
            [5, self.name + " finished for " + ref_time] ])

        normal.__init__( self, ref_time, initial_state )


    def run_external_dummy( self, dummy_clock_rate ):
        # RUN THE EXTERNAL TASK AS A SEPARATE PROCESS
        # TO DO: the subprocess module might be better than os.system?

        # for topnet, supply name of most recent nzlam file from the
        # sharpened fuzzy prerequisite

        prereqs = self.prerequisites.get_list()
        prereq = prereqs[0]
        m = topnet.fuzzy_file_re.match( prereq )
        [ file ] = m.groups()

        self.log.info( "launching external dummy for " + self.ref_time + " (off " + file + ")" )
        os.system( './' + __name__ + '.py ' + self.name + " " + self.ref_time + " " + str(dummy_clock_rate) + " &" )
        self.state = "running"


    def incoming( self, priority, message ):

        # pass on to the base class message handling function
        normal.incoming( self, priority, message)
        
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
class nwpglobal( normal ):

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

        normal.__init__( self, ref_time, initial_state )

#----------------------------------------------------------------------
if __name__ == '__main__':

    import sys
    import Pyro.naming, Pyro.core
    from Pyro.errors import NamingError
    from pyro_ns_naming import pyro_ns_name
    import reference_time
    import datetime

    from time import sleep

    # hardwired dummy clock use
    use_dummy_clock = True

    # unpack script arguments: <task name> <REFERENCE_TIME> <clock rate>
    [task_name, ref_time, clock_rate] = sys.argv[1:]

    # getProxyForURI is the shortcut way to a pyro object proxy; it may
    # be that the long way is better for error checking; see pyro docs.
    task = Pyro.core.getProxyForURI('PYRONAME://' + pyro_ns_name( task_name + '%' + ref_time ))

    completion_time = task.get_postrequisite_times()
    postreqs = task.get_postrequisite_list()

    if not use_dummy_clock:
        #=======> simple method
        # report postrequisites done at the estimated time for each,
        # scaled by the configured dummy clock rate, but without reference
        # to the actual dummy clock: so dummy tasks do not complete faster
        # when we bump the dummy clock forward.

        # print task.identity() + " NOT using dummy clock"
    
        n_postreqs = len( postreqs )

        for req in postreqs:
            sleep( completion_time[ req ] / float( clock_rate ) )

            #print "SENDING MESSAGE: ", time[ req ], req
            task.incoming( "NORMAL", req )


    else:
        #=======> use the controller's accelerated dummy clock
        # i.e. report postrequisites done when the dummy clock time is 
        # greater than or equal to the estimated postrequisite time.
        # Dummy tasks therefore react when we bump the clock forward,
        # AND we can fully simulate catchup operation and the transition
        # to fully caught up.

        # print task.identity() + " using dummy clock"

        clock = Pyro.core.getProxyForURI('PYRONAME://' + pyro_ns_name( 'dummy_clock' ))

        fast_complete = False

        if task_name == "downloader":

            rt = reference_time._rt_to_dt( ref_time )
            rt_3p25 = rt + datetime.timedelta( 0,0,0,0,0,3.25,0 )  # 3hr:15min after the hour
            if clock.get_datetime() >= rt_3p25:
                task.incoming( 'NORMAL', 'CATCHUP: input files already exist for ' + ref_time )
                fast_complete = True
            else:
                task.incoming( 'NORMAL', 'UPTODATE: waiting for input files for ' + ref_time )
                while True:
                    sleep(1)
                    if clock.get_datetime() >= rt_3p25:
                        break

        elif task_name == "topnet":

            rt = reference_time._rt_to_dt( ref_time )
            rt_p25 = rt + datetime.timedelta( 0,0,0,0,0,0.25,0 ) # 15 min past the hour
            # THE FOLLOWING MESSAGES MUST MATCH THOSE IN topnet.incoming()
            if clock.get_datetime() >= rt_p25:
                task.incoming( 'NORMAL', 'CATCHUP: streamflow data available, for ' + ref_time )
            else:
                task.incoming( 'NORMAL', 'UPTODATE: waiting for streamflow, for ' + ref_time ) 
                while True:
                    sleep(1)
                    if clock.get_datetime() >= rt_p25:
                        break

        # set each postrequisite satisfied in turn
        start_time = clock.get_datetime()

        done = {}
        time = {}

        for req in postreqs:
            done[ req ] = False
            if fast_complete:
                hours = completion_time[ req] / 60.0 / 20.
            else:
                hours = completion_time[ req] / 60.0
            time[ req ] = start_time + datetime.timedelta( 0,0,0,0,0,hours,0)

        while True:
            sleep(1)
            dt = clock.get_datetime()
            all_done = True
            for req in postreqs:
                if not done[ req]:
                    if dt >= time[ req ]:
                        #print "SENDING MESSAGE: ", time[ req ], req
                        task.incoming( "NORMAL", req )
                        done[ req ] = True
                    else:
                        all_done = False

            if all_done:
                break

