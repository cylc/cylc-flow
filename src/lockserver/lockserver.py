#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|

import Pyro.core, Pyro.naming, Pyro.errors
import os,sys,socket
import logging, logging.handlers

groupname = ':cylc-lockserver'
name = 'broker'

def get_lockserver( pns_host ):
    try:
        server = Pyro.core.getProxyForURI('PYRONAME://' + pns_host + '/' + groupname + '.' + name)
    except Pyro.errors.NamingError:
        raise SystemExit( "Failed to connect to a lockserver on " + pns_host )

    return server

class lockserver( Pyro.core.ObjBase ):
    def __init__( self, pns_host, logfile, loglevel=logging.INFO ):
        Pyro.core.ObjBase.__init__(self)

        try:
            self.nameserver = Pyro.naming.NameServerLocator().getNS( pns_host )
        except Pyro.errors.NamingError:
            raise SystemExit("Failed to find a Pyro nameserver on " + hostname )

        # CREATE A UNIQUE NAMESERVER GROUPNAME FOR THE LOCK SERVER ------------
        try:
            self.nameserver.createGroup( groupname )
        except Pyro.errors.NamingError:
            # group already exists
            pass

        # task locks
        self.locked = {}

        # suite locks
        self.exclusive = {}       # exclusive[ suite_dir ] = [ groupname ]
        self.inclusive = {}       # inclusive[ suite_dir ] = [ groupname, ... ]

        self.configure_logging( logfile, loglevel )

    def configure_logging( self, logfile, loglevel ):
        self.log = logging.getLogger( logfile )
        self.log.setLevel( loglevel )
        max_bytes = 1000000
        backups = 5
        logging_dir = os.path.dirname( logfile )
        if not os.path.exists( logging_dir ):
            try:
                os.makedirs( logging_dir )
            except:
                raise SystemExit( 'Unable to create lockserver logging directory ' + logging_dir )

        h = logging.handlers.RotatingFileHandler( logfile, 'a', max_bytes, backups )
        # roll the log file if it already exists
        if os.path.getsize( logfile ) > 0:
            h.doRollover()

        self.log.addHandler( h )


    def get_ns( self ):
        return self.nameserver

    def get_pyro_name( self ):
        return groupname + '.' + name

    def get_lock_id( self, lockgroup, task_id ):
        return lockgroup + ':' + task_id

    def get_lockgroup( self, lock_id ):
        (lockgroup, id) = lock_id.split(':')
        return lockgroup

    def get_suite_string( self, lockgroup, suite_dir ):
        return lockgroup + '-->' + suite_dir

    def acquire( self, task_id, lockgroup ):
        id = self.get_lock_id( lockgroup, task_id )
        if id not in self.locked:
            self.locked[ id ] = True
            self.log.info( "acquired task lock " + id ) 
            return True
        else:
            self.log.warning( "refused task lock " + id ) 
            return False

    def release( self, task_id, lockgroup ):
        id = self.get_lock_id( lockgroup, task_id )
        if id in self.locked:
            del self.locked[ id ]
            self.log.info( "released task lock " + id ) 
            return True
        else:
            self.log.warning( "failed to release task lock " + id ) 
            return False

    def dump( self ):
         self.log.info( "Dumping locks") 
         return ( self.locked.keys(), self.exclusive, self.inclusive )

    def clear( self ):
        # release all locks one at a time so each release gets logged
        n = len( self.locked.keys() )
        self.log.info( "Clearing " + str(n) + " task locks") 
        # MUST USE .keys() here to avoid:
        # RuntimeError: dictionary changed size during iteration
        for lock in self.locked.keys():
            ( group, id ) = lock.split( ':' )
            self.release( id, group )

        n = len( self.exclusive.keys() )
        self.log.info( "Clearing " + str(n) + " exclusive suite locks") 
        for suitedir in self.exclusive.keys():
            [ group ] = self.exclusive[ suitedir ]
            self.release_suite_access( suitedir, group )

        n = 0
        for suitedir in self.inclusive.keys():
            groups = self.inclusive[ suitedir ]
            n += len( groups )
        self.log.info( "Clearing " + str(n) + " non-exlusive suite locks") 
        for suitedir in self.inclusive.keys():
            groups = self.inclusive[ suitedir ]
            for group in groups:
                self.release_suite_access( suitedir, group )

    def is_locked( self, task_id, lockgroup ):
        id = self.get_lock_id( lockgroup, task_id )
        if id in self.locked:
            return True
        else:
            return False

    def get_suite_access( self, suite_dir, lockgroup, cylc_mode, request_exclusive ):
        # EXCLUSIVE: one only named suite can use suite_dir at once
        #   - submit can attempt to get a task lock IF via the same name
        # INCLUSIVE: multiple named suites can use suite_dir at once
        #   - submit can attempt to get a task lock always

        suite_descr = self.get_suite_string( lockgroup, suite_dir ) 

        result = True
        reason = "granted"
 
        if cylc_mode != 'submit':
            if ( request_exclusive and suite_dir in self.inclusive ) or \
                    ( not request_exclusive and suite_dir in self.exclusive ):
                result = False
                reason = "inconsistent exclusivity for " + suite_dir
                self.log.warning( reason ) 
                return ( False, reason )
 
        if request_exclusive:
            if suite_dir in self.exclusive:
                name = self.exclusive[ suite_dir ][0]
                already = self.get_suite_string( name, suite_dir )

                if cylc_mode == 'submit':
                    # grant access only if lockgroup is the same
                    if lockgroup == name:
                        pass
                    else:
                        result = False
                        reason = self.get_suite_string( name, suite_dir ) + " in exclusive use"
                else:
                    # no exclusive access to any suite already in use
                    result = False
                    reason = suite_descr + " in exclusive use" 
            else:
                # suite dir not already in self.exclusive
                if cylc_mode == 'submit':
                    # grant access but don't set a lock
                    pass 
                else: 
                    # grant exclusive access
                    self.exclusive[ suite_dir ] = [ lockgroup ]
        else:
            # inclusive access requested
            if suite_dir in self.inclusive:
                names = self.inclusive[ suite_dir ]

                if cylc_mode == 'submit':
                    # granted
                    pass
                else:
                    # grant access unless same name already in use
                    if lockgroup in names:
                        result = False
                        reason =  lockgroup + '-->' + suite_dir + " already in use"
                    else:
                        # granted
                        self.inclusive[ suite_dir ].append( lockgroup )
            else:
                if cylc_mode == 'submit':
                    # granted
                    pass
                else:
                    # granted
                    self.inclusive[ suite_dir ] = [ lockgroup ]
 
        if result:
            if cylc_mode == 'submit':
                self.log.info( "granted suite access " + lockgroup + " --> " + suite_dir )
            else:
                self.log.info( "acquired suite lock " + lockgroup + " --> " + suite_dir )
        else:
            if cylc_mode == 'submit':
                self.log.warning( "refused suite access " + lockgroup + " --> " + suite_dir )
            else:
                self.log.warning( "refused suite lock " + lockgroup + " --> " + suite_dir )
            self.log.warning( " " + reason )

        return ( result, reason )


    def release_suite_access( self, suite_dir, lockgroup ):
        # first release any task locks held by the suite
        for id in self.locked.keys():
            print id
            print self.get_lockgroup( id ), lockgroup
            if self.get_lockgroup( id ) == lockgroup:
                print "HELLO"
                del self.locked[ id ]
                self.log.info( "released task lock " + id ) 

        result = True
        if suite_dir in self.exclusive:
            if lockgroup not in self.exclusive[ suite_dir ]:
                #self.log.warning( "suite release group name error" )
                result = False
            else:
                del self.exclusive[ suite_dir ]
                result = True
        elif suite_dir in self.inclusive:
            names = self.inclusive[ suite_dir ]
            if lockgroup not in names:
                #self.log.warning( "suite release group name error" )
                result = False
            elif len( names ) == 1:
                del self.inclusive[ suite_dir ]
                result = True
            else:
                self.inclusive[ suite_dir ].remove( lockgroup )
                result = True
        else:
            #self.log.warning( "erroneous suite release request" )
            result = False
        if result:
            self.log.info( "released suite lock " + lockgroup + " --> " + suite_dir )
        else:
            self.log.warning( "failed to release suite lock " + lockgroup + " --> " + suite_dir )

        return result

class control:
    def __init__( self, pns_host=None ):
        self.server = get_lockserver( pns_host )

    def dump( self ):
        return self.server.dump()

    def clear( self ):
        self.server.clear()
