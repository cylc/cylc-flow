#!/usr/bin/python

import Pyro.core
import datetime
import reference_time
from time import sleep
import datetime, time

class clock( Pyro.core.ObjBase ):
    """
    REAL TIME or ACCELERATED DUMMY MODE clock for cyclon.

    In dummy mode, equate a given dummy YYYYMMDDHH with the real time at
    initialisation, and thereafter advance dummy time at the requested
    rate of seconds per hour.
    """

    def __init__( self ):
        # initialise as a real time clock
        self.dummy_mode = False

        Pyro.core.ObjBase.__init__(self)
        self.base_realtime = datetime.datetime.now() 

        # time acceleration (N real seconds = 1 dummy hour)
        self.acceleration = 3600.0

        # start time offset (relative to start reference time)
        self.offset_hours = 0.0

        # how many accelerated seconds to wait between alarms
        # (use to trigger the event loop regularly even when
        # no task messages come in, as happens when the whole
        # system waits on a contact task that isn't running yet).
        self.alarm_seconds = 60.0

        # remember last time an alarm was used
        self.last_alarm_realtime = self.base_realtime

        print "CLOCK ........"
        print " - start time:", datetime.datetime.now()
        print " - alarm:  " + str( self.alarm_seconds ) + " seconds"

    def accelerate( self, alarm, base_reftime, accel, offset ):
        # call this only to accelerate the clock in dummy mode

        self.dummy_mode = True

        self.alarm_seconds = alarm
        self.acceleration = accel
        self.offset_hours = offset

        self.base_dummytime = datetime.datetime( 
                int(base_reftime[0:4]), int(base_reftime[4:6]), 
                int(base_reftime[6:8]), int(base_reftime[8:10]))
                
        self.base_dummytime += datetime.timedelta( 0,0,0,0,0, offset, 0) 

        print "ACCELERATING THE CLOCK........" 
        print " - accel:  " + str( self.acceleration ) + "s = 1 dummy hour"
        print " - start:  " + str( self.base_dummytime )
        print " - offset: " + str( self.offset_hours )
        print " - alarm:  " + str( self.alarm_seconds ) + "s"

    def get_datetime( self ):

        if not self.dummy_mode:
            # return real time
            return datetime.datetime.now()

        else:
            # compute dummy time based on how much real time has passed
            delta_real = datetime.datetime.now() - self.base_realtime
        
            # time deltas are expressed as days, seconds, microseconds
            days = delta_real.days
            seconds = delta_real.seconds
            microseconds = delta_real.microseconds

            seconds_passed_real = microseconds / 1000000. + seconds + days * 24 * 3600
            dummy_hours_passed = seconds_passed_real / self.acceleration

            return self.base_dummytime + datetime.timedelta( 0,0,0,0,0, dummy_hours_passed, 0 )


    def get_alarm( self ):
        # return True if more than self.alarm_seconds has passed since
        # the last alarm was triggered.

        alarm = False
        current_real = datetime.datetime.now()
        
        delta_realtime = current_real - self.last_alarm_realtime
        days = delta_realtime.days
        seconds = delta_realtime.seconds
        microseconds = delta_realtime.microseconds

        seconds_passed_realtime = microseconds / 1000000. + seconds + days * 24 * 3600

        if self.dummy_mode:
            dummy_seconds_passed = seconds_passed_realtime / self.acceleration * 3600
            if dummy_seconds_passed > self.alarm_seconds:
                alarm = True
        else:
            if seconds_passed_realtime > self.alarm_seconds:
                alarm = True
 
        if alarm:
            #print 'ALARM: ', current_real
            self.last_alarm_realtime = current_real

        return alarm


    def bump( self, hours ):
        if not self.dummy_mode:
            print "WARNING: bump is for dummy mode only"

        else:
            # bump the dummy time clock forward by some hours
            self.base_dummytime += datetime.timedelta( 0,0,0,0,0, int(hours), 0 )
            return self.get_datetime()

    def get_epoch( self ):
        dt = self.get_datetime()
        return time.mktime( dt.timetuple() )


def test():

    foo = clock()
    bar = clock()

    rt = "2008080800"
    foo.accelerate( 60, rt, 10, 0 )     # 10 seconds / hour
    bar.accelerate( 60, rt, 10, 3 )     # 10 seconds / hour

    print rt                        # 2008080800
    print foo.get_datetime()        # 2008080800
    print bar.get_datetime()        # 2008080803
    sleep(11)                       # 10 secons => 1 hour
    print foo.get_datetime()        # 2008080801
    print bar.get_datetime()        # 2008080804

if __name__ == "__main__":
    test()
