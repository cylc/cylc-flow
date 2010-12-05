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

if sys.version_info >= (2,6):
    # Python 2.6+:
    # (because we need the dict_type argument)
    from ConfigParser import SafeConfigParser
elif sys.version_info >= (2,4):
    # Python 2.4+:
    from CylcSafeConfigParser import CylcSafeConfigParser
else:
    raise SystemExit( "suiterc.py is not compatible with Python < 2.4)" )

# Pre Python 2.7:
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
            self.rcfile = os.path.join( suite_dir, 'suite.rc' )
        else:
            self.rcfile = path

        cdefaults = OrderedDict()

        if sys.version_info >= (2,6):
            # Python 2.6+:
            self.config = SafeConfigParser( defaults=None, dict_type=OrderedDict )
        elif sys.version_info >= (2,4 ):
            # Python 2.4+:
            self.config = CylcSafeConfigParser()
        else:
            raise SystemExit( "Python 2.4+ required" )

        # prevent conversion of item names to lower case
        self.config.optionxform = str

        self.config.add_section( 'general' )
        self.config.set( 'general', 'title', 'REPLACE WITH SUITE TITLE STRING' )
        self.config.set( 'general', 'allow simultaneous instances', 'False' )
        self.config.set( 'general', 'maximum runahead (hours)', '24' )
        #self.config.set( 'general', 'restricted startup hours', 'True' )
        #self.config.set( 'general', 'logging level', 'info' )
        self.config.set( 'general', 'job log directory', '' )

        self.config.set( 'general', 'state dump rolling archive length', '10' )

        self.config.set( 'general', 'coldstart tasks', '' )
        self.config.set( 'general', 'tasks excluded at startup', '' )
        #Example: self.config.set( 'general', 'tasks excluded at startup', 'A,B,C,D' )
        self.config.set( 'general', 'tasks included at startup', '' )
        #Example: self.config.set( 'general', 'tasks included at startup', 'A,B,C,D' )
        self.config.set( 'general', 'tasks to dummy out', '' )
        #Example: self.config.set( 'general', 'tasks to dummy out', 'D,E,F' )

        self.config.add_section( 'task insertion groups' )
        #Example: self.config.set( 'task insertion groups', 'coldstart', 'A,B,C,D' )
        #Example: self.config.set( 'task insertion groups', 'foo', 'A,B,D,F' )

        self.config.add_section( 'job submission' )
        self.config.set( 'job submission', 'default', 'background' )
        #Example: self.config.set( 'job submission', 'at_now', 'A,B,C' )

        self.config.add_section( 'global environment' )
        #self.config.set( 'global environment','MY_EXAMPLE_TMP_DIR', '/tmp/$USER/$CYLC_SUITE_NAME' )

        self.config.add_section( 'dependency graph defaults' )
        self.config.set( 'dependency graph defaults','node attributes', 'style=filled, fillcolor=gray, color=invis' )
        self.config.set( 'dependency graph defaults','edge attributes', 'color=gray, style=bold' )
        self.config.set( 'dependency graph defaults','use node color for edges', 'True' )
        self.config.set( 'dependency graph defaults','task families in subgraphs', 'True' )

        self.config.add_section( 'dependency graph node attributes' )

        if os.path.exists( self.rcfile ):
            print "Loading Suite Config File: " + self.rcfile
            self.load()
        else:
            print "Writing new Suite Config File: " + self.rcfile 
            self.write()

        # we don't check for the existence of, or create, the job log
        # directory because there may be tasks that run under other
        # usernames or on other machines. So job all log directories
        # required by the suite (i.e. same dir relatively to $HOME for
        # all task owners on their respecitve task host machines) must
        # exist before the suite is started. 

    def load( self ):
        self.config.read( self.rcfile )

    def write( self ):
        # not compatible with python 2.4.3: 
        #with open( self.rcfile, 'w' ) as configfile:
        #    self.config.write( configfile )
        configfile = open( self.rcfile, 'w' )
        self.config.write( configfile )

    def get( self, section, item ):
        return self.config.get( section, item )

    def get_coldstart_tasks( self ):
        tlist = self.get( 'general', 'coldstart tasks' )
        return re.split( r', *| +', tlist )

    def get_global_environment( self ):
        return self.config.items( 'global environment' )

    def get_tasks_included( self ):
        tlist = self.get('general', 'tasks included at startup')
        tlist.rstrip()
        if tlist == '':
            return []
        else:
            return re.split( r', *| +', tlist )

    def get_tasks_excluded( self ):
        tlist = self.get('general', 'tasks excluded at startup')
        tlist.rstrip()
        if tlist == '':
            return []
        else:
            return re.split( r', *| +', tlist )

    def get_tasks_dummied_out( self ):
        tlist = self.get('general', 'tasks to dummy out')
        tlist.rstrip()
        if tlist == '':
            return []
        else:
            return re.split( r', *| +', tlist )

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
