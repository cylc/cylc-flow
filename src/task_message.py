#!/usr/bin/env python

# messaging class to be used for task-to-cylc Pyro communication

# SEND MESSAGES TO A CYLC SCHEDULER VIA PYRO IF THIS SCRIPT WAS:
#  (a) called by a task that was invoked by a cylc scheduler
#  (b) invoked manually on the command line
# OTHERWISE DIVERT MESSAGES TO STDOUT, i.e. IF THIS SCRIPT WAS:
#  (a) called by a task that was invoked by 'cylc run-task'
#  (b) called by a task that was run manually on the command line

import os, sys
import socket
from connector import connector

class message:
    def __init__( self, msg=None, priority='NORMAL' ):

        self.msg = msg

        legal_priority = [ 'NORMAL', 'WARNING', 'CRITICAL' ]

        if priority in legal_priority:
            self.priority = priority
        else:
            print >> sys.stderr, 'illegal message priority', priority
            sys.exit(1)

        self.username = os.environ[ 'USER' ] 

        if 'CYLC_MODE' in os.environ:
            self.mode = os.environ[ 'CYLC_MODE' ] # 'scheduler' or 'run-task'
        else:
            self.mode = 'raw'

        if 'TASK_ID' in os.environ.keys():
            self.task_id = os.environ[ 'TASK_ID' ]
        elif self.mode == 'raw':
            self.task_id = 'TASK_ID'
        else:
            print >> sys.stderr, '$TASK_ID not defined'
            sys.exit(1)

        if 'CYLC_NS_GROUP' in os.environ.keys():
            self.groupname = os.environ[ 'CYLC_NS_GROUP' ]
        elif self.mode == 'raw':
            pass
        else:
            print >> sys.stderr, '$CYLC_NS_GROUP not defined'
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

    def get_proxy( self ):
        try:
            proxy = connector( self.pns_host, self.groupname, self.task_id ).get()
        except:
            #print >> sys.stderr, "Failed to connect to " + self.task_id + \
            #" in " + self.groupname + " on " + self.pns_host
            raise
            sys.exit(1)
        else:
            return proxy

    def print_msg_sp( self, msg ):
        prefix = 'cylc (' + self.mode + '): '
        if self.priority == 'NORMAL':
            print prefix + msg
        else:
            print >> sys.stderr, prefix + self.priority + ' ' + msg

    def print_msg( self ):
        if self.msg:
            prefix = 'cylc (' + self.mode + '): '
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

    def send_completed( self ):
        self.send_sp( self.task_id + ' completed' )

    def send_finished( self ):
        self.send_completed()
        self.send_sp( self.task_id + ' finished' )

    def send_started( self ):
        self.send_sp( self.task_id + ' started' )

    def send_failed( self ):
        self.priority = 'CRITICAL'
        # send reason for failure
        self.send()
        # send completed
        self.send_completed()
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


# TO DO: REINSTATE THE DEAD LETTER BOX
#    # nameserver not found, or object not registered with it?
#    print "ERROR: failed to connect to " + task_id
#    print "Trying dead letter box"
#    try:
#        dead_box = Pyro.core.getProxyForURI('PYRONAME://' + groupname + '.' + 'dead_letter_box' )
#        dead_box.incoming( message )
#    except:
#        # nameserver not found, or object not registered with it?
#        print "ERROR: failed to connect to pyro nameserver"
#        sys.exit(1)
