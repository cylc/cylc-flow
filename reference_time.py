#!/usr/bin/python

""" 
Ecoconnect REFERENCE_TIME (YYYYMMDDHH) handling 
"""

import datetime
from ec_globals import period

class reference_time:

	cycle_period = period 

	def __init__( self, year, month, day, hour ):
		self.reftime = datetime.datetime( year, month, day, hour )

	def increment( self, hours = cycle_period ):
		tmp = datetime.timedelta( 0, 0, 0, 0, 0, hours, 0 )
		self.reftime += tmp

	def decrement( self, hours = cycle_period ):
		tmp = datetime.timedelta( 0, 0, 0, 0, 0, hours, 0 )
		self.reftime -= tmp

	def to_str( self ):
		return self.reftime.strftime( "%Y%m%d%H" )

