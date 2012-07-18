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

import os, re
from optparse import OptionParser
from hostname import hostname

"""Common options for all cylc commands."""

class cop( OptionParser ):

    def __init__( self, usage, argdoc=[('REG', 'Suite name')], pyro=False ):

        # commands that interact with a running suite ("controlcom=True")
        # normally get remote access via Pyro RPC; but optionally
        # ("--use-ssh") you can use passwordless ssh to re-invoke the
        # command on the suite host, as for non-control commands.

        print argdoc

        usage += """

Arguments:"""
        args = ""
        self.n_compulsory_args = 0
        self.n_optional_args = 0
        self.unlimited_args = False
        for arg in argdoc:
            if arg[0].startswith('['):
                self.n_optional_args += 1
            else:
                self.n_compulsory_args += 1
            if arg[0].endswith('...]'):
                self.unlimited_args = True

            args += arg[0] + " "
            usage += "\n   " + arg[0] + "                  " + arg[1]

        usage = re.sub( 'ARGS', args, usage )
        
        OptionParser.__init__( self, usage )

        self.add_option( "-o", "--owner",
                help="User account name (defaults to $USER).",
                metavar="USER", default=os.environ["USER"],
                action="store", dest="owner" )

        self.add_option( "--host",
                help="Host name (defaults to localhost).",
                metavar="HOST", action="store", default=hostname,
                dest="host" )

        self.add_option( "-v", "--verbose",
                help="Verbose output mode (if applicable).",
                action="store_true", default=False, dest="verbose" )

        self.add_option( "--debug",
                help="Turn on exception tracebacks.",
                action="store_true", default=False, dest="debug" )

        self.add_option( "--db",
                help="Alternative suite database location.",
                metavar="FILE", action="store", default=None,
                dest="db" )

        if pyro:
            self.add_option( "--use-ssh",
                    help="Use ssh to re-invoke the command on the suite host.",
                    action="store_true", default=False, dest="use_ssh" )

            self.add_option( "-p", "--passphrase",
                    help="Suite passphrase file",
                    metavar="FILE", action="store", dest="pfile" )

            # This is only required for commands that prompt for
            # confirmation before interfering in a running suite,
            # but for simplicity we add it to all suite-connecting
            # commands (it has no affect for non-prompted ones).
            self.add_option( "-f", "--force",
                help="Do not ask for confirmation before acting (if applicable).",
                action="store_true", default=False, dest="force" )

    def parse_args( self ):
        (options, args) = OptionParser.parse_args( self )
        if len(args) < self.n_compulsory_args:
            self.error( "Wrong number of arguments (too few)" )
        elif not self.unlimited_args and \
                len(args) > self.n_compulsory_args + self.n_optional_args:
            self.error( "Wrong number of arguments (too many)" )
        return ( options, args )

