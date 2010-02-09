#!/usr/bin/python

import user_config
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
                        'dummy_mode',
                        'use_qsub',
                        'job_queue',
                        'logging_level'
                 ]
        self.load_system_config()
        if not self.check():
            print "ERROR: there were undefined config items"
            sys.exit(1)


    def check( self ):
        items = self.configured.keys()
        ok = True
        for item in self.item_list:
            if item not in items:
                print 'UNDEFINED CONFIG ITEM:', item
                ok = False
        return ok



    def load_system_config( self ):
        # set config items from those in the system user_config module
        for key in user_config.config.keys():
            self.configured[ key ] = user_config.config[ key ]


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

