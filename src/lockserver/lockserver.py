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
import os, logging

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

        # system locks
        self.exclusive = {}       # exclusive[ system_dir ] = [ groupname ]
        self.inclusive = {}       # inclusive[ system_dir ] = [ groupname, ... ]

        logging.basicConfig( filename=logfile, level=loglevel, format="%(asctime)s [%(levelname)s] %(message)s" )

    def get_ns( self ):
        return self.nameserver

    def get_pyro_name( self ):
        return groupname + '.' + name

    def get_lock_id( self, lockgroup, task_id ):
        return lockgroup + ':' + task_id

    def get_sys_string( self, lockgroup, system_dir ):
        return lockgroup + '-->' + system_dir

    def acquire( self, task_id, lockgroup ):
        id = self.get_lock_id( lockgroup, task_id )
        if id not in self.locked:
            self.locked[ id ] = True
            logging.info( "acquired task lock " + id ) 
            return True
        else:
            logging.warning( "refused task lock " + id ) 
            return False

    def release( self, task_id, lockgroup ):
        id = self.get_lock_id( lockgroup, task_id )
        if id in self.locked:
            del self.locked[ id ]
            logging.info( "released task lock " + id ) 
            return True
        else:
            logging.warning( "failed to release task lock " + id ) 
            return False

    def dump( self ):
         logging.info( "Dumping locks") 
         return ( self.locked.keys(), self.exclusive, self.inclusive )

    def clear( self ):
        # release all locks one at a time so each release gets logged
        n = len( self.locked.keys() )
        logging.info( "Clearing " + str(n) + " task locks") 
        # MUST USE .keys() here to avoid:
        # RuntimeError: dictionary changed size during iteration
        for lock in self.locked.keys():
            ( group, id ) = lock.split( ':' )
            self.release( id, group )

        n = len( self.exclusive.keys() )
        logging.info( "Clearing " + str(n) + " exclusive system locks") 
        for sysdir in self.exclusive.keys():
            [ group ] = self.exclusive[ sysdir ]
            self.release_system_access( sysdir, group )

        n = 0
        for sysdir in self.inclusive.keys():
            groups = self.inclusive[ sysdir ]
            n += len( groups )
        logging.info( "Clearing " + str(n) + " non-exlusive system locks") 
        for sysdir in self.inclusive.keys():
            groups = self.inclusive[ sysdir ]
            for group in groups:
                self.release_system_access( sysdir, group )

    def is_locked( self, task_id, lockgroup ):
        id = self.get_lock_id( lockgroup, task_id )
        if id in self.locked:
            return True
        else:
            return False

    def get_system_access( self, system_dir, lockgroup, cylc_mode, request_exclusive ):
        # EXCLUSIVE: one only named system can use system_dir at once
        #   - submit can attempt to get a task lock IF via the same name
        # INCLUSIVE: multiple named systems can use system_dir at once
        #   - submit can attempt to get a task lock always

        sys_descr = self.get_sys_string( lockgroup, system_dir ) 

        result = True
        reason = "granted"
 
        if cylc_mode != 'submit':
            if ( request_exclusive and system_dir in self.inclusive ) or \
                    ( not request_exclusive and system_dir in self.exclusive ):
                result = False
                reason = "inconsistent exclusivity for " + system_dir
                logging.warning( reason ) 
                return ( False, reason )
 
        if request_exclusive:
            if system_dir in self.exclusive:
                name = self.exclusive[ system_dir ][0]
                already = self.get_sys_string( name, system_dir )

                if cylc_mode == 'submit':
                    # grant access only if lockgroup is the same
                    if lockgroup == name:
                        pass
                    else:
                        result = False
                        reason = self.get_sys_string( name, system_dir ) + " in exclusive use"
                else:
                    # no exclusive access to any system already in use
                    result = False
                    reason = sys_descr + " in exclusive use" 
            else:
                # system dir not already in self.exclusive
                if cylc_mode == 'submit':
                    # grant access but don't set a lock
                    pass 
                else: 
                    # grant exclusive access
                    self.exclusive[ system_dir ] = [ lockgroup ]
        else:
            # inclusive access requested
            if system_dir in self.inclusive:
                names = self.inclusive[ system_dir ]

                if cylc_mode == 'submit':
                    # granted
                    pass
                else:
                    # grant access unless same name already in use
                    if lockgroup in names:
                        result = False
                        reason =  lockgroup + '-->' + system_dir + " already in use"
                    else:
                        # granted
                        self.inclusive[ system_dir ].append( lockgroup )
            else:
                if cylc_mode == 'submit':
                    # granted
                    pass
                else:
                    # granted
                    self.inclusive[ system_dir ] = [ lockgroup ]
 
        if result:
            if cylc_mode == 'submit':
                logging.info( "granted system access " + lockgroup + " --> " + system_dir )
            else:
                logging.info( "acquired system lock " + lockgroup + " --> " + system_dir )
        else:
            if cylc_mode == 'submit':
                logging.warning( "refused system access " + lockgroup + " --> " + system_dir )
            else:
                logging.warning( "refused system lock " + lockgroup + " --> " + system_dir )
            logging.warning( " " + reason )

        return ( result, reason )


    def release_system_access( self, system_dir, lockgroup ):
        result = True
        if system_dir in self.exclusive:
            if lockgroup not in self.exclusive[ system_dir ]:
                #logging.warning( "system release group name error" )
                result = False
            else:
                del self.exclusive[ system_dir ]
                result = True
        elif system_dir in self.inclusive:
            names = self.inclusive[ system_dir ]
            if lockgroup not in names:
                #logging.warning( "system release group name error" )
                result = False
            elif len( names ) == 1:
                del self.inclusive[ system_dir ]
                result = True
            else:
                self.inclusive[ system_dir ].remove( lockgroup )
                result = True
        else:
            #logging.warning( "erroneous system release request" )
            result = False
        if result:
            logging.info( "released system lock " + lockgroup + " --> " + system_dir )
        else:
            logging.warning( "failed to release system lock " + lockgroup + " --> " + system_dir )

        return result

class control:
    def __init__( self, pns_host=None ):
        self.server = get_lockserver( pns_host )

    def dump( self ):
        return self.server.dump()

    def clear( self ):
        self.server.clear()
