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

# Custom derived option parsers, with standard options, for cylc commands.

# TO DO: CLEAN UP OR REDESIGN THESE CLASSES.

import os
import re
from optparse import OptionParser
from hostname import hostname

#class NoPromptOptionParser( OptionParser ):
class NoPromptOptionParser_u( OptionParser ):

    def __init__( self, usage, extra_args=None ):

        usage += """

Arguments:
   SUITE                Target suite.""" 

        self.n_args = 1  # suite name
        if extra_args:
            for arg in extra_args:
                usage += '\n   ' + arg
                self.n_args += 1

        OptionParser.__init__( self, usage )

        self.add_option( "-o", "--owner",
                help="Owner of the target suite (defaults to $USER).",
                metavar="USER", default=os.environ["USER"],
                action="store", dest="owner" )

        self.add_option( "--host",
                help="Cylc suite host (defaults to local host).",
                metavar="HOST", action="store", default=hostname,
                dest="host" )

        #self.add_option( "--port",
        #        help="Cylc suite port (default: scan cylc ports).",
        #        metavar="INT", action="store", default=None, dest="port" )

        #DISABLED self.add_option( "-p", "--practice",
        #DISABLED         help="Target a suite running in practice mode.", 
        #DISABLED         action="store_true", default=False, dest="practice" )

        self.add_option( "-f", "--force",
                help="(No effect; for consistency with interactive commands)",
                action="store_true", default=False, dest="force" )

        self.add_option( "--debug",
                help="Turn on exception tracebacks.",
                action="store_true", default=False, dest="debug" )
    
    def parse_args( self ):
        (options, args) = OptionParser.parse_args( self )

        if len( args ) == 0:
            self.error( "Please supply a target suite name" )
        elif len( args ) > self.n_args:
            self.error( "Too many arguments" )

        self.suite_name = args[0]

        # user name 
        # self.owner = options.owner  # see default above!

        # cylc suite host
        # self.host = options.host   # see default above!

        #DISABLED self.practice = options.practice  # practice mode or not

        return ( options, args )

    def get_suite_name( self ):
       return self.suite_name

    def get_groupname( self ):
        # TO DO: USER PYREX MODULE HERE
        groupname = ':cylc.' + self.owner + '.' + self.suite_name
        #DISABLED if self.practice:
        #DISABLED     groupname += '-practice'
        return groupname


class NoPromptOptionParser( OptionParser ):
    # same, but no owner

    def __init__( self, usage, extra_args=None ):

        usage += """

You must be the owner of the target suite to use this command.

Arguments:
   SUITE                Target suite.""" 

        self.n_args = 1  # suite name
        if extra_args:
            for arg in extra_args:
                usage += '\n   ' + arg
                self.n_args += 1

        OptionParser.__init__( self, usage )

        #self.add_option( "--host",
        #        help="Cylc suite host (default: localhost).",
        #        metavar="HOSTNAME", action="store", default=hostname,
        #        dest="host" )

        #self.add_option( "--port",
        #        help="Cylc suite port (default: scan cylc ports).",
        #        metavar="INT", action="store", default=None, dest="port" )

        #DISABLED self.add_option( "-p", "--practice",
        #DISABLED         help="Target a suite running in practice mode.", 
        #DISABLED         action="store_true", default=False, dest="practice" )

        self.add_option( "-f", "--force",
                help="(No effect; for consistency with interactive commands)",
                action="store_true", default=False, dest="force" )

        self.add_option( "--debug",
                help="Turn on exception tracebacks.",
                action="store_true", default=False, dest="debug" )

        self.owner = os.environ['USER']

    def parse_args( self ):

        (options, args) = OptionParser.parse_args( self )

        if len( args ) == 0:
            self.error( "Please supply a target suite name" )
        elif len( args ) > self.n_args:
            self.error( "Too many arguments" )

        self.suite_name = args[0]
        #self.host = options.host   # see default above!
        #DISABLED self.practice = options.practice  # practice mode or not

        return ( options, args )

    def get_suite_name( self ):
        return self.suite_name

    def get_groupname( self ):
        # TO DO: USER PYREX MODULE HERE
        groupname = ':cylc.' + self.owner + '.' + self.suite_name
        #DISABLED if self.practice:
        #DISABLED     groupname += '-practice'
        return groupname


class PromptOptionParser( NoPromptOptionParser ):

    def __init__( self, usage, extra_args=None ):

        NoPromptOptionParser.__init__( self, usage, extra_args )

        self.remove_option( "-f" )
        self.add_option( "-f", "--force",
                help="Do not ask for confirmation before acting.",
                action="store_true", default=False, dest="force" )

    def parse_args( self ):

        (options, args) = NoPromptOptionParser.parse_args( self )

        if options.force:
            self.force = True
        else:
            self.force = False

        return (options, args)

    def prompt( self, reason ):
        msg =  reason + " '" + self.suite_name + "'"

        if self.force:
            return True

        response = raw_input( msg + ': ARE YOU SURE (y/n)? ' )
        if response == 'y':
            return True
        else:
            return False
