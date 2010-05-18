#!/usr/bin/python

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

import os, sys
import socket
from optparse import OptionParser

#class NoPromptOptionParser( OptionParser ):
class NoPromptOptionParser_u( OptionParser ):

    def __init__( self, usage ):

        usage += """

If you are not the owner of the target system, the username must be
supplied so that the Pyro nameserver group name can be inferred.

Arguments:
   SYSTEM               Registered name of the target system.""" 

        OptionParser.__init__( self, usage )

        self.add_option( "-u", "--user",
                help="Owner of the target system, defaults to $USER. "
                "Needed to infer the Pyro nameserver group name.",
                metavar="USERNAME",
                default=os.environ["USER"],
                action="store", dest="username" )

        self.add_option( "--host",
                help="Pyro nameserver host, defaults to local hostname. Use "
                "if not auto-detected (which depends on network config).", 
                metavar="HOSTNAME", action="store", default=socket.getfqdn(),
                dest="pns_host" )

        self.add_option( "-p", "--practice",
                help="Target a system running in practice mode.", 
                action="store_true", default=False, dest="practice" )

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

        self.practice = options.practice  # practice mode or not

        return ( options, args )


    def get_system_name( self ):
        return self.system_name

    def get_pns_host( self ):
        return self.pns_host

    def get_groupname( self ):
        groupname = self.username + '^' + self.system_name
        if self.practice:
            groupname += '_practice'
        return groupname


class NoPromptOptionParser( OptionParser ):
    # same, but own username

    def __init__( self, usage ):

        usage += """

You must be the owner of the target system in order to use this command.

arguments:
   SYSTEM               Registered name of the target system.""" 

        OptionParser.__init__( self, usage )

        self.add_option( "--host",
                help="Pyro nameserver host, defaults to local hostname. Use "
                "if not auto-detected (which depends on network config).", 
                metavar="HOSTNAME", action="store", default=socket.getfqdn(),
                dest="pns_host" )

        self.add_option( "-p", "--practice",
                help="Target a system running in practice mode.", 
                action="store_true", default=False, dest="practice" )

        self.username = os.environ['USER']

    def parse_args( self ):

        (options, args) = OptionParser.parse_args( self )

        if len( args ) == 0:
            self.error( "Please supply a target system name" )
        elif len( args ) > 1:
            self.error( "Too many arguments" )

        # system name
        self.system_name = args[0]

        # nameserver host
        self.pns_host = options.pns_host   # see default above!

        self.practice = options.practice  # practice mode or not

        return ( options, args )


    def get_system_name( self ):
        return self.system_name

    def get_pns_host( self ):
        return self.pns_host

    def get_groupname( self ):
        groupname = self.username + '^' + self.system_name
        if self.practice:
            groupname += '_practice'
        return groupname



class PromptOptionParser( NoPromptOptionParser ):

    def __init__( self, usage ):

        NoPromptOptionParser.__init__( self, usage )

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
        msg =  reason + " '" + self.system_name + "'"

        if self.force:
            return True

        response = raw_input( msg + ': ARE YOU SURE (y/n)? ' )
        if response == 'y':
            return True
        else:
            return False
