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

    def __init__( self, task_name, ref_time, use_clock, clock_rate = 20 ):
        self.task_name = task_name
        self.ref_time = ref_time
        self.use_clock = use_clock
        self.clock_rate = clock_rate

        if self.use_clock:
            self.clock = Pyro.core.getProxyForURI('PYRONAME://' + pyro_ns_name( 'dummy_clock' ))

        self.task = Pyro.core.getProxyForURI('PYRONAME://' + pyro_ns_name( self.task_name + '%' + self.ref_time ))
        self.fast_complete = False

    def run( self ):

        completion_time = self.task.get_postrequisite_times()
        postreqs = self.task.get_postrequisite_list()

        if not self.use_clock:

            # report postrequisites done at the estimated time for each,
            # scaled by the configured dummy clock rate, but without reference
            # to the actual dummy clock: so dummy tasks do not complete faster
            # when we bump the dummy clock forward.
         
            n_postreqs = len( postreqs )
         
            for req in postreqs:
                sleep( completion_time[ req ] / float( self.clock_rate ) )
                self.task.incoming( "NORMAL", req )

        else:

            self.delay()

            start_time = self.clock.get_datetime()

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
                dt = self.clock.get_datetime()
                all_done = True
                for req in postreqs:
                    if not done[ req]:
                        if dt >= time[ req ]:
                            #print "SENDING MESSAGE: ", time[ req ], req
                            self.task.incoming( "NORMAL", req )
                            done[ req ] = True
                        else:
                            all_done = False

                if all_done:
                    break
            
    def delay( self ):
        # override this to delay abnormal dummy tasks (downloader,
        # topnet streamflow) according to clock time restraints
        pass
