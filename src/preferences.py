#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|

import os, sys, pwd
import logging
from ConfigParser import SafeConfigParser

# system-wide cylc settings

class prefs(object):
    def __init__( self, user=None, silent=False ):

        self.silent = silent

        if not user:
            self.readonly = False
            home = os.environ['HOME']
        elif user == os.environ['USER']:
            self.readonly = False
            home = os.environ['HOME']
        else:
            # attempt to read another user's suite registration
            self.readonly = True
            home = pwd.getpwnam( user )[5]

        # file used to store user preferences
        self.rcfile = os.path.join( home, '.cylcrc' )
        # cylc user config directory
        self.config_dir = os.path.join( home, '.cylc' )

        self.config = {}
        self.configparser = SafeConfigParser()

        self.set_defaults()

        if os.path.exists( self.rcfile ):
            if not self.silent:
                print "Loading Cylc Preferences file: " + self.rcfile
            self.load()
        elif not self.readonly:
            if not self.silent:
                print "Creating new Cylc Preferences file: " + self.rcfile 
            self.write()

    def set_defaults( self ):

        self.config[ 'cylc' ] = {}
        self.config[ 'cylc' ][ 'state dump directory' ] = os.path.join( self.config_dir, 'state' )
        self.config[ 'cylc' ][ 'logging directory' ] = os.path.join( self.config_dir, 'logging' )
        self.config[ 'cylc' ][ 'logging level' ] = 'info'
        self.config[ 'cylc' ][ 'use lockserver' ] = 'True'
        self.config[ 'cylc' ][ 'use quick task elimination' ] = 'True'

        #self.config[ 'control' ] = {}

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

    def create_dirs( self ):
        if self.readonly:
            return

        # get a unique list of directories to create
        dirs = {}
        for dir in [ self.config_dir, 
                self.config['cylc']['logging directory'],
                self.config['cylc']['state dump directory'] ]:
            dirs[ dir ] = True

        for dir in dirs:
            if not os.path.exists( dir ):
                if not self.silent:
                    print "Creating directory: " + dir
                try:
                    os.makedirs( dir )
                except:
                    raise SystemExit( "ERROR: unable to create directory " + dir )
            else:
                if not self.silent:
                    print "directory exists: " + dir

    def write( self ):
        if self.readonly:
            return

        # write the file only if user has access to defined dirs
        self.create_dirs()

        for section in self.config:
            if not self.configparser.has_section( section ):
                self.configparser.add_section( section )
            for item in self.config[ section ]:
                self.configparser.set( section, item, self.config[ section][item] )

        if not self.silent:
            print "Writing Cylc Preferences file: " + self.rcfile
        # not compatible with python 2.4.3! 
        #with open( self.rcfile, 'w' ) as configfile:
        #    self.configparser.write( configfile )
        configfile = open( self.rcfile, 'w' )
        self.configparser.write( configfile )
        if not self.silent:
            print "Done"

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

    def get_suite_statedump_dir( self, suite_name, practice=False ):
        if practice:
            dir = os.path.join( self.config[ 'cylc' ][ 'state dump directory' ], suite_name, '-practice' )
        else:
            dir = os.path.join( self.config[ 'cylc' ][ 'state dump directory' ], suite_name )

        if not os.path.exists( dir ):
            if not self.silent:
                print "Creating directory", dir
            os.makedirs( dir )

        return dir

    def get_suite_logging_dir( self, suite_name, practice=False ):
        if practice:
            dir = os.path.join( self.config[ 'cylc' ][ 'logging directory' ], suite_name, '-practice' )
        else:
            dir = os.path.join( self.config[ 'cylc' ][ 'logging directory' ], suite_name )

        if not os.path.exists( dir ):
            if not self.silent:
                print "Creating directory", dir
            os.makedirs( dir )

        return dir

    def get_logging_level( self ):
        level = self.config[ 'cylc' ][ 'logging level' ]
        # default
        value = logging.INFO

        if level == 'debug':
            value = logging.DEBUG
        elif level == 'info':
            value = logging.INFO
        elif level == 'warning':
            value = logging.WARNING
        elif level == 'error':
            value = logging.ERROR
        elif level == 'critical':
            value = logging.CRITICAL

        return value
