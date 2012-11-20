#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
from owner import user

"""Common options for all cylc commands."""

class db_optparse( object ):
    def __init__( self, dbopt ):
        # input is DB option spec from the cylc command line
        self.owner = user
        self.location = None
        if dbopt:
            self.parse( dbopt )

    def parse( self, dbopt ):
        # determine DB location and owner
        if dbopt.startswith('u:'):
            self.owner = dbopt[2:]
            dbopt = os.path.join( '~' + self.owner, '.cylc', 'DB' )
        if dbopt.startswith( '~' ):
            dbopt = os.path.expanduser( dbopt )
        else: 
            dbopt = os.path.abspath( dbopt )
        self.location = dbopt

    def get_db_owner( self ):
        return self.owner

    def get_db_location( self ):
        return self.location

class cop( OptionParser ):

    def __init__( self, usage, argdoc=[('REG', 'Suite name')], pyro=False ):

        # commands that interact with a running suite ("controlcom=True")
        # normally get remote access via Pyro RPC; but optionally
        # ("--use-ssh") you can use passwordless ssh to re-invoke the
        # command on the suite host, as for non-control commands.

        usage += """

Arguments:"""
        args = ""
        self.n_compulsory_args = 0
        self.n_optional_args = 0
        self.unlimited_args = False
        self.pyro = pyro
        maxlen = 0
        for arg in argdoc:
            if len(arg[0]) > maxlen:
                maxlen = len(arg[0])
 
        for arg in argdoc:
            if arg[0].startswith('['):
                self.n_optional_args += 1
            else:
                self.n_compulsory_args += 1
            if arg[0].endswith('...]'):
                self.unlimited_args = True

            args += arg[0] + " "

            pad = ( maxlen - len(arg[0]) ) * ' ' + '               '
            usage += "\n   " + arg[0] + pad + arg[1]

        usage = re.sub( 'ARGS', args, usage )
        
        OptionParser.__init__( self, usage )

        self.add_option( "--owner",
                help="User account name (defaults to $USER).",
                metavar="USER", default=user,
                action="store", dest="owner" )

        self.add_option( "--host",
                help="Host name (defaults to localhost).",
                metavar="HOST", action="store", default=hostname,
                dest="host" )

        self.add_option( "-v", "--verbose",
                help="Verbose output mode.",
                action="store_true", default=False, dest="verbose" )

        self.add_option( "--debug",
                help="Turn on exception tracebacks.",
                action="store_true", default=False, dest="debug" )

        self.add_option( "--db",
                help="Suite database: 'u:USERNAME' for another user's "
                "default database, or PATH to an explicit location. "
                "Defaults to $HOME/.cylc/DB.",
                metavar="DB", action="store", default=None, dest="db" )

        self.add_option( "--invoked",
                help="Override cylc version compatibility checking.",
                action="store_true", default=False, dest="override" )

        if pyro:
            self.add_option( "--use-ssh",
                    help="Use ssh to re-invoke the command on the suite host.",
                    action="store_true", default=False, dest="use_ssh" )

            self.add_option( "--pyro-timeout", metavar='SEC',
                    help="Set a timeout value for Pyro network connections "
                    "to the running suite. The default is no timeout.",
                    action="store", default=None, dest="pyro_timeout" )

            self.add_option( "-p", "--passphrase",
                    help="Suite passphrase file (if not in a default location)",
                    metavar="FILE", action="store", dest="pfile" )

            self.add_option( "-f", "--force",
                help="Do not ask for confirmation before acting.",
                action="store_true", default=False, dest="force" )
        else:
            self.add_option( "-s", "--set", metavar="NAME=VALUE",
                help="Pass a template variable value to the suite definition. "
                "Can be used multiple times to set multiple variables. ",
                action="append", default=[], dest="templatevars" )

            self.add_option( "--set-file", metavar="FILE",
                help="Pass template variable values to the suite definition, "
                "from a file containing NAME=VALUE pairs (one per line).", 
                action="store", default=None, dest="templatevars_file" )

    def parse_args( self ):
        (options, args) = OptionParser.parse_args( self )

        if len(args) < self.n_compulsory_args:
            self.error( "Wrong number of arguments (too few)" )

        elif not self.unlimited_args and \
                len(args) > self.n_compulsory_args + self.n_optional_args:
            self.error( "Wrong number of arguments (too many)" )

        foo = db_optparse( options.db )
        options.db = foo.get_db_location()
        options.db_owner = foo.get_db_owner()

        if self.pyro:
            if options.pfile:
                options.pfile = os.path.abspath( options.pfile )

        return ( options, args )

