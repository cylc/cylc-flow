#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2011 Hilary Oliver, NIWA
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

# messaging class to be used for task-to-cylc Pyro communication

# SEND MESSAGES TO A CYLC SCHEDULER VIA PYRO IF THIS SCRIPT WAS:
#  (a) called by a task that was invoked by a cylc scheduler
#  (b) invoked manually on the command line
# OTHERWISE DIVERT MESSAGES TO STDOUT, i.e. IF THIS SCRIPT WAS:
#  (a) called by a task that was invoked by 'cylc submit'
#  (b) called by a task that was run manually on the command line

import os, sys
import datetime
import cylc_pyro_client

class message(object):
    def __init__( self, msg=None, priority='NORMAL' ):

        self.msg = msg

        legal_priority = [ 'NORMAL', 'WARNING', 'CRITICAL' ]

        if priority in legal_priority:
            self.priority = priority
        else:
            print >> sys.stderr, 'illegal message priority', priority
            sys.exit(1)

        if 'CYLC_MODE' in os.environ:
            self.mode = os.environ[ 'CYLC_MODE' ] # 'scheduler' or 'submit'
        else:
            self.mode = 'raw'

        if 'CYLC_TASK_ID' in os.environ.keys():
            self.task_id = os.environ[ 'CYLC_TASK_ID' ]
        elif self.mode == 'raw':
            self.task_id = 'CYLC_TASK_ID'
        else:
            print >> sys.stderr, '$CYLC_TASK_ID not defined'
            sys.exit(1)

        if 'CYLC_SUITE_REG_NAME' in os.environ.keys():
            self.suite = os.environ[ 'CYLC_SUITE_REG_NAME' ]
        elif self.mode == 'raw':
            pass
        else:
            print >> sys.stderr, '$CYLC_SUITE_REG_NAME not defined'
            sys.exit(1)

        if 'CYLC_SUITE_OWNER' in os.environ.keys():
            self.owner = os.environ[ 'CYLC_SUITE_OWNER' ]
        elif self.mode == 'raw':
            pass
        else:
            print >> sys.stderr, '$CYLC_SUITE_OWNER not defined'
            sys.exit(1)

        if 'CYLC_SUITE_HOST' in os.environ.keys():
            self.host = os.environ[ 'CYLC_SUITE_HOST' ]
        elif self.mode == 'raw':
            pass
        else:
            # we always define the host explicitly, but could
            # default to localhost's fully qualified domain name.
            print >> sys.stderr, '$CYLC_SUITE_HOST not defined'
            sys.exit(1)

        if 'CYLC_SUITE_PORT' in os.environ.keys():
            self.port = os.environ[ 'CYLC_SUITE_PORT' ]
        elif self.mode == 'raw':
            pass
        else:
            print >> sys.stderr, '$CYLC_SUITE_PORT not defined'
            sys.exit(1)

        self.utc = False
        if 'CYLC_UTC' in os.environ.keys():
            if os.environ['CYLC_UTC'] == 'True':
                self.utc = True

    def now( self ):
        if self.utc:
            return datetime.datetime.utcnow()
        else:
            return datetime.datetime.now()

    def get_proxy( self ):
        # this raises an exception on failure to connect:
        return cylc_pyro_client.client( self.suite, self.owner, self.host, self.port ).get_proxy( self.task_id )

    def print_msg_sp( self, msg ):
        now = self.now().strftime( "%Y/%m/%d %H:%M:%S" ) 
        prefix = 'cylc (' + self.mode + ' - ' + now + '): '
        if self.priority == 'NORMAL':
            print prefix + msg
        else:
            print >> sys.stderr, prefix + self.priority + ' ' + msg

    def print_msg( self ):
        if self.msg:
            now = self.now().strftime( "%Y/%m/%d %H:%M:%S" )
            prefix = 'cylc (' + self.mode + ' - ' + now + '): '
            if self.priority == 'NORMAL':
                print prefix + self.msg
            else:
                print >> sys.stderr, prefix + self.priority + ' ' + self.msg

    def send_sp( self, msg ):
        self.print_msg_sp( msg )
        if self.mode == 'scheduler':
            self.get_proxy().incoming( self.priority, msg )

    def send( self ):
        if self.msg:
            self.print_msg()
            if self.mode == 'scheduler':
                self.get_proxy().incoming( self.priority, self.msg )

    def send_succeeded( self ):
        self.send_sp( self.task_id + ' succeeded' )

    def send_started( self ):
        self.send_sp( self.task_id + ' started' )

    def send_failed( self ):
        self.priority = 'CRITICAL'
        # send reason for failure
        self.send()
        # send failed
        self.send_sp( self.task_id + ' failed' )

    def shortcut_next_restart( self ):
        self.print_msg_sp( 'next restart file completed' )
        if self.mode == 'scheduler':
            self.get_proxy().set_next_restart_completed()

    def shortcut_all_restarts( self ):
        self.print_msg_sp( 'all restart files completed' )
        if self.mode == 'scheduler':
            self.get_proxy().set_all_restarts_completed()

    def shortcut_all_outputs( self ):
        self.print_msg_sp( 'all outputs completed' )
        if self.mode == 'scheduler':
            self.get_proxy().set_all_internal_outputs_completed()

