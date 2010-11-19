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
import os

from lockserver import lockserver

class task_lock:
    # NOTE: THE FOLLOWING COMMENT MAY NO LONGER APPLY NOW THAT
    # TASK-SPECIFIC LOGS ARE GONE?

    # ATTEMPT TO ACQUIRE YOUR LOCK AFTER SENDING THE CYLC START MESSAGE
    # so that failure to lock will be reported to the cylc task logs, as
    # well as to stdout, without causing cylc to complain that it has
    # received a message from a task that has not started running yet.
    # Similarly, the lock release message is only echoed to stdout
    # because it is necessarily emitted after the task finished message.
    # (a cylc message after that time will cause cylc to complain that
    # it has received a message from a task that has finished running). 

    def __init__( self, task_id=None, suite=None, host=None, owner=None, port=None ):

        self.use_lock_server = False
        if 'CYLC_USE_LOCKSERVER' in os.environ:
            if os.environ[ 'CYLC_USE_LOCKSERVER' ] == 'True':
                self.use_lock_server = True

        self.mode = 'raw'
        if 'CYLC_MODE' in os.environ:
            self.mode = os.environ[ 'CYLC_MODE' ]
            # 'scheduler' or 'submit'

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

        if port:
            self.port = port
        else:
            if 'CYLC_SUITE_PORT' in os.environ.keys():
                self.port = os.environ[ 'CYLC_SUITE_PORT' ]
            elif self.mode == 'raw':
                self.port = 'PORT'
            else:
                print >> sys.stderr, '$CYLC_SUITE_PORT not defined'
                sys.exit(1)

        if owner:
            self.owner = owner
        else:
            if 'CYLC_SUITE_OWNER' in os.environ.keys():
                self.owner = os.environ['CYLC_SUITE_OWNER']
            elif self.mode == 'raw':
                self.owner = os.environ['USER']
            else:
                print >> sys.stderr, '$CYLC_SUITE_OWNER not defined'
                sys.exit(1)

        if suite:
            self.suite_name = suite
        else:
            if 'CYLC_SUITE_NAME' in os.environ.keys():
                self.suite_name = os.environ[ 'CYLC_SUITE_NAME' ]
            elif self.mode == 'raw':
                pass
            else:
                print >> sys.stderr, '$CYLC_SUITE_NAME not defined'
                sys.exit(1)

        self.lockgroup = self.owner + '.' + self.suite_name

        if host:
            self.host = host
        else:
            if 'CYLC_SUITE_HOST' in os.environ.keys():
                self.host = os.environ[ 'CYLC_SUITE_HOST' ]
            elif self.mode == 'raw':
                pass
            else:
                # we always define the host explicitly, but could
                # default to localhost's fully qualified domain name
                # like this:   self.host = socket.getfqdn()
                print >> sys.stderr, '$CYLC_SUITE_HOST not defined'
                sys.exit(1)

    def acquire( self ):
        # print statements here will go to task stdout and stderr

        if not self.use_lock_server:
            print >> sys.stderr, "WARNING: you are not using the cylc lockserver." 
            return True
 
        server = lockserver( self.host ).get()
        if server.acquire( self.task_id, self.lockgroup ):
            print "Acquired task lock"
            return True
        else:
            print >> sys.stderr, "Failed to acquire task lock"
            if server.is_locked( self.task_id, self.lockgroup ):
                print >> sys.stderr, self.lockgroup + ':' + self.task_id, "is already locked!"
            return False

    def release( self ):
        if not self.use_lock_server:
            print >> sys.stderr, "WARNING: you are not using the cylc lockserver." 
            return True

        server = lockserver( self.host ).get()
        if server.is_locked( self.task_id, self.lockgroup ):
            if server.release( self.task_id, self.lockgroup ):
                print "Released task lock"
                return True
            else:
                print >> sys.stderr, "Failed to release task lock"
                return False
        else:
            print >> sys.stderr, "WARNING", self.lockgroup + ':' + self.task_id, "was not locked!"
            return True
