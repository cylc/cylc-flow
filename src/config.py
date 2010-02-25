#!/usr/bin/python

import system_config
import logging
import sys
import os
import re

class config:

    def __init__( self ):
        self.configured = {}
        self.item_list = \
                [
                        'system_name',
                        'logging_dir',
                        'state_dump_dir',
                        'state_dump_file',
                        'task_list',
                        'task_groups',
                        'environment',
                        'max_runahead_hours',
                        'job_submit_method',
                        'job_submit_overrides',
                        'logging_level'
                 ]
        self.load_system_config()
        if not self.check():
            print "ABORTING due to undefined config items"
            sys.exit(1)


    def check( self ):
        items = self.configured.keys()
        ok = True
        for item in self.item_list:
            if item not in items:
                print 'ERROR: REQUIRED CONFIG ITEM UNDEFINED:', item
                ok = False
        return ok


    def load_system_config( self ):
        # set config items from those in the system_config module
        for key in system_config.config.keys():
            self.configured[ key ] = system_config.config[ key ]

        # set state_dump_file here; user set is unnecessary
        self.configured['state_dump_file'] = 'cylc-state'

        # create dict of job submit methods by task name
        self.configured['submit'] = {}
        for task in self.configured['task_list']:
            self.configured['submit'][ task ] = self.configured[ 'job_submit_method' ]
            for method in self.configured[ 'job_submit_overrides' ]:
                if task in self.configured[ 'job_submit_overrides' ][ method ]:
                    self.configured['submit'][ task ] = method

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

