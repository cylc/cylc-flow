#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

import Pyro.core
import os,sys
import os

from lockserver import lockserver

class task_lock(object):
    # NOTE: THE FOLLOWING COMMENT MAY NO LONGER APPLY NOW THAT
    # TASK-SPECIFIC LOGS ARE GONE?

    # ATTEMPT TO ACQUIRE YOUR LOCK AFTER SENDING THE CYLC START MESSAGE
    # so that failure to lock will be reported to the cylc task logs, as
    # well as to stdout, without causing cylc to complain that it has
    # received a message from a task that has not started running yet.
    # Similarly, the lock release message is only echoed to stdout
    # because it is necessarily emitted after the task succeeded message.
    # (a cylc message after that time will cause cylc to complain that
    # it has received a message from a task that has succeeded). 

    def __init__( self, task_id=None, suite=None, owner=None, host=None, port=None ):
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
            if 'CYLC_TASK_ID' in os.environ.keys():
                self.task_id = os.environ[ 'CYLC_TASK_ID' ]
            elif self.mode == 'raw':
                self.task_id = 'CYLC_TASK_ID'
            else:
                print >> sys.stderr, '$CYLC_TASK_ID not defined'
                sys.exit(1)

        if suite:
            self.suite = suite
        else:
            if 'CYLC_SUITE_REG_NAME' in os.environ.keys():
                self.suite = os.environ[ 'CYLC_SUITE_REG_NAME' ]
            elif self.mode == 'raw':
                pass
            else:
                print >> sys.stderr, '$CYLC_SUITE_REG_NAME not defined'
                sys.exit(1)

        if owner:
            self.owner = owner
        else:
            if 'CYLC_SUITE_OWNER' in os.environ.keys():
                self.owner = os.environ[ 'CYLC_SUITE_OWNER' ]
            elif self.mode == 'raw':
                pass
            else:
                print >> sys.stderr, '$CYLC_SUITE_OWNER not defined'
                sys.exit(1)

        # IT IS CURRENTLY ASSUMED THAT LOCKSERVER AND SUITE HOST ARE THE SAME
        if host:
            self.host = host
        else:
            if 'CYLC_SUITE_HOST' in os.environ.keys():
                self.host = os.environ[ 'CYLC_SUITE_HOST' ]
            elif self.mode == 'raw':
                pass
            else:
                # we always define the host explicitly, but could
                # default to localhost's fully qualified domain name.
                print >> sys.stderr, '$CYLC_SUITE_HOST not defined'
                sys.exit(1)

        # port here is the lockserver port, not the suite port
        # (port = None forces scan).
        self.port = port
        if not self.port:
            if 'CYLC_LOCKSERVER_PORT' in os.environ.keys():
                self.port = os.environ[ 'CYLC_LOCKSERVER_PORT' ]

    def acquire( self ):
        # print statements here will go to task stdout and stderr

        if not self.use_lock_server:
            #print >> sys.stderr, "WARNING: you are not using the cylc lockserver." 
            return True
 
        # Owner required here because cylc suites can run tasks as other
        # users - but the lockserver is owned by the suite owner:
        server = lockserver( self.host, owner=self.owner, port=self.port ).get()
        if server.acquire( self.task_id, self.suite ):
            print "Acquired task lock"
            return True
        else:
            print >> sys.stderr, "Failed to acquire task lock"
            if server.is_locked( self.task_id, self.suite ):
                print >> sys.stderr, self.suite + ':' + self.task_id, "is already locked!"
            return False

    def release( self ):
        if not self.use_lock_server:
            #print >> sys.stderr, "WARNING: you are not using the cylc lockserver." 
            return True

        # Owner required here because cylc suites can run tasks as other
        # users - but the lockserver is owned by the suite owner:
        server = lockserver( self.host, owner=self.owner, port=self.port ).get()
        if server.is_locked( self.task_id, self.suite ):
            if server.release( self.task_id, self.suite ):
                print "Released task lock"
                return True
            else:
                print >> sys.stderr, "Failed to release task lock"
                return False
        else:
            print >> sys.stderr, "WARNING", self.suite + ':' + self.task_id, "was not locked!"
            return True
