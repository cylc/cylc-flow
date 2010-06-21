#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver\@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|

import os, sys
from ConfigParser import SafeConfigParser

# system-wide cylc settings

class rc:

    def __init__( self, rcfile=os.path.join( os.environ['HOME'], '.cylcrc' ) ):

        self.rcfile = rcfile
        self.config = {}
        self.configparser = SafeConfigParser()

        config_dir = os.path.join( os.environ[ 'HOME' ], '.cylc' )

        self.config[ 'cylc' ] = {}
        self.config[ 'cylc' ][ 'config directory' ] = config_dir
        self.config[ 'cylc' ][ 'state dump directory' ] = os.path.join( config_dir, 'state-dumps' )
        self.config[ 'cylc' ][ 'logging directory' ] = os.path.join( config_dir, 'log-files' )

        self.config[ 'lockserver' ] = {}
        self.config[ 'lockserver' ][ 'log file' ] = os.path.join( config_dir, 'lockserver.log' )
        self.config[ 'lockserver' ][ 'pid file' ] = os.path.join( config_dir, 'lockserver.pid' )

        if os.path.exists( rcfile ):
            print "Loading Cylc RC File $HOME/.cylcrc"
            self.load()
        else:
            print "Creating default Cylc RC File $HOME/.cylcrc"
            self.write()

    def load( self ):
        self.configparser.read( self.rcfile )
        for section in self.configparser.sections():
            #print "Loading Section", section
            for (item, value) in self.configparser.items( section ):
                try:
                    self.config[section][ item ] = value
                except:
                    #print '  Using default ', item, self.config[section][ item ]
                    pass
                else:
                    #print '  Loaded item', item, value
                    pass

    def write( self ):
        for section in self.config:
            if not self.configparser.has_section( section ):
                self.configparser.add_section( section )
            for item in self.config[ section ]:
                self.configparser.set( section, item, self.config[ section][item] )

        with open( self.rcfile, 'wb' ) as configfile:
            self.configparser.write( configfile )


    def dump( self ):
        for section in self.config:
            print '[' + section + ']'
            for item in self.config[ section ]:
                print ' ', item, '=', self.config[section][item]


    def get( self, section, item ):
        try:
            return self.config[ section ][ item ]
        except:
            pass
