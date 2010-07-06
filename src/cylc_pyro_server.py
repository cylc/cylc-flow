#!/usr/bin/pyro

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# Different cylc systems must register their Pyro objects under
# different "group names" in the Pyro Nameserver so that they don't 
# interfere with each other. 

# See the Pyro manual for nameserver hierachical naming details.
 
import os, re
import Pyro.naming, Pyro.errors

class pyrex:
    def __init__( self, hostname, sysname, username=os.environ['USER'] ):
        self.hostname = hostname

        self.rootgroup = ':cylc'
        self.usergroup = self.rootgroup + '.' + username
        self.groupname = self.usergroup + '.' + sysname

        # LOCATE THE PYRO NAMESERVER
        try:
            self.ns = Pyro.naming.NameServerLocator().getNS( self.hostname )
        except Pyro.errors.NamingError:
            raise SystemExit("Failed to find a Pyro Nameserver on " + self.hostname )

        # create root group ':cylc'
        try:
            self.ns.createGroup( self.rootgroup )
        except Pyro.errors.NamingError:
            # handle only NamingError: group exists already
            pass
        
        # create groupname ':cylc.username'
        try:
            self.ns.createGroup( self.usergroup )
        except Pyro.errors.NamingError:
            # handle only NamingError: group exists already
            pass

        # create full groupname ':cylc.username'
        try:
            self.ns.createGroup( self.groupname )
        except Pyro.errors.NamingError:
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

    def get_groupname( self ):
        return self.groupname

    def shutdown( self, thing ):
        # TO DO: WHAT IS THING (T/F)

        print "Shutting down my Pyro daemon"
        self.pyro_daemon.shutdown( thing )

        print "Deleting Pyro Nameserver group " + self.groupname
        self.ns.deleteGroup( self.groupname )

    def get_ns( self ): ########################################### NEEDED?
        return self.ns

    def connect( self, obj, name ):
        reg_name = self.groupname + '.' + name
        self.pyro_daemon.connect( obj, reg_name )

    def disconnect( self, obj ):
        self.pyro_daemon.disconnect( obj )

    def handleRequests( self, timeout=None ):
        self.pyro_daemon.handleRequests( timeout )
