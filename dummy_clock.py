#!/usr/bin/python

import Pyro.core
import datetime
import reference_time
from time import sleep
import datetime, time

class dummy_clock( Pyro.core.ObjBase ):
    """Equate a given dummy YYYYMMDDHH with the real time at
    initialisation, and thereafter advance dummy time at the
    requested rate of seconds per hour.
    
    This is for timing control in dummy_mode.
    """

    def __init__( self, base_ref_time, rate, offset = None ):

        Pyro.core.ObjBase.__init__(self)

        self.base_datetime = datetime.datetime.now() 

        self.base_dummytime = datetime.datetime( 
            int(base_ref_time[0:4]), int(base_ref_time[4:6]), 
            int(base_ref_time[6:8]), int(base_ref_time[8:10]))

        if offset:
            # start the dummy clock <offset> HOURS beyond the start time
            self.base_dummytime += datetime.timedelta( 0,0,0,0,0, offset, 0) 

        # rate of dummy time advance (S/HOUR)
        self.rate = rate

        print
        print "DUMMY MODE CLOCK" 
        print "  o rate " + str(self.rate) + " seconds / dummy hour"
        print "  o start time " + str( self.base_dummytime )

    def get_datetime( self ):
        delta = datetime.datetime.now() - self.base_datetime
        
        # time deltas are expressed as days, seconds, microseconds
        days = delta.days
        seconds = delta.seconds
        microseconds = delta.microseconds

        seconds_passed = microseconds / 1000000. + seconds + days * 24 * 3600
        dummy_hours_passed = seconds_passed / self.rate

        return self.base_dummytime + datetime.timedelta( 0,0,0,0,0, dummy_hours_passed, 0 )

    def bump( self, hours ):
        # bump the dummy time clock forward by some hours
        self.base_dummytime += datetime.timedelta( 0,0,0,0,0, int(hours), 0 )
        return self.get_datetime()

    def get_epoch( self ):
        dt = self.get_datetime()
        return time.mktime( dt.timetuple() )


def test():

    rt = "2008080800"
    foo = dummy_clock( rt, 10 )     # 10 seconds / hour
    bar = dummy_clock( rt, 10, 3 )  # 10 seconds / hour

    print rt                        # 2008080800
    print foo.get_datetime()        # 2008080800
    print bar.get_datetime()        # 2008080803
    sleep(11)                       # 10 secons => 1 hour
    print foo.get_datetime()        # 2008080801
    print bar.get_datetime()        # 2008080804


if __name__ == "__main__":
    test()
