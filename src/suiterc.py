#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|

import os, sys, pwd, re
import logging
from ConfigParser import SafeConfigParser
from OrderedDict import OrderedDict

# suite-wide settings

#  rc = suiterc()
# TO RETRIEVE SINGLE ITEMS:
#  rc.get( section, item )
# SPECIAL FUNCTIONS TO RETRIEVE CERTAIN ITEMS:
#  rc.get_global_environment()
#  rc.get_task_insertion_groups()
#  rc.get_default_job_submission()
#  rc.get_nondefault_job_submission()

class suiterc:
    def __init__( self, path=None ):
        if not path:
            suite_dir = os.environ[ 'CYLC_SUITE_DIR' ]  
            self.rcfile = os.path.join( suite_dir, 'suite.config' )
        else:
            self.rcfile = path

        cdefaults = OrderedDict()

        self.config = SafeConfigParser( defaults=None, dict_type=OrderedDict )
        # prevent conversion of item names to lower case
        self.config.optionxform = str

        self.config.add_section( 'general' )
        self.config.set( 'general', 'title', 'REPLACE WITH SUITE TITLE STRING' )
        self.config.set( 'general', 'allow simultaneous instances', 'False' )
        #self.config.set( 'general', 'restricted startup hours', 'True' )
        #self.config.set( 'general', 'logging level', 'info' )

        self.config.add_section( 'task insertion groups' )
        #Example: self.config.set( 'task insertion groups', 'coldstart', 'A,B,C,D' )
        #Example: self.config.set( 'task insertion groups', 'foo', 'A,B,D,F' )

        self.config.add_section( 'job submission' )
        self.config.set( 'job submission', 'default', 'background' )
        #Example: self.config.set( 'job submission', 'at_now', 'A,B,C' )

        self.config.add_section( 'global environment' )
        self.config.set( 'global environment','MY_EXAMPLE_TMP_DIR', '/tmp/$USER/$CYLC_SUITE_NAME' )

        if os.path.exists( self.rcfile ):
            print "Loading Suite Config File: " + self.rcfile
            self.load()
        else:
            print "Writing new default Suite Config File: " + self.rcfile 
            self.write()

    def load( self ):
        self.config.read( self.rcfile )

    def write( self ):
        # not compatible with python 2.4.3: 
        #with open( self.rcfile, 'wb' ) as configfile:
        #    self.config.write( configfile )
        configfile = open( self.rcfile, 'wb' )
        self.config.write( configfile )

    def get( self, section, item ):
        return self.config.get( section, item )

    def get_global_environment( self ):
        return self.config.items( 'global environment' )

    def get_task_insertion_groups( self ):
        xgroups = {}
        for (name, val) in self.config.items('task insertion groups'):
            xgroups[ name ] = re.split( r', *| +', val )
        return xgroups

    def get_default_job_submission( self ):
        return self.config.get( 'job submission', 'default' )

    def get_nondefault_job_submission( self ):
        xgroups = {}
        for (name, val) in self.config.items('job submission'):
            if name == 'default':
                continue
            xgroups[ name ] = re.split( r', *| +', val )
        return xgroups

    def get_logging_level( self ):
        level = self.config[ 'general' ][ 'logging level' ]
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
