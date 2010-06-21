#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver\@niwa.co.nz  |
#         |    +64-4-386 0461      |
#         |________________________|

import Pyro.core
import os,sys,socket
from connector import connector
import logging

class lockserver( Pyro.core.ObjBase ):

    def __init__( self, logfile, loglevel=logging.INFO ):
        Pyro.core.ObjBase.__init__(self)

        # task locks
        self.locked = {}

        # system locks
        self.exclusive = {}       # exclusive[ system_dir ] = [ groupname ]
        self.inclusive = {}       # inclusive[ system_dir ] = [ groupname, ... ]

        logging.basicConfig( filename=logfile, level=loglevel, format="%(asctime)s [%(levelname)s] %(message)s" )

    def get_lock_id( self, group_name, task_id ):
        return group_name + ':' + task_id

    def acquire( self, task_id, group_name ):
        id = self.get_lock_id( group_name, task_id )
        if id not in self.locked:
            self.locked[ id ] = True
            logging.info( "Acquired task lock for " + id ) 
            return True
        else:
            logging.info( "Refused task lock for " + id ) 
            return False

    def release( self, task_id, group_name ):
        id = self.get_lock_id( group_name, task_id )
        if id in self.locked:
            del self.locked[ id ]
            logging.info( "Released task lock for " + id ) 
            return True
        else:
            logging.info( "Failed to release task lock for " + id ) 
            return False

    def dump( self ):
         logging.info( "Dumping locks") 
         return self.locked.keys()

    def clear( self ):
        logging.info( "Clearing locks") 
        # MUST USE .keys() here to avoid:
        # RuntimeError: dictionary changed size during iteration
        for id in self.locked.keys():
            self.release( id, 'foo' )

    def is_locked( self, task_id, group_name ):
        id = self.get_lock_id( group_name, task_id )
        if id in self.locked:
            return True
        else:
            return False

    def get_system_access( self, system_dir, group_name, cylc_mode, request_exclusive ):
        # EXCLUSIVE: one only named system can use system_dir at once
        #   - run-task can attempt to get a task lock IF via the same name
        # INCLUSIVE: multiple named systems can use system_dir at once
        #   - run-task can attempt to get a task lock always

        if ( request_exclusive and system_dir in self.inclusive ) or \
                ( not request_exclusive and system_dir in self.exclusive ):
            logging.warn( "inconsistent system exclusivity detected!" ) 
            return ( False, "inconsistent system exclusivity detected!" )
 
        if request_exclusive:

            if system_dir in self.exclusive:
                name = self.exclusive[ system_dir ][0]

                if cylc_mode == 'run-task':
                    # grant access only if group_name is the same
                    if group_name == name:
                        return ( True, "granted" )
                    else:
                        return ( False, name + "-->" + system_dir + " in exclusive use" )

                else:
                    # no exclusive access to any system already in use
                    return ( False, name + "-->" + system_dir + " in exclusive use" )
            else:
                # grant exclusive access
                self.exclusive[ system_dir ] = [ group_name ]
                return ( True, "granted" )
 
        else:
            # inclusive access requested

            if system_dir in self.inclusive:
                names = self.inclusive[ system_dir ]

                if cylc_mode == 'run-task':
                    return ( True, "granted" )

                else:
                    # grant access unless same name already in use
                    if group_name in names:
                        return ( False, name + '-->' + system_dir + " already in use" )
                    else:
                        self.inclusive[ system_dir ].append( group_name )
                        return ( True, "granted" )

            else:
                self.inclusive[ system_dir ] = [ group_name ]
                return ( True, "granted" )
 

    def release_system_access( self, system_dir, group_name ):
        result = True
        if system_dir in self.exclusive:
            if group_name not in self.exclusive[ system_dir ]:
                #logging.warning( "system release group name error" )
                result = False

            else:
                del self.exclusive[ system_dir ]
                result = True

        elif system_dir in self.inclusive:
            names = self.inclusive[ system_dir ]
            if group_name not in names:
                #logging.warning( "system release group name error" )
                result = False

            elif len( names ) == 1:
                del self.inclusive[ system_dir ]
                result = True
            else:
                self.inclusive[ system_dir ].remove( group_name )
                result = True
            
        else:
            #logging.warning( "erroneous system release request" )
            result = False

        if result:
            logging.info( "releasing system access for " + group_name + " --> " + system_dir )
        else:
            logging.warning( "error in system access release for " + group_name + " --> " + system_dir )

        return result

class syslock:

    def __init__( self, pns_host, group_name, system_dir, cylc_mode ):
        self.pns_host = pns_host
        self.system_dir = system_dir
        self.group_name = group_name
        self.cylc_mode = cylc_mode

    def request_system_access( self, exclusive=True ):

        # Cylc system name is user-specific (i.e. different users can
        # register systems with the same name), but the cylc groupname
        # (USERNAME^SYSTEMNAME) is unique (because two users cannot have
        # the same username).        

        # System config files should specify whether or not a system is
        # 'exclusive' - i.e. is it possible to run multiple copies (with
        # different registered group names) of the entire system at
        # once? 
        
        server = connector( self.pns_host, 'cylc', 'lockserver' ).get() 

        (result, reason) = server.get_system_access( self.system_dir, self.group_name, self.cylc_mode, exclusive )
        if not result:
            print >> sys.stderr, 'ERROR, failed to get system access:'
            print >> sys.stderr, reason
            return False
       
        else:
           return True


    def release_system_access( self):
        server = connector( self.pns_host, 'cylc', 'lockserver' ).get() 
        result = server.release_system_access( self.system_dir, self.group_name )
        if not result:
            print >> sys.stderr, 'WARNING, failed to release system access: ', reason
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

    def __init__( self, task_id=None, group_name=None, pns_host=None ):
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

        if group_name:
            self.group_name = group_name
        else:
            if 'CYLC_SYSTEM_NAME' in os.environ.keys():
                self.group_name = os.environ['USER'] + '^' + os.environ[ 'CYLC_SYSTEM_NAME' ]
            elif self.mode == 'raw':
                pass
            else:
                # we always define the PNS Host explicitly, but could
                # default to localhost's fully qualified domain name
                # like this:   self.pns_host = socket.getfqdn()
                print >> sys.stderr, '$CYLC_SYSTEM_NAME not defined'
                sys.exit(1)

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
                print >> sys.stderr, '$CYLC_NS_GROUP not defined'
                sys.exit(1)

    def acquire( self ):
        server = connector( self.pns_host, 'cylc', 'lockserver' ).get() 
        if server.acquire( self.task_id, self.group_name ):
            print "Acquired task lock for", self.group_name + ':' + self.task_id
            return True
        else:
            print >> sys.stderr, "Refused task lock for", self.group_name + ':' + self.task_id
            if server.is_locked( self.task_id, self.group_name ):
                print >> sys.stderr, self.group_name + ':' + self.task_id, "is already locked!"
            return False

    def release( self ):
        server = connector( self.pns_host, 'cylc', 'lockserver' ).get()
        if server.is_locked( self.task_id, self.group_name ):
            if server.release( self.task_id, self.group_name ):
                print "Released task lock for", self.group_name + ':' + self.task_id
                return True
            else:
                print >> sys.stderr, "Failed to release task lock for", self.group_name + ':' + self.task_id
                return False
        else:
            print >> sys.stderr, "WARNING", self.group_name + ':' + self.task_id, "was not locked!"
            return True

class control:
    def __init__( self, pns_host=None ):
        self.server = connector( pns_host, 'cylc', 'lockserver' ).get() 

    def dump( self ):
        return self.server.dump()

    def clear( self ):
        self.server.clear()
