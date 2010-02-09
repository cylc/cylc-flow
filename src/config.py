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

        # LOGGING DIRECTORY (default: in cwd)
        self.configured['logging_dir'] = 'CYLC-LOGS'
        # STATE DUMP FILE (default: in cwd)
        self.configured['state_dump_dir'] = 'CYLC-STATE'
        self.configured['state_dump_file'] = 'state'

        # LIST OF TASK NAMES
        self.configured['task_list'] = []
        # TASK GROUPS
        self.configured['task_groups'] = {}

        # ENVIRONMENT VARIABLES TO SET
        self.configured['environment'] = {}

        # MAXIMUM TIME ANY TASK IS ALLOWED TO GET AHEAD OF THE SLOWEST
        self.configured['max_runahead_hours'] = 24

        # DUMMY MODE
        self.configured['dummy_mode'] = False

        # JOB LAUNCH METHOD (qsub or direct in background)
        # default to qsub in real mode
        self.configured['use_qsub'] = True
        self.configured['job_queue'] = 'default'

        # LOG VERBOSITY
        self.configured['logging_level'] = logging.INFO
        #self.configured['logging_level'] = logging.DEBUG


    def load( self, dump = False ):
        self.user_override()
        self.check()
        if dump:
            self.dump()
        #else:
        #    print
        #    print "SYSTEM: " + self.configured['system_name']



    def user_override( self ):
        # override config items with those in the user_config module
        for key in user_config.config.keys():
            self.configured[ key ] = user_config.config[ key ]


    def check( self ):

        die = False

        # check compulsory items have been defined in user_config.py
        compulsory = [ 'system_name' ]
        for item in compulsory:
            if self.configured[ item ] == None:
                print "ERROR: you must define " + item + " in user_config.py"
                die = True

        if len( self.configured[ 'task_list' ] ) == 0:
            print "ERROR: empty task list for system " + self.configured['system_name']
            die = True

        if die:
            print "ABORTING due to aforementioned errors"
            sys.exit(1)


    def get( self, key ):
        return self.configured[ key ]

    def put( self, key, value ):
        self.configured[ key ] = value

    def set( self, key, value ):
        self.configured[ key ] = value


    def dump( self ):
            
        print
        print "SYSTEM NAME.............", 
        print self.configured['system_name']

        print "MAX RUNAHEAD ...........",
        print self.configured['max_runahead_hours'], "hours"

        print "TASK EXECUTION..........",
        if self.configured['use_qsub']:
            print "qsub, queue = " + self.configured['job_queue']
        else:
            print "direct, in background"

        print 'LOGGING DIRECTORY.......',
        print self.configured['logging_dir']

        print 'STATE DUMP DIRECTORY....',
        print self.configured['state_dump_dir']

        print 'CONFIGURED TASK LIST....',
        #print '- ' + self.configured['task_list'][0]
        #for task in self.configured['task_list'][1:]:
        #    print '                         - ' + task
        for task in self.configured['task_list']:
            print '                         - ' + task

