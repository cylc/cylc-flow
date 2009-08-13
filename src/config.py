#!/usr/bin/python

import user_config
import logging
import sys
import os
import re

class config:

    def __init__( self ):

        self.configured = {}
        self.set_defaults()


    def set_defaults( self ):
        # SET DEFAULT CONFIG VALUES

        # SYSTEM NAME (also used as Pyro nameserver group)
        self.configured['system_name'] = None
        # LOGGING DIRECTORY
        self.configured['logging_dir'] = None
        # STATE DUMP FILE
        self.configured['state_dump_file'] = None
        # LIST OF TASK NAMES
        self.configured['task_list'] = []
        # START REFERENCE TIME
        self.configured['start_time'] = None
        # STOP REFERENCE TIME
        self.configured['stop_time'] = None   

        # MAXIMUM TIME ANY TASK IS ALLOWED TO GET AHEAD OF THE SLOWEST
        self.configured['max_runahead_hours'] = 24

        # DUMMY MODE
        self.configured['dummy_mode'] = False
        self.configured['dummy_clock_rate'] = 10      
        self.configured['dummy_clock_offset'] = 10 

        # JOB LAUNCH METHOD (qsub or direct in background)
        # default to qsub in real mode
        self.configured['use_qsub'] = True
        self.configured['job_queue'] = 'default'

        # LOG VERBOSITY
        self.configured['logging_level'] = logging.INFO
        #self.configured['logging_level'] = logging.DEBUG


    def load( self ):
        self.user_override()
        self.check()
        self.dump()
       

    def user_override( self ):
        # override config items with those in the user_config module
        for key in user_config.config.keys():
            self.configured[ key ] = user_config.config[ key ]


    def check( self ):

        die = False

        # check compulsory items have been defined in user_config.py
        env = os.environ[ 'CYCON_ENV' ]
        user_config_file = re.sub( 'environment.sh', 'user_config.py', env )
        compulsory = [ 'system_name', 'logging_dir', 'state_dump_file' ]
        for item in compulsory:
            if self.configured[ item ] == None:
                print "ERROR: you must define " + item + " in " + user_config_file
                die = True

        if self.configured['start_time'] == None:
            print "WARNING: no start time defined for " + self.configured['system_name']
            print "This will fail if you are not restarting from a state dump file" 

        if len( self.configured[ 'task_list' ] ) == 0:
            print "ERROR: empty task list for system " + self.configured['system_name']
            die = True

        if die:
            print "ABORTING due to aforementioned errors"
            sys.exit(1)


    def get( self, key ):
        return self.configured[ key ]


    def set( self, key, value ):
        self.configured[ key ] = value


    def dump( self ):
            
        print
        print "SYSTEM NAME.............", 
        print self.configured['system_name']

        print "MODE....................",
        if self.configured['dummy_mode']:
            print "DUMMY MODE"
        else:
            print "real mode"
 
        print "START TIME..............",
        print self.configured['start_time']

        print "STOP TIME...............",
        if self.configured['stop_time']:
            print self.configured['stop_time']
        else:
            print "(none)"

        print "MAX RUNAHEAD ...........",
        print self.configured['max_runahead_hours'], "hours"

        print "TASK EXECUTION..........",
        if self.configured['use_qsub']:
            print "qsub, queue = " + self.configured['job_queue']
        else:
            print "direct, in background"

        print 'LOGGING DIRECTORY.......',
        print self.configured['logging_dir']

        print "STATE DUMP FILE.........",
        print self.configured['state_dump_file']

        print 'CONFIGURED TASK LIST....',
        print '- ' + self.configured['task_list'][0]
        for task in self.configured['task_list'][1:]:
            print '                         - ' + task
