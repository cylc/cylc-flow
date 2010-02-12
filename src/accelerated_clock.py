#!/usr/bin/python

import Pyro.core
import datetime
import cycle_time
from time import sleep
import datetime, time

class clock( Pyro.core.ObjBase ):
    """
    REAL TIME or ACCELERATED DUMMY MODE clock for cylc.

    In dummy mode, equate a given dummy YYYYMMDDHH with the real time at
    initialisation, and thereafter advance dummy time at the requested
    rate of seconds per hour.
    """

    def __init__( self, rate, offset, dummy_mode ):
        
        Pyro.core.ObjBase.__init__(self)
        
        self.dummy_mode = dummy_mode

        # time acceleration (N real seconds = 1 dummy hour)
        self.acceleration = rate
        
        # start time offset (relative to start cycle time)
        self.offset_hours = offset

        self.base_realtime = datetime.datetime.now() 
        self.base_dummytime = self.base_realtime

        if dummy_mode:
            print "DUMMY CLOCK ........"
            print " - accel:  " + str( self.acceleration ) + "s = 1 simulated hour"
            print " - offset: " + str( self.offset_hours )


    def set( self, ctime ):

        print 'Setting dummy mode clock time'
        self.base_dummytime = datetime.datetime( 
                int(ctime[0:4]), int(ctime[4:6]), 
                int(ctime[6:8]), int(ctime[8:10]))
                
        self.base_dummytime += datetime.timedelta( 0,0,0,0,0, self.offset_hours, 0) 


    def get_rate( self ):
        return self.acceleration

    def reset( self, dstr ):
        # set clock from string of the form made by self.dump_to_str()
        # Y:M:D:H:m:s

        if not self.dummy_mode:
            print "(ignoring clock reset in real time)"
            return
        
        print 'Setting dummy mode clock time'

        YMDHms = dstr.split( ':' )
        Y = YMDHms[0]
        M = YMDHms[1]
        D = YMDHms[2]
        H = YMDHms[3]

        if len( M ) == 1:
            M = '0' + M
        if len( D ) == 1:
            D = '0' + D
        if len( H ) == 1:
            H = '0' + H

        base_ctime = Y + M + D + H

        self.base_dummytime = datetime.datetime( 
                int(base_ctime[0:4]), int(base_ctime[4:6]), 
                int(base_ctime[6:8]), int(base_ctime[8:10]))
                
        print "CLOCK RESET ......."
        print " - accel:  " + str( self.acceleration ) + "s = 1 dummy hour"
        print " - start:  " + str( self.base_dummytime )

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

    def dump_to_str( self ):
        # dump current clock time to a string: Y:M:D:H:m:s
        # ignore microseconds
        now =  self.get_datetime()
        YMDHms = [ str( now.year), str( now.month ), str( now.day ), str( now.hour), str( now.minute ), str( now.second ) ]
        return ':'.join( YMDHms )


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
