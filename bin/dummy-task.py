#!/usr/bin/python

# TO DO: DERIVE CLASSES FOR STREAMFLOW AND DOWNLOAD, ETC. to get
# rid of the nasty 'IF' blocks, or move them to main() at least.
# TO DO: THIS SHOULD BE JUST THE GENERIC DUMMY TASK - PROVIDE A
# MEANS OF DEFINING TASK-SPECIFIC BEHAVIOUR FOR DUMMY TASKS TOO.

# For external dummy task programs that report their postrequisites done
# on time relative to the controllers internal accelerated dummy clock.

# If dummy_mode = False we must have dummied out a particular task in
# real mode, in which case there's no dummy clock to consult. Instead 
# we complete requisites done after the right length of time has passed
# (still sped up according to dummy_clock_rate, however).

import os, sys

import Pyro.naming, Pyro.core
from Pyro.errors import NamingError
import reference_time
import datetime
import re
from time import sleep

class dummy_task_base:

    def __init__( self, task_name, ref_time ):
        self.name = task_name
        self.ref_time = ref_time

        if dummy_mode:
            self.clock = Pyro.core.getProxyForURI('PYRONAME://' + pyro_group + '.dummy_clock' )

        self.task = Pyro.core.getProxyForURI('PYRONAME://' + pyro_group + '.' + self.name + '%' + self.ref_time )
        self.fast_complete = False

    def run( self ):

        completion_time = self.task.get_postrequisite_times()
        postreqs = self.task.get_postrequisite_list()

        if not dummy_mode:

            # report postrequisites done at the estimated time for each,
            # scaled by the configured dummy clock rate, but without reference
            # to the actual dummy clock: so dummy tasks do not complete faster
            # when we bump the dummy clock forward.
 
            if self.name == "streamflow":
                # if caught up, delay as if waiting for streamflow data

                rt = reference_time._rt_to_dt( self.ref_time )
                rt_p25 = rt + datetime.timedelta( 0,0,0,0,0,0.25,0 ) # 15 min past the hour
                # THE FOLLOWING MESSAGES MUST MATCH WHAT'S EXPECTED IN streamflow.incoming()
                # AND IN THE REAL STREAMFLOW TASK
                if datetime.datetime.now() >= rt_p25:
                    self.task.incoming( 'NORMAL', 'CATCHINGUP: streamflow data already available for ' + self.ref_time )
                else:
                    self.task.incoming( 'NORMAL', 'CAUGHTUP: waiting for streamflow data for ' + self.ref_time ) 
                    while True:
                        sleep(10)
                        if datetime.datetime.now() >= rt_p25:
                            break
        
            n_postreqs = len( postreqs )
         
            for req in postreqs:
                sleep( completion_time[ req ] / float( dummy_clock_rate ) )
                self.task.incoming( "NORMAL", req )

        else:

            self.delay()

            start_time = self.clock.get_datetime()

            done = {}
            time = {}

            if self.fast_complete:
                speedup = 20.
            else:
                speedup = 1.
 
            for req in postreqs:
                done[ req ] = False
                hours = completion_time[ req] / 60.0 / speedup
                time[ req ] = start_time + datetime.timedelta( 0,0,0,0,0,hours,0)

            while True:
                sleep(1)
                dt = self.clock.get_datetime()
                all_done = True
                for req in postreqs:
                    if not done[ req]:
                        if dt >= time[ req ]:
                            #print "SENDING MESSAGE: ", time[ req ], req
                            self.task.incoming( "NORMAL", req )
                            done[ req ] = True
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
                self.task.incoming( 'NORMAL', 'CATCHINGUP: input files already exist for ' + self.ref_time )
                self.fast_complete = True
            else:
                self.task.incoming( 'NORMAL', 'CAUGHTUP: waiting for input files for ' + self.ref_time )
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
                self.task.incoming( 'NORMAL', 'CATCHINGUP: operational tn file already exists for ' + self.ref_time )
                self.fast_complete = True
            else:
                self.task.incoming( 'NORMAL', 'CAUGHTUP: waiting for operational tn file for ' + self.ref_time )
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
                self.task.incoming( 'NORMAL', 'CATCHINGUP: streamflow data available, for ' + self.ref_time )
            else:
                self.task.incoming( 'NORMAL', 'CAUGHTUP: waiting for streamflow, for ' + self.ref_time ) 
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
        
    #print "DUMMY TASK STARTING: " + task_name + " " + ref_time
    dummy = dummy_task( task_name, ref_time )
    dummy.run()
    #print "DUMMY TASK FINISHED: " + task_name + " " + ref_time
