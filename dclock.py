#!/usr/bin/python

"""
A reference time clock that runs in its own thread, for use in dummy mode.
"""

from time import sleep
from threading import Thread
import reference_time

class dclock( Thread ):

    def __init__( self, initial_time, seconds_per_hour = 30 ):
        self.time = initial_time
        self.seconds_per_hour = seconds_per_hour

        Thread.__init__(self)

    def run( self ):
        while True:
            #print "TICK " + self.time
            sleep(30)
            self.time = reference_time.increment( self.time, 1 )
