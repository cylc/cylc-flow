#!/usr/bin/python

import user_config
import logging
import os, sys

class config:

    def __init__( self ):

        self.configured = {}
        self.set_defaults()


    def set_defaults( self ):
        # SET DEFAULTS FOR ALL USER CONFIG

        # SYSTEM NAME (used as Pyro nameserver group)
        self.configured['system_name'] = 'REPLACE_ME'

        # START AND STOP (OPTIONAL) REFERENCE TIMES
        self.configured['start_time'] = 'YYYYMMDDHH' 
        self.configured['stop_time'] = None   

        # MAXIMUM TIME ANY TASK IS ALLOWED TO GET AHEAD OF THE SLOWEST
        self.configured['max_runahead_hours'] = 24

        # SCHEDULING ALGORITHM (task interaction or requisite broker)
        self.configured['use_broker'] = True

        # DUMMY MODE
        self.configured['dummy_mode'] = False
        self.configured['dummy_clock_rate'] = 10      
        self.configured['dummy_clock_offset'] = 10 

        # JOB LAUNCH METHOD (qsub or direct in background)
        # default to qsub in real mode
        self.configured['use_qsub'] = True
        self.configured['job_queue'] = 'default'

        # LOGGING DIRECTORY
        self.configured['logging_dir'] = os.environ['HOME'] + '/running/sequenz-logs' 

        # STATE DUMP FILE
        self.configured['state_dump_file'] = os.environ['HOME'] + '/running/sequenz-state' 

        # LOG VERBOSITY
        self.configured['logging_level'] = logging.INFO
        #self.configured['logging_level'] = logging.DEBUG

        # LIST OF TASK NAMES
        self.configured['task_list'] = []


    def load( self ):
        self.user_override()
        self.check()
        self.dump()
       

    def user_override( self ):
        # override config items with those in the user_config module
        for key in user_config.config.keys():
            self.configured[ key ] = user_config.config[ key ]


    def check( self ):
        # make sure all compulsory config items have been defined

        die = False

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
 
        print "SCHEDULING METHOD ......",
        if self.configured['use_broker']:
            print "broker negotiation"
        else:
            print "task interaction (may be slow for large task numbers)" 

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
