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
from cylc.owner import user

from lockserver import lockserver

class task_lock(object):
    # TODO - (old!) this may not apply now that task-specific logs are gone:
    # ATTEMPT TO ACQUIRE YOUR LOCK AFTER SENDING THE CYLC START MESSAGE
    # so that failure to lock will be reported to the cylc task logs, as
    # well as to stdout, without causing cylc to complain that it has
    # received a message from a task that has not started running yet.
    # Similarly, the lock release message is only echoed to stdout
    # because it is necessarily emitted after the task succeeded message.
    # (a cylc message after that time will cause cylc to complain that
    # it has received a message from a task that has succeeded). 

    def __init__( self, task_id=None, suite=None, owner=user, host='localhost', port=None ):
        self.use_lock_server = False
        if 'CYLC_USE_LOCKSERVER' in os.environ:
            if os.environ[ 'CYLC_USE_LOCKSERVER' ] == 'True':
                self.use_lock_server = True
        if not self.use_lock_server:
            return

        # 'scheduler', 'submit', (or 'raw' if job script run manually)
        mode = os.environ.get( 'CYLC_MODE', 'raw' )

        # (lockserver and suite must be on the same host)
        # (port=None forces a port scan)
        for attr, key, default in (
                ('task_id', 'CYLC_TASK_ID',         task_id ),
                ('owner',   'CYLC_SUITE_OWNER',     owner   ),
                ('host',    'CYLC_SUITE_HOST',      host    ),
                ('port',    'CYLC_LOCKSERVER_PORT', port    )):
            val = os.environ.get( key, default )

            if mode is not 'raw' and key is not 'port':
                if not val:
                    sys.exit( 'ERROR: $' + key + ' not defined' )

            setattr(self, attr, val)

        # back compat for ssh messaging from task host with cylc <= 5.1.1:
        self.suite = os.environ.get('CYLC_SUITE_NAME')
        if not self.suite:
            self.suite = os.environ.get('CYLC_SUITE_REG_NAME')
            if self.suite:
                os.environ['CYLC_SUITE_NAME'] = self.suite

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

