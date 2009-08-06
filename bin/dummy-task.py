#!/usr/bin/python

# A program that masquerade's as a given tasks by reporting its outputs
# completed on time according to the controller's dummy clock.

import Pyro.naming, Pyro.core
from Pyro.errors import NamingError
import reference_time
import datetime
import sys
import os
import re
from time import sleep

class dummy_task_base:

    def __init__( self, task_name, ref_time ):

        # get a pyro proxy for the task object that I'm masquerading as
        self.name = task_name
        self.ref_time = ref_time
        self.task = Pyro.core.getProxyForURI('PYRONAME://' + pyro_group + '.' + self.name + '%' + self.ref_time )
        
        # get a pyro proxy for the dummy clock
        self.clock = Pyro.core.getProxyForURI('PYRONAME://' + pyro_group + '.dummy_clock' )

        # fast completion            
        self.fast_complete = False

    def run( self ):

        # get a list of output messages to fake: outputs[ time ] = output
        outputs = self.task.get_timed_postrequisites()

        # ordered list of times
        times = outputs.keys()
        times.sort()
        
        # task-specific delay
        self.delay()

        # time to start counting from 
        start_time = self.clock.get_datetime()

        done = {}
        stop_time = {}

        if self.fast_complete:
            speedup = 20.
        else:
            speedup = 1.
            
        # time to stop counting and generate the output
        for output_time in times:
            done[ output_time ] = False
            hours = output_time / 60.0 / speedup
            stop_time[ output_time ] = start_time + datetime.timedelta( 0,0,0,0,0,hours,0)

        # wait until the stop time for each output, and then generate the output
        while True:
            sleep(1)
            dt = self.clock.get_datetime()
            all_done = True
            for output_time in times:
                output = outputs[ output_time ]
                if not done[ output_time ]:
                    if dt >= stop_time[ output_time ]:
                        #print "SENDING MESSAGE: ", output_time, output
                        self.task.incoming( "NORMAL", output )
                        done[ output_time ] = True
                    else:
                        all_done = False

            if all_done:
                break
            
    def delay( self ):
        # override this to delay dummy tasks that have non-standard
        # behavior after startup (external tasks can usually start
        # executing immediately, but some (e.g. download, streamflow)
        # are delayed by having to wait from some external
        pass


#----------------------------------------------------------------------
class dummy_task( dummy_task_base ):

    def delay( self ):

        if self.name == 'download':

            rt = reference_time._rt_to_dt( self.ref_time )
            rt_3p25 = rt + datetime.timedelta( 0,0,0,0,0,3.25,0 )  # 3hr:15min after the hour
            if self.clock.get_datetime() >= rt_3p25:
                # THE FOLLOWING MESSAGES MUST MATCH THOSE EXPECTED IN download_foo.incoming()
                self.task.incoming( 'NORMAL', 'CATCHINGUP: input files already exist' )
                self.fast_complete = True
            else:
                self.task.incoming( 'NORMAL', 'CAUGHTUP: waiting for input files' )
                while True:
                    sleep(1)
                    if self.clock.get_datetime() >= rt_3p25:
                        break

        elif self.name == "oper_interface":

            current_time = self.clock.get_datetime()
            rt = reference_time._rt_to_dt( self.ref_time )
            delayed_start = rt + datetime.timedelta( 0,0,0,0,0,4.5,0 )  # 4.5 hours 
            #print "oper_interface: current time   " + current_time.isoformat()
            #print "oper_interface: reference time " + rt.isoformat()
            #print "oper_interface: delayed start  " + delayed_start.isoformat()

            # UNCOMMENT THIS TO SIMULATE A STUCK TASK (when Met Office files
            # fail to arrive and nzlam therefore can't run):
            #if self.ref_time == '2009052218':
            #    print self.identity, "STUCK (for one hour real time)"
            #    sleep(3600)

            if current_time >= delayed_start:
                self.task.incoming( 'NORMAL', 'CATCHINGUP: operational tn file already exists' )
                self.fast_complete = True
            else:
                self.task.incoming( 'NORMAL', 'CAUGHTUP: waiting for operational tn file' )
                while True:
                    sleep(1)
                    if self.clock.get_datetime() >= delayed_start:
                        break


        elif self.name == "streamflow":

            current_time = self.clock.get_datetime()
            rt = reference_time._rt_to_dt( self.ref_time )
            rt_p25 = rt + datetime.timedelta( 0,0,0,0,0,0.25,0 ) # 15 min past the hour
            # THE FOLLOWING MESSAGES MUST MATCH WHAT'S EXPECTED IN streamflow.incoming()
            if current_time >= rt_p25:
                self.task.incoming( 'NORMAL', 'CATCHINGUP: streamflow data available' )
            else:
                self.task.incoming( 'NORMAL', 'CAUGHTUP: waiting for streamflow' ) 
                while True:
                    sleep(1)
                    if self.clock.get_datetime() >= rt_p25:
                        break

#----------------------------------------------------------------------
if __name__ == '__main__':
    if len( sys.argv ) == 7:
        [task_name, ref_time, pyro_group, dummy_mode, dummy_clock_rate, dummy_clock_offset ] = sys.argv[1:]
    else:
        print "DUMMY TASK ABORTING: WRONG NUMBER OF ARGUMENTS!"
        sys.exit(1)
        
    if not dummy_mode:
        print "DUMMY TASK ABORTING: NOT IN DUMMY MODE"
        sys.exit(1)

    #print "DUMMY TASK STARTING: " + task_name + " " + ref_time
    dummy = dummy_task( task_name, ref_time )
    dummy.run()
    #print "DUMMY TASK FINISHED: " + task_name + " " + ref_time
