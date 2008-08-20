#!/usr/bin/python

""" 
Ecoconnect REFERENCE_TIME (YYYYMMDDHH) handling 
"""

import datetime
from ec_globals import period

class reference_time:

    cycle_period = period 

    def __init__( self, rt ): 
        # string: "YYYYMMDDHH"
        self.reftime = datetime.datetime( 
                    int(rt[0:4]), int(rt[4:6]), 
                    int(rt[6:8]), int(rt[8:10]))

    def increment( self, hours = cycle_period ): 
        tmp = datetime.timedelta( 0, 0, 0, 0, 0, hours, 0 ) 
        self.reftime += tmp

    def decrement( self, hours = cycle_period ): 
        tmp = datetime.timedelta( 0, 0, 0, 0, 0, hours, 0 ) 
        self.reftime -= tmp

    def to_str( self ): 
        return self.reftime.strftime( "%Y%m%d%H" )
