#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


import sys, os, re
from registration import registrations
from interp_env import interp_self, interp_local, replace_delayed

from task_list import task_list, task_list_shortnames
from suiterc import suiterc

class config:
    def __init__( self, reg_name, global_env, logging_dir ):
        # derived class for suite configuration must call this base
        # class init FIRST then override settings where required.

        self.items = {}
        self.suite_name = reg_name

        self.items[ 'suite_registered_name' ] = self.suite_name
        self.items[ 'task_list' ] = task_list
        self.items[ 'task_list_shortnames' ] = task_list_shortnames
        self.items[ 'suite_username' ] = os.environ['USER']
        self.items[ 'task_groups' ] = {}

        self.items[ 'logging_dir' ] = logging_dir

        suite_dir = registrations().get( self.suite_name )
        self.items['suite_def_dir' ] = suite_dir

        rc = suiterc( os.path.join( suite_dir, 'suite.rc' ) )

        self.items['job_submit_method'] = rc.get_default_job_submission()
        self.items['job_submit_overrides' ] = rc.get_nondefault_job_submission()
        self.items['suite_title' ] = rc.get( 'general', 'title' )
        self.items['max_runahead_hours' ] = rc.get( 'general', 'maximum runahead (hours)' )
        self.items['task_groups' ] = rc.get_task_insertion_groups()
        self.items['coldstart_tasks' ] = rc.get_coldstart_tasks()
        self.items['joblog_dir' ] = rc.get( 'general', 'job log directory' )

        allow = rc.get( 'general', 'allow simultaneous instances' )
        if allow == 'True':
            self.items[ 'allow_simultaneous_suite_instances' ] = True
        else:
            self.items[ 'allow_simultaneous_suite_instances' ] = False

        self.items[ 'environment' ] = global_env  # must be OrderedDict
        for (item,value) in rc.get_global_environment():
            self.items['environment'][ item ] = value


    def check_start_time( self, startup_cycle ):
        if 'legal_startup_hours' in self.items.keys():
            # convert to integer to deal with leading zeroes (06 == 6)
            startup_hour = int( startup_cycle[8:10] )
            legal_hours = [ int(i) for i in self.items[ 'legal_startup_hours' ] ]
            print "Legal startup hours for " + self.suite_name + ":",
            for item in legal_hours:
                print item,
            print
            if startup_hour not in legal_hours:
                raise SystemExit( "Illegal Start Time" )

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
                    'job_submit_overrides', ]:
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

