#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


import logging, sys, os, re
from registration import registrations
from interp_env import interp_self, interp_local, replace_delayed

class config:

    def __init__( self, reg_name ):
        # derived class for system configuration must call this base
        # class init FIRST then override settings where required.

        self.items = {}
        self.system_name = reg_name
        self.set_defaults()

    def set_defaults( self ):

        self.items[ 'logging_dir' ] = os.environ['HOME'] + '/cylc-logs/' + self.system_name
        self.items[ 'state_dump_dir' ] = os.environ['HOME'] + '/cylc-state/' + self.system_name
        self.items[ 'state_dump_file' ] = self.items['state_dump_dir'] + '/state'

        self.items[ 'task_list' ] = []

        self.items[ 'system_title' ] = 'SYSTEM TITLE (override me in system config)'
        self.items[ 'system_registered_name' ] = self.system_name
        self.items[ 'system_username' ] = os.environ['USER']

        self.items[ 'system_info' ] = {}
        self.items[ 'task_groups' ] = {}
        self.items[ 'environment' ] = {}
        self.items['job_submit_overrides'] = {}

        self.items['max_runahead_hours'] = 24
        self.items['job_submit_method'] = 'background'
        self.items['logging_level'] = logging.INFO

        reg = registrations()
        self.items['system_def_dir' ] = reg.get( self.system_name )

    def check_environment( self ):
        env = self.items[ 'environment' ]
        # Convert all values to strings in case the user set integer
        # values, say, in the system config file.
        for var in env:
            env[ var ] = str( env[ var ] )

        # work out any references to other global variables or local
        # environment variables
        env = interp_self( env )
        env = interp_local( env )
        # don't interpolate delayed variables here though; this must
        # be done at the last, before job submission.
        #env = replace_delayed( env )

        self.items[ 'environment' ] = env

    def check_start_time( self, startup_cycle ):
        if 'legal_startup_hours' in self.items.keys():
            # convert to integer to deal with leading zeroes (06 == 6)
            startup_hour = int( startup_cycle[8:10] )
            legal_hours = [ int(i) for i in self.items[ 'legal_startup_hours' ] ]
            print "Legal startup hours for " + self.system_name + ":",
            for item in legal_hours:
                print item,
            print
            if startup_hour not in legal_hours:
                raise SystemExit( "Illegal Start Time" )

    def create_state_dump_dir( self, practice ):
        
        if practice:
            self.items[ 'state_dump_dir' ] += '-practice'

        self.items[ 'state_dump_file' ] = self.items['state_dump_dir'] + '/state'

        statedir = self.items[ 'state_dump_dir' ]
        if not os.path.exists( statedir ):
            try:
                print "Creating state dump directory"
                os.makedirs(  statedir )
            except Exception, e:
                raise SystemExit( e )

    def create_logging_dir( self, practice ):
        
        if practice:
            self.items[ 'logging_dir'    ] += '-practice'

        logdir = self.items[ 'logging_dir' ]
        if not os.path.exists( logdir ):
            try:
                print "Creating logging directory"
                os.makedirs(  logdir )
            except Exception, e:
                raise SystemExit( e )

    def check_task_groups( self ):
        # check tasks in any named group are in the task list
        for group in ( self.items['task_groups'] ).keys():
            tasks = self.items['task_groups'][group]
            for task in tasks:
                if task not in self.items[ 'task_list' ]:
                    raise SystemExit( "Task group member " + task + " not in task list" )

    def job_submit_config( self, dummy_mode = False ):
        # create dict of job submit methods by task name
        self.items['job submit class'] = {}

        if dummy_mode:
            # background job submission only
            for task in self.items['task_list']:
                self.items['job submit class'][ task ] = 'background'
            return

        for task in self.items['task_list']:
            self.items['job submit class'][ task ] = self.items[ 'job_submit_method' ]
            for method in self.items[ 'job_submit_overrides' ]:
                if task in self.items[ 'job_submit_overrides' ][ method ]:
                    self.items['job submit class'][ task ] = method


    def get( self, key ):
        return self.items[ key ]

    def put( self, key, value ):
        self.items[ key ] = value

    def set( self, key, value ):
        self.items[ key ] = value

    def put_env( self, key, value ):
        self.items[ 'environment' ][ key ] = value

    def dump( self ):
        items = self.items.keys()

        plain_items = {}
        sub_items = []
        for item in items:
            if item in ['clock', \
                    'daemon', \
                    'job_submit_method', \
                    'job_submit_overrides', \
                    'state_dump_file' ]:
                # TO DO: CLOCK AND DAEMON SHOULD NOT BE IN CONFIG!
                # job_submit_method and _overrides are subsumed into
                # the 'job submit class' item.
                continue

            try:
                subitems = (self.items[item]).keys()
                sub_items.append( item )
            except:
                plain_items[ item ] = self.items[ item ]

        self.dump_dict( plain_items )

        for item in sub_items:
            self.dump_dict( self.items[ item ], item )

    def dump_dict( self, mydict, name = None ):

        indent = ' o '
        if name:
            print ' o  ' + name + ':'
            indent = '   - '

        items = mydict.keys()
        if len( items ) == 0:
            return

        longest_item = items[0]
        for item in items:
            if len(item) > len(longest_item):
                longest_item = item

        template = re.sub( '.', '.', longest_item )

        for item in items:
            print indent, re.sub( '^.{' + str(len(item))+ '}', item, template) + '...' + str( mydict[ item ] )

