#!/usr/bin/env python

# Implement a "locking directory" mechanism to prevent THIS TASK (or
# rather the task that SOURCES this script) from running if another
# instance of it is running already (and has already acquired the lock).
# Locking must be done by the external task script, not by cylc, so that 
# the lock will be released by external tasks when they finish even if
# cylc has been shut down. 

# This version acquires a lock to prevent multiple copies of the task
# from running REGARDLESS of their registered cylc system names. 

# See also 'cylc-task-lock-sys' for a system-specific lock, for tasks that
# can tolerate parallel instances running under different cylc systems.

# $TASK_ID is in the cylc execution environment.

# Based on a bash script by Chris Edsall @ NIWA.
# - Uses directory creation as mkdir is an atomic operation.
# - Sourcing (dot-run) allows us to auto-release the lock on exit.

# ATTEMPT TO ACQUIRE YOUR LOCK AFTER SENDING THE CYLC START MESSAGE
# so that failure to lock will be reported to the cylc task logs, as
# well as to stdout, without causing cylc to complain that it has
# received a message from a task that has not started running yet. 
# Similarly, the lock release message is only echoed to stdout
# because it is necessarily emitted after the task finished message.
# (a cylc message after that time will cause cylc to complain that it
# has received a message from a task that has finished running). 

from task_message import message
import sys, os

class lock:
    def __init__( self, system_specific=False ):

        self.lockdir = os.environ['HOME'] + '/.cylc/locks'

        if 'CYLC_MODE' in os.environ:
            mode = os.environ[ 'CYLC_MODE' ] # 'scheduler' or 'run-task'
        else:
            mode = 'raw'

        if 'TASK_ID' in os.environ.keys():
            task_id = os.environ[ 'TASK_ID' ]
        elif mode == 'raw':
            task_id = 'TASK_ID'
        else:
            print >> sys.stderr, '$TASK_ID not defined'
            sys.exit(1)

        if system_specific:
            if 'CYLC_SYSTEM_NAME' in os.environ.keys():
                system_name = os.environ[ 'CYLC_SYSTEM_NAME' ]
            elif mode == 'raw':
                system_name = 'CYLC_SYSTEM_NAME'
            else:
                print >> sys.stderr, '$CYLC_SYSTEM_NAME not defined'
                sys.exit(1)

            self.tasklock = self.lockdir + '/' + system_name + '/' + task_id
        else:
            self.tasklock = self.lockdir + '/' + task_id

    def acquire( self ):
        # create top level lockdir if necessary
        if not os.path.exists( self.lockdir ):
            try:
                os.makedirs( self.lockdir )
            except Exception,x:
                print >> sys.stderr, "ERROR: failed to create main lock directory", self.lockdir
                print x
                sys.exit(1)

        # acquire the lock
        try:
            os.mkdir( self.tasklock )
        except:
            message( "failed to acquire lock " + self.tasklock ).send_failed()
            # The calling script should NOT release the lock!
            sys.exit(1)
        else:
           # got it
            message( "acquired task lock " + self.tasklock ).send()

    def release( self ):

        if os.path.exists( self.tasklock ) and os.path.isdir( self.tasklock ):
            try:
                os.rmdir( self.tasklock )
            except:
                message( "failed to release lock " + self.tasklock ).send_failed()
            else:
                message( "released task lock " + self.tasklock ).send()

        else:
            message( "task lock not found: " + self.tasklock, priority='WARNING' ).send()
