#!/usr/bin/pyro

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
 
import Pyro.core, Pyro.naming
from Pyro.errors import NamingError

import sys
import re


class pyrex:
    def __init__( self, groupname, hostname ):

        self.groupname = groupname

        print "CONFIGURING Pyro........"
        # REQUIRE SINGLE THREADED OPERATION (see documentation)
        print " - single threaded" 
        Pyro.config.PYRO_MULTITHREADED = 0

        # locate the Pyro nameserver
        print " - locating nameserver on " + hostname + " ...",
        try:
            self.nameserver = Pyro.naming.NameServerLocator().getNS( hostname )
        except NamingError:
            raise SystemExit("Failed to find a Pyro nameserver on " + hostname )

        print "found"
        # create a nameserver group for this system
        print " - creating nameserver group '" + groupname + "'"
        try:
            # abort if any existing objects are registered in my group name
            # (this may indicate another instance of cylc is running
            # with the same groupname; must be unique for each instance
            # else the different systems will interfere with each other) 
            self.nameserver.createGroup( groupname )

        except NamingError:
            print "\nERROR: group '" + groupname + "' is already registered"
            objs = self.nameserver.list( groupname )
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

        Pyro.core.initServer()

        # create a pyro_daemon for this program
        self.daemon = Pyro.core.Daemon()
        self.daemon.useNameServer(self.nameserver)

    def object_id( self, name ):
        return self.groupname + '.' + name
    
    def connect( self, object, name ):
        self.daemon.connect( object, self.object_id( name ) )

    def disconnect( self, object ):
        self.daemon.disconnect( object )

    def shutdown( self, bool ):
        # shut down the daemon
        print "Shutting down my Pyro daemon"
        self.daemon.shutdown( bool )
        print "Deleting group " + self.groupname + " from the Pyro nameserver"
        # delete my group from the nameserver
        self.nameserver.deleteGroup( self.groupname )

    def handleRequests( self, timeout ):
        self.daemon.handleRequests( timeout )


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

    def registered( self, name ):
        if name in self.ns_groups.keys():
            return True
        else:
            return False

    def print_info( self ):
        n_groups = len( self.ns_groups.keys() )
        print "Currently ", len( self.ns_groups.keys() ), " systems registered with Pyro"
        for group in self.ns_groups.keys():
            print ' + ', group, ' ... (', self.ns_groups[group], 'objects )'
