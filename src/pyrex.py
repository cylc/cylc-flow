#!/usr/bin/pyro

# Here's how to run a Pyro nameserver in its own thread in the main program:
#import threading
#ns_starter = Pyro.naming.NameServerStarter()
#ns_thread = threading.Thread( target = ns_starter.start )
#ns_thread.setDaemon(True)
#ns_thread.start()
#ns_starter.waitUntilStarted(10)

# Different sequenz instances must use different Pyro nameserver 
# group names to prevent the different systems interfering with
# each other via the common nameserver. 

# See Pyro manual for nameserver hierachical naming details ...
# prepending ':' puts names or sub-groups under the root group. 
 
import Pyro.core, Pyro.naming
from Pyro.errors import NamingError

import sys

class pyrex:

    def __init__( self, groupname ):

        self.groupname = groupname

        print "CONFIGURING Pyro........"
        # REQUIRE SINGLE THREADED OPERATION (see documentation)
        print " - single threaded" 
        Pyro.config.PYRO_MULTITHREADED = 0

        # locate the Pyro nameserver
        print " - locating nameserver ...",
        try:
            pyro_nameserver = Pyro.naming.NameServerLocator().getNS()
        except:
            print "ERROR: failed to find a Pyro nameserver"
            raise

        print "found"
        # create a nameserver group for this system
        print " - creating nameserver group '" + groupname + "'"
        try:
            # abort if any existing objects are registered in my group name
            # (this may indicate another instance of sequenz is running
            # with the same groupname; must be unique for each instance
            # else the different systems will interfere with each other) 
            pyro_nameserver.createGroup( groupname )

        except NamingError:
            print "\nERROR: group '" + groupname + "' is already registered"
            objs = pyro_nameserver.list( groupname )
            if len( objs ) == 0:
                print "(although it currently contains no registered objects)."
            else:
                print "And contains the following registered objects:"
                for obj in objs:
                    print '  + ' + obj[0]

            print "\nOPTIONS:"
            print "(i) if the group is yours from a previous aborted run you can"
            print "    manually delete it with 'pyro-nsc deletegroup " + groupname +"'"
            print "(ii) if the group is being used by another program, change"
            print "    'system_name' in your config file to avoid interference.\n"

            print "ABORTING NOW"
            #raise NamingError
            sys.exit(1)

        # create a pyro_daemon for this program
        self.daemon = Pyro.core.Daemon()
        self.daemon.useNameServer(pyro_nameserver)

    def object_id( self, name ):
        return self.groupname + '.' + name
    
    def connect( self, object, name ):
        self.daemon.connect( object, self.object_id( name ) )

    def disconnect( self, object ):
        self.daemon.disconnect( object )

    def shutdown( self, bool ):
        self.daemon.shutdown( bool )

    def handleRequests( self, timeout ):
        self.daemon.handleRequests( timeout )

