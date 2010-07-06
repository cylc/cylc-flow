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

import os, re

class pyrex:

    def __init__( self, hostname, sysname, username=None ):

        self.hostname = hostname

        if username:
            self.username = username
        else:
            self.username = os.environ['USER']

        # LOCATE THE PYRO NAMESERVER
        try:
            self.ns = Pyro.naming.NameServerLocator().getNS( self.hostname )
        except NamingError:
            raise SystemExit("Failed to find a Pyro nameserver on " + self.hostname )

        self.groupname = ':cylc'
        try:
            self.ns.createGroup( self.groupname )
        except Pyro.errors.NamingError:
            #print self.groupname, 'exists'
            pass
        
        self.groupname += '.' + self.username
        try:
            self.ns.createGroup( self.groupname )
        except Pyro.errors.NamingError:
            #print self.groupname, 'exists'
            pass

        self.groupname += '.' + sysname
        try:
            self.ns.createGroup( self.groupname )
        except NamingError:
            # abort if any existing objects are registered in my group name
            objs = self.ns.list( self.groupname )
            print "\nERROR: " + self.groupname + " is already registered with Pyro (" + str( len( objs )) + " objects)."
            for obj in objs:
                print '  + ' + obj[0]
            print "Either you are running system already", sysname, "OR the previous run failed"
            print "to shut down cleanly, in which case you can clean up like this:"
            print 
            print "pyro-nsc deletegroup " + self.groupname + "   #<-------(manual cleanup)" 
            print
            raise SystemExit( "ABORTING NOW" )

        # REQUIRE SINGLE THREADED PYRO (see documentation)
        Pyro.config.PYRO_MULTITHREADED = 0
        # USE DNS NAMES INSTEAD OF FIXED IP ADDRESSES FROM /etc/hosts
        # (see the Userguide "Networking Issues" section).
        Pyro.config.PYRO_DNS_URI = True

        Pyro.core.initServer()

        # CREATE A PYRO DAEMON FOR THIS SYSTEM
        self.pyro_daemon = Pyro.core.Daemon()
        self.pyro_daemon.useNameServer(self.ns)

    def shutdown( self, thing ):
        # TO DO: WHAT IS THING (T/F)

        print "Shutting down my Pyro daemon"
        self.pyro_daemon.shutdown( thing )

        print "Deleting Pyro nameserver group " + self.groupname
        self.ns.deleteGroup( self.groupname )

    def connect( self, obj, name ):
        self.pyro_daemon.connect( obj, self.pyro_obj_name( name ) )

    def disconnect( self, obj ):
        self.pyro_daemon.disconnect( obj )

    def handleRequests( self, timeout=None ):
        self.pyro_daemon.handleRequests( timeout )

    def get_ns( self ):
        return self.ns

    def pyro_obj_name( self, name ):
        # object name as registered with the Pyro nameserver
        return self.groupname + '.' + name

    def get_groupname( self ):
        return self.groupname

class discover:
    def __init__( self, hostname ):
        self.root = ':cylc'

        # LOCATE THE PYRO NAMESERVER
        try:
            self.ns = Pyro.naming.NameServerLocator().getNS( hostname )
        except NamingError:
            raise SystemExit("Failed to find a Pyro nameserver on " + hostname )

    def registered( self, groupname ):
        if groupname in self.get_groups():
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

            if re.match( ':cylc\.', group ):
                pass
                #group = re.sub( '^:cylc\.', '', group )
            else:
                continue

            if group not in groups.keys():
                groups[ group ] = 1
            else:
                groups[ group ] += 1

        return groups

    def print_info( self ):
        groups = self.get_groups()
        n_groups = len( groups.keys() )
        print "There are ", len( groups.keys() ), " groups registered with Pyro"
        for group in groups:
            print ' + ', group, ' ... (', groups[group], 'objects )'
