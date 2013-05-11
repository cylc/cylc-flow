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

"""Task to cylc progress messaging."""

import os, sys
import socket
import subprocess
from datetime import datetime
from time import sleep
from remote import remrun
from cylc.passphrase import passphrase
from cylc.strftime import strftime
from cylc.global_config import gcfg
from cylc import cylc_mode

class message(object):
    def __init__( self, msg=None, priority='NORMAL', verbose=False ):

        self.msg = msg

        if priority in [ 'NORMAL', 'WARNING', 'CRITICAL' ]:
            self.priority = priority
        else:
            raise Exception( 'Illegal message priority ' + priority )

        # load the environment
        self.env_map = dict(os.environ)

        # set some instance variables 
        for attr, key, default in (
                ('task_id', 'CYLC_TASK_ID', '(CYLC_TASK_ID)'),
                ('owner', 'CYLC_SUITE_OWNER', None),
                ('host', 'CYLC_SUITE_HOST', '(CYLC_SUITE_HOST)'),
                ('port', 'CYLC_SUITE_PORT', '(CYLC_SUITE_PORT)')):
            value = self.env_map.get(key, default)
            setattr(self, attr, value)
        
        rd = self.env_map.get( 'CYLC_SUITE_RUN_DIR', '.' )
        self.env_file_path = os.path.join (rd, 'cylc-suite-env' )

        self.utc = self.env_map.get('CYLC_UTC') == 'True'

        # Record the time the messaging system was called and append it
        # to the message, in case the message is delayed in some way.
        if self.utc:
            self.true_event_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        else:
            self.true_event_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        self.verbose = verbose or self.env_map.get('CYLC_VERBOSE') == 'True'

        # 'scheduler' or 'submit', (or 'raw' if job script run manually)
        self.mode = self.env_map.get( 'CYLC_MODE', 'raw' )

        self.ssh_messaging = (
                self.env_map.get('CYLC_TASK_COMMUNICATION') == 'ssh' )
        self.polling = (
                self.env_map.get('CYLC_TASK_COMMUNICATION') == 'poll' )

        self.ssh_login_shell = (
                self.env_map.get('CYLC_TASK_SSH_LOGIN_SHELL') != 'False')

        g = gcfg.cfg['task messaging']
        self.retry_seconds = g['retry interval in seconds']
        self.max_tries = g['maximum number of tries']
        self.try_timeout = g['connection timeout in seconds']

    def load_suite_contact_file( self ):
        # override CYLC_SUITE variables using the contact environment file,
        # in case the suite was stopped and then restarted on another port:
        if os.access(self.env_file_path, os.F_OK | os.R_OK):
            for line in open(self.env_file_path):
                key, value = line.strip().split('=', 1)
                self.env_map[key] = value
        # set some instance variables 
        for attr, key, default in (
                ('task_id', 'CYLC_TASK_ID', '(CYLC_TASK_ID)'),
                ('owner', 'CYLC_SUITE_OWNER', None),
                ('host', 'CYLC_SUITE_HOST', '(CYLC_SUITE_HOST)'),
                ('port', 'CYLC_SUITE_PORT', '(CYLC_SUITE_PORT)')):
            value = self.env_map.get(key, default)
            setattr(self, attr, value)

        # back compat for ssh messaging from task host with cylc <= 5.1.1:
        self.suite = env_map.get('CYLC_SUITE_NAME')
        if not self.suite:
            self.suite = env_map.get('CYLC_SUITE_REG_NAME')
            if self.suite:
                os.environ['CYLC_SUITE_NAME'] = self.suite

        self.utc = self.env_map.get('CYLC_UTC') == 'True'

        self.ssh_messaging = (
                env_map.get('CYLC_TASK_SSH_MESSAGING') == 'True')

        self.ssh_login_shell = (
                env_map.get('CYLC_TASK_SSH_LOGIN_SHELL') != 'False')
            
    def now( self ):
        if self.utc:
            return datetime.utcnow()
        else:
            return datetime.now()

    def get_proxy( self ):
        # get passphrase here, not in __init__, because it is not needed
        # on remote task hosts if 'ssh messaging = True' (otherwise, if
        # it is needed, we will end up in this method). 

        suite = self.env_map.get( 'CYLC_SUITE_NAME', None )

        self.pphrase = passphrase( suite, self.owner, self.host,
                verbose=self.verbose ).get( None, None )

        import cylc_pyro_client
        return cylc_pyro_client.client( suite, self.pphrase,
                self.owner, self.host, self.try_timeout, self.port,
                self.verbose ).get_proxy( self.task_id )

    def print_msg( self, msg ):
        if self.utc:
            dt = datetime.utcnow()
        else:
            dt = datetime.now()
        now = strftime( dt, "%Y/%m/%d %H:%M:%S" )
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
            # nothing to send (TODO - not needed?)
            return

        # append event time to the message
        msg += ' at ' + self.true_event_time

        if self.mode != 'scheduler' or self.polling:
            # no suite to communicate with, just print to stdout.
            self.print_msg( msg )
            return

        if self.ssh_messaging:
            self.load_suite_contact_file()

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

            if self.ssh_login_shell:
                sys.argv.append('--login')
            else:
                sys.argv.append('--no-login')

            # Some variables from the task execution environment are
            # also required by the re-invoked remote command: Note that
            # $CYLC_TASK_SSH_MESSAGING is not passed through so the
            # re-invoked command on the remote side will not end up in
            # this code block.
            env = {}
            for var in ['CYLC_MODE', 'CYLC_TASK_ID', 'CYLC_VERBOSE', 
                    'CYLC_SUITE_DEF_PATH_ON_SUITE_HOST', 
                    'CYLC_SUITE_NAME', 'CYLC_SUITE_OWNER',
                    'CYLC_SUITE_HOST', 'CYLC_SUITE_PORT', 'CYLC_UTC',
                    'CYLC_USE_LOCKSERVER', 'CYLC_LOCKSERVER_PORT' ]:
                # (no exception handling here as these variables should
                # always be present in the task execution environment)
                env[var] = self.env_map.get( var, 'UNSET' )

            # The path to cylc/bin on the remote end may be required:
            path = [ os.path.join( self.env_map['CYLC_DIR_ON_SUITE_HOST'], 'bin' ) ]

            if remrun().execute( env=env, path=path ):
                # Return here if remote re-invocation occurred,
                # otherwise drop through to local Pyro messaging.
                # Note: do not sys.exit(0) here as the commands do, it
                # will cause messaging failures on the remote host. 
                return

        self.print_msg( msg )
        self.send_pyro( msg )


    def send_pyro( self, msg ):
        print "Sending message (connection timeout is", str(self.try_timeout) + ") ..."
        sent = False
        itry = 0
        while True:
            itry += 1
            print '  ', "Try", itry, "of", self.max_tries, "...",  
            try:
                # Get a proxy for the remote object and send the message.
                self.load_suite_contact_file() # might have change between tries
                self.get_proxy().incoming( self.priority, msg )
            except Exception, x:
                print "failed:", str(x)
                if itry == self.max_tries:
                    break
                print "   retry in", self.retry_seconds, "seconds ..."
                sleep( self.retry_seconds )
            else:
                print "succeeded"
                sent = True
                break
        if not sent:
            # issue a warning and let the task carry on
            print >> sys.stderr, 'WARNING: MESSAGE SEND FAILED'

    def send_started( self ):
        self.send( self.task_id + ' started' )
        self.task_lock()

    def send_succeeded( self ):
        self.task_lock( False )
        self.send( self.task_id + ' succeeded' )

    def send_failed( self ):
        self.priority = 'CRITICAL'
        if self.msg:
            # send reason for failure first so it does not contaminate
            # the special task failed message.
            self.send()
        self.task_lock( False )
        self.send( self.task_id + ' failed' )
 
    def task_lock( self, acquire=True ):
        # acquire or release a task lock if using the lockserver
        if cylc_mode.mode().is_raw() or self.ssh_messaging:
            return
        from cylc.locking.task_lock import task_lock
        try:
            if acquire:
                if not task_lock().acquire():
                    raise SystemExit( "Failed to acquire a task lock" )
            else:
                if not task_lock().release():
                    raise SystemExit( "Failed to release task lock" )
        except Exception, z:
            print >> sys.stderr, z
            if debug:
                raise
            raise SystemExit( "Failed to connect to the lockserver?" )

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

