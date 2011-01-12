#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# Custom derived option parsers, with standard options, for cylc commands.

# TO DO: CLEAN UP OR REDESIGN THESE CLASSES.

import os
import socket
from optparse import OptionParser

#class NoPromptOptionParser( OptionParser ):
class NoPromptOptionParser_u( OptionParser ):

    def __init__( self, usage, extra_args=None ):

        usage += """

Arguments:
   SUITE                Registered name of the target suite.""" 

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
                metavar="HOST", action="store", default=socket.getfqdn(),
                dest="host" )

        self.add_option( "--port",
                help="Cylc suite port (default: scan cylc ports).",
                metavar="INT", action="store", default=None, dest="port" )

        self.add_option( "-p", "--practice",
                help="Target a suite running in practice mode.", 
                action="store_true", default=False, dest="practice" )

        self.add_option( "-f", "--force",
                help="(No effect; for consistency with interactive commands)",
                action="store_true", default=False, dest="force" )

        self.add_option( "--debug",
                help="Print full Python exception tracebacks",
                action="store_true", default=False, dest="debug" )
    
    def parse_args( self ):

        (options, args) = OptionParser.parse_args( self )

        if len( args ) == 0:
            self.error( "Please supply a target suite name" )
        elif len( args ) > self.n_args:
            self.error( "Too many arguments" )

        # suite name
        self.suite_name = args[0]

        # user name 
        self.owner = options.owner  # see default above!

        # cylc suite host
        self.host = options.host   # see default above!

        self.practice = options.practice  # practice mode or not

        return ( options, args )


    def get_suite_name( self ):
        return self.suite_name

    def get_host( self ):
        # TO DO: GET RID OF THIS METHOD
        return self.host

    def get_groupname( self ):
        # TO DO: USER PYREX MODULE HERE
        groupname = ':cylc.' + self.owner + '.' + self.suite_name
        if self.practice:
            groupname += '-practice'
        return groupname


class NoPromptOptionParser( OptionParser ):
    # same, but no owner

    def __init__( self, usage, extra_args=None ):

        usage += """

You must be the owner of the target suite in order to use this command.

arguments:
   SUITE                Registered name of the target suite.""" 

        self.n_args = 1  # suite name
        if extra_args:
            for arg in extra_args:
                usage += '\n   ' + arg
                self.n_args += 1


        OptionParser.__init__( self, usage )

        self.add_option( "--host",
                help="Cylc suite host (default: localhost).",
                metavar="HOSTNAME", action="store", default=socket.getfqdn(),
                dest="host" )

        self.add_option( "--port",
                help="Cylc suite port (default: scan cylc ports).",
                metavar="INT", action="store", default=None, dest="port" )

        self.add_option( "-p", "--practice",
                help="Target a suite running in practice mode.", 
                action="store_true", default=False, dest="practice" )

        self.add_option( "-f", "--force",
                help="(No effect; for consistency with interactive commands)",
                action="store_true", default=False, dest="force" )

        self.add_option( "--debug",
                help="Print full Python exception tracebacks",
                action="store_true", default=False, dest="debug" )

        self.owner = os.environ['USER']

    def parse_args( self ):

        (options, args) = OptionParser.parse_args( self )

        if len( args ) == 0:
            self.error( "Please supply a target suite name" )
        elif len( args ) > self.n_args:
            self.error( "Too many arguments" )

        # suite name
        self.suite_name = args[0]

        self.host = options.host   # see default above!

        self.practice = options.practice  # practice mode or not

        return ( options, args )


    def get_suite_name( self ):
        return self.suite_name

    def get_host( self ):
        return self.host

    def get_groupname( self ):
        # TO DO: USER PYREX MODULE HERE
        groupname = ':cylc.' + self.owner + '.' + self.suite_name
        if self.practice:
            groupname += '-practice'
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
