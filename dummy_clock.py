#!/usr/bin/python

import Pyro.core
import datetime
import reference_time
from time import sleep

class dummy_clock( Pyro.core.ObjBase ):
    """equates a given reference time with the real time when an object
    is initialised, and thereafter increment the reference time at some
    rate of hours-per-realtime-second."""

    def __init__( self, ref_time, rate ):

        Pyro.core.ObjBase.__init__(self)

        self.base_time = datetime.datetime.now() 
        self.base_ref_time = ref_time
        self.rate = rate    # real seconds per hour of reference time

    def get_dummytime( self ):
        # compute current reference time

        delta = datetime.datetime.now() - self.base_time
        
        # time deltas are expressed as days, seconds, microseconds
        days = delta.days
        seconds = delta.seconds
        microseconds = delta.microseconds

        real_seconds = microseconds / 1000000 + seconds + days * 24 * 3600
        reftime_hours = real_seconds / self.rate

        return reference_time.increment( self.base_ref_time, reftime_hours )


def test():

    rt = "2008080800"
    foo = dummy_clock( rt, 10 )  # 10 seconds / hour

    print rt                     # 2008080800
    sleep(20)                    # 20 secons => 2 hours
    print foo.get_dummytime()    # 2008080802


if __name__ == "__main__":
    test()
