#!/usr/bin/python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


from cycling import cycling
from mod_oneoff import oneoff
import re

class cycling_daemon( oneoff, cycling ):
    # A oneoff task that adds outputs dynamically as messages matching
    # registered patterns come in. The corresponding real task may keep
    # running indefinitely, e.g. to watch for incoming external data.

    # not 'daemon' - hasattr(task, 'daemon') returns True for all tasks 
    # due to the pyro daemon (I think).
    daemon_task = True  

    def incoming( self, priority, message ):
        # intercept incoming messages and check for a pattern match 
        for pattern in self.output_patterns:
            m = re.match( pattern, message )
            if m:
                self.outputs.add( 10, message )
                # RESET MY REFERENCE TIME
                #foo = m.groups()[0]
                #self.c_time = foo
                #self.tag = foo
                #self.id = self.name + '%' + self.tag

        cycling.incoming( self, priority, message )
