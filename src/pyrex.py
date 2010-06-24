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
            self.ns = Pyro.naming.NameServerLocator().getNS( hostname )
        except NamingError:
            raise SystemExit("Failed to find a Pyro nameserver on " + hostname )

    def get_ns( self ):
        return self.ns


    def obj_name( self, name, groupname ):
        # object name as registered with the Pyro nameserver
        return groupname + '.' + name

    def registered( self, groupname ):
        if groupname in self.get_groups().keys():
            return True
        else:
            return False

    def get_groups( self ):
        groups = {}
        # loop through registered objects
        for obj in self.ns.flatlist():
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

            if group not in groups.keys():
                groups[ group ] = 1
            else:
                groups[ group ] += + 1

        return groups

    def print_info( self ):
        groups = self.get_groups()
        n_groups = len( groups.keys() )
        print "There are ", len( groups.keys() ), " groups registered with Pyro"
        for group in groups:
            print ' + ', group, ' ... (', groups[group], 'objects )'


    def create_groupname( self, groupname ):
        try:
            self.ns.createGroup( groupname )

        except NamingError:
            # abort if any existing objects are registered in my group name
            # (this may indicate another instance of cylc is running
            # with the same groupname; must be unique for each instance
            # else the different systems will interfere with each other) 
            print "\nERROR: the Pyro Nameserver group '" + groupname + "' is already in use."
            objs = self.ns.list( groupname )
            if len( objs ) == 0:
                print "It currently contains no objects."
            else:
                print "It contains the following registered objects:"
                for obj in objs:
                    print '  + ' + obj[0]

            print
            print "YOUR OPTIONS ARE:"
            print 
            print "(1) If the nameserver group is being used by another cylc instance,"
            print "re-register your system under a different name before running it."
            print 
            print "(2) If the nameserver group is a relic of a cylc instance that did"
            print "not shut down cleanly, you can delete it from the nameserver by:"
            print 
            print "pyro-nsc deletegroup " + groupname + "   #<-------(manual cleanup)" 
            print
            raise SystemExit( "ABORTING NOW" )

