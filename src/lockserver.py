#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|

import Pyro.core
import os,sys,socket
import os, logging

groupname = ':cylc-lockserver'
name = 'broker'

def get_lockserver( pns_host ):
    try:
        server = Pyro.core.getProxyForURI('PYRONAME://' + pns_host + '/' + groupname + '.' + name)
    except:
        raise SystemExit( "Failed to connect to a lockserver on " + pns_host )
    return server

def get_lockgroup( system, obj_name, user=os.environ['USER'] ):
    return user + '.' + system + '.' + obj_name

class lockserver( Pyro.core.ObjBase ):
    def __init__( self, pns_host, logfile, loglevel=logging.INFO ):
        Pyro.core.ObjBase.__init__(self)

        try:
            self.nameserver = Pyro.naming.NameServerLocator().getNS( pns_host )
        except NamingError:
            raise SystemExit("Failed to find a Pyro nameserver on " + hostname )

        # CREATE A UNIQUE NAMESERVER GROUPNAME FOR THE LOCK SERVER ------------
        try:
            self.nameserver.createGroup( groupname )
        except:
            # group already exists
            pass
            #raise
            #self.nameserver.deleteGroup( groupname )
            #self.nameserver.createGroup( groupname )

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
        #   - run-task can attempt to get a task lock IF via the same name
        # INCLUSIVE: multiple named systems can use system_dir at once
        #   - run-task can attempt to get a task lock always

        sys_descr = self.get_sys_string( lockgroup, system_dir ) 

        result = True
        reason = "granted"
 
        if cylc_mode != 'run-task':
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

                if cylc_mode == 'run-task':
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
                if cylc_mode == 'run-task':
                    # grant access but don't set a lock
                    pass 
                else: 
                    # grant exclusive access
                    self.exclusive[ system_dir ] = [ lockgroup ]
        else:
            # inclusive access requested
            if system_dir in self.inclusive:
                names = self.inclusive[ system_dir ]

                if cylc_mode == 'run-task':
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
                if cylc_mode == 'run-task':
                    # granted
                    pass
                else:
                    # granted
                    self.inclusive[ system_dir ] = [ lockgroup ]
 
        if result:
            if cylc_mode == 'run-task':
                logging.info( "granted system access " + lockgroup + " --> " + system_dir )
            else:
                logging.info( "acquired system lock " + lockgroup + " --> " + system_dir )
        else:
            if cylc_mode == 'run-task':
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

class syslock:
    def __init__( self, pns_host, username, sysname, system_dir, cylc_mode ):

        self.pns_host = pns_host
        self.system_dir = system_dir
        self.cylc_mode = cylc_mode

        self.lockgroup = username + '.' + sysname


    def request_system_access( self, exclusive=True ):
        # Cylc system name is user-specific (i.e. different users can
        # register systems with the same name), but the cylc groupname
        # (USERNAME^SYSTEMNAME) is unique (because two users cannot have
        # the same username).        

        # System config files should specify whether or not a system is
        # 'exclusive' - i.e. is it possible to run multiple copies (with
        # different registered group names) of the entire system at
        # once? 
        
        # GET A NEW CONNECTION WITH EACH REQUEST
        # TO DO: OR GET A SINGLE CONNECTION IN INIT

        server = get_lockserver( self.pns_host )
        (result, reason) = server.get_system_access( self.system_dir, self.lockgroup, self.cylc_mode, exclusive )
        if not result:
            print >> sys.stderr, 'ERROR, failed to get system access:'
            print >> sys.stderr, reason
            return False
        else:
           return True


    def release_system_access( self):
        server = get_lockserver( self.pns_host )
        result = server.release_system_access( self.system_dir, self.lockgroup )
        if not result:
            print >> sys.stderr, 'WARNING, failed to release system access'
            return False
        else:
           return True

class lock:

    # ATTEMPT TO ACQUIRE YOUR LOCK AFTER SENDING THE CYLC START MESSAGE
    # so that failure to lock will be reported to the cylc task logs, as
    # well as to stdout, without causing cylc to complain that it has
    # received a message from a task that has not started running yet.
    # Similarly, the lock release message is only echoed to stdout
    # because it is necessarily emitted after the task finished message.
    # (a cylc message after that time will cause cylc to complain that
    # it has received a message from a task that has finished running). 

    def __init__( self, task_id=None, user=None, sysname=None, pns_host=None ):

        self.use_lock_server = False
        if 'CYLC_USE_LOCKSERVER' in os.environ:
            if os.environ[ 'CYLC_USE_LOCKSERVER' ] == 'True':
                self.use_lock_server = True

        self.mode = 'raw'
        if 'CYLC_MODE' in os.environ:
            self.mode = os.environ[ 'CYLC_MODE' ]
            # 'scheduler' or 'run-task'

        if task_id:
            self.task_id = task_id
        else:
            if 'TASK_ID' in os.environ.keys():
                self.task_id = os.environ[ 'TASK_ID' ]
            elif self.mode == 'raw':
                self.task_id = 'TASK_ID'
            else:
                print >> sys.stderr, '$TASK_ID not defined'
                sys.exit(1)

        if user:
            self.username = user
        else:
            self.username = os.environ['USER']

        if sysname:
            self.system_name = sysname
        else:
            if 'CYLC_SYSTEM_NAME' in os.environ.keys():
                self.system_name = os.environ[ 'CYLC_SYSTEM_NAME' ]
            elif self.mode == 'raw':
                pass
            else:
                print >> sys.stderr, '$CYLC_SYSTEM_NAME not defined'
                sys.exit(1)

        self.lockgroup = self.username + '.' + self.system_name

        if pns_host:
            self.pns_host = pns_host
        else:
            if 'CYLC_NS_HOST' in os.environ.keys():
                self.pns_host = os.environ[ 'CYLC_NS_HOST' ]
            elif self.mode == 'raw':
                pass
            else:
                # we always define the PNS Host explicitly, but could
                # default to localhost's fully qualified domain name
                # like this:   self.pns_host = socket.getfqdn()
                print >> sys.stderr, '$CYLC_NS_HOST not defined'
                sys.exit(1)

    def acquire( self ):
        if not self.use_lock_server:
            print >> sys.stderr, "WARNING: you are not using cylc the lockserver." 
            return True
 
        server = get_lockserver( self.pns_host )
        if server.acquire( self.task_id, self.lockgroup ):
            print "Gave task lock for", self.lockgroup + ':' + self.task_id
            return True
        else:
            print >> sys.stderr, "Refused task lock for", self.lockgroup + ':' + self.task_id
            if server.is_locked( self.task_id, self.lockgroup ):
                print >> sys.stderr, self.lockgroup + ':' + self.task_id, "is already locked!"
            return False

    def release( self ):
        if not self.use_lock_server:
            print >> sys.stderr, "WARNING: you are not using cylc the lockserver." 
            return True

        server = get_lockserver( self.pns_host )
        if server.is_locked( self.task_id, self.lockgroup ):
            if server.release( self.task_id, self.lockgroup ):
                print "Released task lock for", self.lockgroup + ':' + self.task_id
                return True
            else:
                print >> sys.stderr, "Failed to release task lock for", self.lockgroup + ':' + self.task_id
                return False
        else:
            print >> sys.stderr, "WARNING", self.lockgroup + ':' + self.task_id, "was not locked!"
            return True

class control:
    def __init__( self, pns_host=None ):
        self.server = get_lockserver( pns_host )

    def dump( self ):
        return self.server.dump()

    def clear( self ):
        self.server.clear()
