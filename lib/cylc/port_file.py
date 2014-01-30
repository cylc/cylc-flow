#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
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

import os, sys
from suite_host import is_remote_host
from owner import user, is_remote_user
from global_config import get_global_cfg
import flags

"""Processes connecting to a running suite must know which port the
suite server is listening on: at start-up cylc writes the port to
$HOME/.cylc/ports/SUITE.

Task messaging commands know the port number of the target suite from
the task execution environment supplied by the suite: $CYLC_SUITE_PORT,
so they do not need to read the port file (they do not use this class).

Other cylc commands: on the suite host read the port file; on remote
hosts use passwordless ssh to read the port file on the suite host. If
passwordless ssh to the suite host is not configured this will fail and
the user will have to give the port number on the command line."""

class PortFileError( Exception ):
    """
    Attributes:
        message - what the problem is.
    """
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)

class PortFileExistsError( PortFileError ):
    pass

class port_file( object ):
    def __init__(self, suite, port ):
        self.suite = suite

        # the ports directory is assumed to exist
        gcfg = get_global_cfg()
        pdir = gcfg.cfg['pyro']['ports directory']

        self.local_path = os.path.join( pdir, suite )

        try:
            self.port = str(int(port))
        except ValueError, x:
            print >> sys.stderr, x
            raise PortFileError( "ERROR, illegal port number: " + str(port) )

        self.write()

    def write( self ):
        if os.path.exists( self.local_path ):
            raise PortFileExistsError( "ERROR, port file exists: " + self.local_path )
        if flags.verbose:
            print "Writing port file:", self.local_path
        try:
            f = open( self.local_path, 'w' )
        except OSError,x:
            raise PortFileError( "ERROR, failed to open port file: " + self.port )
        f.write( self.port )
        f.close()

    def unlink( self ):
        if flags.verbose:
            print "Removing port file:", self.local_path
        try:
            os.unlink( self.local_path )
        except OSError,x:
            print >> sys.stderr, x
            raise PortFileError( "ERROR, cannot remove port file: " + self.local_path )

class port_retriever( object ):
    def __init__(self, suite, host, owner ):
        self.suite = suite
        self.host = host
        self.owner = owner
        self.locn = None

        gcfg = get_global_cfg()
        self.local_path = os.path.join( gcfg.cfg['pyro']['ports directory'], suite )

    def get_local( self ):
        self.locn = self.local_path
        if not os.path.exists( self.local_path ):
            raise PortFileError( "ERROR, port file not found: " + self.local_path )
        f = open( self.local_path, 'r' )
        str_port = f.readline().rstrip('\n')
        f.close()
        return str_port

    def get_remote( self ):
        import subprocess
        target = self.owner + '@' + self.host
        remote_path = self.local_path.replace( os.environ['HOME'], '$HOME' )
        self.locn = target + ':' + remote_path
        ssh = subprocess.Popen( ['ssh', '-oBatchMode=yes', target, 'cat', remote_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE )
        str_port = ssh.stdout.readline().rstrip('\n')
        err = ssh.stderr.readline()
        res = ssh.wait()
        if err:
            print >> sys.stderr, err.rstrip('\n')
        if res != 0:
            raise PortFileError( "ERROR, remote port file not found" )
        return str_port

    def get( self ):
        if flags.verbose:
            print "Retrieving suite port number..."

        if is_remote_host( self.host ) or is_remote_user( self.owner ):
            str_port = self.get_remote()
        else:
            str_port = self.get_local()

        try:
            # convert to integer
            port = int( str_port )
        except ValueError, x:
            # this also catches an empty port file (touch)
            print >> sys.stderr, x
            print >> sys.stderr, "ERROR: bad port file", self.locn
            raise PortFileError( "ERROR, illegal port file content: " + str_port )

        if flags.verbose:
            print '...', port

        return port

