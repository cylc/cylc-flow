#!/usr/bin/python

import user_config
import logging
import os, sys

class config:

    def __init__( self ):

        self.configured = {}

        # SET DEFAULTS FOR ALL USER CONFIG
        self.configured['system_name'] = 'REPLACE_ME'

        # START AND STOP (OPTIONAL) REFERENCE TIMES
        self.configured['start_time'] = 'YYYYMMDDHH' 
        self.configured['stop_time'] = None   

        # SCHEDULING ALGORITHM (task interaction or requisite broker)
        self.configured['use_broker'] = True

        # DUMMY MODE
        self.configured['dummy_mode'] = False
        self.configured['dummy_clock_rate'] = 10      
        self.configured['dummy_clock_offset'] = 10 

        # JOB LAUNCH METHOD (qsub or direct in background)
        self.configured['use_qsub'] = True
        self.configured['job_queue'] = 'default'

        # TOP LEVEL OUTPUT DIR
        self.configured['output_dir'] = os.environ['HOME'] + '/sequenz-output' 

        # LOG VERBOSITY
        self.configured['logging_level'] = logging.INFO
        #self.configured['logging_level'] = logging.DEBUG

        # LIST OF TASK NAMES
        self.configured['task_list'] = []

        # TASKS TO DUMMY OUT IN REAL MODE
        self.configured['dummy_out'] = []

        self.derive_the_rest()


    def derive_the_rest( self ):

        # LOG FILE LOCATION
        self.configured['logging_dir'] = self.configured['output_dir'] + '/' + self.configured['system_name'] + '/log-files' 

        # STATE DUMP FILE LOCATION
        self.configured['state_dump_file'] = self.configured['output_dir'] + '/' + self.configured['system_name'] + '/state-dump'

        # PYRO NAMESERVER CONFIGURATION 
        # group must be unique per sequenz instance so that different systems don't interfere
        self.configured['pyro_ns_group'] = self.configured['system_name']

       
    def user_override( self ):
        for key in user_config.config.keys():
            self.configured[ key ] = user_config.config[ key ]

        self.derive_the_rest()

    def check( self ):
        if self.configured['start_time'] == None:
            print "ERROR: you must define a start time in your user_config.py"
            print "module for system " + self.configured['system_name']
            sys.exit(1)

        if self.configured['dummy_mode'] and self.configured['use_qsub']:
            print "ERROR: you can't use qsub in dummy mode."
            print "change the 'use_qsub' config in your user_config.py"
            print "module for system " + self.configured['system_name']
            sys.exit(1)

        if len( self.configured[ 'task_list' ] ) == 0:
            print "ERROR: your task list is empty"
            print "define config[ 'task_list' ] in your user_config.py"
            print "module for system " + self.configured['system_name']
            sys.exit(1)

    def get( self, key ):
        return self.configured[ key ]

    def set( self, key, value ):
        self.configured[ key ] = value

    def dump( self ):
            
        print
        print " + SYSTEM NAME: " + self.configured['system_name']

        if self.configured['dummy_mode']:
            print " + RUNNING IN DUMMY MODE"
            print "   clock rate: ", self.configured['dummy_clock_rate']
            print "   clock offset: ", self.configured['dummy_clock_offset']
        else:
            print " + running in real mode"
 
        if self.configured['use_broker']:
            print " + task sequencing method: broker negotiation"
        else:
            print " + task sequencing method: task interaction"
            print "   (may be slow if number of tasks is very large)" 

        print " + start time: " + self.configured['start_time']
        if self.configured['stop_time']:
            print " + stop time: " + self.configured['stop_time']
        else:
            print " + (no stop time configured)"

        if self.configured['use_qsub']:
            print " + job launch method: qsub"
            print " + job queue: " + self.configured['job_queue']
        else:
            print " + job launch method: direct, in background"

        print ' + logging dir: ' + self.configured['logging_dir']

        print ' + state dump file: ' + self.configured['state_dump_file']

        print ' + pyro nameserver group name: ' + self.configured['pyro_ns_group']

        print ' + task list: '
        for task in self.configured['task_list']:
            print '   - ' + task

        if len( self.configured['dummy_out'] ) > 0:
            print ' + dummying out in real mode: '
            for task in self.configured['dummy_out']:
                print '    ' + task
