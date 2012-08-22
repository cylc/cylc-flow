#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.


import Pyro.core
import datetime, time
from time import sleep

class clock( Pyro.core.ObjBase ):
    """
    REAL TIME or ACCELERATED clock. 

    In simulation or dummy mode, equate a given simulation YYYYMMDDHH
    with the real time at initialisation, and thereafter advance
    simulation time at the requested rate of seconds per hour.
    """

    def __init__( self, rate, offset, utc, disable ):
        
        Pyro.core.ObjBase.__init__(self)
        
        self.disable = disable
        self.utc = utc

        # time acceleration (N real seconds = 1 simulation hour)
        self.acceleration = rate
        
        # start time offset (relative to start cycle time)
        self.offset_hours = offset

        self.base_realtime = self.now() 
        self.base_simulationtime = self.base_realtime

        #if not self.disable:
        #    print "accelerated CLOCK ........"
        #    print " - accel:  " + str( self.acceleration ) + "s = 1 simulated hour"
        #    print " - offset: " + str( self.offset_hours )

    def now( self ):
        if self.utc:
            return datetime.datetime.utcnow()
        else:
            return datetime.datetime.now()

    def set( self, ctime ):
        #print 'Setting accelerated clock time'
        self.base_simulationtime = datetime.datetime( 
                int(ctime[0:4]), int(ctime[4:6]), 
                int(ctime[6:8]), int(ctime[8:10]))
                
        self.base_simulationtime += datetime.timedelta( 0,0,0,0,0, self.offset_hours, 0) 

    def get_rate( self ):
        return self.acceleration

    def reset( self, dstr, rate ):
        # set clock from string of the form made by self.dump_to_str()
        # Y:M:D:H:m:s

        self.acceleration = int( rate )

        if self.disable:
            print "(ignoring clock reset in real time)"
            return
        
        print 'Setting accelerated clock time'

        YMDHms = dstr.split( ':' )
        Y = YMDHms[0]
        M = YMDHms[1]
        D = YMDHms[2]
        H = YMDHms[3]
        m = YMDHms[4]
        s = YMDHms[5]

        if len( M ) == 1:
            M = '0' + M
        if len( D ) == 1:
            D = '0' + D
        if len( H ) == 1:
            H = '0' + H
        if len( m ) == 1:
            m = '0' + m
        if len( s ) == 1:
            s = '0' + s

        base_ctime = Y + M + D + H + m + s
        #base_ctime = Y + M + D + H 

        self.base_simulationtime = datetime.datetime( 
                int(base_ctime[0:4]), int(base_ctime[4:6]), 
                int(base_ctime[6:8]), int(base_ctime[8:10]),
                int(base_ctime[10:12]), int(base_ctime[12:14]))
                
        print "CLOCK RESET ......."
        print " - accel:  " + str( self.acceleration ) + "s = 1 simulation hour"
        print " - start:  " + str( self.base_simulationtime )

    def get_datetime( self ):
        if self.disable:
            # just return real time
            return self.now()
        else:
            # compute simulation time based on how much real time has passed
            delta_real = self.now() - self.base_realtime
        
            # time deltas are expressed as days, seconds, microseconds
            days = delta_real.days
            seconds = delta_real.seconds
            microseconds = delta_real.microseconds

            seconds_passed_real = microseconds / 1000000. + seconds + days * 24 * 3600
            simulation_hours_passed = seconds_passed_real / self.acceleration

            return self.base_simulationtime + datetime.timedelta( 0,0,0,0,0, simulation_hours_passed, 0 )

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
