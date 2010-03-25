#!/usr/bin/pyro

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# Here's how to run a Pyro nameserver in its own thread in the main program:
#import threading
#ns_starter = Pyro.naming.NameServerStarter()
#ns_thread = threading.Thread( target = ns_starter.start )
#ns_thread.setDaemon(True)
#ns_thread.start()
#ns_starter.waitUntilStarted(10)

# Different cylc instances must use different Pyro nameserver 
# group names to prevent the different systems interfering with
# each other via the common nameserver. 

# See Pyro manual for nameserver hierachical naming details ...
# prepending ':' puts names or sub-groups under the root group. 
 
import Pyro.naming
from Pyro.errors import NamingError

import re

class discover:
    # what groups are currently registered with the Pyro nameserver

    def __init__( self, hostname ):
        try:
            ns = Pyro.naming.NameServerLocator().getNS( hostname )
        except NamingError:
            raise SystemExit("Failed to find a Pyro nameserver on " + hostname )

        self.ns_groups = {}
        # loop through registered objects
        for obj in ns.flatlist():
            # Extract the group name for each object (GROUP.name).
            # Note that GROUP may contain '.' characters too.
            # E.g. ':Default.ecoconnect.name'
            group = obj[0].rsplit('.', 1)[0]
            # now strip off ':Default'
            # TO DO: use 'cylc' group!
            group = re.sub( '^:Default\.', '', group )
            if re.match( ':Pyro', group ):
                # avoid Pyro.nameserver itself
                continue

            if group not in self.ns_groups.keys():
                self.ns_groups[ group ] = 1
            else:
                self.ns_groups[ group ] += + 1

    def registered( self, groupname ):
        if groupname in self.ns_groups.keys():
            return True
        else:
            return False

    def get_groups( self ):
        return self.ns_groups.keys()

    def print_info( self ):
        n_groups = len( self.ns_groups.keys() )
        print "Currently ", len( self.ns_groups.keys() ), " systems registered with Pyro"
        for group in self.ns_groups.keys():
            print ' + ', group, ' ... (', self.ns_groups[group], 'objects )'
