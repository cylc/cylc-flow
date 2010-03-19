#!/usr/bin/python

import logging, sys, os, re

class config:

    def __init__( self, reg_name ):

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

        # get system definition dir, for system_info
        reg_file = os.environ['HOME'] + '/.cylc/registered/' + self.system_name
        if os.path.exists( reg_file ):
            try:
                FILE = open( reg_file, 'r' )
            except:
                # this should never have because the reg file has to 
                # be accessed in order to run the system in the first
                # place
                print 'UNABLE TO OPEN REGISTRATION FILE'
            else:
                line = FILE.read()
            FILE.close()
            self.items['system_def_dir' ] = line.rstrip() 
        else:
            self.items['system_def_dir' ] = 'UNKNOWN!'

    def configure( self, practice ):
        self.check_task_groups()
        self.job_submit_config()
        
        if practice:
            self.items[ 'state_dump_dir' ] += '-practice'
            self.items[ 'logging_dir'    ] += '-practice'

        self.items[ 'state_dump_file' ] = self.items['state_dump_dir'] + '/state'

        statedir = self.items[ 'state_dump_dir' ]
        if not os.path.exists( statedir ):
            try:
                print "Creating state dump directory"
                os.makedirs(  statedir )
            except Exception, e:
                raise SystemExit( e )

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

    def job_submit_config( self ):
        # create dict of job submit methods by task name
        self.items['job submit class'] = {}
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

