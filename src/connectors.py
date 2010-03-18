#!/usr/bin/python

# import standard Python modules
import os, sys
import Pyro.core
from Pyro.errors import PyroError,NamingError,ProtocolError
from optparse import OptionParser
from time import sleep

class connect_to_control:

    def __init__( self, usage, no_prompt = False ):

        usage += """

If you are not the owner of the target system, the username must be
supplied so that the Pyro nameserver group name can be inferred.

arguments:
   SYSTEM               Registered name of the target system.""" 

        self.parser = OptionParser( usage )

        self.parser.add_option( "--user",
                help="Owner of the target system, defaults to $USER. "
                "Needed to infer the system's Pyro nameserver "
                "group name.",
                metavar="USERNAME", action="store", dest="username" )

        self.parser.add_option( "--pyro-ns",
                help="Pyro nameserver host, defaults to 'localhost'. Use "
                "if not auto-detected (which depends on network config).", 
                metavar="HOSTNAME", action="store", default="localhost",
                dest="pns_host" )

        if not no_prompt:
            self.parser.add_option( "-f", "--force",
                    help="Do not ask for confirmation before acting.",
                    action="store_true", default=False, dest="force" )

    def parse_args( self ):
        ( options, args ) = self.parser.parse_args()
        self.options = options
        self.args = args

        if len( self.args ) == 0:
            self.parser.error( "Please supply a target system name" )
        elif len( self.args ) > 1:
            self.parser.error( "Too many arguments" )

        self.system_name = self.args[0]

        if not self.options.pns_host:
            self.parser.error( "Required: Pyro nameserver hostname" )
        #else:
        #    self.pns_host = self.options.pns_host

        # Pyro nameserver groupname of the target system
        if self.options.username:
            username = self.options.username
        else:
            username = os.environ[ 'USER' ] 

        self.groupname = username + '_' + self.system_name

    def get_control( self ):

        # import cylc modules now, after parsing the command line, so so
        # we don't need access to a defined system just to print the
        # usage message.
        import pyrex

        # get systems currently registered in the Pyro nameserver
        ns_groups = pyrex.discover( self.options.pns_host )

        if ns_groups.registered( self.groupname ):
            #print "system: " + system_name
            pass
        else:
            print "WARNING: no " + self.groupname + " registered yet ..." 
            ns_groups.print_info()

            # print available systems and exit
            print
            self.parser.print_help()
            print
            ns_groups.print_info()
            print
            sys.exit(1)

        try:
            # connect to the remote switch object in cylc
            control = Pyro.core.getProxyForURI('PYRONAME://' + self.options.pns_host + '/' + self.groupname + '.' + 'remote' )
        except NamingError, x:
            print "\n\033[1;37;41m" + x + "\033[0m"
            raise SystemExit( "ERROR" )

        except Exception, x:
            #print x
            #raise SystemExit( "ERROR" )
            raise SystemExit( x )

        return control

    def prompt( self, reason ):

        msg =  reason + " '" + self.system_name + "'"

        if self.options.force:
            return True

        response = raw_input( msg + ': ARE YOU SURE (y/n)? ' )
        if response == 'y':
            return True
        else:
            return False


class connect_to_task:

    def __init__( self, name, ctime, pns_host, groupname ):
        self.host = pns_host
        self.group = groupname
        self.name = name
        self.ctime = ctime

    def get_task( self ):

        count = 0
        while True:
            count += 1
            try:
                uri =  'PYRONAME://' + self.host + '/' + self.group + '.' + self.name + '%' + self.ctime 
                task = Pyro.core.getProxyForURI( uri )
       
            except ProtocolError, x:
                # retry if temporary network problems prevented connection

                # TO DO: do we need to single out just the 'connection failed error?'

                # http://pyro.sourceforge.net/manual/10-errors.html
                # Exception: ProtocolError,
                #    Error string: connection failed
                #    Raised by: bindToURI method of PYROAdapter
                #    Description: Network problems caused the connection to fail.
                #                 Also the Pyro server may have crashed.
                #                 (presumably after connection established - hjo)

                print x
                print 'cylc message [' + str( count ) + ']: Network Problem, RETRYING in 5 seconds'
                sleep(5)

            except NamingError, x:
                # can't find nameserver, or no such object registered ...
                #print x
                #raise SystemExit( 'PYRO NAMESERVER ERROR' )
                raise SystemExit( x )

            except Exception, x:
                # all other exceptions
                #print x
                #raise SystemExit( 'ERROR' )
                raise SystemExit( x )

            else:
                # successful connection
                break

        return task
