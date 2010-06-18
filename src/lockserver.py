#!/usr/bin/env python

import Pyro.core
import os,sys
from connector import connector

class lockserver( Pyro.core.ObjBase ):

    def __init__( self ):
        Pyro.core.ObjBase.__init__(self)

        self.locked = {}      

        self.exclusive = {}       # exclusive[ system_dir ] = groupname
        self.allow_run_task = {}  # allow_run_task[ group_name ] = True/False

    def acquire( self, task_id, system_name ):
        if task_id not in self.locked:
            self.locked[ task_id ] = True
            return True
        else:
            return False

    def release( self, task_id, system_name ):
        if task_id in self.locked:
            del self.locked[ task_id ]
            return True
        else:
            return False

    #def print_locks( self ):
    #    for id in self.locked:
    #        print id

    def is_locked( self, task_id, system_name ):
        if task_id in self.locked:
            return True
        else:
            return False

    def get_system_access( self, system_dir, group_name, cylc_mode, exclusive, allow_run_task ):
        if system_dir not in self.exclusive:
            if cylc_mode != 'run-task':
                if exclusive:
                    self.exclusive[ system_dir ] = group_name
                self.allow_run_task[ group_name ] = allow_run_task
            return ( True, "granted" )

        else:
            # this system definition directory is already in use
            # so check whether or not we can allow access to it.
            if system_dir in self.exclusive:
                # is exclusive
                # who's using it?
                other_group = self.exclusive[ system_dir ]
                if self.allow_run_task[ other_group ] and cylc_mode == 'run-task':
                    return ( True, 'granted for run-task only' )
                else:
                    return ( False, 'denied, access is allowed for run-task only' )

            else:
                # not exclusive (multiple groups for same system dir )
                
                if group_name in self.allow_run_task:
                    # group already registered
                    if self.allow_run_task[ group_name ] and cylc_mode == 'run-task':
                        return ( True, 'granted, for run-task only' )
                    else:
                        return ( False, 'denied, access to ' + group_name + ' is allowed for run-task only' )

                else:
                    # group not registered yet
                    if cylc_mode != 'run-task':
                        if exclusive:
                            self.exclusive[ system_dir ] = group_name
                        self.allow_run_task[ group_name ] = allow_run_task
                    return ( True, "granted" )


    def release_system_access( self, system_dir, group_name ):
        result = True
        if system_dir in self.exclusive:
            del self.exclusive[ system_dir ]
        else:
            #print "WARNING: erroneous system release requested"
            result = False

        if group_name in self.allow_run_task:
            del self.allow_run_task[ group_name ]
        else:
            #print "WARNING: erroneous group release requested"
            result = False

        return result

class syslock:

    def __init__( self, pns_host, group_name, system_dir, cylc_mode ):
        self.pns_host = pns_host
        self.system_dir = system_dir
        self.group_name = group_name
        self.cylc_mode = cylc_mode

    def request_system_access( self, exclusive=True, allow_run_task=True ):

        # Cylc system name is user-specific (i.e. different users can
        # register systems with the same name), but the cylc groupname
        # (USERNAME^SYSTEMNAME) is unique (because two users cannot have
        # the same username).        

        # System config files should specify whether or not a system is
        # 'exclusive' - i.e. is it possible to run multiple copies (with
        # different registered group names) of the entire system at
        # once?  Then, on top of this, the user can choose whether or
        # not to allow use of run-task simultaneously with a given
        # running system.
 
        server = connector( self.pns_host, 'cylc', 'lockserver' ).get() 

        (result, reason) = server.get_system_access( self.system_dir, self.group_name, self.cylc_mode, exclusive, allow_run_task )
        if not result:
            print >> sys.stderr, "WARNING: system", self.group_name, "is locked (" + reason + ")"
            return False
       
        else:
           return True


    def release_system_access( self):

        server = connector( self.pns_host, 'cylc', 'lockserver' ).get() 
        result = server.release_system_access( self.system_dir, self.group_name )
        if not result:
            print >> sys.stderr, "WARNING: system", self.group_name, "release failed (" + reason + ")"
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

    def __init__( self ):
        if 'TASK_ID' in os.environ.keys():
            self.task_id = os.environ[ 'TASK_ID' ]
        elif self.mode == 'raw':
            self.task_id = 'TASK_ID'
        else:
            print >> sys.stderr, '$TASK_ID not defined'
            sys.exit(1)

        self.groupname = 'cylc'

        if 'CYLC_SYSTEM_NAME' in os.environ.keys():
            self.system_name = os.environ[ 'CYLC_SYSTEM_NAME' ]
        elif self.mode == 'raw':
            pass
        else:
            # we always define the PNS Host explicitly, but could
            # default to localhost's fully qualified domain name
            # like this:   self.pns_host = socket.getfqdn()
            print >> sys.stderr, '$CYLC_SYSTEM_NAME not defined'
            sys.exit(1)

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
        server = connector( self.pns_host, self.groupname, 'lockserver' ).get() 
        if server.is_locked( self.task_id, self.system_name ):
            print >> sys.stderr, "WARNING: task", self.task_id, "is locked!"
            return False
        if server.acquire( self.task_id, self.system_name ):
            print "Task lock acquired for", self.task_id
            return True
        else:
            print "Failed to acquire a task lock for", self.task_id
            return False

    def release( self ):
        server = connector( self.pns_host, self.groupname, 'lockserver' ).get()
        if server.is_locked( self.task_id, self.system_name ):
            if server.release( self.task_id, self.system_name ):
                print "Released task lock for", self.task_id
                return True
            else:
                print "WARNING failed to release task lock for", self.task_id
                return False
        else:
            print >> sys.stderr, "WARNING, task", self.task_id, "was not locked!"
            return True
