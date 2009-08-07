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

class dummy_task:

    def __init__( self, task_name, ref_time ):

        # get a pyro proxy for the task object that I'm masquerading as
        self.name = task_name
        self.ref_time = ref_time
        self.task = Pyro.core.getProxyForURI('PYRONAME://' + system_name + '.' + self.name + '%' + self.ref_time )
        
        # get a pyro proxy for the dummy clock
        self.clock = Pyro.core.getProxyForURI('PYRONAME://' + system_name + '.dummy_clock' )

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

        # time to stop counting and generate the output
        for output_time in times:
            done[ output_time ] = False

            if self.fast_complete:
                hours = 0
            else:
                hours = output_time / 60.0

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

        current_time = self.clock.get_datetime()
        rt = reference_time._rt_to_dt( self.ref_time )
        delay = self.task.get_real_time_delay()

        delayed_start = rt + datetime.timedelta( 0,0,0,0,0,delay,0 ) 

        if current_time >= delayed_start:
            self.task.incoming( 'NORMAL', 'CATCHINGUP: real world event already occurred' )
            self.fast_complete = True
        else:
            self.task.incoming( 'NORMAL', 'CAUGHTUP: waiting on real world event' )
            # TO DO: change this to a single long sleep of the right length
            while True:
                sleep(1)
                if self.clock.get_datetime() >= delayed_start:
                    break

#----------------------------------------------------------------------
if __name__ == '__main__':
    task_name = os.environ['TASK_NAME']
    ref_time = os.environ['REFERENCE_TIME']
    system_name = os.environ['SYSTEM_NAME'] 
    dummy_clock_rate = os.environ['CLOCK_RATE']
    dummy_clock_offset = os.environ['CLOCK_OFFSET']
        
    #print "DUMMY TASK STARTING: " + task_name + " " + ref_time
    dummy = dummy_task( task_name, ref_time )
    dummy.run()
    #print "DUMMY TASK FINISHED: " + task_name + " " + ref_time
