#!/usr/bin/python

import sys
import datetime
from reference_time import _rt_to_dt

class contact:
    # A task that waits on an event in the external world, such as
    # incoming data, that occurs at some known (but approximate) time
    # interval relative to the task reference time.  There's no point in
    # running the task earlier than this delayed start time as the task
    # would just sit in the queue waiting on the external event.

    def __init__( self ):
        # THE ASSOCIATED TASK CLASS MUST DEFINE 
        # self.real_time_delay
        try:
            self.real_time_delay
        except AttributeError:
            print 'ERROR: contact tasks require a real time delay'
            sys.exit(1)

    def get_real_time_delay( self ):
        return self.real_time_delay

    def ready_to_run( self, clock ):
        # ready IF waiting AND all prerequisites satisfied AND if my
        # delayed start time is up.
        ready = False
        if self.state.is_waiting() and self.prerequisites.all_satisfied():
            # check current time against expected start time
            rt = _rt_to_dt( self.ref_time )
            delayed_start = rt + datetime.timedelta( 0,0,0,0,0,self.real_time_delay,0 ) 
            current_time = clock.get_datetime()

            if current_time >= delayed_start:
                ready = True
            else:
                self.log( 'DEBUG', 'ready, but waiting on delayed start time' )

        return ready
