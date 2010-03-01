#!/usr/bin/python

import system_config
import logging
import sys
import os
import re

class config:

    def __init__( self, system_name ):

        self.configured = {}

        self.system_item_list = \
                [
                        'logging_dir',
                        'state_dump_dir',
                        'task_list',
                        'task_groups',
                        'environment',
                        'max_runahead_hours',
                        'job_submit_method',
                        'job_submit_overrides',
                        'logging_level'
                 ]


        # load items in system_item_list from system config module
        self.load_system_config()

        # check all were defined
        items = self.configured.keys()
        ok = True
        for item in self.system_item_list:
            if item not in items:
                print 'ERROR: REQUIRED CONFIG ITEM UNDEFINED:', item
                ok = False

        if not ok:
            raise SystemExit( "Required config items missing" )

        # create dict of job submit methods by task name
        self.configured['submit'] = {}
        for task in self.configured['task_list']:
            self.configured['submit'][ task ] = self.configured[ 'job_submit_method' ]
            for method in self.configured[ 'job_submit_overrides' ]:
                if task in self.configured[ 'job_submit_overrides' ][ method ]:
                    self.configured['submit'][ task ] = method

        # DYNAMIC CONFIG
        # add registered system name to the logging and state dump dirs
        # to allow multiple instances of the same system (with different
        # names) to coexist
        statedir = self.configured['state_dump_dir'] + '/' + system_name

        self.configured['state_dump_dir'] = statedir
        self.configured['state_dump_file'] = statedir + '/state'

        logdir = self.configured[ 'logging_dir' ] + '/' + system_name 
        self.configured['logging_dir'] = logdir 

        if not os.path.exists( statedir ):
            os.makedirs(  statedir )

        if not os.path.exists( logdir ):
            os.makedirs(  logdir )

    def load_system_config( self ):
        # set config items from those in the system_config module
        for key in system_config.config.keys():
            self.configured[ key ] = system_config.config[ key ]


    def get( self, key ):
        return self.configured[ key ]

    def put( self, key, value ):
        self.configured[ key ] = value

    def set( self, key, value ):
        self.configured[ key ] = value
