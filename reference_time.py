#!/usr/bin/python

""" 
Ecoconnect REFERENCE_TIME (YYYYMMDDHH) handling 
"""

import datetime

class reference_time:

    def __init__( self, rt ): 
        # string: "YYYYMMDDHH"
        self.reftime = datetime.datetime( 
                    int(rt[0:4]), int(rt[4:6]), 
                    int(rt[6:8]), int(rt[8:10]))

    def increment( self ): 
        # change to the next reference time 
        # (doesn't necessarily have to be a constant increment)

        # 0, 6, 12, 18 

        #hour = int( self.get_hour() )
        # 0, 3, 6, 12, 18 
        #if hour == 0 or hour == 3:
        #    delta = 3
        #else:
        delta = 6

        tmp = datetime.timedelta( 0, 0, 0, 0, 0, delta, 0 ) 
        self.reftime += tmp

    def decrement( self ): 
        # change to the previous reference time

        # 0, 6, 12, 18 

        delta = 6

        tmp = datetime.timedelta( 0, 0, 0, 0, 0, delta, 0 ) 
        self.reftime -= tmp

    def add( self, hours ): 
        tmp = datetime.timedelta( 0, 0, 0, 0, 0, hours, 0 ) 
        self.reftime += tmp

    def subtract( self, hours ): 
        tmp = datetime.timedelta( 0, 0, 0, 0, 0, hours, 0 ) 
        self.reftime -= tmp

    def to_str( self ): 
        return self.reftime.strftime( "%Y%m%d%H" )

    def to_int( self ): 
        return int( self.to_str() )

    def is_lessthan( self, rt ):
        if self.to_int() < rt.to_int():
            return True
        else:
            return False

    def is_greaterthan( self, rt ):
        if self.to_int() > rt.to_int():
            return True
        else:
            return False

    def is_equalto( self, rt ):
        if self.to_int() == rt.to_int():
            return True
        else:
            return False

    def is_lessthan_or_equalto( self, rt ):
        if self.is_lessthan( rt ) or self.is_equalto( rt ):
            return True
        else:
            return False

    def is_greaterthan_or_equalto( self, rt ):
        if self.is_greaterthan( rt ) or self.is_equalto( rt ):
            return True
        else:
            return False

    def get_hour( self ):
        return self.to_str()[8:10]
