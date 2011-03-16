#!/usr/bin/env python

# messaging class to be used for task-to-cylc Pyro communication

# SEND MESSAGES TO A CYLC SCHEDULER VIA PYRO IF THIS SCRIPT WAS:
#  (a) called by a task that was invoked by a cylc scheduler
#  (b) invoked manually on the command line
# OTHERWISE DIVERT MESSAGES TO STDOUT, i.e. IF THIS SCRIPT WAS:
#  (a) called by a task that was invoked by 'cylc submit'
#  (b) called by a task that was run manually on the command line

import os, sys
import socket
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

        if 'TASK_ID' in os.environ.keys():
            self.task_id = os.environ[ 'TASK_ID' ]
        elif self.mode == 'raw':
            self.task_id = 'TASK_ID'
        else:
            print >> sys.stderr, '$TASK_ID not defined'
            sys.exit(1)

        if 'CYLC_SUITE' in os.environ.keys():
            self.suite = os.environ[ 'CYLC_SUITE' ]
        elif self.mode == 'raw':
            pass
        else:
            print >> sys.stderr, '$CYLC_SUITE not defined'
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
            # default to localhost's fully qualified domain name
            # like this:   self.host = socket.getfqdn()
            print >> sys.stderr, '$CYLC_SUITE_HOST not defined'
            sys.exit(1)

        if 'CYLC_SUITE_PORT' in os.environ.keys():
            self.port = os.environ[ 'CYLC_SUITE_PORT' ]
        elif self.mode == 'raw':
            pass
        else:
            print >> sys.stderr, '$CYLC_SUITE_PORT not defined'
            sys.exit(1)

    def get_proxy( self ):
        # this raises an exception on failure to connect:
        return cylc_pyro_client.client( self.suite, self.owner, self.host, self.port ).get_proxy( self.task_id )

    def print_msg_sp( self, msg ):
        now = datetime.datetime.now().strftime( "%Y/%m/%d %H:%M:%S" ) 
        prefix = 'cylc (' + self.mode + ' - ' + now + '): '
        if self.priority == 'NORMAL':
            print prefix + msg
        else:
            print >> sys.stderr, prefix + self.priority + ' ' + msg

    def print_msg( self ):
        if self.msg:
            now = datetime.datetime.now().strftime( "%Y/%m/%d %H:%M:%S" )
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

    def send_finished( self ):
        self.send_sp( self.task_id + ' finished' )

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



