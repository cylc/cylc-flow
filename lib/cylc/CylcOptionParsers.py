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

import os, re
from optparse import OptionParser
from suite_host import get_hostname
from owner import user
from cylc.command_prep import prep_file

"""Common options for all cylc commands."""

multitask_usage = """
For matching multiple tasks or families at once note that MATCH is 
interpreted as a full regular expression, not a simple shell glob."""

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

    def __init__( self, usage, argdoc=None, pyro=False, noforce=False,
            jset=False, multitask=False, prep=False, twosuites=False ):

        if argdoc == None:
            if not prep:
                argdoc = [('REG', 'Suite name')]
            else:
                argdoc = [('SUITE', 'Suite name or path')]

        # noforce=True is for commands that don't use interactive prompts at all

        usage += """

Arguments:"""
        args = ""
        self.n_compulsory_args = 0
        self.n_optional_args = 0
        self.unlimited_args = False
        self.pyro = pyro
        self.jset = jset

        self.multitask = multitask

        self.prep = prep
        self.suite_info = []
        self.twosuites = twosuites
 
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
                metavar="HOST", action="store", default=get_hostname(),
                dest="host" )

        self.add_option( "-v", "--verbose",
                help="Verbose output mode.",
                action="store_true", default=False, dest="verbose" )

        self.add_option( "--debug",
                help="Run suites in non-daemon mode, and show exception tracebacks.",
                action="store_true", default=False, dest="debug" )

        self.add_option( "--db",
                help="Suite database: 'u:USERNAME' for another user's "
                "default database, or PATH to an explicit location. "
                "Defaults to $HOME/.cylc/DB.",
                metavar="DB", action="store", default=None, dest="db" )

        if pyro:
            self.add_option( "--port",
                help="Suite port number on the suite host. NOTE: this is retrieved "
                "automatically if passwordless ssh is configured to the suite host.",
                metavar="INT", action="store", default=None, dest="port" )

            self.add_option( "--use-ssh",
                    help="Use ssh to re-invoke the command on the suite host.",
                    action="store_true", default=False, dest="use_ssh" )

            self.add_option( "--no-login",
                    help="Do not use a login shell to run remote ssh commands. "
                    "The default is to use a login shell.",
                    action="store_false", default=True, dest="ssh_login" )

            self.add_option( "--pyro-timeout", metavar='SEC',
                    help="Set a timeout for network connections "
                    "to the running suite. The default is no timeout. "
                    "For task messaging connections see "
                    "site/user config file documentation.",
                    action="store", default=None, dest="pyro_timeout" )

            if not noforce:
                self.add_option( "-f", "--force",
                        help="Do not ask for confirmation before acting. Note that "
                        "it is not necessary to use this option if interactive command "
                        "prompts have been disabled in the site/user config files.",
                        action="store_true", default=False, dest="force" )

        if self.jset:
            self.add_option( "-s", "--set", metavar="NAME=VALUE",
                    help="Set the value of a Jinja2 template variable in the suite "
                    "definition. This option can be used multiple times on the command "
                    "line.  WARNING: these settings do not persist across suite restarts; "
                    "they need to be set again on the \"cylc restart\" command line.",
                    action="append", default=[], dest="templatevars" )

            self.add_option( "--set-file", metavar="FILE",
                    help="Set the value of Jinja2 template variables in the suite "
                    "definition from a file containing NAME=VALUE pairs (one per line). "
                    "WARNING: these settings do not persist across suite restarts; "
                    "they need to be set again on the \"cylc restart\" command line.",
                    action="store", default=None, dest="templatevars_file" )

        if self.multitask:
            self.add_option( "-m", "--family", 
                    help="Match members of named families rather than tasks.",
                    action="store_true", default=False, dest="is_family" )

    def get_suite( self, index=0 ):
        return self.suite_info[index]

    def _getdef( self, arg, options ):
        suiterc = arg
        if os.path.isdir( suiterc ):
            # directory
            suite = suiterc
            suiterc = os.path.join( suiterc, 'suite.rc' )
        if os.path.isfile( suiterc ):
            # suite.rc file
            suite = os.path.basename( os.path.dirname( suiterc ))
            suiterc = os.path.abspath( suiterc)
            # TODO - return suite def include files to, as below
            watchers = [suiterc]
        else:
            # must be a registered suite name
            prepper = prep_file( arg, options )
            suite, suiterc = prepper.execute()
            # This lists top level suite def include files too:
            watchers = prepper.get_rcfiles()
        return suite, suiterc, watchers

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

        if self.jset:
            if options.templatevars_file:
                options.templatevars_file = os.path.abspath( os.path.expanduser( options.templatevars_file ))

        if self.prep:
            # allow file path or suite name 
            try:
                self.suite_info.append( self._getdef( args[0], options ))
                if self.twosuites:
                    self.suite_info.append( self._getdef( args[1], options ))
            except IndexError:
                if options.filename:
                    # Empty args list is OK if we supplied a filename
                    pass
                else:
                    # No filename, so we're expecting an argument
                    self.error( "Need either a filename or suite name(s)" )

        return ( options, args )

