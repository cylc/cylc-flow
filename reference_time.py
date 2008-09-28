#!/usr/bin/python

""" 
Ecoconnect REFERENCE_TIME (YYYYMMDDHH)

This was a class to define reference time objects that know how to
increment themselves, etc. But now that the controller does not have a
global reference time a procedural module will do.
"""

import datetime

def _rt_to_dt( rt ):
    return datetime.datetime( 
            int(rt[0:4]), int(rt[4:6]), 
            int(rt[6:8]), int(rt[8:10]))

def _dt_to_rt( dt ): 
    return dt.strftime( "%Y%m%d%H" )

def increment( rt, hours ): 
        dt = _rt_to_dt( rt )
        return _dt_to_rt( dt + datetime.timedelta( 0, 0, 0, 0, 0, hours, 0 ) )

def decrement( rt, hours ): 
        dt = _rt_to_dt( rt )
        return _dt_to_rt( dt - datetime.timedelta( 0, 0, 0, 0, 0, hours, 0 ) )

# do rt comparisons in integer form via int( rt )
