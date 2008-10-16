#!/usr/bin/python

"""class for external dummy task programs that report task
postrequisites done at the right time relative to the accelerated dummy
mode clock. Use of the dummy clock means that dummy tasks react
correctly to bumping the clock forward AND we can fully simulate the
transition out of catchup mode."""

import sys
import Pyro.naming, Pyro.core
from Pyro.errors import NamingError
from pyro_ns_naming import pyro_ns_name
import reference_time
import datetime
from time import sleep

class dummy_task_base:

    def __init__( self, task_name, ref_time, clock_rate ):
        self.task_name = task_name
        self.ref_time = ref_time
        self.clock_rate = clock_rate
        self.clock = Pyro.core.getProxyForURI('PYRONAME://' + pyro_ns_name( 'dummy_clock' ))
        self.task = Pyro.core.getProxyForURI('PYRONAME://' + pyro_ns_name( task_name + '%' + ref_time ))
        self.fast_complete = False

    def run( self ):

        task_name = self.task_name
        ref_time = self.ref_time
        clock_rate = self.clock_rate
        clock = self.clock
        task = self.task

        completion_time = task.get_postrequisite_times()
        postreqs = task.get_postrequisite_list()

        self.delay()

        # set each postrequisite satisfied in turn
        start_time = clock.get_datetime()

        done = {}
        time = {}

        if self.fast_complete:
            speedup = 20.
        else:
            speedup = 1.
 
        for req in postreqs:
            done[ req ] = False
            hours = completion_time[ req] / 60.0 / speedup
            time[ req ] = start_time + datetime.timedelta( 0,0,0,0,0,hours,0)

        while True:
            sleep(1)
            dt = clock.get_datetime()
            all_done = True
            for req in postreqs:
                if not done[ req]:
                    if dt >= time[ req ]:
                        #print "SENDING MESSAGE: ", time[ req ], req
                        task.incoming( "NORMAL", req )
                        done[ req ] = True
                    else:
                        all_done = False

            if all_done:
                break
            
    def delay( self ):
        # override this to delay specific tasks based on clock time
        pass


# older method not based on the main program's dummy clock:

# report postrequisites done at the estimated time for each,
# scaled by the configured dummy clock rate, but without reference
# to the actual dummy clock: so dummy tasks do not complete faster
# when we bump the dummy clock forward.
#
#n_postreqs = len( postreqs )
#
#for req in postreqs:
#    sleep( completion_time[ req ] / float( clock_rate ) )
#    task.incoming( "NORMAL", req )
