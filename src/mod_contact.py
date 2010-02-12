#!/usr/bin/python

import sys
import datetime
from cycle_time import _rt_to_dt

class contact:
    # A task that waits on an event in the external world, such as
    # incoming data, that occurs at some known (but approximate) time
    # interval relative to the task cycle time.  There's no point in
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

    def start_time_reached( self ):
        reached = False
        # check current time against expected start time
        rt = _rt_to_dt( self.c_time )
        delayed_start = rt + datetime.timedelta( 0,0,0,0,0,self.real_time_delay,0 ) 
        current_time = self.clock.get_datetime()

        if current_time >= delayed_start:
           reached = True

        return reached

    def ready_to_run( self ):
        # ready IF waiting AND all prerequisites satisfied AND if my
        # delayed start time is up.
        ready = False
        if self.state.is_waiting() and self.prerequisites.all_satisfied():

            if self.start_time_reached():
                ready = True
            else:
                self.log( 'DEBUG', 'prerequisites satisfied but waiting on delayed start time' )

        return ready
