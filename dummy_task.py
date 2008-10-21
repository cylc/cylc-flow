#!/usr/bin/python

# For external dummy task programs that report their postrequisites done
# on time relative to the controllers internal accelerated dummy clock.

# If dummy_mode = False we must have dummied out a particular task in
# real mode, in which case there's no dummy clock to consult. Instead 
# we complete requisites done after the right length of time has passed
# (still sped up according to dummy_clock_rate, however).

import sys
import Pyro.naming, Pyro.core
from Pyro.errors import NamingError
import pyro_ns_naming
import reference_time
import datetime
from time import sleep

from config import dummy_mode, dummy_clock_rate, dummy_clock_offset

class dummy_task_base:

    def __init__( self, task_name, ref_time ):
        self.task_name = task_name
        self.ref_time = ref_time

        if dummy_mode:
            self.clock = Pyro.core.getProxyForURI('PYRONAME://' + pyro_ns_naming.name( 'dummy_clock' ))

        self.task = Pyro.core.getProxyForURI('PYRONAME://' + pyro_ns_naming.name( self.task_name + '%' + self.ref_time ))
        self.fast_complete = False

    def run( self ):

        completion_time = self.task.get_postrequisite_times()
        postreqs = self.task.get_postrequisite_list()

        if not dummy_mode:

            # report postrequisites done at the estimated time for each,
            # scaled by the configured dummy clock rate, but without reference
            # to the actual dummy clock: so dummy tasks do not complete faster
            # when we bump the dummy clock forward.
 
            if self.task_name == "topnet":
                # if caught up, delay as if waiting for streamflow data

                rt = reference_time._rt_to_dt( self.ref_time )
                rt_p25 = rt + datetime.timedelta( 0,0,0,0,0,0.25,0 ) # 15 min past the hour
                # THE FOLLOWING MESSAGES MUST MATCH THOSE EXPECTED IN topnet.incoming()
                if datetime.datetime.now() >= rt_p25:
                    self.task.incoming( 'NORMAL', 'CATCHUP: streamflow data available, for ' + self.ref_time )
                else:
                    self.task.incoming( 'NORMAL', 'UPTODATE: waiting for streamflow, for ' + self.ref_time ) 
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
        # executing immediately, but some (downloader, topnet
        # streamflow) are delayed by having to wait from some external
        pass


#----------------------------------------------------------------------
class dummy_task( dummy_task_base ):

    def delay( self ):

        if self.task_name == "downloader":

            rt = reference_time._rt_to_dt( self.ref_time )
            rt_3p25 = rt + datetime.timedelta( 0,0,0,0,0,3.25,0 )  # 3hr:15min after the hour
            if self.clock.get_datetime() >= rt_3p25:
                # THE FOLLOWING MESSAGES MUST MATCH THOSE EXPECTED IN downloader.incoming()
                self.task.incoming( 'NORMAL', 'CATCHUP: input files already exist for ' + self.ref_time )
                self.fast_complete = True
            else:
                self.task.incoming( 'NORMAL', 'UPTODATE: waiting for input files for ' + self.ref_time )
                while True:
                    sleep(1)
                    if self.clock.get_datetime() >= rt_3p25:
                        break

        elif self.task_name == "oper2test_topnet":

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
            # THE FOLLOWING MESSAGES MUST MATCH THOSE EXPECTED IN topnet.incoming()
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
    [task_name, ref_time] = sys.argv[1:]
    dummy = dummy_task( task_name, ref_time )
    dummy.run()
