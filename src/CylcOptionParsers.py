#!/usr/bin/python

# Custom derived option parsers, with standard options, for cylc commands.

import os, sys
from optparse import OptionParser

class NoPromptOptionParser( OptionParser ):

    def __init__( self, usage ):

        usage += """

If you are not the owner of the target system, the username must be
supplied so that the Pyro nameserver group name can be inferred.

arguments:
   SYSTEM               Registered name of the target system.""" 

        OptionParser.__init__( self, usage )

        self.add_option( "--user",
                help="Owner of the target system, defaults to $USER. "
                "Needed to infer the system's Pyro nameserver "
                "group name.",
                metavar="USERNAME",
                default=os.environ["USER"],
                action="store", dest="username" )

        self.add_option( "--host",
                help="Pyro nameserver host, defaults to 'localhost'. Use "
                "if not auto-detected (which depends on network config).", 
                metavar="HOSTNAME", action="store", default="localhost",
                dest="pns_host" )

    def parse_args( self ):

        (options, args) = OptionParser.parse_args( self )

        if len( args ) == 0:
            self.error( "Please supply a target system name" )
        elif len( args ) > 1:
            self.error( "Too many arguments" )

        # system name
        self.system_name = args[0]

        # user name 
        self.username = options.username  # see default above!

        # nameserver host
        self.pns_host = options.pns_host   # see default above!

        return ( options, args )

    def get_system_name( self ):
        return self.system_name

    def get_pns_host( self ):
        return self.pns_host

    def get_groupname( self ):
        return self.username + '_' + self.system_name



class PromptOptionParser( NoPromptOptionParser ):

    def __init__( self, usage ):

        NoPromptOptionParse.__init__( self, usage )

        self.add_option( "-f", "--force",
                help="Do not ask for confirmation before acting.",
                action="store_true", default=False, dest="force" )

#    def parse_args( self ):
#        ( options, args ) = self.parse_args()
#        self.options = options
#        self.args = args
#
#        if len( self.args ) == 0:
#            self.parser.error( "Please supply a target system name" )
#        elif len( self.args ) > 1:
#            self.parser.error( "Too many arguments" )
#
#        self.system_name = self.args[0]
#
#        if not self.options.pns_host:
#            self.parser.error( "Required: Pyro nameserver hostname" )
#        #else:
#        #    self.pns_host = self.options.pns_host
#
#        # Pyro nameserver groupname of the target system
#        if self.options.username:
#            username = self.options.username
#        else:
##            username = os.environ[ 'USER' ] 
#
#        self.groupname = username + '_' + self.system_name


