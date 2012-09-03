#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
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

"""Task to cylc progress messaging."""

import os, sys
import socket
import subprocess
import datetime
from remote import remrun
from cylc.passphrase import passphrase

class message(object):
    def __init__( self, msg=None, priority='NORMAL', verbose=False ):

        self.msg = msg
        self.verbose = verbose
        if not verbose:
            try:
                if os.environ['CYLC_VERBOSE'] == 'True':
                    self.verbose = True
            except:
                pass

        legal_priority = [ 'NORMAL', 'WARNING', 'CRITICAL' ]

        if priority in legal_priority:
            self.priority = priority
        else:
            raise Exception( 'Illegal message priority ' + priority )

        try:
            self.mode = os.environ[ 'CYLC_MODE' ] # 'scheduler' or 'submit'
        except:
            self.mode = 'raw' # direct manual execution

        try:
            self.task_id = os.environ[ 'CYLC_TASK_ID' ]
        except:
            if self.mode == 'raw':
                self.task_id = '(CYLC_TASK_ID)'
            else:
                raise

        try:
            self.suite = os.environ[ 'CYLC_SUITE_REG_NAME' ]
        except:
            if self.mode == 'raw':
                pass
            else:
                raise

        try:
            self.owner = os.environ[ 'CYLC_SUITE_OWNER' ]
        except:
            if self.mode == 'raw':
                pass
            else:
                raise

        try:
            self.host = os.environ[ 'CYLC_SUITE_HOST' ]
        except:
            if self.mode == 'raw':
                self.host = '(CYLC_SUITE_HOST)'
            else:
                raise

        try:
            self.port = os.environ[ 'CYLC_SUITE_PORT' ]
        except:
            if self.mode == 'raw':
                self.port = '(CYLC_SUITE_PORT)'
            else:
                raise

        self.utc = False
        try:
            if os.environ['CYLC_UTC'] == 'True':
                self.utc = True
        except:
            pass
    
        self.ssh_messaging = False
        try:
            if os.environ['CYLC_TASK_SSH_MESSAGING'] == 'True':
                self.ssh_messaging = True
        except:
            pass
            
        try:
            # value may be string 'None'
            self.pyro_timeout = float(os.environ['CYLC_SUITE_PYRO_TIMEOUT'])
        except:
            self.pyro_timeout = None

    def now( self ):
        if self.utc:
            return datetime.datetime.utcnow()
        else:
            return datetime.datetime.now()

    def get_proxy( self ):
        # get passphrase here, not in __init__, because it is not needed
        # on remote task hosts if 'ssh messaging = True' (otherwise, if
        # it is needed, we will end up in this method). 
        self.pphrase = passphrase( self.suite, self.owner, self.host,
                verbose=self.verbose ).get( None, None )
        # this raises an exception on failure to connect:
        import cylc_pyro_client
        return cylc_pyro_client.client( self.suite, self.pphrase,
                self.owner, self.host, self.pyro_timeout, self.port,
                self.verbose ).get_proxy( self.task_id )

    def print_msg( self, msg ):
        now = self.now().strftime( "%Y/%m/%d %H:%M:%S" )
        prefix = 'cylc (' + self.mode + ' - ' + now + '): '
        if self.priority == 'NORMAL':
            print prefix + msg
        else:
            print >> sys.stderr, prefix + self.priority + ' ' + msg

    def send( self, msgin=None ):
        msg = None
        if msgin:
            msg = msgin
        elif self.msg:
            msg = self.msg
        if not msg:
            # nothing to send (To Do: this is not needed?)
            return
        if self.mode != 'scheduler':
            # no suite to communicate with, just print to stdout.
            self.print_msg( msg )
            return
        if self.ssh_messaging:
            # The suite definition specified that this task should
            # communicate back to the suite by means of using
            # passwordless ssh to re-invoke the messaging command on the
            # suite host. 

            # The remote_run() function expects command line options
            # to identify the target user and host names:
            sys.argv.append( '--owner=' + self.owner )
            sys.argv.append( '--host=' + self.host )
            if self.verbose:
                sys.argv.append( '-v' )
            # Some variables from the task execution environment are
            # also required by the re-invoked remote command: Note that
            # $CYLC_TASK_SSH_MESSAGING is not passed through so the
            # re-invoked command on the remote side will not end up in
            # this code block.
            env = {}
            for var in ['CYLC_MODE', 'CYLC_TASK_ID', 'CYLC_VERBOSE', 
                    'CYLC_SUITE_DEF_PATH_ON_SUITE_HOST', 'CYLC_SUITE_PYRO_TIMEOUT', 
                    'CYLC_SUITE_REG_NAME', 'CYLC_SUITE_OWNER',
                    'CYLC_SUITE_HOST', 'CYLC_SUITE_PORT', 'CYLC_UTC',
                    'CYLC_USE_LOCKSERVER', 'CYLC_LOCKSERVER_PORT' ]:
                # (no exception handling here as these variables should
                # always be present in the task execution environment)
                env[var] = os.environ[var]

            # The path to cylc/bin on the remote end may be required:
            path = [ os.path.join( os.environ['CYLC_DIR_ON_SUITE_HOST'], 'bin' ) ]

            if remrun().execute( env=env, path=path ):
                # Return here if remote re-invocation occurred,
                # otherwise drop through to local Pyro messaging.
                # Note: do not sys.exit(0) here as the commands do, it
                # will cause messaging failures on the remote host. 
                return

        self.print_msg( msg )
        self.send_pyro( msg )

    def send_pyro( self, msg ):
        # exceptions are handled by the messaging commands now
        self.get_proxy().incoming( self.priority, msg )

    def send_succeeded( self ):
        self.send( self.task_id + ' succeeded' )

    def send_started( self ):
        self.send( self.task_id + ' started' )

    def send_failed( self ):
        self.priority = 'CRITICAL'
        if self.msg:
            # send reason for failure first so it does not contaminate
            # the special task failed message.
            self.send()
        self.send( self.task_id + ' failed' )

    def shortcut_next_restart( self ):
        self.print_msg( 'next restart file completed' )
        if self.mode == 'scheduler':
            self.get_proxy().set_next_restart_completed()

    def shortcut_all_restarts( self ):
        self.print_msg( 'all restart files completed' )
        if self.mode == 'scheduler':
            self.get_proxy().set_all_restarts_completed()

    def shortcut_all_outputs( self ):
        self.print_msg( 'all outputs completed' )
        if self.mode == 'scheduler':
            self.get_proxy().set_all_internal_outputs_completed()

